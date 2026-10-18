/* On-device timestamp OSD for the Luckfox Cyclops eye.
 *
 * Draws "YYYY-MM-DD HH:MM:SS" into an ARGB8888 bitmap and overlays it on the
 * hardware H.264 encoder output via the Rockchip RGN module, so the timestamp
 * is burned into the stream (matching the Pi eyes' rpiCameraTextOverlay).
 *
 * The viewer applies a per-node display rotation (0/90/180/270 clockwise). To
 * keep the timestamp upright and in the top-left of what the viewer sees, the
 * text is rendered counter-rotated and attached to the corner of the sensor
 * frame that maps to the displayed top-left. */

#include "cyclops_eye/osd.h"

#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "rk_mpi_rgn.h"
#include "rk_common.h"

/* 3x5 blocky font, scaled up. 19 chars ("YYYY-MM-DD HH:MM:SS") at 4 cells each
 * (3 glyph columns + 1 space). */
#define OSD_SCALE 6
#define OSD_CHARS 19
#define OSD_ADV (4 * OSD_SCALE)
#define OSD_W (((OSD_CHARS * OSD_ADV) + 15) / 16 * 16) /* align 16 */
#define OSD_H 32                                        /* 5*4=20 -> align 16 */
#define OSD_RGN_HANDLE 0
#define OSD_MARGIN 16

/* Each row is 3 bits, bit0 = leftmost column. */
static const unsigned char FONT3X5[13][5] = {
    {7, 5, 5, 5, 7}, /* 0 */
    {2, 6, 2, 2, 7}, /* 1 */
    {7, 1, 7, 4, 7}, /* 2 */
    {7, 1, 7, 1, 7}, /* 3 */
    {5, 5, 7, 1, 1}, /* 4 */
    {7, 4, 7, 1, 7}, /* 5 */
    {7, 4, 7, 5, 7}, /* 6 */
    {7, 1, 1, 1, 1}, /* 7 */
    {7, 5, 7, 5, 7}, /* 8 */
    {7, 5, 7, 1, 7}, /* 9 */
    {0, 0, 7, 0, 0}, /* - */
    {0, 2, 0, 2, 0}, /* : */
    {0, 0, 0, 0, 0}, /* space (anything else) */
};

static int glyph_index(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c == '-') return 10;
    if (c == ':') return 11;
    return 12;
}

struct eye_osd {
    RGN_HANDLE handle;
    int venc_channel;
    int frame_w;
    int frame_h;
    int rotation;      /* 0/90/180/270 clockwise, as the viewer rotates */
    int dst_w;         /* rendered bitmap size after counter-rotation */
    int dst_h;
    uint32_t *text;    /* horizontal text, OSD_W x OSD_H */
    uint32_t *buf;     /* counter-rotated bitmap attached to the VENC */
    pthread_t thread;
    atomic_bool running;
    bool started;
};

static void render_text(uint32_t *buf, const char *s) {
    memset(buf, 0, (size_t)OSD_W * OSD_H * sizeof(uint32_t));
    int x0 = 0;
    for (int i = 0; s[i] != '\0' && i < OSD_CHARS; i++) {
        int gi = glyph_index(s[i]);
        for (int row = 0; row < 5; row++) {
            unsigned bits = FONT3X5[gi][row];
            for (int col = 0; col < 3; col++) {
                if (!((bits >> col) & 1u)) continue;
                /* Glyph table encodes bit0 as the RIGHTMOST column, so reverse
                 * the column order here. */
                int px0 = x0 + (2 - col) * OSD_SCALE;
                int py0 = row * OSD_SCALE;
                for (int dy = 0; dy < OSD_SCALE; dy++) {
                    uint32_t *line = buf + (size_t)(py0 + dy) * OSD_W + px0;
                    for (int dx = 0; dx < OSD_SCALE; dx++) line[dx] = 0xFFFFFFFFu;
                }
            }
        }
        x0 += OSD_ADV;
    }
}

/* Rotate src (sw x sh) clockwise by deg (0/90/180/270) into dst, returning the
 * output dimensions. */
static void rotate_cw(const uint32_t *src, int sw, int sh,
                      uint32_t *dst, int deg, int *dw, int *dh) {
    if (deg == 90 || deg == 270) { *dw = sh; *dh = sw; }
    else { *dw = sw; *dh = sh; }
    for (int y = 0; y < *dh; y++) {
        for (int x = 0; x < *dw; x++) {
            int sx, sy;
            if (deg == 90)       { sx = y;          sy = sh - 1 - x; }
            else if (deg == 180) { sx = sw - 1 - x; sy = sh - 1 - y; }
            else if (deg == 270) { sx = sw - 1 - y; sy = x; }
            else                 { sx = x;          sy = y; }
            dst[(size_t)y * (*dw) + x] = src[(size_t)sy * sw + sx];
        }
    }
}

static void osd_render(eye_osd_t *o, const char *s) {
    render_text(o->text, s);
    /* Counter-rotate the text by the viewer's rotation. */
    int deg = (360 - o->rotation) % 360;
    rotate_cw(o->text, OSD_W, OSD_H, o->buf, deg, &o->dst_w, &o->dst_h);
}

