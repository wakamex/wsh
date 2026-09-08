/* Native profile invocation; the existing buffered instrumentation stays unchanged. */
#include <sys/stat.h>
#include <sys/time.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char **wsh_profile_arguments;
static char wsh_profile_directory[PATH_MAX];
static pid_t wsh_profile_owner;
static int wsh_profile_report(const char *directory);
static long long wsh_profile_started;
static struct { const char *name; long long elapsed; } wsh_profile_startup[32];
static size_t wsh_profile_startup_count;

static int
wsh_profile_active(void)
{
    return wsh_profile_owner && wsh_profile_owner == getpid();
}

/* Only native startup passes fixed names here. No allocation, parsing or I/O. */
static void
wsh_profile(char *event)
{
    struct timeval now;
    long long elapsed;
    if (!wsh_profile_active() || wsh_profile_startup_count == 32)
        return;
    gettimeofday(&now, NULL);
    elapsed = (long long)now.tv_sec * 1000000 + now.tv_usec - wsh_profile_started;
    wsh_profile_startup[wsh_profile_startup_count].name = event;
    wsh_profile_startup[wsh_profile_startup_count++].elapsed = elapsed < 0 ? 0 : elapsed;
}

static void
wsh_profile_flush_startup(void)
{
    char path[PATH_MAX], buffer[8192];
    size_t i, used = 0;
    int fd, length;
    struct stat st;
    ssize_t written;
    if (!wsh_profile_startup_count || wsh_profile_owner != getpid())
        return;
    for (i = 0; i < wsh_profile_startup_count; ++i) {
        length = snprintf(buffer + used, sizeof(buffer) - used,
                          "{\"schema_version\":1,\"source\":\"zsh\",\"event\":\"%s\",\"elapsed_us\":%lld}\n",
                          wsh_profile_startup[i].name, wsh_profile_startup[i].elapsed);
        if (length < 0 || (size_t)length >= sizeof(buffer) - used)
            return;
        used += (size_t)length;
    }
    if (snprintf(path, sizeof(path), "%s/trace.jsonl", wsh_profile_directory) >= (int)sizeof(path))
        return;
    fd = open(path, O_WRONLY | O_APPEND | O_NONBLOCK | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0)
        return;
    if (!fstat(fd, &st) && S_ISREG(st.st_mode) && st.st_uid == getuid() && !(st.st_mode & 077)) {
        do { written = write(fd, buffer, used); } while (written < 0 && errno == EINTR);
        /* A partial append is left visibly truncated; never duplicate a prefix. */
        wsh_profile_startup_count = 0;
    }
    close(fd);
}

static void
wsh_profile_at_exit(void)
{
    if (wsh_profile_owner == getpid()) {
        wsh_profile_flush_startup();
        (void)wsh_profile_report(wsh_profile_directory);
    }
}

static int
wsh_profile_mkdirs(char *path)
{
    char *p;
    struct stat st;
    for (p = path + 1; ; ++p) {
        int last = !*p;
        if (*p == '/' || last) {
            char saved = *p;
            *p = 0;
            if (mkdir(path, 0700) && errno != EEXIST) {
                *p = saved;
                return -1;
            }
            if (stat(path, &st) || !S_ISDIR(st.st_mode)) {
                *p = saved;
                return -1;
            }
            *p = saved;
        }
        if (last)
            break;
    }
    return 0;
}

static int
wsh_profile_file(const char *name, const char *contents, char *path)
{
    int fd, result = -1;
    FILE *file;
    if (snprintf(path, PATH_MAX, "%s/%s", wsh_profile_directory, name) >= PATH_MAX)
        return -1;
    fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0)
        return -1;
    if (fchmod(fd, 0600) || !(file = fdopen(fd, "w"))) {
        close(fd);
        return -1;
    }
    if (fputs(contents, file) >= 0)
        result = 0;
    if (fclose(file))
        result = -1;
    return result;
}

