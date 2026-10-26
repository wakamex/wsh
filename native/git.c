#define _GNU_SOURCE
#include "git.h"
#include "portable.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <zlib.h>

#define TEXT_LIMIT (64 * 1024)
#define OUTPUT_LIMIT (4 * 1024 * 1024)
#define TAG_LIMIT (1024 * 1024)
#define TIMEOUT_NS UINT64_C(2000000000)
/* A status this slow is usually re-hashing files whose stat data the index never saved. */
#define REFRESH_NS UINT64_C(100000000)
#define REFRESHED_LIMIT 16

struct context {
    struct wsh_git_result *out;
    int (*cancel)(void *);
    void *user;
    uint64_t deadline;
    int timed_out;
};
struct identity { char *root, *git_dir, *common, *branch, *oid; };

/* Match Rust allocation failure: terminate the optional helper instead of publishing partial state. */
static void *allocate(size_t size)
{
    void *value = malloc(size);
    if (!value) abort();
    return value;
}
static void *resize(void *old, size_t size)
{
    void *value = realloc(old, size);
    if (!value) abort();
    return value;
}
static void *allocate_zero(size_t count, size_t size)
{
    void *value = calloc(count, size);
    if (!value) abort();
    return value;
}
static char *copy_n(const char *text, size_t length)
{
    char *value = allocate(length + 1);
    memcpy(value, text, length); value[length] = 0; return value;
}
static char *copy(const char *text) { return copy_n(text, strlen(text)); }
static uint64_t now_ns(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (uint64_t)now.tv_sec * UINT64_C(1000000000) + (uint64_t)now.tv_nsec;
}
static void fail(struct context *ctx, const char *message)
{
    if (!ctx->out->error) ctx->out->error = copy(message);
}
static int stopped(struct context *ctx)
{
    if (ctx->cancel && ctx->cancel(ctx->user)) {
        ctx->out->cancelled = 1;
        fail(ctx, "Git request cancelled");
        return 1;
    }
    if (now_ns() >= ctx->deadline) {
        ctx->timed_out = 1;
        fail(ctx, "Git request timed out");
        return 1;
    }
    return 0;
}
static char *join(const char *parent, const char *name)
{
    size_t a = strlen(parent), b = strlen(name);
    char *path;
    if (a > TEXT_LIMIT || b > TEXT_LIMIT || a + b + 2 > TEXT_LIMIT) return NULL;
    path = allocate(a + b + 2);
    if (path) { memcpy(path, parent, a); path[a] = '/'; memcpy(path + a + 1, name, b + 1); }
    return path;
}
/* Return a valid width or the negative length of an invalid prefix, like Rust UTF-8 errors. */
static int utf8_width(const unsigned char *text, size_t length)
{
    unsigned char first = text[0];
    unsigned width, i;
    if (first < 0x80) return 1;
    if (first >= 0xc2 && first <= 0xdf) width = 2;
    else if (first >= 0xe0 && first <= 0xef) width = 3;
    else if (first >= 0xf0 && first <= 0xf4) width = 4;
    else return -1;
    for (i = 1; i < width; ++i) {
        if (i >= length || (text[i] & 0xc0) != 0x80) return -(int)i;
        if (i == 1 && ((first == 0xe0 && text[i] < 0xa0) || (first == 0xed && text[i] >= 0xa0) ||
                       (first == 0xf0 && text[i] < 0x90) || (first == 0xf4 && text[i] >= 0x90))) return -1;
    }
    return (int)width;
}
static int utf8(const unsigned char *text, size_t length)
{
    size_t i = 0;
    while (i < length) {
        int width = utf8_width(text + i, length - i);
        if (width < 0) return 0;
        i += (size_t)width;
    }
    return 1;
}
static char *lossy(const char *text)
{
    size_t length = strlen(text), i = 0, used = 0;
    char *result = allocate(length * 3 + 1);
    if (!result) return NULL;
    while (i < length) {
        int width = utf8_width((const unsigned char *)text + i, length - i);
        if (width > 0) { memcpy(result + used, text + i, (size_t)width); used += (size_t)width; i += (size_t)width; }
        else { memcpy(result + used, "\xef\xbf\xbd", 3); used += 3; i += (size_t)-width; }
    }
    result[used] = 0; return result;
}
static size_t whitespace(const unsigned char *p, size_t length)
{
    if (!length) return 0;
    if (*p == ' ' || (*p >= '\t' && *p <= '\r')) return 1;
    if (length >= 2 && p[0] == 0xc2 && (p[1] == 0x85 || p[1] == 0xa0)) return 2;
    if (length >= 3 && ((p[0] == 0xe1 && p[1] == 0x9a && p[2] == 0x80) ||
        (p[0] == 0xe2 && p[1] == 0x80 && ((p[2] >= 0x80 && p[2] <= 0x8a) || p[2] == 0xa8 || p[2] == 0xa9 || p[2] == 0xaf)) ||
        (p[0] == 0xe2 && p[1] == 0x81 && p[2] == 0x9f) || (p[0] == 0xe3 && p[1] == 0x80 && p[2] == 0x80))) return 3;
    return 0;
}
static void trim(char *text)
{
    size_t length = strlen(text), start = 0, i, end, width;
    while ((width = whitespace((unsigned char *)text + start, length - start))) start += width;
    end = start;
    for (i = start; i < length;) {
        width = whitespace((unsigned char *)text + i, length - i);
        if (width) i += width;
        else { i += (size_t)utf8_width((unsigned char *)text + i, length - i); end = i; }
    }
    memmove(text, text + start, end - start); text[end - start] = 0;
}
static int regular_fd(const char *path)
{
    int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    struct stat st;
    if (fd >= 0 && (fstat(fd, &st) || !S_ISREG(st.st_mode))) { close(fd); return -1; }
    return fd;
}
static char *text_file(const char *path)
{
    int fd;
    char *text;
    size_t used = 0;
    ssize_t count;
    if (!path || (fd = regular_fd(path)) < 0) return NULL;
    text = allocate(TEXT_LIMIT + 1);
    if (!text) { close(fd); return NULL; }
    while (used < TEXT_LIMIT) {
        count = read(fd, text + used, TEXT_LIMIT - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) { free(text); close(fd); return NULL; }
        if (!count) break;
        used += (size_t)count;
    }
    close(fd);
    if (used == TEXT_LIMIT || memchr(text, 0, used) || !utf8((unsigned char *)text, used)) { free(text); return NULL; }
    text[used] = 0; trim(text); return text;
}
static char *read_in(const char *parent, const char *name)
{
    char *path = join(parent, name), *value = text_file(path);
    free(path); return value;
}
static int kind(const char *path, int directory)
{
    struct stat st;
    return path && !stat(path, &st) && (!directory || S_ISDIR(st.st_mode));
}
static int exists_in(const char *directory, const char *name, int is_directory)
{
    char *path = join(directory, name);
    int yes = kind(path, is_directory);
    free(path); return yes;
}
static FILE *packed_file(const char *directory)
{
    char *path = join(directory, "packed-refs");
    int fd = path ? regular_fd(path) : -1;
    FILE *file;
    free(path);
    if (fd < 0) return NULL;
    file = fdopen(fd, "r");
    if (!file) close(fd);
    return file;
}
static int next_line(FILE *file, char *line, struct context *ctx)
{
    size_t length = 0;
    int byte;
    if (stopped(ctx)) return 0;
    while ((byte = getc_unlocked(file)) != EOF && byte != '\n') {
        if (length == TEXT_LIMIT || !byte) return -1;
        line[length++] = (char)byte;
    }
    if (!length && byte == EOF) return 0;
    if (!utf8((unsigned char *)line, length)) return -1;
    if (length && line[length - 1] == '\r') --length;
    line[length] = 0; return 1;
}
static char *resolve_ref(struct identity *id, const char *reference, struct context *ctx)
{
    char *value = read_in(id->git_dir, reference), *separator;
    char line[TEXT_LIMIT + 1];
    FILE *file;
    int record;
    if (!value) value = read_in(id->common, reference);
    if (value) return value;
    file = packed_file(id->common);
    if (!file) return NULL;
    while ((record = next_line(file, line, ctx)) > 0) {
        separator = strchr(line, ' ');
        if (!value && separator && !strcmp(separator + 1, reference)) {
            *separator = 0; value = copy(line);
        }
    }
    /* Rust read_to_string ignores the entire file on invalid UTF-8. */
    if (record < 0 || ferror(file)) { free(value); value = NULL; }
    fclose(file); return value;
}
static void free_identity(struct identity *id)
{
    free(id->root); free(id->git_dir); free(id->common); free(id->branch); free(id->oid);
    memset(id, 0, sizeof(*id));
}
static int discover(const char *cwd, struct identity *id, struct context *ctx)
{
    char *candidate = realpath(cwd, NULL), *dot, *value, *slash, *head;
    struct stat st;
    if (!candidate) return 0;
    for (;;) {
        if (stopped(ctx)) break;
        dot = join(candidate, ".git");
        if (dot && !stat(dot, &st) && (S_ISDIR(st.st_mode) || S_ISREG(st.st_mode))) {
            if (S_ISDIR(st.st_mode)) id->git_dir = dot;
            else {
                value = text_file(dot); free(dot);
                if (!value || strncmp(value, "gitdir: ", 8)) { free(value); break; }
                id->git_dir = value[8] == '/' ? copy(value + 8) : join(candidate, value + 8);
                free(value);
            }
            if (!id->git_dir) break;
            value = read_in(id->git_dir, "commondir");
            id->common = value ? (value[0] == '/' ? copy(value) : join(id->git_dir, value)) : copy(id->git_dir);
            free(value);
            if (!id->common || !(head = read_in(id->git_dir, "HEAD"))) break;
            if (!strncmp(head, "ref: ", 5)) {
                if (!strncmp(head + 5, "refs/heads/", 11)) id->branch = copy(head + 16);
                id->oid = resolve_ref(id, head + 5, ctx);
            } else id->oid = copy(head);
            free(head); id->root = candidate; return 1;
        }
        free(dot);
        if (!strcmp(candidate, "/")) break;
        slash = strrchr(candidate, '/');
        if (!slash) break;
        if (slash == candidate) slash[1] = 0;
        else *slash = 0;
    }
    free(candidate); free_identity(id); return 0;
}
static int tag_points_to(const char *directory, const char *oid, const char *head, struct context *ctx)
{
    char relative[160], *path;
    unsigned char compressed[8192], decoded[8192];
    unsigned char *object;
    size_t used = 0, length = strlen(oid), i;
    int fd, status = Z_OK, found = 0;
    ssize_t count;
    z_stream stream = {0};
    if (length < 3 || length > 128) return 0;
    for (i = 0; i < length; ++i) if (!strchr("0123456789abcdefABCDEF", oid[i])) return 0;
    snprintf(relative, sizeof(relative), "objects/%.2s/%s", oid, oid + 2);
    path = join(directory, relative); fd = path ? regular_fd(path) : -1; free(path);
    if (fd < 0) return 0;
    object = allocate(TAG_LIMIT + 1);
    if (!object || inflateInit(&stream) != Z_OK) { free(object); close(fd); return 0; }
    while (status == Z_OK && used < TAG_LIMIT && !stopped(ctx)) {
        if (!stream.avail_in) {
            do { count = read(fd, compressed, sizeof(compressed)); } while (count < 0 && errno == EINTR);
            if (count <= 0) break;
            stream.next_in = compressed; stream.avail_in = (uInt)count;
        }
        stream.next_out = decoded; stream.avail_out = sizeof(decoded);
        status = inflate(&stream, Z_NO_FLUSH);
        length = sizeof(decoded) - stream.avail_out;
        if (length > TAG_LIMIT - used) length = TAG_LIMIT - used;
        memcpy(object + used, decoded, length); used += length;
    }
    inflateEnd(&stream); close(fd); object[used] = 0;
    unsigned char *header = memchr(object, 0, used);
    if ((status == Z_OK || status == Z_STREAM_END) && header && used >= 4 && !memcmp(object, "tag ", 4) && utf8(header + 1, used - (size_t)(header + 1 - object))) {
        size_t position = (size_t)(header + 1 - object), end;
        while (position < used) {
            for (end = position; end < used && object[end] != '\n'; ++end) {}
            size_t line_length = end - position;
            if (end < used && line_length && object[end - 1] == '\r') --line_length;
            if (line_length >= 7 && !memcmp(object + position, "object ", 7)) {
                found = line_length - 7 == strlen(head) && !memcmp(object + position + 7, head, line_length - 7);
                break;
            }
            position = end + (end < used);
        }
    }
    free(object); return found;
}
static void choose_tag(char **best, const char *name)
{
    char *copy = lossy(name);
    if (copy && (!*best || strcmp(copy, *best) < 0)) { free(*best); *best = copy; }
    else free(copy);
}
static void loose_tags(const char *common, const char *root, const char *directory,
                       const char *head, char **best, struct context *ctx)
{
    DIR *dir = opendir(directory);
    struct dirent *entry;
    char *path, *oid;
    if (!dir) return;
    while (!stopped(ctx) && (entry = readdir(dir))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        path = join(directory, entry->d_name);
        if (!path) continue;
        if (kind(path, 1)) loose_tags(common, root, path, head, best, ctx);
        else {
            oid = text_file(path);
            if (oid && (!strcmp(oid, head) || tag_points_to(common, oid, head, ctx))) choose_tag(best, path + strlen(root) + 1);
            free(oid);
        }
        free(path);
    }
    closedir(dir);
}
static char *exact_tag(const char *common, const char *head, struct context *ctx)
{
    char *root = join(common, "refs/tags"), *best = NULL, *packed_best = NULL, *pending = NULL, *separator;
    char line[TEXT_LIMIT + 1];
    FILE *file;
    int record;
    if (root) loose_tags(common, root, root, head, &best, ctx);
    free(root);
    file = packed_file(common);
    if (!file) return best;
    while ((record = next_line(file, line, ctx)) > 0) {
        if (*line == '^') {
            if (pending && !strcmp(line + 1, head)) choose_tag(&packed_best, pending);
            free(pending); pending = NULL;
        } else if ((separator = strchr(line, ' ')) && !strncmp(separator + 1, "refs/tags/", 10)) {
            *separator = 0;
            if (!strcmp(line, head)) choose_tag(&packed_best, separator + 11);
            free(pending); pending = copy(separator + 11);
        }
    }
    if (!record && !ferror(file) && packed_best) choose_tag(&best, packed_best);
    fclose(file); free(packed_best); free(pending); return best;
}
static uint64_t counter(const unsigned char *text, size_t length, char sign)
{
    uint64_t result = 0;
    size_t i = 1;
    if (length < 2 || text[0] != (unsigned char)sign) return 0;
    if (text[i] == '+') ++i;
    if (i == length) return 0;
    for (; i < length; ++i) {
        if (text[i] < '0' || text[i] > '9') return 0;
        unsigned digit = text[i] - '0';
        if (result > ((uint64_t)INT64_MAX - digit) / 10) return 0;
        result = result * 10 + digit;
    }
    return result;
}
static int parse_status(const unsigned char *text, size_t length, struct wsh_git_result *out)
{
    size_t position = 0, end, field, next, width;
    if (!utf8(text, length)) return -1;
    while (position < length) {
        for (end = position; end < length && text[end] != '\n'; ++end) {}
        if (end - position >= 12 && !memcmp(text + position, "# branch.ab ", 12)) {
            field = position + 12;
            while ((width = whitespace(text + field, end - field))) field += width;
            for (next = field; next < end && !whitespace(text + next, end - next); ++next) {}
            out->ahead = counter(text + field, next - field, '+'); field = next;
            while ((width = whitespace(text + field, end - field))) field += width;
            for (next = field; next < end && !whitespace(text + next, end - next); ++next) {}
            out->behind = counter(text + field, next - field, '-');
        } else if (end - position >= 2 && text[position + 1] == ' ') {
            if (text[position] == '1' || text[position] == '2') {
                field = position + 2;
                while ((width = whitespace(text + field, end - field))) field += width;
                if (field < end) out->staged |= text[field] != '.';
                if (field + 1 < end && !whitespace(text + field + 1, end - field - 1)) out->modified |= text[field + 1] != '.';
            } else if (text[position] == 'u') out->staged = out->modified = 1;
            else if (text[position] == '?') out->untracked = 1;
        }
        position = end + (end < length);
    }
    return 0;
}
static char *command_path(const char *cwd, const char *git)
{
    const char *search = getenv("PATH"), *end;
    char *directory, *path, *relative;
    if (strchr(git, '/')) return git[0] == '/' ? copy(git) : join(cwd, git);
    if (!search) search = "/bin:/usr/bin";
    for (;;) {
        end = strchr(search, ':');
        directory = copy_n(search, end ? (size_t)(end - search) : strlen(search));
        if (!directory) return NULL;
        relative = *directory == '/' ? copy(directory) : (*directory ? join(cwd, directory) : copy(cwd));
        path = relative ? join(relative, git) : NULL;
        free(relative); free(directory);
        if (path && !access(path, X_OK)) return path;
        free(path);
        if (!end) return NULL;
        search = end + 1;
    }
}
static int private_fd(int fd)
{
    int copy;
    if (fd < 0 || fd >= 3) return fd;
    copy = fcntl(fd, F_DUPFD_CLOEXEC, 3); close(fd); return copy;
}
static int pipe_pair(int pair[2])
{
    if (wsh_pipe(pair, 0)) return -1;
    pair[0] = private_fd(pair[0]); pair[1] = private_fd(pair[1]);
    if (pair[0] < 0 || pair[1] < 0 || fcntl(pair[0], F_SETFL, O_NONBLOCK) < 0) return -1;
    return 0;
}
static void kill_group(pid_t child)
{
    if (kill(-child, SIGKILL)) (void)kill(child, SIGKILL);
}
static void reap(pid_t child)
{
    while (waitpid(child, NULL, 0) < 0 && errno == EINTR) {}
}
static unsigned char *git_output(const char *cwd, const char *git, size_t *length, struct context *ctx)
{
    extern char **environ;
    char *path = command_path(cwd, git), **environment = NULL;
    char *arguments[] = { (char *)git, "status", "--porcelain=v2", "--branch", "--untracked-files=normal", "--ignore-submodules=dirty", NULL };
    size_t env_count = 0, env_used = 0, i, used = 0, capacity = 8192, error_used = 0;
    unsigned char *output = NULL, error_bytes[sizeof(int)];
    int pipefd[2] = {-1, -1}, errorfd[2] = {-1, -1}, nullfd = -1;
    int child_error = 0, child_status = 0, reaped = 0, eof = 0, exec_done = 0;
    pid_t parent = getpid(), child = -1, waited;
    ssize_t count;
    struct timespec pause = {0, 100000};
    uint64_t started = now_ns();
    if (!path) { fail(ctx, "could not locate Git status executable"); goto done; }
    while (environ[env_count]) ++env_count;
    environment = allocate_zero(env_count + 2, sizeof(char *)); output = allocate(capacity);
    if (!environment || !output) { fail(ctx, "could not allocate Git collector"); goto done; }
    for (i = 0; i < env_count; ++i)
        if (strncmp(environ[i], "GIT_OPTIONAL_LOCKS=", 19)) environment[env_used++] = environ[i];
    environment[env_used] = "GIT_OPTIONAL_LOCKS=0";
    nullfd = private_fd(open("/dev/null", O_WRONLY | O_CLOEXEC));
    if (nullfd < 0 || pipe_pair(pipefd) || pipe_pair(errorfd)) { fail(ctx, "could not open Git process descriptors"); goto done; }
    child = fork();
    if (child < 0) { fail(ctx, "could not fork Git status"); goto done; }
    if (!child) {
        /* Only async-signal-safe operations after a fork from the runtime worker. */
        if (setpgid(0, 0) || wsh_parent_death_signal(SIGKILL) || getppid() != parent || chdir(cwd) ||
            dup2(pipefd[1], STDOUT_FILENO) < 0 || dup2(nullfd, STDERR_FILENO) < 0) child_error = errno ? errno : ECHILD;
        close(pipefd[0]); close(pipefd[1]); close(errorfd[0]); close(nullfd);
        if (!child_error) { execve(path, arguments, environment); child_error = errno; }
        do { count = write(errorfd[1], &child_error, sizeof(child_error)); } while (count < 0 && errno == EINTR);
        _exit(127);
    }
    close(pipefd[1]); pipefd[1] = -1; close(errorfd[1]); errorfd[1] = -1;
    for (;;) {
        int progress = 0;
        if (stopped(ctx)) goto done;
        if (!exec_done) {
            count = read(errorfd[0], error_bytes + error_used, sizeof(int) - error_used);
            if (count == 0) { exec_done = 1; ctx->out->child_processes = 1; }
            else if (count > 0) {
                error_used += (size_t)count;
                if (error_used == sizeof(int)) {
                    char message[256]; memcpy(&child_error, error_bytes, sizeof(int));
                    snprintf(message, sizeof(message), "could not start Git status: %s", strerror(child_error));
                    fail(ctx, message); goto done;
                }
            } else if (errno != EAGAIN && errno != EINTR) { fail(ctx, "could not read Git exec status"); goto done; }
        }
        if (!eof) {
            if (used == capacity) {
                size_t next = capacity * 2;
                if (next > OUTPUT_LIMIT + 1) next = OUTPUT_LIMIT + 1;
                unsigned char *grown = resize(output, next);
                if (!grown) { fail(ctx, "could not allocate Git output"); goto done; }
                output = grown; capacity = next;
            }
            count = read(pipefd[0], output + used, capacity - used);
            if (count == 0) eof = 1;
            else if (count > 0) {
                used += (size_t)count; progress = 1;
                if (used > OUTPUT_LIMIT) { fail(ctx, "Git status exceeds 4194304 bytes"); goto done; }
            } else if (errno != EAGAIN && errno != EINTR) { fail(ctx, "could not read Git status"); goto done; }
        }
        if (!reaped) {
            waited = waitpid(child, &child_status, WNOHANG);
            if (waited == child) reaped = 1;
            else if (waited < 0 && errno != EINTR) { fail(ctx, "could not wait for Git status"); goto done; }
        }
        if (reaped && eof && exec_done) break;
        if (!progress) (void)nanosleep(&pause, NULL);
    }
    if (!WIFEXITED(child_status) || WEXITSTATUS(child_status)) {
        char message[128];
        snprintf(message, sizeof(message), "Git status exited with %s %d", WIFEXITED(child_status) ? "exit status:" : "signal:", WIFEXITED(child_status) ? WEXITSTATUS(child_status) : WTERMSIG(child_status));
        fail(ctx, message); goto done;
    }
    *length = used;
done:
    if (child > 0 && (ctx->out->error || ctx->out->cancelled || !reaped)) {
        kill_group(child); if (!reaped) reap(child);
    }
    for (i = 0; i < 2; ++i) { if (pipefd[i] >= 0) close(pipefd[i]); if (errorfd[i] >= 0) close(errorfd[i]); }
    if (nullfd >= 0) close(nullfd);
    free(path); free(environment);
    if (ctx->out->child_processes) ctx->out->process_ns = now_ns() - started;
    if (ctx->out->error || ctx->out->cancelled || child < 0 || !reaped) { free(output); return NULL; }
    return output;
}
/* Per repository: the index metadata when a refresh last started, whether a fast status has been
 * seen since, and when to try again. A slow status over an index unchanged since an attempt, with
 * nothing fast since, retries after a delay that doubles from 2 seconds to 5 minutes: the attempt
 * may not have helped (the status is slow for another reason) or may have failed. A refresh that
 * finds nothing to write takes no lock, so a retry costs only background hashing. */