static void osd_position(const eye_osd_t *o, int *x, int *y) {
    switch (o->rotation) {
    case 90:
        *x = OSD_MARGIN;
        *y = o->frame_h - o->dst_h - OSD_MARGIN;
        break;
    case 180:
        *x = o->frame_w - o->dst_w - OSD_MARGIN;
        *y = o->frame_h - o->dst_h - OSD_MARGIN;
        break;
    case 270:
        *x = o->frame_w - o->dst_w - OSD_MARGIN;
        *y = OSD_MARGIN;
        break;
    default:
        *x = OSD_MARGIN;
        *y = OSD_MARGIN;
        break;
    }
}

static void osd_chn(MPP_CHN_S *chn, int venc_channel) {
    memset(chn, 0, sizeof(*chn));
    chn->enModId = RK_ID_VENC;
    chn->s32DevId = 0;
    chn->s32ChnId = venc_channel;
}

static void osd_push(eye_osd_t *o) {
    BITMAP_S bmp;
    memset(&bmp, 0, sizeof(bmp));
    bmp.enPixelFormat = RK_FMT_ARGB8888;
    bmp.u32Width = (RK_U32)o->dst_w;
    bmp.u32Height = (RK_U32)o->dst_h;
    bmp.pData = o->buf;
    (void)RK_MPI_RGN_SetBitMap(o->handle, &bmp);
}

static void *osd_thread(void *arg) {
    eye_osd_t *o = arg;
    while (atomic_load(&o->running)) {
        time_t now = time(NULL);
        struct tm tm;
        localtime_r(&now, &tm);
        char s[32];
        if (strftime(s, sizeof(s), "%Y-%m-%d %H:%M:%S", &tm) > 0) {
            osd_render(o, s);
            osd_push(o);
        }
        for (int i = 0; i < 10 && atomic_load(&o->running); i++) usleep(100000);
    }
    return NULL;
}

static int osd_attach(eye_osd_t *o) {
    RGN_ATTR_S attr;
    memset(&attr, 0, sizeof(attr));
    attr.enType = OVERLAY_RGN;
    attr.unAttr.stOverlay.enPixelFmt = RK_FMT_ARGB8888;
    attr.unAttr.stOverlay.stSize.u32Width = (RK_U32)o->dst_w;
    attr.unAttr.stOverlay.stSize.u32Height = (RK_U32)o->dst_h;
    attr.unAttr.stOverlay.u32CanvasNum = 2;
    if (RK_MPI_RGN_Create(o->handle, &attr) != RK_SUCCESS) return -1;
    osd_push(o);

    MPP_CHN_S chn;
    osd_chn(&chn, o->venc_channel);
    int x, y;
    osd_position(o, &x, &y);
    RGN_CHN_ATTR_S ca;
    memset(&ca, 0, sizeof(ca));
    ca.bShow = RK_TRUE;
    ca.enType = OVERLAY_RGN;
    ca.unChnAttr.stOverlayChn.stPoint.s32X = x;
    ca.unChnAttr.stOverlayChn.stPoint.s32Y = y;
    ca.unChnAttr.stOverlayChn.u32FgAlpha = 255;
    ca.unChnAttr.stOverlayChn.u32BgAlpha = 0;
    ca.unChnAttr.stOverlayChn.u32Layer = 0;
    if (RK_MPI_RGN_AttachToChn(o->handle, &chn, &ca) != RK_SUCCESS) {
        (void)RK_MPI_RGN_Destroy(o->handle);
        return -1;
    }
    return 0;
}

eye_osd_t *eye_osd_start(int venc_channel, int frame_w, int frame_h,
                         int rotation) {
    eye_osd_t *o = calloc(1, sizeof(*o));
    if (o == NULL) return NULL;
    o->venc_channel = venc_channel;
    o->frame_w = frame_w;
    o->frame_h = frame_h;
    rotation = ((rotation % 360) + 360) % 360;
    o->rotation = (rotation / 90) * 90;   /* snap to 0/90/180/270 */
    o->handle = OSD_RGN_HANDLE;
    o->text = calloc((size_t)OSD_W * OSD_H, sizeof(uint32_t));
    o->buf = calloc((size_t)OSD_W * OSD_H, sizeof(uint32_t));
    if (o->text == NULL || o->buf == NULL) {
        free(o->text); free(o->buf); free(o);
        return NULL;
    }
    osd_render(o, "0000-00-00 00:00:00");
    if (osd_attach(o) != 0) {
        free(o->text); free(o->buf); free(o);
        return NULL;
    }

    atomic_store(&o->running, true);
    if (pthread_create(&o->thread, NULL, osd_thread, o) != 0) {
        atomic_store(&o->running, false);
        MPP_CHN_S chn;
        osd_chn(&chn, o->venc_channel);
        (void)RK_MPI_RGN_DetachFromChn(o->handle, &chn);
        (void)RK_MPI_RGN_Destroy(o->handle);
        free(o->text); free(o->buf); free(o);
        return NULL;
    }
    o->started = true;
    return o;
}

void eye_osd_stop(eye_osd_t *o) {
    if (o == NULL) return;
    if (o->started) {
        atomic_store(&o->running, false);
        (void)pthread_join(o->thread, NULL);
    }
    MPP_CHN_S chn;
    osd_chn(&chn, o->venc_channel);
    (void)RK_MPI_RGN_DetachFromChn(o->handle, &chn);
    (void)RK_MPI_RGN_Destroy(o->handle);
    free(o->text);
    free(o->buf);
    free(o);
}
