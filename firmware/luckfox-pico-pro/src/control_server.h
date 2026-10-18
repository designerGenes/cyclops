#ifndef CYCLOPS_EYE_CONTROL_SERVER_H
#define CYCLOPS_EYE_CONTROL_SERVER_H

#include "cyclops_eye/eye.h"
#include "cyclops_eye/camera.h"

typedef struct {
    int socket_fd;
    const char *token;
} eye_control_server_t;

int eye_control_server_start(eye_control_server_t *server, int port, const char *token);
/* Returns 1 when a valid control request changed the active camera settings. */
int eye_control_server_poll(eye_control_server_t *server, eye_governor_t *governor,
                            eye_camera_t *camera, bool camera_ready);
void eye_control_server_stop(eye_control_server_t *server);

#endif
