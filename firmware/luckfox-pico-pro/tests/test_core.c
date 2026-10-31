#include "cyclops_eye/eye.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static eye_config_t test_config(void) {
    eye_config_t config;
    eye_config_defaults(&config);
    (void)snprintf(config.node_name, sizeof(config.node_name), "luckfox-eye");
    (void)snprintf(config.enroll_token, sizeof(config.enroll_token), "test-token");
    (void)snprintf(config.cyclops_url, sizeof(config.cyclops_url), "http://cyclops.local:8080");
    (void)snprintf(config.advertise_host, sizeof(config.advertise_host), "192.168.1.52");
    return config;
}

static void test_hot_transition_is_immediate(void) {
    eye_governor_t governor;
    eye_governor_init(&governor);
    assert(!eye_governor_step(&governor, 77.9, false, 1.0));
    assert(eye_governor_step(&governor, 84.0, false, 2.0));
    assert(eye_governor_effective_tier(&governor) == EYE_TIER_HOT);
}

static void test_cooling_requires_dwell(void) {
    eye_governor_t governor;
    eye_governor_init(&governor);
    assert(eye_governor_step(&governor, 90.0, false, 0.0));
    assert(eye_governor_effective_tier(&governor) == EYE_TIER_CRITICAL);
    assert(!eye_governor_step(&governor, 70.0, false, 10.0));
    assert(!eye_governor_step(&governor, 70.0, false, 129.0));
    assert(eye_governor_step(&governor, 70.0, false, 130.0));
    assert(eye_governor_effective_tier(&governor) == EYE_TIER_HOT);
}

static void test_manual_controls_are_a_safety_ceiling(void) {
    eye_governor_t governor;
    eye_governor_init(&governor);
    assert(eye_governor_set_manual_tier(&governor, "critical"));
    assert(eye_governor_effective_tier(&governor) == EYE_TIER_CRITICAL);
    assert(eye_governor_set_manual_tier(&governor, "full"));
    assert(eye_governor_step(&governor, 90.0, false, 1.0));
    assert(eye_governor_effective_tier(&governor) == EYE_TIER_CRITICAL);
    assert(eye_governor_set_fps(&governor, 30));
    assert(eye_governor_effective_fps(&governor) == 5);
}

static void test_cyclops_payloads_preserve_the_contract(void) {
    eye_config_t config = test_config();
    eye_governor_t governor;
    char payload[1024];
    eye_governor_init(&governor);
    assert(eye_registration_json(&config, payload, sizeof(payload)) > 0);
    assert(strstr(payload, "\"streams\":{\"primary\":\"cam\",\"detect\":\"detect\"}") != NULL);
    assert(strstr(payload, "\"rtsp_port\":8554") != NULL);
    assert(eye_heartbeat_json(&config, &governor, 61.2, 33, payload, sizeof(payload)) > 0);
    assert(strstr(payload, "\"tier\":\"full\"") != NULL);
    assert(strstr(payload, "\"uptime_s\":33") != NULL);
}

static void test_configuration_validation(void) {
    char path[] = "/tmp/cyclops-eye-config-XXXXXX";
    char error[128];
    int descriptor = mkstemp(path);
    FILE *file;
    eye_config_t config;
    assert(descriptor >= 0);
    file = fdopen(descriptor, "w");
    assert(file != NULL);
    (void)fputs("node_name=luckfox-eye\nenroll_token=not-a-secret\n"
                "cyclops_url=http://cyclops.local:8080\ncamera_id=0\n", file);
    assert(fclose(file) == 0);
    assert(eye_config_load(path, &config, error, sizeof(error)) == 0);
    assert(config.camera_id == 0);
    assert(unlink(path) == 0);
}

int main(void) {
    test_hot_transition_is_immediate();
    test_cooling_requires_dwell();
    test_manual_controls_are_a_safety_ceiling();
    test_cyclops_payloads_preserve_the_contract();
    test_configuration_validation();
    (void)puts("cyclops-eye core tests passed");
    return 0;
}