static struct refresh_memo { char *git_dir; dev_t dev; ino_t ino; off_t size; struct timespec mtime; int fast; uint64_t retry_ns, delay_ns; } refreshed[REFRESHED_LIMIT];
static size_t refreshed_next;
static int same_file(const struct refresh_memo *memo, const struct stat *st)
{
    return memo->dev == st->st_dev && memo->ino == st->st_ino && memo->size == st->st_size &&
        memo->mtime.tv_sec == WSH_MTIME(*st).tv_sec && memo->mtime.tv_nsec == WSH_MTIME(*st).tv_nsec;
}
static struct refresh_memo *memo_for(const char *git_dir)
{
    size_t i;
    for (i = 0; i < REFRESHED_LIMIT; ++i)
        if (refreshed[i].git_dir && !strcmp(refreshed[i].git_dir, git_dir)) return &refreshed[i];
    return NULL;
}
static void note_fast_status(const char *git_dir)
{
    struct refresh_memo *memo = memo_for(git_dir);
    if (memo) memo->fast = 1;
}
/* Copy with plain system calls, as the refresh child must after a fork from a threaded process. */
static int copy_fd(int from, int to)
{
    char buffer[65536];
    ssize_t count, written, offset;
    for (;;) {
        count = read(from, buffer, sizeof(buffer));
        if (count == 0) return 0;
        if (count < 0) { if (errno == EINTR) continue; return -1; }
        for (offset = 0; offset < count; offset += written) {
            written = write(to, buffer + offset, (size_t)(count - offset));
            if (written < 0) { if (errno == EINTR) { written = 0; continue; } return -1; }
        }
    }
}
static int same_identity(const struct stat *a, const struct stat *b)
{
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino && a->st_size == b->st_size &&
        WSH_MTIME(*a).tv_sec == WSH_MTIME(*b).tv_sec && WSH_MTIME(*a).tv_nsec == WSH_MTIME(*b).tv_nsec;
}
/* WSH_GIT_REFRESH_LOG names a file that records each refresh decision and outcome, for diagnosing
 * repositories that stay stale. Writes use plain system calls, so the refresh child can call it. */
