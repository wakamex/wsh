#ifndef WSH_RUNTIME_JSON_H
#define WSH_RUNTIME_JSON_H
#include <jansson.h>
#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static inline void *allocate(size_t n)
{
    void *p = malloc(n);
    if (!p)
        abort();
    return p;
}
static inline uint64_t clock_ns(clockid_t clock)
{
    struct timespec t;
    if (clock_gettime(clock, &t))
        abort();
    return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec;
}
static inline json_t *object(void)
{
    json_t *d = json_object();
    if (!d) abort();
    return d;
}
static inline char *encode(json_t *d, size_t *length)
{
    char *line = json_dumps(d, JSON_COMPACT);
    if (!line) abort();
    *length = strlen(line);
    return line;
}
static inline void string_field(json_t *d, const char *k, const char *v)
{
    if (json_object_set_new(d, k, v ? json_string(v) : json_null())) abort();
}
static inline void uint_field(json_t *d, const char *k, uint64_t v)
{
    if (v > LLONG_MAX || json_object_set_new(d, k, json_integer((json_int_t)v))) abort();
}
static inline void bool_field(json_t *d, const char *k, int v)
{
    if (json_object_set_new(d, k, json_boolean(v))) abort();
}
static inline int nonnegative(json_t *v)
{
    return json_is_integer(v) && json_integer_value(v) >= 0;
}
static inline char *hex(const char *text)
{
    static const char digits[] = "0123456789abcdef";
    size_t n = strlen(text);
    if (n > (SIZE_MAX - 1) / 2)
        abort();
    char *out = allocate(n * 2 + 1);
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)text[i];
        out[2 * i] = digits[c >> 4];
        out[2 * i + 1] = digits[c & 15];
    }
    out[2 * n] = 0;
    return out;
}
#endif
