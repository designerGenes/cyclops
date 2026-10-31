#ifndef CYCLOPS_EYE_NTP_SYNC_H
#define CYCLOPS_EYE_NTP_SYNC_H

/* One-shot NTP (RFC 4330) client. Sends a single request to `server` (a
 * hostname or IPv4 address) and, on a valid reply, sets the system clock via
 * settimeofday(). Returns 0 on success, non-zero otherwise. Best-effort: the
 * camera should start regardless of the result. Non-blocking on failure with
 * a bounded timeout (usually a few seconds). */
int eye_ntp_sync(const char *server, int timeout_seconds);

#endif /* CYCLOPS_EYE_NTP_SYNC_H */