static void refresh_note(const char *log, const char *git_dir, const char *event)
{
    /* Wall-clock seconds and the writing process, formatted without stdio so the child can call it. */
    char stamp[48], *end = stamp + sizeof(stamp), *p = end;
    struct timespec now;
    long long value;
    int fd, digit;
    if (!log || !*log || (fd = open(log, O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, 0600)) < 0) return;
    if (clock_gettime(CLOCK_REALTIME, &now)) now.tv_sec = now.tv_nsec = 0;
    *--p = ' ';
    for (value = getpid(); p > stamp && (value || p == end - 1); value /= 10) *--p = (char)('0' + value % 10);
    *--p = ' ';
    for (digit = 0, value = now.tv_nsec / 1000000; digit < 3; ++digit, value /= 10) *--p = (char)('0' + value % 10);
    *--p = '.';
    for (value = now.tv_sec; p > stamp && (value || *p == '.'); value /= 10) *--p = (char)('0' + value % 10);
    if (write(fd, p, (size_t)(end - p)) < 0 || write(fd, git_dir, strlen(git_dir)) < 0 || write(fd, " ", 1) < 0 ||
        write(fd, event, strlen(event)) < 0 || write(fd, "\n", 1) < 0) {}
    close(fd);
}
/* GIT_OPTIONAL_LOCKS=0 keeps status from saving its refresh, so refresh once here instead, and
 * without holding index.lock while Git rehashes files: Git refreshes a private copy, and the copy
 * replaces the index under index.lock only if the index is unchanged, so the lock is held for one
 * file copy and a rename, and not at all when nothing was stale. Workaround: status with locks
 * allowed creates index.lock on every run even when it writes nothing. Remove this once a Git
 * release locks only when there is something to write:
 * https://lore.kernel.org/git/20261022184420.3648771-1-mcosma@gmail.com/ */
