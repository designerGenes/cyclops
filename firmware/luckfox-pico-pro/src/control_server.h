#ifndef CYCLOPS_EYE_CONTROL_SERVER_H
#define CYCLOPS_EYE_CONTROL_SERVER_H

#include "cyclops_eye/eye.h"
#include "cyclops_eye/camera.h"

typedef struct {
    int socket_fd;
    const char *token;
} eye_control_server_t;

int eye_control_server_start(eye_control_server_t *server, int port, const char *token);
/* Returns 0 for no change, 1 when a tier/fps request changed active camera
 * settings, or 2 when an OSD request changed the timestamp scale/color (values
 * written to *osd_scale and *osd_color). */
int eye_control_server_poll(eye_control_server_t *server, eye_governor_t *governor,
                            eye_camera_t *camera, bool camera_ready,
                            int *osd_scale, int *osd_color);
void eye_control_server_stop(eye_control_server_t *server);

#endif
