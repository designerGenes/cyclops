#include "cyclops_eye/eye.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *trim(char *value) {
    char *end;
    while (isspace((unsigned char)*value)) value++;
    end = value + strlen(value);
    while (end > value && isspace((unsigned char)end[-1])) *--end = '\0';
    return value;
}

static bool copy_value(char *destination, size_t destination_size, const char *value) {
    size_t length = strlen(value);
    if (length == 0 || length >= destination_size || strpbrk(value, "\"\\\r\n") != NULL) return false;
    memcpy(destination, value, length + 1);
    return true;
}

static bool parse_positive_int(const char *value, int *destination) {
    char *end = NULL;
    long parsed = strtol(value, &end, 10);
    if (*value == '\0' || *end != '\0' || parsed < 1 || parsed > 65535) return false;
    *destination = (int)parsed;
    return true;
}

void eye_config_defaults(eye_config_t *config) {
    memset(config, 0, sizeof(*config));
    config->camera_id = 0;
    config->rtsp_port = 8554;
    config->control_port = 8800;
    config->heartbeat_seconds = 15;
    config->thermal_poll_seconds = 5;
    config->reboot_after_unreachable_seconds = 600;
    (void)copy_value(config->iq_dir, sizeof(config->iq_dir), "/etc/iqfiles");
}

bool eye_config_is_valid(const eye_config_t *config) {
    return config->node_name[0] != '\0' && config->enroll_token[0] != '\0' &&
           config->cyclops_url[0] != '\0' && strncmp(config->cyclops_url, "http://", 7) == 0 &&
           config->rtsp_port > 0 && config->control_port > 0;
}

int eye_config_load(const char *path, eye_config_t *config, char *error, size_t error_size) {
    FILE *file = fopen(path, "r");
    char line[512];
    unsigned line_number = 0;
    if (file == NULL) {
        (void)snprintf(error, error_size, "cannot open %s", path);
        return -1;
    }
    eye_config_defaults(config);
    while (fgets(line, sizeof(line), file) != NULL) {
        char *key;
        char *value;
        char *equals;
        line_number++;
        key = trim(line);
        if (*key == '\0' || *key == '#') continue;
        equals = strchr(key, '=');
        if (equals == NULL) goto invalid;
        *equals = '\0';
        key = trim(key);
        value = trim(equals + 1);
        if (strcmp(key, "node_name") == 0) {
            if (!copy_value(config->node_name, sizeof(config->node_name), value)) goto invalid;
        } else if (strcmp(key, "enroll_token") == 0) {
            if (!copy_value(config->enroll_token, sizeof(config->enroll_token), value)) goto invalid;
        } else if (strcmp(key, "cyclops_url") == 0) {
            if (!copy_value(config->cyclops_url, sizeof(config->cyclops_url), value)) goto invalid;
        } else if (strcmp(key, "advertise_host") == 0) {
            if (*value != '\0' && !copy_value(config->advertise_host, sizeof(config->advertise_host), value)) goto invalid;
        } else if (strcmp(key, "iq_dir") == 0) {
            if (!copy_value(config->iq_dir, sizeof(config->iq_dir), value)) goto invalid;
        } else if (strcmp(key, "camera_id") == 0) {
            if (!parse_positive_int(value, &config->camera_id) && strcmp(value, "0") != 0) goto invalid;
        } else if (strcmp(key, "rtsp_port") == 0) {
            if (!parse_positive_int(value, &config->rtsp_port)) goto invalid;
        } else if (strcmp(key, "control_port") == 0) {
            if (!parse_positive_int(value, &config->control_port)) goto invalid;
        } else if (strcmp(key, "heartbeat_seconds") == 0) {
            if (!parse_positive_int(value, &config->heartbeat_seconds)) goto invalid;
        } else if (strcmp(key, "thermal_poll_seconds") == 0) {
            if (!parse_positive_int(value, &config->thermal_poll_seconds)) goto invalid;
        } else if (strcmp(key, "reboot_after_unreachable_seconds") == 0) {
            if (!parse_positive_int(value, &config->reboot_after_unreachable_seconds)) goto invalid;
        } else {
            goto invalid;
        }
    }
    fclose(file);
    if (!eye_config_is_valid(config)) {
        (void)snprintf(error, error_size, "node_name, enroll_token, and http:// cyclops_url are required");
        return -1;
    }
    return 0;
invalid:
    fclose(file);
    (void)snprintf(error, error_size, "invalid configuration on line %u", line_number);
    return -1;
}
