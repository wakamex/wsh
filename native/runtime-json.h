#ifndef WSH_RUNTIME_JSON_H
#define WSH_RUNTIME_JSON_H
#include "yyjson.h"
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
static inline yyjson_mut_doc *object(void)
{
    yyjson_mut_doc *d = yyjson_mut_doc_new(NULL);
    if (!d)
        abort();
    yyjson_mut_val *v = yyjson_mut_obj(d);
    if (!v)
        abort();
    yyjson_mut_doc_set_root(d, v);
    return d;
}
static inline void string_field(yyjson_mut_doc *d, const char *k, const char *v)
{
    if (!(v ? yyjson_mut_obj_add_strcpy(d, yyjson_mut_doc_get_root(d), k, v)
            : yyjson_mut_obj_add_null(d, yyjson_mut_doc_get_root(d), k)))
        abort();
}
static inline void uint_field(yyjson_mut_doc *d, const char *k, uint64_t v)
{
    if (!yyjson_mut_obj_add_uint(d, yyjson_mut_doc_get_root(d), k, v))
        abort();
}
static inline void bool_field(yyjson_mut_doc *d, const char *k, int v)
{
    if (!yyjson_mut_obj_add_bool(d, yyjson_mut_doc_get_root(d), k, v != 0))
        abort();
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
