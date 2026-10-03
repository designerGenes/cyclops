#include "cyclops_eye/eye.h"

#include <stdio.h>

int main(int argc, char **argv) {
    eye_config_t config;
    char error[128];
    if (argc != 2) {
        (void)fprintf(stderr, "usage: %s /path/to/cyclops-eye.conf\n", argv[0]);
        return 64;
    }
    if (eye_config_load(argv[1], &config, error, sizeof(error)) != 0) {
        (void)fprintf(stderr, "configuration error: %s\n", error);
        return 1;
    }
    (void)printf("configuration valid for %s; target=RV1106, RTSP port=%d\n", config.node_name,
                 config.rtsp_port);
    return 0;
}
