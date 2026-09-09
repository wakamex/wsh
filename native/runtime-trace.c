#define _GNU_SOURCE
#include "runtime-trace.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

int wsh_runtime_trace_open(struct wsh_runtime_trace *t)
{
    memset(t, 0, sizeof(*t));
    t->fd = -1;
    t->limit = 8 * 1024 * 1024;
    t->started_ns = clock_ns(CLOCK_MONOTONIC);
    const char *path = getenv("WSH_TRACE_FILE");
    if (!path)
        return 0;
    t->fd = open(path, O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK, 0600);
    struct stat st;
    if (t->fd < 0 || fstat(t->fd, &st) || !S_ISREG(st.st_mode) || st.st_size < 0 ||
        (uint64_t)st.st_size >= t->limit || fchmod(t->fd, 0600)) {
        if (t->fd >= 0)
            close(t->fd);
        t->fd = -1;
        return -1;
    }
    t->bytes = (size_t)st.st_size;
    const char *profile = getenv("WSH_PROFILE_STARTED_UNIX_US");
    if (profile && *profile) {
        const char *p = *profile == '+' ? profile + 1 : profile;
        uint64_t n = 0;
        int valid = *p != 0;
        for (; *p; ++p) {
            if (*p < '0' || *p > '9' || n > (UINT64_MAX - (unsigned)(*p - '0')) / 10) {
                valid = 0;
                break;
            }
            n = n * 10 + (unsigned)(*p - '0');
        }
        if (valid) {
            t->profile_us = n;
            t->buffered = 1;
            t->limit = 7 * 1024 * 1024;
        }
    }
    return 0;
}
uint64_t wsh_runtime_trace_time(const struct wsh_runtime_trace *t)
{
    if (t->buffered) {
        uint64_t now = clock_ns(CLOCK_REALTIME) / 1000;
        return now > t->profile_us ? now - t->profile_us : 0;
    }
    return (clock_ns(CLOCK_MONOTONIC) - t->started_ns) / 1000;
}
yyjson_mut_doc *wsh_runtime_trace_event(const char *event, int has_generation, uint64_t generation)
{
    yyjson_mut_doc *d = object();
    uint_field(d, "schema_version", 1);
    string_field(d, "source", "runtime");
    string_field(d, "event", event);
    if (has_generation)
        uint_field(d, "generation", generation);
    return d;
}
static void write_bytes(struct wsh_runtime_trace *t, const char *p, size_t n)
{
    while (n) {
        ssize_t used = write(t->fd, p, n);
        if (used < 0 && errno == EINTR)
            continue;
        if (used <= 0) {
            t->failed = 1;
            return;
        }
        p += used;
        n -= (size_t)used;
    }
}
void wsh_runtime_trace_record(struct wsh_runtime_trace *t, yyjson_mut_doc *d, uint64_t elapsed_us)
{
    if (t->fd < 0 || t->failed) {
        yyjson_mut_doc_free(d);
        return;
    }
    uint_field(d, "elapsed_us", elapsed_us);
    size_t n;
    char *line = yyjson_mut_write(d, 0, &n);
    if (!line)
        abort();
    yyjson_mut_doc_free(d);
    if (t->bytes < t->limit && n < t->limit - t->bytes) {
        line[n++] = '\n';
        t->bytes += n;
        if (t->buffered) {
            char *pending = realloc(t->pending, t->pending_size + n);
            if (!pending)
                abort();
            t->pending = pending;
            memcpy(t->pending + t->pending_size, line, n);
            t->pending_size += n;
        } else
            write_bytes(t, line, n);
    }
    free(line);
}
void wsh_runtime_trace_flush(struct wsh_runtime_trace *t)
{
    if (t->pending_size && !t->failed)
        write_bytes(t, t->pending, t->pending_size);
    free(t->pending);
    t->pending = NULL;
    t->pending_size = 0;
}
void wsh_runtime_trace_close(struct wsh_runtime_trace *t)
{
    wsh_runtime_trace_flush(t);
    if (t->fd >= 0)
        close(t->fd);
    t->fd = -1;
}