static int
wsh_profile_start(int argc, char **argv)
{
    const char *root = getenv("WSH_STATE_ROOT"), *home;
    char base[PATH_MAX], profiles[PATH_MAX], path[PATH_MAX];
    char metadata[2048], event[512], seconds[64], micros[64];
    struct timeval began, now;
    struct stat st;
    int first = 2, functions = 0;
    long long started, elapsed;

    if (first < argc && !strcmp(argv[first], "--functions")) {
        functions = 1;
        ++first;
    }
    if (first < argc) {
        if (strcmp(argv[first], "--")) {
            fputs("usage: wsh --wsh-profile [--functions] -- [Zsh arguments]\n", stderr);
            return 2;
        }
        ++first;
    }
    gettimeofday(&began, NULL);
    started = (long long)began.tv_sec * 1000000 + began.tv_usec;
    if (!root || !*root) {
        home = getenv("XDG_DATA_HOME");
        if (home && *home) {
            if (snprintf(base, sizeof(base), "%s/wsh", home) >= (int)sizeof(base))
                goto failure;
        } else {
            home = getenv("HOME");
            if (!home || !*home || snprintf(base, sizeof(base), "%s/.local/share/wsh", home) >= (int)sizeof(base))
                goto failure;
        }
        root = base;
    }
    if (root[0] == '/') {
        if (snprintf(profiles, sizeof(profiles), "%s/profiles", root) >= (int)sizeof(profiles))
            goto failure;
    } else {
        if (!getcwd(path, sizeof(path)) || snprintf(profiles, sizeof(profiles), "%s/%s/profiles", path, root) >= (int)sizeof(profiles))
            goto failure;
    }
    /* Existing parents keep their modes. Only our dedicated profile directory is private. */
    if (wsh_profile_mkdirs(profiles) || lstat(profiles, &st) || !S_ISDIR(st.st_mode) || st.st_uid != getuid() || (st.st_mode & 077))
        goto failure;
    if (snprintf(wsh_profile_directory, sizeof(wsh_profile_directory), "%s/%lld-%ld-XXXXXX", profiles, (long long)began.tv_sec, (long)getpid()) >= (int)sizeof(wsh_profile_directory) || !mkdtemp(wsh_profile_directory))
        goto failure;
    snprintf(metadata, sizeof(metadata),
             "{\"schema_version\":2,\"wsh_version\":\"%s\",\"source_revision\":\"%s\",\"native_inputs_sha256\":\"%s\",\"zsh_version\":\"%s\",\"zsh_source_revision\":\"%s\",\"target\":\"%s\"}\n",
             WSH_VERSION, WSH_SOURCE_REVISION, WSH_INPUTS_SHA256, ZSH_VERSION, WSH_ZSH_SOURCE_REVISION, WSH_TARGET);
    if (wsh_profile_file("metadata.json", metadata, path))
        goto failure;
    gettimeofday(&now, NULL);
    elapsed = ((long long)now.tv_sec * 1000000 + now.tv_usec) - started;
    snprintf(event, sizeof(event), "{\"schema_version\":1,\"source\":\"manager\",\"event\":\"launch-ready\",\"elapsed_us\":%lld,\"wsh_version\":\"%s\",\"bundle_sha256\":\"%s\"}\n", elapsed < 0 ? 0 : elapsed, WSH_VERSION, WSH_INPUTS_SHA256);
    if (wsh_profile_file("trace.jsonl", event, path) || setenv("WSH_PROFILE_FILE", path, 1) || setenv("WSH_TRACE_FILE", path, 1))
        goto failure;
    if (functions) {
        if (wsh_profile_file("zprof.txt", "", path))
            goto failure;
    } else if (snprintf(path, sizeof(path), "%s/zprof.txt", wsh_profile_directory) >= (int)sizeof(path))
        goto failure;
    snprintf(seconds, sizeof(seconds), "%lld.%06ld", (long long)began.tv_sec, (long)began.tv_usec);
    snprintf(micros, sizeof(micros), "%lld", started);
    if (setenv("WSH_PROFILE_ZPROF_FILE", path, 1) || setenv("WSH_PROFILE_DIRECTORY", wsh_profile_directory, 1) ||
        setenv("WSH_PROFILE_STARTED_AT", seconds, 1) || setenv("WSH_PROFILE_STARTED_UNIX_US", micros, 1) ||
        setenv("WSH_PROFILE_FUNCTIONS", functions ? "1" : "0", 1) || setenv("WSH_PROFILE_REPORTER", "", 1))
        goto failure;
    memmove(argv + 1, argv + first, (size_t)(argc - first + 1) * sizeof(char *));
    wsh_profile_arguments = argv;
    wsh_profile_owner = getpid();
    wsh_profile_started = started;
    if (atexit(wsh_profile_at_exit))
        goto failure;
    fprintf(stderr, "Profiling this shell. Exit to view the report.\nTrace: %s\n", wsh_profile_directory);
    return -1;

failure:
    fputs("wsh: could not create private profile storage\n", stderr);
    return 1;
}
