/* Opt-in complete C helper. The native shell remains a separate process. */
#define _GNU_SOURCE
#include "render.h"
#include "runtime-trace.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdio.h>
#include <sys/prctl.h>
#include <unistd.h>

struct request {
    uint64_t id, generation, duration, received_us;
    char *cwd;
    int status, has_duration, privileged, reset, received_recorded;
};
struct worker {
    pthread_t thread;
    atomic_int cancel;
    struct request request;
    struct wsh_git_result git;
    uint64_t elapsed_ns;
    int notify_fd;
};
struct runtime {
    struct wsh_renderer renderer;
    struct wsh_runtime_trace trace;
    struct worker *active;
    struct request *pending;
    uint64_t latest, cancelled;
    char *last_left, *last_right;
    int notifications[2], failed, stopping;
};
static volatile sig_atomic_t terminating;
static void terminate(int signal_number)
{
    terminating = signal_number;
}
static void request_free(struct request *request)
{
    if (request) {
        free(request->cwd);
        free(request);
    }
}
static void trace_event(struct runtime *r, const char *name, int has_generation,
                        uint64_t generation)
{
    if (r->trace.fd >= 0)
        wsh_runtime_trace_record(&r->trace,
                                 wsh_runtime_trace_event(name, has_generation, generation),
                                 wsh_runtime_trace_time(&r->trace));
}
static void response(struct runtime *r, yyjson_mut_doc *doc)
{
    size_t length;
    char *line = yyjson_mut_write(doc, 0, &length);
    if (!line)
        abort();
    yyjson_mut_doc_free(doc);
    line[length++] = '\n';
    size_t offset = 0;
    while (offset < length) {
        ssize_t n = write(STDOUT_FILENO, line + offset, length - offset);
        if (n < 0 && errno == EINTR && !terminating)
            continue;
        if (n <= 0) {
            r->failed = 1;
            break;
        }
        offset += (size_t)n;
    }
    free(line);
}
static yyjson_mut_doc *message(const char *type)
{
    yyjson_mut_doc *d = object();
    uint_field(d, "version", 1);
    string_field(d, "type", type);
    return d;
}
static void reply(struct runtime *r, const char *type, int has_id, uint64_t id, const char *error)
{
    yyjson_mut_doc *d = message(type);
    if (has_id)
        uint_field(d, "id", id);
    else
        string_field(d, "id", NULL);
    if (error)
        string_field(d, "error", error);
    response(r, d);
}
static int cancelled(void *data)
{
    return atomic_load_explicit(&((struct worker *)data)->cancel, memory_order_acquire);
}
static void *collect(void *data)
{
    struct worker *w = data;
    uint64_t started = clock_ns(CLOCK_MONOTONIC);
    wsh_git_collect(w->request.cwd, "git", cancelled, w, &w->git);
    w->elapsed_ns = clock_ns(CLOCK_MONOTONIC) - started;
    while (write(w->notify_fd, "x", 1) < 0 && errno == EINTR) {
    }
    return NULL;
}
static void start_worker(struct runtime *r, struct request *request)
{
    struct worker *w = allocate(sizeof(*w));
    memset(w, 0, sizeof(*w));
    atomic_init(&w->cancel, 0);
    w->request = *request;
    free(request);
    w->notify_fd = r->notifications[1];
    if (pthread_create(&w->thread, NULL, collect, w)) {
        free(w->request.cwd);
        free(w);
        r->failed = 1;
        return;
    }
    r->active = w;
}
static void record_received(struct runtime *r, struct worker *w)
{
    if (r->trace.fd >= 0 && r->trace.buffered && !w->request.received_recorded) {
        wsh_runtime_trace_record(
            &r->trace, wsh_runtime_trace_event("refresh-received", 1, w->request.generation),
            w->request.received_us);
        w->request.received_recorded = 1;
    }
}
static void record_worker(struct runtime *r, struct worker *w, const char *event)
{
    if (r->trace.fd < 0)
        return;
    record_received(r, w);
    yyjson_mut_doc *d = wsh_runtime_trace_event(event, 1, w->request.generation);
    uint_field(d, "duration_us", w->elapsed_ns / 1000);
    uint_field(d, "repository_discovery_us", w->git.discovery_ns / 1000);
    if (w->git.child_processes)
        uint_field(d, "git_process_us", w->git.process_ns / 1000);
    else
        string_field(d, "git_process_us", NULL);
    if (w->git.parsing_ns)
        uint_field(d, "parse_duration_us", w->git.parsing_ns / 1000);
    else
        string_field(d, "parse_duration_us", NULL);
    uint_field(d, "child_processes", w->git.child_processes);
    wsh_runtime_trace_record(&r->trace, d, wsh_runtime_trace_time(&r->trace));
}
static void snapshot(struct runtime *r, struct worker *w)
{
    const struct request *q = &w->request;
    const struct wsh_git_result *g = &w->git;
    if (q->reset)
        wsh_renderer_reset(&r->renderer);
    char *left, *right;
    uint64_t start = clock_ns(CLOCK_MONOTONIC);
    wsh_render(&r->renderer, q->cwd, g, q->status, q->has_duration, q->duration, q->privileged,
               &left, &right);
    uint64_t render_ns = clock_ns(CLOCK_MONOTONIC) - start;
    int changed = !r->last_left || strcmp(r->last_left, left) || strcmp(r->last_right, right);
    start = clock_ns(CLOCK_MONOTONIC);
    yyjson_mut_doc *d = message("snapshot"), *s = object();
    uint_field(d, "id", q->id);
    uint_field(d, "generation", q->generation);
    char *encoded = hex(left);
    string_field(d, "prompt_hex", encoded);
    free(encoded);
    encoded = hex(right);
    string_field(d, "rprompt_hex", encoded);
    free(encoded);
    uint_field(s, "schema_version", 1);
    uint_field(s, "generation", q->generation);
    encoded = hex(q->cwd);
    string_field(s, "cwd_hex", encoded);
    free(encoded);
    encoded = g->root ? hex(g->root) : NULL;
    string_field(s, "root_hex", encoded);
    free(encoded);
    bool_field(s, "found", g->found);
    string_field(s, "branch", g->branch);
    string_field(s, "detached_sha", g->detached_sha);
    string_field(s, "exact_tag", g->exact_tag);
    bool_field(s, "staged", g->staged);
    bool_field(s, "modified", g->modified);
    bool_field(s, "untracked", g->untracked);
    uint_field(s, "ahead", g->ahead);
    uint_field(s, "behind", g->behind);
    bool_field(s, "worktree", g->worktree);
    const char *operations[] = {NULL, "rebase", "merge", "cherry-pick", "revert", "bisect"};
    string_field(s, "operation", operations[g->operation]);
    yyjson_mut_val *value = yyjson_mut_val_mut_copy(d, yyjson_mut_doc_get_root(s));
    if (!value || !yyjson_mut_obj_add_val(d, yyjson_mut_doc_get_root(d), "snapshot", value))
        abort();
    yyjson_mut_doc_free(s);
    response(r, d);
    uint64_t write_ns = clock_ns(CLOCK_MONOTONIC) - start;
    if (r->trace.fd >= 0) {
        record_received(r, w);
        d = wsh_runtime_trace_event("snapshot-published", 1, q->generation);
        uint_field(d, "rendered_bytes", strlen(left) + strlen(right));
        uint_field(d, "render_duration_us", render_ns / 1000);
        uint_field(d, "response_write_duration_us", write_ns / 1000);
        bool_field(d, "prompt_changed", changed);
        string_field(d, "repaint_cause", changed ? "git-snapshot" : NULL);
        wsh_runtime_trace_record(&r->trace, d, wsh_runtime_trace_time(&r->trace));
    }
    free(r->last_left);
    free(r->last_right);
    r->last_left = left;
    r->last_right = right;
}
static void finish_worker(struct runtime *r)
{
    struct worker *w = r->active;
    if (!w)
        return;
    pthread_join(w->thread, NULL);
    r->active = NULL;
    if (w->git.cancelled || w->request.generation != r->latest ||
        w->request.generation <= r->cancelled)
        record_worker(r, w, "worker-cancelled");
    else if (w->git.error) {
        record_worker(r, w, "worker-failed");
        reply(r, "error", 1, w->request.id, w->git.error);
    } else {
        snapshot(r, w);
        record_worker(r, w, "worker-completed");
    }
    free(w->request.cwd);
    wsh_git_free(&w->git);
    free(w);
    if (r->pending && !r->failed && !terminating) {
        struct request *next = r->pending;
        r->pending = NULL;
        start_worker(r, next);
    }
}
static void stop_worker(struct runtime *r)
{
    request_free(r->pending);
    r->pending = NULL;
    if (!r->active)
        return;
    struct worker *w = r->active;
    atomic_store_explicit(&w->cancel, 1, memory_order_release);
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += 2;
    deadline.tv_nsec += 500000000;
    if (deadline.tv_nsec >= 1000000000) {
        deadline.tv_sec++;
        deadline.tv_nsec -= 1000000000;
    }
    int result;
    do
        result = pthread_timedjoin_np(w->thread, NULL, &deadline);
    while (result == EINTR);
    if (result) {
        fprintf(stderr, "error: Git worker did not stop within 2.5 seconds\n");
        _Exit(1);
    }
    free(w->request.cwd);
    wsh_git_free(&w->git);
    free(w);
    r->active = NULL;
}
static int equals(yyjson_val *v, const char *text)
{
    return yyjson_is_str(v) && yyjson_get_len(v) == strlen(text) &&
           !memcmp(yyjson_get_str(v), text, strlen(text));
}
static int digit(unsigned char ch)
{
    return ch >= '0' && ch <= '9'   ? ch - '0'
           : ch >= 'a' && ch <= 'f' ? ch - 'a' + 10
           : ch >= 'A' && ch <= 'F' ? ch - 'A' + 10
                                    : -1;
}
static char *decode(yyjson_val *v, const char **error)
{
    size_t n = yyjson_get_len(v);
    const unsigned char *s = (const unsigned char *)yyjson_get_str(v);
    if (n > 8192 || n % 2) {
        *error = "cwd_hex is malformed or too long";
        return NULL;
    }
    char *out = allocate(n / 2 + 1);
    for (size_t i = 0; i < n / 2; ++i) {
        int a = s[2 * i] == '+' ? 0 : digit(s[2 * i]), b = digit(s[2 * i + 1]);
        if (a < 0 || b < 0) {
            *error = "cwd_hex is malformed";
            free(out);
            return NULL;
        }
        out[i] = (char)(a * 16 + b);
        if (!out[i]) {
            *error = "cwd contains a NUL byte";
            free(out);
            return NULL;
        }
    }
    out[n / 2] = 0;
    if (*out != '/') {
        *error = "cwd must be an absolute path";
        free(out);
        return NULL;
    }
    return out;
}
static void request_line(struct runtime *r, const char *line, size_t length)
{
    yyjson_doc *doc = yyjson_read(line, length, 0);
    yyjson_val *root = doc ? yyjson_doc_get_root(doc) : NULL;
    const char *keys[] = {"type",        "version",     "id",         "generation",     "cwd_hex",
                          "exit_status", "duration_ms", "privileged", "reset_transient"};
    yyjson_val *fields[9] = {0};
    unsigned mask = 0;
    size_t i, max;
    yyjson_val *key, *value;
    if (!yyjson_is_obj(root))
        goto malformed;
    yyjson_obj_foreach(root, i, max, key, value)
    {
        unsigned index;
        for (index = 0; index < 9; ++index)
            if (equals(key, keys[index]))
                break;
        if (index == 9 || fields[index])
            goto malformed;
        fields[index] = value;
        mask |= 1u << index;
    }
    int type = equals(fields[0], "ping")       ? 1
               : equals(fields[0], "refresh")  ? 2
               : equals(fields[0], "cancel")   ? 3
               : equals(fields[0], "shutdown") ? 4
                                               : 0;
    unsigned expected = type == 2 ? 511 : type == 3 ? 15 : 7;
    if (!type || (type == 2 ? (mask | 64) != expected : mask != expected))
        goto malformed;
    if (!yyjson_is_uint(fields[1]) || yyjson_get_uint(fields[1]) > UINT32_MAX ||
        !yyjson_is_uint(fields[2]))
        goto malformed;
    if ((type == 2 || type == 3) && !yyjson_is_uint(fields[3]))
        goto malformed;
    if (type == 2) {
        if (!yyjson_is_str(fields[4]) || !yyjson_is_int(fields[5]) || !yyjson_is_bool(fields[7]) ||
            !yyjson_is_bool(fields[8]))
            goto malformed;
        if (yyjson_is_uint(fields[5]) ? yyjson_get_uint(fields[5]) > INT32_MAX
                                      : yyjson_get_sint(fields[5]) < INT32_MIN)
            goto malformed;
        if (fields[6] && !yyjson_is_null(fields[6]) && !yyjson_is_uint(fields[6]))
            goto malformed;
    }
    uint64_t id = yyjson_get_uint(fields[2]), generation = yyjson_get_uint(fields[3]);
    if (yyjson_get_uint(fields[1]) != 1) {
        reply(r, "error", 1, id, "unsupported protocol version");
        goto done;
    }
    if (type == 1)
        reply(r, "pong", 1, id, NULL);
    else if (type == 4) {
        trace_event(r, "shutdown-requested", 0, 0);
        stop_worker(r);
        reply(r, "stopping", 1, id, NULL);
        trace_event(r, "runtime-stopping", 0, 0);
        r->stopping = 1;
    } else if (type == 3) {
        if (generation > r->cancelled)
            r->cancelled = generation;
        if (r->active && r->active->request.generation <= generation)
            atomic_store_explicit(&r->active->cancel, 1, memory_order_release);
        request_free(r->pending);
        r->pending = NULL;
        trace_event(r, "generation-cancelled", 1, generation);
        reply(r, "cancelled", 1, id, NULL);
    } else {
        const char *error = NULL;
        char *cwd = decode(fields[4], &error);
        if (!cwd) {
            reply(r, "error", 1, id, error);
            goto done;
        }
        if (generation <= r->latest) {
            free(cwd);
            reply(r, "error", 1, id, "refresh generation is stale");
            goto done;
        }
        r->latest = generation;
        struct request *q = allocate(sizeof(*q));
        memset(q, 0, sizeof(*q));
        q->id = id;
        q->generation = generation;
        q->cwd = cwd;
        q->status = (int)yyjson_get_sint(fields[5]);
        q->has_duration = yyjson_is_uint(fields[6]);
        q->duration = yyjson_get_uint(fields[6]);
        q->privileged = yyjson_get_bool(fields[7]);
        q->reset = yyjson_get_bool(fields[8]);
        if (r->trace.buffered)
            q->received_us = wsh_runtime_trace_time(&r->trace);
        else
            trace_event(r, "refresh-received", 1, generation);
        if (r->active) {
            atomic_store_explicit(&r->active->cancel, 1, memory_order_release);
            request_free(r->pending);
            r->pending = q;
            trace_event(r, "worker-cancel-requested", 1, r->active->request.generation);
        } else
            start_worker(r, q);
    }
    goto done;
malformed:
    reply(r, "error", 0, 0, "malformed request");
done:
    if (doc)
        yyjson_doc_free(doc);
}
static int serve(const struct wsh_theme *theme)
{
    struct runtime r = {0};
    r.notifications[0] = r.notifications[1] = -1;
    if (wsh_runtime_trace_open(&r.trace)) {
        fprintf(stderr, "error: could not open a bounded regular trace file\n");
        return 1;
    }
    wsh_renderer_init(&r.renderer, theme);
    if (pipe2(r.notifications, O_CLOEXEC | O_NONBLOCK)) {
        r.failed = 1;
        goto done;
    }
    yyjson_mut_doc *ready = message("ready");
    const char *id = wsh_theme_get(theme, "id").u.s;
    string_field(ready, "theme", id);
    response(&r, ready);
    if (r.trace.fd >= 0) {
        yyjson_mut_doc *d = wsh_runtime_trace_event("runtime-ready", 0, 0);
        string_field(d, "theme", id);
        wsh_runtime_trace_record(&r.trace, d, wsh_runtime_trace_time(&r.trace));
    }
    char line[65536], block[4096];
    size_t used = 0;
    while (!r.failed && !r.stopping && !terminating) {
        if (!r.active)
            wsh_runtime_trace_flush(&r.trace);
        if (r.trace.failed) {
            r.failed = 1;
            break;
        }
        struct pollfd descriptors[] = {{STDIN_FILENO, POLLIN, 0}, {r.notifications[0], POLLIN, 0}};
        int count = poll(descriptors, 2, -1);
        if (count < 0) {
            if (errno == EINTR)
                continue;
            r.failed = 1;
            break;
        }
        if (descriptors[1].revents & POLLIN) {
            char token;
            if (read(r.notifications[0], &token, 1) == 1)
                finish_worker(&r);
        }
        if (descriptors[0].revents & (POLLIN | POLLHUP)) {
            ssize_t n = read(STDIN_FILENO, block, sizeof(block));
            if (n < 0) {
                if (errno == EINTR)
                    continue;
                r.failed = 1;
                break;
            }
            if (!n) {
                if (used)
                    request_line(&r, line, used);
                break;
            }
            for (ssize_t i = 0; i < n && !r.failed && !r.stopping; ++i) {
                if (used == sizeof(line)) {
                    fprintf(stderr, "error: protocol line exceeds 65536 bytes\n");
                    r.failed = 1;
                    break;
                }
                line[used++] = block[i];
                if (block[i] == '\n') {
                    request_line(&r, line, used);
                    used = 0;
                }
            }
        }
        if (descriptors[0].revents & (POLLERR | POLLNVAL))
            r.failed = 1;
    }
done:
    stop_worker(&r);
    wsh_runtime_trace_close(&r.trace);
    if (r.trace.failed)
        r.failed = 1;
    for (int i = 0; i < 2; ++i)
        if (r.notifications[i] >= 0)
            close(r.notifications[i]);
    free(r.last_left);
    free(r.last_right);
    wsh_renderer_free(&r.renderer);
    return r.failed ? 1 : 0;
}
int main(int argc, char **argv)
{
    struct sigaction action = {0};
    action.sa_handler = terminate;
    sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGHUP, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    signal(SIGPIPE, SIG_IGN);
    pid_t parent = getppid();
    if (prctl(PR_SET_PDEATHSIG, SIGTERM) || getppid() != parent)
        return 1;
    int validate = argc == 3 && !strcmp(argv[1], "validate-theme"),
        serving = argc == 4 && !strcmp(argv[1], "serve") && !strcmp(argv[2], "--theme");
    if (!validate && !serving) {
        fprintf(stderr, "usage:\n  wsh-runtime validate-theme <theme.toml>\n  wsh-runtime serve "
                        "--theme <theme.toml>\n");
        return 1;
    }
    if (serving && setpgid(0, 0)) {
        perror("could not isolate runtime process group");
        return 1;
    }
    struct wsh_theme theme;
    char error[512];
    if (wsh_theme_load(argv[argc - 1], &theme, error, sizeof(error))) {
        fprintf(stderr, "error: %s\n", error);
        return 1;
    }
    int result = 0;
    if (validate)
        puts(wsh_theme_get(&theme, "id").u.s);
    else
        result = serve(&theme);
    wsh_theme_free(&theme);
    return result;
}
