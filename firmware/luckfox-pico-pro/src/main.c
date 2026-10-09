#include "cyclops_eye/camera.h"
#include "cyclops_eye/eye.h"
#include "control_server.h"
#include "http_client.h"

#include <arpa/inet.h>
#include <ifaddrs.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/reboot.h>
#include <time.h>
#include <unistd.h>
#include <linux/watchdog.h>

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

/* Hardware watchdog: enable /dev/watchdog and pet it from the main loop. With
 * CONFIG_WATCHDOG_NOWAYOUT set the driver stays armed, so if the app or the
 * system hangs the board resets itself instead of sitting wedged. Returns -1
 * when there is no watchdog (the app then runs unchanged). */
static int watchdog_open(void) {
    int fd = open("/dev/watchdog", O_WRONLY);
    if (fd < 0) return -1;
    int timeout = 30; /* seconds */
    (void)ioctl(fd, WDIOC_SETTIMEOUT, &timeout);
    return fd;
}

static void watchdog_pet(int fd) {
    if (fd >= 0) (void)write(fd, "k", 1);
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
    int applied_tier = EYE_TIER_FULL;
    int applied_fps = -1;

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
    /* Remember the tier/fps actually applied so a redundant control command or
     * a no-op governor step does not tear down and rebuild the MPP pipeline.
     * Every teardown is a chance for the RK ISP/VENC driver to wedge. */
    applied_tier = eye_governor_effective_tier(&governor);
    applied_fps = eye_governor_effective_fps(&governor);
    int watchdog = watchdog_open();
    double next_watchdog = started;
    while (keep_running) {
        double now = monotonic_seconds();
        if (eye_control_server_poll(&control, &governor, eye_camera_ready(camera)) > 0) {
            int want_tier = eye_governor_effective_tier(&governor);
            int want_fps = eye_governor_effective_fps(&governor);
            if (want_tier != applied_tier || want_fps != applied_fps) {
                if (eye_camera_apply_tier(camera, eye_tier(want_tier), want_fps) != 0)
                    (void)fprintf(stderr, "camera control reconfiguration failed\n");
                applied_tier = want_tier;
                applied_fps = want_fps;
            }
        }
        if (now >= next_thermal) {
            double temperature = temperature_celsius();
            if (temperature >= 0.0 && eye_governor_step(&governor, temperature, false, now)) {
                int want_tier = eye_governor_effective_tier(&governor);
                int want_fps = eye_governor_effective_fps(&governor);
                if (want_tier != applied_tier || want_fps != applied_fps) {
                    const eye_tier_t *tier = eye_tier(want_tier);
                    (void)fprintf(stderr, "thermal %.1fC: applying %s tier\n", temperature, tier->name);
                    if (eye_camera_apply_tier(camera, tier, want_fps) != 0)
                        (void)fprintf(stderr, "camera reconfiguration failed\n");
                    applied_tier = want_tier;
                    applied_fps = want_fps;
                }
            }
            next_thermal = now + config.thermal_poll_seconds;
        }
        if (now >= next_heartbeat) {
            double temperature = temperature_celsius();
            /* Re-discover the LAN address every heartbeat: the wired interface
             * may only get its DHCP lease after this daemon starts, and the
             * coordinator needs the current LAN route to pull our RTSP. */
            discover_lan_ip(config.advertise_host, sizeof(config.advertise_host));
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
        if (now >= next_watchdog) {
            watchdog_pet(watchdog);
            next_watchdog = now + 5.0;
        }
        (void)eye_camera_ready(camera);
        (void)usleep(100000);
    }
    eye_control_server_stop(&control);
    eye_camera_stop(camera);
    return 0;
}
