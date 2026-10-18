#include "control_server.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static void send_json(int socket_fd, int status, const char *body) {
    char response[1024];
    const char *text = status == 200 ? "OK" : status == 400 ? "Bad Request" :
                       status == 403 ? "Forbidden" : "Not Found";
    int length = snprintf(response, sizeof(response),
                          "HTTP/1.1 %d %s\r\nContent-Type: application/json\r\n"
                          "Content-Length: %zu\r\nConnection: close\r\n\r\n%s",
                          status, text, strlen(body), body);
    if (length > 0 && (size_t)length < sizeof(response)) (void)send(socket_fd, response, (size_t)length, 0);
}

static bool authorized(const char *request, const char *token) {
    const char *header = strstr(request, "\r\nX-Camnode-Token:");
    size_t token_length = strlen(token);
    if (header == NULL) return false;
    header += strlen("\r\nX-Camnode-Token:");
    while (*header == ' ') header++;
    return strncmp(header, token, token_length) == 0 &&
           (header[token_length] == '\r' || header[token_length] == '\n');
}

static bool body_value(const char *request, const char *key, char *value, size_t value_size) {
    char pattern[64];
    const char *start;
    const char *end;
    if (snprintf(pattern, sizeof(pattern), "\"%s\":\"", key) < 0) return false;
    start = strstr(request, pattern);
    if (start == NULL) return false;
    start += strlen(pattern);
    end = strchr(start, '"');
    if (end == NULL || end == start || (size_t)(end - start) >= value_size) return false;
    memcpy(value, start, (size_t)(end - start));
    value[end - start] = '\0';
    return true;
}

int eye_control_server_start(eye_control_server_t *server, int port, const char *token) {
    struct sockaddr_in address;
    int enabled = 1;
    memset(server, 0, sizeof(*server));
    server->socket_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server->socket_fd < 0) return -1;
    (void)setsockopt(server->socket_fd, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof(enabled));
    (void)fcntl(server->socket_fd, F_SETFL, fcntl(server->socket_fd, F_GETFL, 0) | O_NONBLOCK);
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    address.sin_port = htons((uint16_t)port);
    if (bind(server->socket_fd, (struct sockaddr *)&address, sizeof(address)) != 0 ||
        listen(server->socket_fd, 4) != 0) {
        close(server->socket_fd);
        server->socket_fd = -1;
        return -1;
    }
    server->token = token;
    return 0;
}

int eye_control_server_poll(eye_control_server_t *server, eye_governor_t *governor,
                            eye_camera_t *camera, bool camera_ready) {
    char request[2048];
    int client;
    ssize_t received;
    if (server->socket_fd < 0) return 0;
    client = accept(server->socket_fd, NULL, NULL);
    if (client < 0) return errno == EAGAIN || errno == EWOULDBLOCK ? 0 : -1;
    received = recv(client, request, sizeof(request) - 1, 0);
    if (received <= 0) {
        close(client);
        return 0;
    }
    request[received] = '\0';
    if (strncmp(request, "GET /health ", 12) == 0) {
        char body[256];
        const eye_tier_t *tier = eye_tier(eye_governor_effective_tier(governor));
        (void)snprintf(body, sizeof(body),
                       "{\"tier\":\"%s\",\"fps\":%d,\"camera_ready\":%s}",
                       tier->name, eye_governor_effective_fps(governor), camera_ready ? "true" : "false");
        send_json(client, 200, body);
        close(client);
        return 0;
    }
    if (strncmp(request, "POST /tier ", 11) == 0 || strncmp(request, "POST /fps ", 10) == 0) {
        char value[32];
        bool updated = false;
        if (!authorized(request, server->token)) {
            send_json(client, 403, "{\"error\":\"bad token\"}");
        } else if (strncmp(request, "POST /tier ", 11) == 0 && body_value(request, "tier", value, sizeof(value))) {
            updated = eye_governor_set_manual_tier(governor, value);
            send_json(client, updated ? 200 : 400, updated ? "{\"tier\":\"updated\"}" : "{\"error\":\"unknown tier\"}");
        } else if (body_value(request, "fps", value, sizeof(value))) {
            char *end = NULL;
            long fps = strtol(value, &end, 10);
            if (strcmp(value, "auto") == 0) {
                updated = eye_governor_set_fps(governor, 0);
            } else {
                updated = end != value && *end == '\0' && eye_governor_set_fps(governor, (int)fps);
            }
            send_json(client, updated ? 200 : 400, updated ? "{\"fps\":\"updated\"}" : "{\"error\":\"bad fps\"}");
        } else {
            send_json(client, 400, "{\"error\":\"bad request\"}");
        }
        close(client);
        return updated ? 1 : 0;
    }
    if (strncmp(request, "POST /rotation ", 15) == 0) {
        char value[32];
        bool updated = false;
        if (!authorized(request, server->token)) {
            send_json(client, 403, "{\"error\":\"bad token\"}");
        } else if (body_value(request, "rotation", value, sizeof(value))) {
            char *end = NULL;
            long degrees = strtol(value, &end, 10);
            if (end != value && *end == '\0' && camera != NULL)
                updated = eye_camera_set_rotation(camera, (int)degrees) == 0;
            send_json(client, updated ? 200 : 400,
                      updated ? "{\"rotation\":\"updated\"}" : "{\"error\":\"bad rotation\"}");
        } else {
            send_json(client, 400, "{\"error\":\"bad request\"}");
        }
        close(client);
        return updated ? 1 : 0;
    }
    send_json(client, 404, "{\"error\":\"not found\"}");
    close(client);
    return 0;
}

void eye_control_server_stop(eye_control_server_t *server) {
    if (server->socket_fd >= 0) close(server->socket_fd);
    server->socket_fd = -1;
}
