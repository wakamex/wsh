#ifndef WSH_RUNTIME_TRACE_H
#define WSH_RUNTIME_TRACE_H
#include "runtime-json.h"
struct wsh_runtime_trace {
    int fd, buffered, failed;
    uint64_t started_ns, profile_us;
    size_t bytes, limit, pending_size;
    char *pending;
};
int wsh_runtime_trace_open(struct wsh_runtime_trace *t);
uint64_t wsh_runtime_trace_time(const struct wsh_runtime_trace *t);
yyjson_mut_doc *wsh_runtime_trace_event(const char *event, int has_generation, uint64_t generation);
void wsh_runtime_trace_record(struct wsh_runtime_trace *t, yyjson_mut_doc *d, uint64_t elapsed_us);
void wsh_runtime_trace_flush(struct wsh_runtime_trace *t);
void wsh_runtime_trace_close(struct wsh_runtime_trace *t);
#endif
