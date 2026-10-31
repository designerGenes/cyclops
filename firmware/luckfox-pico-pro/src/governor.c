#include "cyclops_eye/eye.h"

#include <string.h>

/* Tier thresholds are set well above the board's normal full-load range
 * (observed ~62-70 C). A tier change tears down and rebuilds the MPP/VI
 * pipeline, and RKAIQ's 3A sometimes comes back with a green/dark cast; at
 * 70 C the governor flapped right at steady-state temperature, which made the
 * image "fix then go green". Keep headroom so throttling only happens when the
 * SoC is genuinely hot (RK1106 Tj max is far above this). */
static const eye_tier_t TIERS[EYE_TIER_COUNT] = {
    {"full", 0.0, 1280, 720, 15, 1500},
    {"warm", 78.0, 1280, 720, 12, 1000},
    {"hot", 84.0, 854, 480, 8, 500},
    {"critical", 90.0, 640, 360, 5, 250},
};

enum { FPS_BOOST_MAX_TIER = EYE_TIER_WARM };
static const double EXIT_MARGIN_C = 5.0;
static const double UP_DWELL_SECONDS = 120.0;

const eye_tier_t *eye_tier(eye_tier_id_t id) {
    return id >= EYE_TIER_FULL && id < EYE_TIER_COUNT ? &TIERS[id] : NULL;
}

void eye_governor_init(eye_governor_t *governor) {
    governor->thermal_tier = EYE_TIER_FULL;
    governor->manual_tier = -1;
    governor->fps_override = 0;
    governor->cool_since_seconds = -1.0;
}

bool eye_governor_step(eye_governor_t *governor, double temperature_c, bool thermal_alarm,
                       double now_seconds) {
    eye_tier_id_t required = EYE_TIER_FULL;
    eye_tier_id_t index;
    for (index = EYE_TIER_WARM; index < EYE_TIER_COUNT; index++) {
        if (temperature_c >= TIERS[index].enter_c) required = index;
    }
    if (thermal_alarm && required < EYE_TIER_CRITICAL) required++;
    if (required > governor->thermal_tier) {
        governor->thermal_tier = required;
        governor->cool_since_seconds = -1.0;
        return true;
    }
    if (required < governor->thermal_tier) {
        double gate = TIERS[governor->thermal_tier].enter_c - EXIT_MARGIN_C;
        if (!thermal_alarm && temperature_c < gate) {
            if (governor->cool_since_seconds < 0.0) governor->cool_since_seconds = now_seconds;
            if (now_seconds - governor->cool_since_seconds >= UP_DWELL_SECONDS) {
                governor->thermal_tier--;
                governor->cool_since_seconds = -1.0;
                return true;
            }
        } else {
            governor->cool_since_seconds = -1.0;
        }
    }
    return false;
}

eye_tier_id_t eye_governor_effective_tier(const eye_governor_t *governor) {
    eye_tier_id_t effective = governor->thermal_tier;
    if (governor->manual_tier > (int)effective) effective = (eye_tier_id_t)governor->manual_tier;
    return effective;
}

int eye_governor_effective_fps(const eye_governor_t *governor) {
    eye_tier_id_t tier = eye_governor_effective_tier(governor);
    if (governor->fps_override > 0 && tier <= FPS_BOOST_MAX_TIER) return governor->fps_override;
    return TIERS[tier].fps;
}

bool eye_governor_set_manual_tier(eye_governor_t *governor, const char *tier_name) {
    eye_tier_id_t index;
    if (strcmp(tier_name, "auto") == 0) {
        governor->manual_tier = -1;
        return true;
    }
    for (index = EYE_TIER_FULL; index < EYE_TIER_COUNT; index++) {
        if (strcmp(tier_name, TIERS[index].name) == 0) {
            governor->manual_tier = index;
            return true;
        }
    }
    return false;
}

bool eye_governor_set_fps(eye_governor_t *governor, int fps) {
    if (fps == 0) {
        governor->fps_override = 0;
        return true;
    }
    if (fps < 5 || fps > 30) return false;
    governor->fps_override = fps;
    return true;
}
