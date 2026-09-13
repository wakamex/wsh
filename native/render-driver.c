/* Standalone comparison driver. This JSON snapshot interface is not shipped. */
#define _GNU_SOURCE
#include "render.h"
#include <jansson.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int nonnegative(json_t *v) { return json_is_integer(v) && json_integer_value(v) >= 0; }
static json_t *field(json_t *object, const char *key) { json_t *v = json_object_get(object, key); assert(v); return v; }
static const char *text(json_t *object, const char *key)
{
    json_t *v = field(object, key); if (json_is_null(v)) return NULL;
    assert(json_is_string(v)); const char *s = json_string_value(v); assert(strlen(s) == json_string_length(v)); return s;
}
static int flag(json_t *object, const char *key) { json_t *v = field(object, key); assert(json_is_boolean(v)); return json_is_true(v); }
static uint64_t number(json_t *object, const char *key) { json_t *v = field(object, key); assert(nonnegative(v)); return json_integer_value(v); }
static char *unhex(const char *source)
{
    if (!source) return NULL;
    static const char digits[] = "0123456789abcdef";
    size_t length = strlen(source); assert(length <= 8192 && !(length % 2));
    char *out = malloc(length / 2 + 1); assert(out);
    for (size_t i = 0; i < length / 2; ++i) {
        const char *a = strchr(digits, source[2 * i]), *b = strchr(digits, source[2 * i + 1]);
        assert(a && b); out[i] = (char)((a - digits) * 16 + (b - digits)); assert(out[i]);
    }
    out[length / 2] = 0; return out;
}
static uint64_t now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec; }
int main(int argc, char **argv)
{
    assert(argc == 2); struct wsh_theme theme; char error[512];
    if (wsh_theme_load(argv[1], &theme, error, sizeof(error))) { fprintf(stderr, "%s\n", error); return 1; }
    struct wsh_renderer renderer; wsh_renderer_init(&renderer, &theme);
    char *line = NULL; size_t capacity = 0; ssize_t length;
    while ((length = getline(&line, &capacity, stdin)) >= 0) {
        assert(length <= 65536);
        json_t *doc = json_loadb(line, (size_t)length, JSON_REJECT_DUPLICATES, NULL); assert(doc);
        json_t *request = doc, *snapshot = field(request, "snapshot");
        assert(json_is_object(request) && json_is_object(snapshot));
        char *cwd = unhex(text(snapshot, "cwd_hex")); assert(cwd);
        struct wsh_git_result git = {0}; git.root = unhex(text(snapshot, "root_hex"));
        git.branch = (char *)text(snapshot, "branch"); git.exact_tag = (char *)text(snapshot, "exact_tag"); git.detached_sha = (char *)text(snapshot, "detached_sha");
        git.found = flag(snapshot, "found"); git.staged = flag(snapshot, "staged"); git.modified = flag(snapshot, "modified"); git.untracked = flag(snapshot, "untracked");
        git.ahead = number(snapshot, "ahead"); git.behind = number(snapshot, "behind");
        const char *operation = text(snapshot, "operation");
        const char *operations[] = {"rebase", "merge", "cherry-pick", "revert", "bisect"};
        if (operation) { for (size_t i = 0; i < 5; ++i) if (!strcmp(operation, operations[i])) git.operation = (int)i + 1; assert(git.operation); }
        json_t *status = field(request, "status"), *duration = field(request, "duration");
        assert(json_is_integer(status) && (json_is_null(duration) || nonnegative(duration)));
        int privileged = flag(request, "privileged");
        if (flag(request, "reset")) wsh_renderer_reset(&renderer);
        char *left, *right; uint64_t start = now();
        wsh_render(&renderer, cwd, &git, (int)json_integer_value(status), !json_is_null(duration), json_integer_value(duration), privileged, &left, &right);
        uint64_t elapsed = now() - start;
        start = now(); uint64_t empty = now() - start;
        json_t *response = json_pack("[ssII]", left, right, (json_int_t)elapsed, (json_int_t)empty); assert(response);
        char *encoded = json_dumps(response, JSON_COMPACT); assert(encoded); puts(encoded); fflush(stdout);
        free(encoded); json_decref(response); free(left); free(right); free(cwd); free(git.root); json_decref(doc);
    }
    free(line); wsh_renderer_free(&renderer); wsh_theme_free(&theme); return 0;
}
