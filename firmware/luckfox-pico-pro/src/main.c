#include "cyclops_eye/camera.h"
#include "cyclops_eye/eye.h"
#include "control_server.h"
#include "http_client.h"

#include <arpa/inet.h>
#include <ifaddrs.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/reboot.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t keep_running = 1;

static void stop_handler(int signal_number) {
    (void)signal_number;
    keep_running = 0;
}

static double monotonic_seconds(void) {
    struct timespec value;
    (void)clock_gettime(CLOCK_MONOTONIC, &value);
    return (double)value.tv_sec + (double)value.tv_nsec / 1000000000.0;
}

static double temperature_celsius(void) {
    FILE *file = fopen("/sys/class/thermal/thermal_zone0/temp", "r");
    long millidegrees;
    if (file == NULL) return -1.0;
    if (fscanf(file, "%ld", &millidegrees) != 1) {
        fclose(file);
        return -1.0;
    }
    fclose(file);
    return (double)millidegrees / 1000.0;
}

static void discover_lan_ip(char *destination, size_t destination_size) {
    struct ifaddrs *interfaces = NULL;
    struct ifaddrs *entry;
    destination[0] = '\0';
    if (getifaddrs(&interfaces) != 0) return;
    for (entry = interfaces; entry != NULL; entry = entry->ifa_next) {
        struct sockaddr_in *address;
        const unsigned char *octets;
        if (entry->ifa_addr == NULL || entry->ifa_addr->sa_family != AF_INET) continue;
        address = (struct sockaddr_in *)entry->ifa_addr;
        octets = (const unsigned char *)&address->sin_addr;
        if (octets[0] == 127 || octets[0] == 169 || octets[0] == 100 || octets[0] == 172) continue;
        if (inet_ntop(AF_INET, &address->sin_addr, destination, destination_size) != NULL) break;
    }
    freeifaddrs(interfaces);
}

static int post_registration(const eye_config_t *config) {
    char payload[1024];
    char error[128];
    if (eye_registration_json(config, payload, sizeof(payload)) < 0 ||
        eye_http_post(config->cyclops_url, "/api/nodes/register", payload, error, sizeof(error)) != 0) {
        (void)fprintf(stderr, "registration failed: %s\n", error);
        return -1;
    }
    return 0;
}

static int post_heartbeat(const eye_config_t *config, const eye_governor_t *governor,
                          double temperature, unsigned long uptime) {
    char payload[1024];
    char error[128];
    if (eye_heartbeat_json(config, governor, temperature, uptime, payload, sizeof(payload)) < 0 ||
        eye_http_post(config->cyclops_url, "/api/nodes/heartbeat", payload, error, sizeof(error)) != 0) {
        (void)fprintf(stderr, "heartbeat failed: %s\n", error);
        return -1;
    }
    return 0;
}

int main(int argc, char **argv) {
    const char *config_path = argc == 2 ? argv[1] : "/etc/cyclops-eye.conf";
    eye_config_t config;
    eye_governor_t governor;
    eye_camera_t *camera = NULL;
    eye_control_server_t control = {.socket_fd = -1};
    char error[128];
    double started;
    double last_contact;
    double next_thermal;
    double next_heartbeat;
    bool registered = false;

    if (eye_config_load(config_path, &config, error, sizeof(error)) != 0) {
        (void)fprintf(stderr, "configuration error: %s\n", error);
        return 1;
    }
    if (config.advertise_host[0] == '\0') discover_lan_ip(config.advertise_host, sizeof(config.advertise_host));
    eye_governor_init(&governor);
    if (eye_camera_start(&camera, &config, eye_tier(EYE_TIER_FULL), eye_governor_effective_fps(&governor)) != 0) {
        (void)fprintf(stderr, "cannot start RV1106 camera pipeline\n");
        return 1;
    }
    if (eye_control_server_start(&control, config.control_port, config.enroll_token) != 0) {
        (void)fprintf(stderr, "cannot start local control server\n");
        eye_camera_stop(camera);
        return 1;
    }

    signal(SIGINT, stop_handler);
    signal(SIGTERM, stop_handler);
    started = last_contact = monotonic_seconds();
    next_thermal = started;
    next_heartbeat = started;
    while (keep_running) {
        double now = monotonic_seconds();
        if (eye_control_server_poll(&control, &governor, eye_camera_ready(camera)) > 0) {
            const eye_tier_t *tier = eye_tier(eye_governor_effective_tier(&governor));
            if (eye_camera_apply_tier(camera, tier, eye_governor_effective_fps(&governor)) != 0)
                (void)fprintf(stderr, "camera control reconfiguration failed\n");
        }
        if (now >= next_thermal) {
            double temperature = temperature_celsius();
            if (temperature >= 0.0 && eye_governor_step(&governor, temperature, false, now)) {
                const eye_tier_t *tier = eye_tier(eye_governor_effective_tier(&governor));
                (void)fprintf(stderr, "thermal %.1fC: applying %s tier\n", temperature, tier->name);
                if (eye_camera_apply_tier(camera, tier, eye_governor_effective_fps(&governor)) != 0)
                    (void)fprintf(stderr, "camera reconfiguration failed\n");
            }
            next_thermal = now + config.thermal_poll_seconds;
        }
        if (now >= next_heartbeat) {
            double temperature = temperature_celsius();
            int status = registered ? post_heartbeat(&config, &governor, temperature, (unsigned long)(now - started))
                                    : post_registration(&config);
            if (status == 0) {
                registered = true;
                last_contact = now;
            }
            next_heartbeat = now + config.heartbeat_seconds;
        }
        if (now - last_contact >= config.reboot_after_unreachable_seconds) {
            (void)fprintf(stderr, "Cyclops unreachable for %d seconds; rebooting\n",
                          config.reboot_after_unreachable_seconds);
            sync();
            (void)reboot(RB_AUTOBOOT);
            last_contact = now;
        }
        (void)eye_camera_ready(camera);
        (void)usleep(100000);
    }
    eye_control_server_stop(&control);
    eye_camera_stop(camera);
    return 0;
}
