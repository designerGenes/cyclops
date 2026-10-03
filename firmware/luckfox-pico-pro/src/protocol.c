#include "cyclops_eye/eye.h"

#include <stdio.h>

int eye_registration_json(const eye_config_t *config, char *output, size_t output_size) {
    return snprintf(output, output_size,
                    "{\"name\":\"%s\",\"token\":\"%s\",\"host\":\"%s\","
                    "\"lan_host\":\"%s\",\"rtsp_port\":%d,"
                    "\"streams\":{\"primary\":\"cam\",\"detect\":\"detect\"}}",
                    config->node_name, config->enroll_token,
                    config->advertise_host[0] ? config->advertise_host : config->node_name,
                    config->advertise_host, config->rtsp_port);
}

int eye_heartbeat_json(const eye_config_t *config, const eye_governor_t *governor,
                       double temperature_c, unsigned long uptime_seconds,
                       char *output, size_t output_size) {
    const eye_tier_t *tier = eye_tier(eye_governor_effective_tier(governor));
    return snprintf(output, output_size,
                    "{\"name\":\"%s\",\"token\":\"%s\",\"temp_c\":%.1f,"
                    "\"throttled\":\"%s\",\"tier\":\"%s\",\"uptime_s\":%lu,"
                    "\"lan_host\":\"%s\"}",
                    config->node_name, config->enroll_token, temperature_c,
                    governor->thermal_tier == EYE_TIER_CRITICAL ? "0x1" : "0x0",
                    tier->name, uptime_seconds, config->advertise_host);
}
