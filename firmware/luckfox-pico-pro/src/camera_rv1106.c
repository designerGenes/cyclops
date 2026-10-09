#include "cyclops_eye/camera.h"
#include "cyclops_eye/osd.h"

#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "rtsp_demo.h"
#include "rk_aiq_user_api2_sysctl.h"
#include "rk_mpi_mb.h"
#include "rk_mpi_sys.h"
#include "rk_mpi_venc.h"
#include "rk_mpi_vi.h"

enum { PRIMARY_CHANNEL = 0, DETECT_CHANNEL = 1, DETECT_WIDTH = 640, DETECT_HEIGHT = 360,
       DETECT_FPS_CAP = 4, DETECT_BITRATE_KBPS = 250 };

typedef struct {
    int vi_channel;
    int venc_channel;
    rtsp_session_handle session;
    rtsp_demo_handle rtsp;
    pthread_t thread;
    atomic_bool running;
    bool configured;
} encoder_stream_t;

struct eye_camera {
    const eye_config_t *config;
    rtsp_demo_handle rtsp;
    rk_aiq_sys_ctx_t *aiq_ctx;
    encoder_stream_t primary;
    encoder_stream_t detect;
    bool aiq_started;
    bool system_initialized;
    eye_osd_t *osd;
};

/* The Rockchip ISP is a separate owner from the VI/VENC MPP pipeline. It
 * must be initialized with the sensor-specific IQ files before video input
 * is enabled; without it the camera may enumerate but produce no usable ISP
 * frames. This follows the vendor RV1106 simple_vi_bind_venc_rtsp example. */
static int isp_start(eye_camera_t *camera) {
    rk_aiq_static_info_t info;
    memset(&info, 0, sizeof(info));
    if (rk_aiq_uapi2_sysctl_enumStaticMetas(camera->config->camera_id, &info) !=
        XCAM_RETURN_NO_ERROR || info.sensor_info.sensor_name[0] == '\0') {
        return -1;
    }
    camera->aiq_ctx = rk_aiq_uapi2_sysctl_init(
        info.sensor_info.sensor_name, camera->config->iq_dir, NULL, NULL);
    if (camera->aiq_ctx == NULL) return -1;
    if (rk_aiq_uapi2_sysctl_prepare(camera->aiq_ctx, 0, 0,
                                    RK_AIQ_WORKING_MODE_NORMAL) !=
        XCAM_RETURN_NO_ERROR) {
        rk_aiq_uapi2_sysctl_deinit(camera->aiq_ctx);
        camera->aiq_ctx = NULL;
        return -1;
    }
    if (rk_aiq_uapi2_sysctl_start(camera->aiq_ctx) != XCAM_RETURN_NO_ERROR) {
        rk_aiq_uapi2_sysctl_deinit(camera->aiq_ctx);
        camera->aiq_ctx = NULL;
        return -1;
    }
    camera->aiq_started = true;
    return 0;
}

static void isp_stop(eye_camera_t *camera) {
    if (camera->aiq_ctx == NULL) return;
    if (camera->aiq_started)
        (void)rk_aiq_uapi2_sysctl_stop(camera->aiq_ctx, false);
    rk_aiq_uapi2_sysctl_deinit(camera->aiq_ctx);
    camera->aiq_ctx = NULL;
    camera->aiq_started = false;
}

static int vi_device_start(void) {
    VI_DEV_ATTR_S device_attr;
    VI_DEV_BIND_PIPE_S pipe;
    memset(&device_attr, 0, sizeof(device_attr));
    memset(&pipe, 0, sizeof(pipe));
    if (RK_MPI_VI_GetDevAttr(0, &device_attr) == RK_ERR_VI_NOT_CONFIG &&
        RK_MPI_VI_SetDevAttr(0, &device_attr) != RK_SUCCESS) return -1;
    if (RK_MPI_VI_GetDevIsEnable(0) != RK_SUCCESS) {
        pipe.u32Num = 1;
        pipe.PipeId[0] = 0;
        if (RK_MPI_VI_EnableDev(0) != RK_SUCCESS || RK_MPI_VI_SetDevBindPipe(0, &pipe) != RK_SUCCESS) return -1;
    }
    return 0;
}

