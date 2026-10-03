#ifndef CYCLOPS_EYE_EYE_H
#define CYCLOPS_EYE_EYE_H

#include <stdbool.h>
#include <stddef.h>

#define EYE_VALUE_MAX 256
#define EYE_NAME_MAX 64

typedef struct {
    char node_name[EYE_NAME_MAX];
    char enroll_token[EYE_VALUE_MAX];
    char cyclops_url[EYE_VALUE_MAX];
    char advertise_host[EYE_NAME_MAX];
    char iq_dir[EYE_VALUE_MAX];
    int camera_id;
    int rtsp_port;
    int control_port;
    int heartbeat_seconds;
    int thermal_poll_seconds;
    int reboot_after_unreachable_seconds;
} eye_config_t;

typedef enum {
    EYE_TIER_FULL = 0,
    EYE_TIER_WARM,
    EYE_TIER_HOT,
    EYE_TIER_CRITICAL,
    EYE_TIER_COUNT,
} eye_tier_id_t;

typedef struct {
    const char *name;
    double enter_c;
    int width;
    int height;
    int fps;
    int bitrate_kbps;
} eye_tier_t;

typedef struct {
    eye_tier_id_t thermal_tier;
    int manual_tier; /* -1 means automatic. Overrides only lower quality. */
    int fps_override; /* 0 means automatic. */
    double cool_since_seconds;
} eye_governor_t;

void eye_config_defaults(eye_config_t *config);
int eye_config_load(const char *path, eye_config_t *config, char *error, size_t error_size);
bool eye_config_is_valid(const eye_config_t *config);

const eye_tier_t *eye_tier(eye_tier_id_t id);
void eye_governor_init(eye_governor_t *governor);
bool eye_governor_step(eye_governor_t *governor, double temperature_c, bool thermal_alarm,
                       double now_seconds);
eye_tier_id_t eye_governor_effective_tier(const eye_governor_t *governor);
int eye_governor_effective_fps(const eye_governor_t *governor);
bool eye_governor_set_manual_tier(eye_governor_t *governor, const char *tier_name);
bool eye_governor_set_fps(eye_governor_t *governor, int fps);

int eye_registration_json(const eye_config_t *config, char *output, size_t output_size);
int eye_heartbeat_json(const eye_config_t *config, const eye_governor_t *governor,
                       double temperature_c, unsigned long uptime_seconds,
                       char *output, size_t output_size);

#endif
