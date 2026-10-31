/* Minimal one-shot NTP client so the burned-in timestamp starts out correct.
 *
 * The LuckFox image does not keep its RTC warm across boots (S99rtcinit only
 * initializes it once), so each boot starts on a stale clock and the running
 * `ntpd -g` then STEPS the clock a few seconds - which shows up as the
 * timestamp bouncing forward/backward during the first minute of video. By
 * syncing once, before the camera pipeline starts, the daemon later finds
 * ~zero offset and never steps. */
#include "cyclops_eye/ntp_sync.h"

#include <arpa/inet.h>
#include <netdb.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define NTP_EPOCH_OFFSET 2208988800ULL /* seconds between 1900 and 1970 */
#define NTP_MIN_EPOCH 1577836800ULL    /* 2020-01-01; reject absurd times */

typedef struct {
    uint8_t li_vn_mode; /* leap(0) | version(4) | mode(3 = client) */
    uint8_t stratum;
    int8_t poll;
    int8_t precision;
    uint32_t root_delay;
    uint32_t root_dispersion;
    uint32_t ref_id;
    uint32_t ref_ts_sec;
    uint32_t ref_ts_frac;
    uint32_t orig_ts_sec;
    uint32_t orig_ts_frac;
    uint32_t recv_ts_sec;
    uint32_t recv_ts_frac;
    uint32_t tx_ts_sec;
    uint32_t tx_ts_frac;
} ntp_packet_t;

int eye_ntp_sync(const char *server, int timeout_seconds) {
    ntp_packet_t packet;
    struct addrinfo hints;
    struct addrinfo *res = NULL;
    struct timeval timeout;
    socklen_t from_len = sizeof(struct sockaddr_in);
    struct sockaddr_in from;
    int fd = -1;
    int rc = -1;

    memset(&packet, 0, sizeof(packet));
    packet.li_vn_mode = 0x23; /* no leap warning, version 4, client */

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_DGRAM;
    if (getaddrinfo(server, "123", &hints, &res) != 0 || res == NULL) return -1;

    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) {
        freeaddrinfo(res);
        return -1;
    }
    timeout.tv_sec = timeout_seconds > 0 ? timeout_seconds : 3;
    timeout.tv_usec = 0;
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));

    if (sendto(fd, &packet, sizeof(packet), 0, res->ai_addr, res->ai_addrlen) ==
        (ssize_t)sizeof(packet)) {
        ssize_t received = recvfrom(fd, &packet, sizeof(packet), 0,
                                    (struct sockaddr *)&from, &from_len);
        if (received >= 48) {
            /* The transmit timestamp is the server's time (big-endian). */
            uint64_t ntp_sec = (uint64_t)ntohl(packet.tx_ts_sec);
            time_t epoch = (time_t)(ntp_sec - NTP_EPOCH_OFFSET);
            if (epoch >= (time_t)NTP_MIN_EPOCH && epoch < (time_t)0x7FFFFFFF) {
                struct timeval now;
                now.tv_sec = epoch;
                now.tv_usec = 0;
                if (settimeofday(&now, NULL) == 0) rc = 0;
            }
        }
    }

    close(fd);
    freeaddrinfo(res);
    return rc;
}