static int stream_start(encoder_stream_t *stream, int width, int height, int fps, int bitrate_kbps) {
    VI_CHN_ATTR_S vi_attr;
    VENC_CHN_ATTR_S venc_attr;
    VENC_RECV_PIC_PARAM_S receive;
    MPP_CHN_S source = {RK_ID_VI, 0, stream->vi_channel};
    MPP_CHN_S destination = {RK_ID_VENC, 0, stream->venc_channel};
    memset(&vi_attr, 0, sizeof(vi_attr));
    vi_attr.stIspOpt.u32BufCount = 3;
    vi_attr.stIspOpt.enMemoryType = VI_V4L2_MEMORY_TYPE_DMABUF;
    vi_attr.stSize.u32Width = (RK_U32)width;
    vi_attr.stSize.u32Height = (RK_U32)height;
    vi_attr.enPixelFormat = RK_FMT_YUV420SP;
    vi_attr.enCompressMode = COMPRESS_MODE_NONE;
    vi_attr.u32Depth = 0;
    vi_attr.stFrameRate.s32SrcFrameRate = -1;
    vi_attr.stFrameRate.s32DstFrameRate = fps;
    if (RK_MPI_VI_SetChnAttr(0, stream->vi_channel, &vi_attr) != RK_SUCCESS ||
        RK_MPI_VI_EnableChn(0, stream->vi_channel) != RK_SUCCESS) return -1;

    memset(&venc_attr, 0, sizeof(venc_attr));
    venc_attr.stRcAttr.enRcMode = VENC_RC_MODE_H264CBR;
    venc_attr.stRcAttr.stH264Cbr.u32BitRate = (RK_U32)bitrate_kbps;
    venc_attr.stRcAttr.stH264Cbr.u32Gop = (RK_U32)fps;
    venc_attr.stVencAttr.enType = RK_VIDEO_ID_AVC;
    venc_attr.stVencAttr.enPixelFormat = RK_FMT_YUV420SP;
    venc_attr.stVencAttr.u32Profile = H264E_PROFILE_HIGH;
    venc_attr.stVencAttr.u32PicWidth = (RK_U32)width;
    venc_attr.stVencAttr.u32PicHeight = (RK_U32)height;
    venc_attr.stVencAttr.u32VirWidth = (RK_U32)width;
    venc_attr.stVencAttr.u32VirHeight = (RK_U32)height;
    venc_attr.stVencAttr.u32StreamBufCnt = 3;
    venc_attr.stVencAttr.u32BufSize = (RK_U32)(width * height * 3 / 2);
    if (RK_MPI_VENC_CreateChn(stream->venc_channel, &venc_attr) != RK_SUCCESS) return -1;
    memset(&receive, 0, sizeof(receive));
    receive.s32RecvPicNum = -1;
    if (RK_MPI_VENC_StartRecvFrame(stream->venc_channel, &receive) != RK_SUCCESS ||
        RK_MPI_SYS_Bind(&source, &destination) != RK_SUCCESS) return -1;
    stream->configured = true;
    return 0;
}

static void *stream_frames(void *argument) {
    encoder_stream_t *stream = argument;
    VENC_STREAM_S frame;
    VENC_PACK_S pack;
    memset(&frame, 0, sizeof(frame));
    frame.pstPack = &pack;
    while (atomic_load(&stream->running)) {
        if (RK_MPI_VENC_GetStream(stream->venc_channel, &frame, 200000) == RK_SUCCESS) {
            const uint8_t *data = RK_MPI_MB_Handle2VirAddr(frame.pstPack->pMbBlk);
            if (data != NULL && stream->session != NULL)
                (void)rtsp_tx_video(stream->session, data, (int)frame.pstPack->u32Len, frame.pstPack->u64PTS);
            if (stream->rtsp != NULL) (void)rtsp_do_event(stream->rtsp);
            (void)RK_MPI_VENC_ReleaseStream(stream->venc_channel, &frame);
        }
    }
    return NULL;
}

static void stream_stop(encoder_stream_t *stream) {
    MPP_CHN_S source = {RK_ID_VI, 0, stream->vi_channel};
    MPP_CHN_S destination = {RK_ID_VENC, 0, stream->venc_channel};
    if (!stream->configured) return;
    if (atomic_exchange(&stream->running, false)) (void)pthread_join(stream->thread, NULL);
    (void)RK_MPI_SYS_UnBind(&source, &destination);
    (void)RK_MPI_VENC_StopRecvFrame(stream->venc_channel);
    (void)RK_MPI_VENC_DestroyChn(stream->venc_channel);
    (void)RK_MPI_VI_DisableChn(0, stream->vi_channel);
    stream->configured = false;
}

