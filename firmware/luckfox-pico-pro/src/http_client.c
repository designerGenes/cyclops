#include "http_client.h"

#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

static int split_url(const char *url, char *host, size_t host_size, char *port, size_t port_size,
                     char *prefix, size_t prefix_size) {
    const char *authority;
    const char *path;
    const char *colon;
    size_t authority_length;
    if (strncmp(url, "http://", 7) != 0) return -1;
    authority = url + 7;
    path = strchr(authority, '/');
    authority_length = path == NULL ? strlen(authority) : (size_t)(path - authority);
    colon = memchr(authority, ':', authority_length);
    if (authority_length == 0 || authority_length >= host_size) return -1;
    if (colon != NULL) {
        size_t host_length = (size_t)(colon - authority);
        size_t port_length = authority_length - host_length - 1;
        if (host_length == 0 || host_length >= host_size || port_length == 0 || port_length >= port_size) return -1;
        memcpy(host, authority, host_length);
        host[host_length] = '\0';
        memcpy(port, colon + 1, port_length);
        port[port_length] = '\0';
    } else {
        memcpy(host, authority, authority_length);
        host[authority_length] = '\0';
        (void)snprintf(port, port_size, "80");
    }
    if (path == NULL) {
        prefix[0] = '\0';
    } else if (strlen(path) >= prefix_size) {
        return -1;
    } else {
        (void)snprintf(prefix, prefix_size, "%s", path);
    }
    return 0;
}

int eye_http_post(const char *base_url, const char *path, const char *json,
                  char *error, size_t error_size) {
    char host[256], port[8], prefix[256], request[2048], response[256];
    struct addrinfo hints = {0}, *addresses = NULL, *candidate;
    int socket_fd = -1;
    int result = -1;
    int bytes;
    if (split_url(base_url, host, sizeof(host), port, sizeof(port), prefix, sizeof(prefix)) != 0 ||
        path[0] != '/' || strlen(prefix) + strlen(path) >= sizeof(prefix)) {
        (void)snprintf(error, error_size, "invalid Cyclops URL");
        return -1;
    }
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(host, port, &hints, &addresses) != 0) {
        (void)snprintf(error, error_size, "cannot resolve Cyclops host");
        return -1;
    }
    for (candidate = addresses; candidate != NULL; candidate = candidate->ai_next) {
        socket_fd = socket(candidate->ai_family, candidate->ai_socktype, candidate->ai_protocol);
        if (socket_fd >= 0 && connect(socket_fd, candidate->ai_addr, candidate->ai_addrlen) == 0) break;
        if (socket_fd >= 0) close(socket_fd);
        socket_fd = -1;
    }
    freeaddrinfo(addresses);
    if (socket_fd < 0) {
        (void)snprintf(error, error_size, "cannot connect to Cyclops");
        return -1;
    }
    bytes = snprintf(request, sizeof(request),
                     "POST %s%s HTTP/1.1\r\nHost: %s\r\nContent-Type: application/json\r\n"
                     "Content-Length: %zu\r\nConnection: close\r\n\r\n%s",
                     prefix, path, host, strlen(json), json);
    if (bytes < 0 || (size_t)bytes >= sizeof(request) || send(socket_fd, request, (size_t)bytes, 0) != bytes) {
        (void)snprintf(error, error_size, "failed to send request");
        goto done;
    }
    bytes = (int)recv(socket_fd, response, sizeof(response) - 1, 0);
    if (bytes <= 0) {
        (void)snprintf(error, error_size, "empty Cyclops response");
        goto done;
    }
    response[bytes] = '\0';
    if (strncmp(response, "HTTP/1.1 2", 10) != 0 && strncmp(response, "HTTP/1.0 2", 10) != 0) {
        (void)snprintf(error, error_size, "Cyclops rejected request: %.32s", response);
        goto done;
    }
    result = 0;
done:
    close(socket_fd);
    return result;
}
