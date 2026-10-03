#ifndef CYCLOPS_EYE_HTTP_CLIENT_H
#define CYCLOPS_EYE_HTTP_CLIENT_H

#include <stddef.h>

int eye_http_post(const char *base_url, const char *path, const char *json,
                  char *error, size_t error_size);

#endif