static int camera_start_streams(eye_camera_t *camera, const eye_tier_t *tier, int primary_fps) {
    int detect_fps = primary_fps < DETECT_FPS_CAP ? primary_fps : DETECT_FPS_CAP;
    camera->primary = (encoder_stream_t){.vi_channel = PRIMARY_CHANNEL, .venc_channel = PRIMARY_CHANNEL};
    camera->detect = (encoder_stream_t){.vi_channel = DETECT_CHANNEL, .venc_channel = DETECT_CHANNEL};
    camera->primary.rtsp = camera->rtsp;
    camera->detect.rtsp = camera->rtsp;
    camera->primary.session = rtsp_new_session(camera->rtsp, "/cam");
    camera->detect.session = rtsp_new_session(camera->rtsp, "/detect");
    if (camera->primary.session == NULL || camera->detect.session == NULL ||
        rtsp_set_video(camera->primary.session, RTSP_CODEC_ID_VIDEO_H264, NULL, 0) != 0 ||
        rtsp_set_video(camera->detect.session, RTSP_CODEC_ID_VIDEO_H264, NULL, 0) != 0 ||
        stream_start(&camera->primary, tier->width, tier->height, primary_fps, tier->bitrate_kbps) != 0 ||
        stream_start(&camera->detect, DETECT_WIDTH, DETECT_HEIGHT, detect_fps, DETECT_BITRATE_KBPS) != 0) return -1;
    (void)rtsp_sync_video_ts(camera->primary.session, rtsp_get_reltime(), rtsp_get_ntptime());
    (void)rtsp_sync_video_ts(camera->detect.session, rtsp_get_reltime(), rtsp_get_ntptime());
    atomic_store(&camera->primary.running, true);
    atomic_store(&camera->detect.running, true);
    if (pthread_create(&camera->primary.thread, NULL, stream_frames, &camera->primary) != 0) {
        atomic_store(&camera->primary.running, false);
        atomic_store(&camera->detect.running, false);
        return -1;
    }
    if (pthread_create(&camera->detect.thread, NULL, stream_frames, &camera->detect) != 0) {
        atomic_store(&camera->detect.running, false);
        stream_stop(&camera->primary);
        return -1;
    }
    /* Burn a timestamp into the primary encoder output (RGN overlay). */
    camera->osd = eye_osd_start(PRIMARY_CHANNEL, 16, 16);
    return 0;
}

int eye_camera_start(eye_camera_t **out_camera, const eye_config_t *config, const eye_tier_t *tier,
                     int primary_fps) {
    eye_camera_t *camera = calloc(1, sizeof(*camera));
    if (camera == NULL) return -1;
    camera->config = config;
    if (isp_start(camera) != 0 || RK_MPI_SYS_Init() != RK_SUCCESS ||
        vi_device_start() != 0) goto failed;
    camera->system_initialized = true;
    camera->rtsp = create_rtsp_demo(config->rtsp_port);
    if (camera->rtsp == NULL || camera_start_streams(camera, tier, primary_fps) != 0) goto failed;
    *out_camera = camera;
    return 0;
failed:
    eye_camera_stop(camera);
    return -1;
}

int eye_camera_apply_tier(eye_camera_t *camera, const eye_tier_t *tier, int primary_fps) {
    eye_osd_stop(camera->osd);
    camera->osd = NULL;
    stream_stop(&camera->primary);
    stream_stop(&camera->detect);
    if (camera->primary.session != NULL) rtsp_del_session(camera->primary.session);
    if (camera->detect.session != NULL) rtsp_del_session(camera->detect.session);
    return camera_start_streams(camera, tier, primary_fps);
}

bool eye_camera_ready(const eye_camera_t *camera) {
    return camera != NULL && atomic_load(&camera->primary.running) && atomic_load(&camera->detect.running);
}

void eye_camera_stop(eye_camera_t *camera) {
    if (camera == NULL) return;
    eye_osd_stop(camera->osd);
    camera->osd = NULL;
    stream_stop(&camera->primary);
    stream_stop(&camera->detect);
    if (camera->primary.session != NULL) rtsp_del_session(camera->primary.session);
    if (camera->detect.session != NULL) rtsp_del_session(camera->detect.session);
    if (camera->rtsp != NULL) rtsp_del_demo(camera->rtsp);
    /* Stop the ISP/AIQ while the MPP media system is still up. Tearing
     * RK_MPI_SYS down first leaves rk_aiq holding dangling media buffers, and
     * rk_aiq_uapi2_sysctl_stop() then dereferences NULL -- the librkaiq
     * SIGSEGV seen in the core-*-cyclops-eye dumps. */
    isp_stop(camera);
    if (camera->system_initialized) {
        (void)RK_MPI_VI_DisableDev(0);
        (void)RK_MPI_SYS_Exit();
    }
    free(camera);
}
