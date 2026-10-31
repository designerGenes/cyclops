#ifndef CYCLOPS_EYE_OSD_H
#define CYCLOPS_EYE_OSD_H

#include "cyclops_eye/eye.h"

/* A timestamp overlay burned into the encoded video via the Rockchip RGN
 * (region) module. The Luckfox image has no TUN and no rkipc OSD, so this is
 * the on-device equivalent of the Pi eyes' MediaMTX rpiCameraTextOverlay. */
typedef struct eye_osd eye_osd_t;

/* Create a "YYYY-MM-DD HH:MM:SS" overlay attached to a VENC channel and start
 * a thread that refreshes it once per second. `rotation` is the display
 * rotation applied by the viewer (0/90/180/270 clockwise); the text is
 * rendered counter-rotated and moved to the matching corner so it stays
 * upright and in the top-left of the *displayed* frame. `scale` is the glyph
 * cell size in pixels (3..12); `color` is an EYE_OSD_* mode (WHITE, CYCLE, or
 * a fixed high-contrast hue). Returns NULL on failure (the caller should
 * continue without an OSD). */
eye_osd_t *eye_osd_start(int venc_channel, int frame_w, int frame_h,
                         int rotation, int scale, int color);

/* Stop the refresh thread, then detach and destroy the overlay. Must be called
 * before the VENC channel it is attached to is destroyed. */
void eye_osd_stop(eye_osd_t *osd);

#endif /* CYCLOPS_EYE_OSD_H */