static void refresh_index(const char *cwd, const char *git, const char *git_dir)
{
    extern char **environ;
    char *index = join(git_dir, "index"), *lock = join(git_dir, "index.lock"), *path = command_path(cwd, git);
    char *copy_path = join(git_dir, "index.wsh-XXXXXX"), *index_variable = NULL, **environment = NULL;
    char *arguments[] = { (char *)git, "update-index", "-q", "--refresh", NULL };
    struct stat before, after, copied;
    struct refresh_memo *memo;
    size_t count = 0, i, used = 0;
    int nullfd = -1, source = -1, private_copy = -1;
    pid_t child;
    DIR *directory;
    const char *log = getenv("WSH_GIT_REFRESH_LOG");
    struct dirent *entry;
    if (!index || !lock || !path || !copy_path || getenv("GIT_INDEX_FILE")) goto done;
    if (!lstat(lock, &before) || errno != ENOENT) { refresh_note(log, git_dir, "skip lock-held"); goto done; }
    if (stat(index, &before) || before.st_size <= 0 || before.st_size > (off_t)256 * 1024 * 1024) goto done;
    memo = memo_for(git_dir);
    uint64_t now = now_ns(), delay = UINT64_C(2000000000);
    if (memo && same_file(memo, &before) && !memo->fast) {
        if (now < memo->retry_ns) { refresh_note(log, git_dir, "skip retry-later"); goto done; }
        delay = memo->delay_ns * 2 < UINT64_C(300000000000) ? memo->delay_ns * 2 : UINT64_C(300000000000);
    }
    if (!memo) {
        memo = &refreshed[refreshed_next];
        refreshed_next = (refreshed_next + 1) % REFRESHED_LIMIT;
        free(memo->git_dir);
        if (!(memo->git_dir = copy(git_dir))) goto done;
    }
    memo->dev = before.st_dev; memo->ino = before.st_ino; memo->size = before.st_size;
    memo->mtime = WSH_MTIME(before); memo->fast = 0;
    memo->delay_ns = delay; memo->retry_ns = now + delay;
    /* A split index refers to shared index files that a private copy would not keep consistent;
     * stale private copies left by an interrupted refresh are removed. */
    if (!(directory = opendir(git_dir))) goto done;
    while ((entry = readdir(directory))) {
        if (!strncmp(entry->d_name, "sharedindex.", 12)) { closedir(directory); refresh_note(log, git_dir, "skip split-index"); goto done; }
        if (!strncmp(entry->d_name, "index.wsh-", 10)) {
            char *stale = join(git_dir, entry->d_name);
            struct stat old;
            if (stale && !lstat(stale, &old) && S_ISREG(old.st_mode) && time(NULL) - old.st_mtime > 600) unlink(stale);
            free(stale);
        }
    }
    closedir(directory);
    source = open(index, O_RDONLY | O_CLOEXEC);
    private_copy = mkstemp(copy_path);
    if (source < 0 || private_copy < 0 || fcntl(private_copy, F_SETFD, FD_CLOEXEC) < 0 || copy_fd(source, private_copy) || fstat(private_copy, &copied) ||
        stat(index, &after) || !same_identity(&before, &after) || copied.st_size != before.st_size) {
        if (private_copy >= 0) unlink(copy_path);
        refresh_note(log, git_dir, "skip copy-failed");
        goto done;
    }
    close(private_copy); private_copy = -1;
    if (stat(copy_path, &copied)) goto done;
    while (environ[count]) ++count;
    index_variable = malloc(strlen(copy_path) + sizeof("GIT_INDEX_FILE="));
    environment = allocate_zero(count + 2, sizeof(char *));
    if (!index_variable || !environment) { unlink(copy_path); goto done; }
    strcpy(index_variable, "GIT_INDEX_FILE="); strcat(index_variable, copy_path);
    for (i = 0; i < count; ++i)
        if (strncmp(environ[i], "GIT_INDEX_FILE=", 15)) environment[used++] = environ[i];
    environment[used] = index_variable;
    nullfd = private_fd(open("/dev/null", O_RDWR | O_CLOEXEC));
    if (nullfd < 0) { unlink(copy_path); goto done; }
    refresh_note(log, git_dir, "start");
    /* The intermediate child exits at once, so the refresh outlives no one and needs no reaping. */
    child = fork();
    if (!child) {
        struct stat refreshed_copy, current;
        int status = 0, target;
        pid_t refresher;
        if (setsid() < 0 || chdir(cwd) || dup2(nullfd, STDIN_FILENO) < 0 || dup2(nullfd, STDOUT_FILENO) < 0 || dup2(nullfd, STDERR_FILENO) < 0) _exit(127);
        if (fork()) _exit(0);
        /* Lower priority is best effort; the refresh runs either way. */
        if (setpriority(PRIO_PROCESS, 0, 10)) {}
        /* Git's read path compares an entry's time with the index's in whole seconds, so an index
         * written in the same second as the touch that made the status slow leaves every touched
         * entry racy and rechecked by each status. Starting Git in the next second avoids that
         * without trusting anything Git would not. */
        {
            struct timespec now, pause;
            if (!clock_gettime(CLOCK_REALTIME, &now)) {
                pause.tv_sec = 0;
                pause.tv_nsec = 1000000000L - now.tv_nsec + 20000000L;
                if (pause.tv_nsec >= 1000000000L) { pause.tv_sec = 1; pause.tv_nsec -= 1000000000L; }
                while (nanosleep(&pause, &pause) < 0 && errno == EINTR) {}
            }
        }
        refresher = fork();
        if (!refresher) { execve(path, arguments, environment); _exit(127); }
        while (refresher > 0 && waitpid(refresher, &status, 0) < 0 && errno == EINTR) {}
        if (refresher <= 0 || !WIFEXITED(status) || WEXITSTATUS(status)) refresh_note(log, git_dir, "git-failed");
        else if (!stat(copy_path, &refreshed_copy) && same_identity(&copied, &refreshed_copy)) refresh_note(log, git_dir, "nothing-to-write");
        /* Install only a copy Git rewrote, over an index that no one has replaced meanwhile. */
        if (refresher > 0 && WIFEXITED(status) && !WEXITSTATUS(status) && !stat(copy_path, &refreshed_copy) &&
            !same_identity(&copied, &refreshed_copy) && (target = open(lock, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0666)) >= 0) {
            int from = open(copy_path, O_RDONLY | O_CLOEXEC), installed = 0;
            /* The index keeps the timestamp Git gave the copy: Git trusts an entry only if its file is
             * older than the index, so an install time in the same second as a touch would leave every
             * touched entry racy and rehashed at each status. */
            struct timespec times[2] = { { 0, UTIME_OMIT }, WSH_MTIME(refreshed_copy) };
            if (from >= 0 && !stat(index, &current) && same_identity(&before, &current) && !copy_fd(from, target) &&
                !futimens(target, times) && !fsync(target)) {
                close(target); target = -1;
                installed = !rename(lock, index);
            }
            if (target >= 0) close(target);
            if (from >= 0) close(from);
            if (!installed) unlink(lock);
            refresh_note(log, git_dir, installed ? "installed" : "discarded index-changed");
        } else if (refresher > 0 && WIFEXITED(status) && !WEXITSTATUS(status) && !stat(copy_path, &refreshed_copy) &&
                   !same_identity(&copied, &refreshed_copy)) {
            refresh_note(log, git_dir, "discarded lock-busy");
        }
        unlink(copy_path);
        _exit(0);
    }
    if (child > 0) reap(child);
    else unlink(copy_path);
done:
    if (nullfd >= 0) close(nullfd);
    if (source >= 0) close(source);
    if (private_copy >= 0) close(private_copy);
    free(index); free(lock); free(path); free(copy_path); free(index_variable); free(environment);
}
int wsh_git_operation(const char *directory)
{
        if (exists_in(directory, "rebase-merge", 1) || exists_in(directory, "rebase-apply", 1)) return 1;
        else if (exists_in(directory, "MERGE_HEAD", 0)) return 2;
        else if (exists_in(directory, "CHERRY_PICK_HEAD", 0)) return 3;
        else if (exists_in(directory, "REVERT_HEAD", 0)) return 4;
        else if (exists_in(directory, "BISECT_LOG", 0)) return 5;
    return 0;
}
void wsh_git_free(struct wsh_git_result *result)
{
    free(result->root); free(result->branch); free(result->detached_sha); free(result->exact_tag); free(result->error);
    memset(result, 0, sizeof(*result));
}
int wsh_git_collect(const char *cwd, const char *git, int (*cancel)(void *), void *user, struct wsh_git_result *out)
{
    uint64_t start = now_ns(), parsing;
    struct context ctx = {out, cancel, user, start + TIMEOUT_NS, 0};
    struct identity id = {0};
    unsigned char *output;
    size_t length = 0;
    int found;
    memset(out, 0, sizeof(*out));
    found = discover(cwd, &id, &ctx);
    out->discovery_ns = now_ns() - start;
    if (!found) return out->error || out->cancelled ? -1 : 0;
    output = git_output(cwd, git, &length, &ctx);
    if (!output) {
        /* A status past the deadline is the slowest case, so it refreshes too. */
        if (ctx.timed_out && !out->cancelled && !wsh_git_operation(id.git_dir)) refresh_index(cwd, git, id.git_dir);
        free_identity(&id); return -1;
    }
    parsing = now_ns();
    if (parse_status(output, length, out)) fail(&ctx, "Git status output is not UTF-8");
    free(output);
    if (!out->error && !out->cancelled) {
        if (id.oid) out->exact_tag = exact_tag(id.common, id.oid, &ctx);
        out->root = id.root; id.root = NULL;
        out->branch = id.branch; id.branch = NULL;
        if (!out->branch && id.oid && *id.oid) {
            size_t bytes = 0, characters = 0, size = strlen(id.oid);
            while (bytes < size && characters++ < 7) bytes += (size_t)utf8_width((unsigned char *)id.oid + bytes, size - bytes);
            out->detached_sha = copy_n(id.oid, bytes);
        }
        out->found = out->worktree = 1;
        out->operation = wsh_git_operation(id.git_dir);
        if (getenv("WSH_GIT_REFRESH_LOG")) {
            char event[40];
            snprintf(event, sizeof(event), "status %llu ms", (unsigned long long)(out->process_ns / 1000000));
            refresh_note(getenv("WSH_GIT_REFRESH_LOG"), id.git_dir, event);
        }
        if (out->process_ns < REFRESH_NS) note_fast_status(id.git_dir);
        else if (!out->operation) refresh_index(cwd, git, id.git_dir);
    }
    out->parsing_ns = now_ns() - parsing;
    free_identity(&id);
    return out->error || out->cancelled ? -1 : 0;
}
