/* On-device timestamp OSD for the Luckfox Cyclops eye.
 *
 * Draws "YYYY-MM-DD HH:MM:SS" into an ARGB8888 bitmap and overlays it on the
 * hardware H.264 encoder output via the Rockchip RGN module, so the timestamp
 * is burned into the stream (matching the Pi eyes' rpiCameraTextOverlay). */

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
#define OSD_SCALE 4
#define OSD_CHARS 19
#define OSD_ADV (4 * OSD_SCALE)
#define OSD_W (((OSD_CHARS * OSD_ADV) + 15) / 16 * 16) /* align 16 */
#define OSD_H 32                                        /* 5*4=20 -> align 16 */
#define OSD_RGN_HANDLE 0

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
    uint32_t *buf;
    pthread_t thread;
    atomic_bool running;
    bool started;
};

static void render(uint32_t *buf, const char *s) {
    memset(buf, 0, (size_t)OSD_W * OSD_H * sizeof(uint32_t));
    int x0 = 0;
    for (int i = 0; s[i] != '\0' && i < OSD_CHARS; i++) {
        int gi = glyph_index(s[i]);
        for (int row = 0; row < 5; row++) {
            unsigned bits = FONT3X5[gi][row];
            for (int col = 0; col < 3; col++) {
                if (!((bits >> col) & 1u)) continue;
                int px0 = x0 + col * OSD_SCALE;
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

static void osd_push(eye_osd_t *o) {
    BITMAP_S bmp;
    memset(&bmp, 0, sizeof(bmp));
    bmp.enPixelFormat = RK_FMT_ARGB8888;
    bmp.u32Width = OSD_W;
    bmp.u32Height = OSD_H;
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
            render(o->buf, s);
            osd_push(o);
        }
        for (int i = 0; i < 10 && atomic_load(&o->running); i++) usleep(100000);
    }
    return NULL;
}

static void osd_chn(MPP_CHN_S *chn, int venc_channel) {
    memset(chn, 0, sizeof(*chn));
    chn->enModId = RK_ID_VENC;
    chn->s32DevId = 0;
    chn->s32ChnId = venc_channel;
}

eye_osd_t *eye_osd_start(int venc_channel, int x, int y) {
    eye_osd_t *o = calloc(1, sizeof(*o));
    if (o == NULL) return NULL;
    o->venc_channel = venc_channel;
    o->handle = OSD_RGN_HANDLE;
    o->buf = calloc((size_t)OSD_W * OSD_H, sizeof(uint32_t));
    if (o->buf == NULL) { free(o); return NULL; }
    render(o->buf, "0000-00-00 00:00:00");

    RGN_ATTR_S attr;
    memset(&attr, 0, sizeof(attr));
    attr.enType = OVERLAY_RGN;
    attr.unAttr.stOverlay.enPixelFmt = RK_FMT_ARGB8888;
    attr.unAttr.stOverlay.stSize.u32Width = OSD_W;
    attr.unAttr.stOverlay.stSize.u32Height = OSD_H;
    attr.unAttr.stOverlay.u32CanvasNum = 2;
    if (RK_MPI_RGN_Create(o->handle, &attr) != RK_SUCCESS) {
        free(o->buf); free(o); return NULL;
    }
    osd_push(o);

    MPP_CHN_S chn;
    osd_chn(&chn, venc_channel);
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
        free(o->buf); free(o); return NULL;
    }

    atomic_store(&o->running, true);
    if (pthread_create(&o->thread, NULL, osd_thread, o) != 0) {
        atomic_store(&o->running, false);
        (void)RK_MPI_RGN_DetachFromChn(o->handle, &chn);
        (void)RK_MPI_RGN_Destroy(o->handle);
        free(o->buf); free(o); return NULL;
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
    free(o->buf);
    free(o);
}
