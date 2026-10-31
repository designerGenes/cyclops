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
    config->rotation = 0;
    config->osd_scale = 6;
    config->osd_color = EYE_OSD_WHITE;
    /* Luckfox's official Pro/Max SPI-NAND Buildroot image installs the
     * sensor tuning profiles in its OEM partition. */
    (void)copy_value(config->iq_dir, sizeof(config->iq_dir), "/oem/usr/share/iqfiles");
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
        } else if (strcmp(key, "rotation") == 0) {
            char *end = NULL;
            long parsed = strtol(value, &end, 10);
            if (*value == '\0' || *end != '\0' ||
                (parsed != 0 && parsed != 90 && parsed != 180 && parsed != 270)) goto invalid;
            config->rotation = (int)parsed;
        } else if (strcmp(key, "osd_scale") == 0) {
            char *end = NULL;
            long parsed = strtol(value, &end, 10);
            if (*value == '\0' || *end != '\0' || parsed < 3 || parsed > 12) goto invalid;
            config->osd_scale = (int)parsed;
        } else if (strcmp(key, "osd_color") == 0) {
            char *end = NULL;
            long parsed = strtol(value, &end, 10);
            if (*value == '\0' || *end != '\0' ||
                parsed < 0 || parsed > EYE_OSD_COLOR_MAX) goto invalid;
            config->osd_color = (int)parsed;
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

int eye_config_write_osd(const char *path, int scale, int color) {
    enum { MAXLINES = 64 };
    char lines[MAXLINES][512];
    int count = 0;
    int wrote_scale = 0;
    int wrote_color = 0;
    char temp[512];
    FILE *in;
    FILE *out;
    int i;

    if (scale < 3) scale = 3;
    if (scale > 12) scale = 12;
    if (color < EYE_OSD_WHITE) color = EYE_OSD_WHITE;
    if (color > EYE_OSD_COLOR_MAX) color = EYE_OSD_COLOR_MAX;

    in = fopen(path, "r");
    if (in == NULL) return -1;
    while (count < MAXLINES && fgets(lines[count], sizeof(lines[0]), in) != NULL) count++;
    fclose(in);

    (void)snprintf(temp, sizeof(temp), "%s.tmp", path);
    out = fopen(temp, "w");
    if (out == NULL) return -1;
    for (i = 0; i < count; i++) {
        char *line = lines[i];
        char *end;
        char *key;
        size_t length = strlen(line);
        if (length > 0 && (line[length - 1] == '\n' || line[length - 1] == '\r')) {
            line[--length] = '\0';
            if (length > 0 && line[length - 1] == '\r') line[--length] = '\0';
        }
        key = line;
        while (*key == ' ' || *key == '\t') key++;
        end = key;
        while (*end != '\0' && *end != '=' && *end != ' ' && *end != '\t') end++;
        if ((size_t)(end - key) == 9 && strncmp(key, "osd_scale", 9) == 0) {
            (void)fprintf(out, "osd_scale=%d\n", scale);
            wrote_scale = 1;
        } else if ((size_t)(end - key) == 9 && strncmp(key, "osd_color", 9) == 0) {
            (void)fprintf(out, "osd_color=%d\n", color);
            wrote_color = 1;
        } else {
            (void)fputs(line, out);
            (void)fputc('\n', out);
        }
    }
    if (!wrote_scale) (void)fprintf(out, "osd_scale=%d\n", scale);
    if (!wrote_color) (void)fprintf(out, "osd_color=%d\n", color);
    if (fclose(out) != 0 || rename(temp, path) != 0) {
        (void)remove(temp);
        return -1;
    }
    return 0;
}
