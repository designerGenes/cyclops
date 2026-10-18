#ifndef CYCLOPS_EYE_CAMERA_H
#define CYCLOPS_EYE_CAMERA_H

#include "cyclops_eye/eye.h"

typedef struct eye_camera eye_camera_t;

int eye_camera_start(eye_camera_t **camera, const eye_config_t *config, const eye_tier_t *tier,
                     int primary_fps);
int eye_camera_apply_tier(eye_camera_t *camera, const eye_tier_t *tier, int primary_fps);
/* Re-render the timestamp OSD for a new display rotation (0/90/180/270). */
int eye_camera_set_rotation(eye_camera_t *camera, int rotation);
bool eye_camera_ready(const eye_camera_t *camera);
void eye_camera_stop(eye_camera_t *camera);

#endif
