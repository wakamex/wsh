/* Standalone comparison driver. This JSON snapshot interface is not shipped. */
#define _GNU_SOURCE
#include "render.h"
#include "yyjson.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static yyjson_val *field(yyjson_val *object, const char *key) { yyjson_val *v = yyjson_obj_get(object, key); assert(v); return v; }
static const char *text(yyjson_val *object, const char *key)
{
    yyjson_val *v = field(object, key); if (yyjson_is_null(v)) return NULL;
    assert(yyjson_is_str(v)); const char *s = yyjson_get_str(v); assert(strlen(s) == yyjson_get_len(v)); return s;
}
static int flag(yyjson_val *object, const char *key) { yyjson_val *v = field(object, key); assert(yyjson_is_bool(v)); return yyjson_get_bool(v); }
static uint64_t number(yyjson_val *object, const char *key) { yyjson_val *v = field(object, key); assert(yyjson_is_uint(v)); return yyjson_get_uint(v); }
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
        yyjson_doc *doc = yyjson_read(line, (size_t)length, 0); assert(doc);
        yyjson_val *request = yyjson_doc_get_root(doc), *snapshot = field(request, "snapshot");
        assert(yyjson_is_obj(request) && yyjson_is_obj(snapshot));
        char *cwd = unhex(text(snapshot, "cwd_hex")); assert(cwd);
        struct wsh_git_result git = {0}; git.root = unhex(text(snapshot, "root_hex"));
        git.branch = (char *)text(snapshot, "branch"); git.exact_tag = (char *)text(snapshot, "exact_tag"); git.detached_sha = (char *)text(snapshot, "detached_sha");
        git.found = flag(snapshot, "found"); git.staged = flag(snapshot, "staged"); git.modified = flag(snapshot, "modified"); git.untracked = flag(snapshot, "untracked");
        git.ahead = number(snapshot, "ahead"); git.behind = number(snapshot, "behind");
        const char *operation = text(snapshot, "operation");
        const char *operations[] = {"rebase", "merge", "cherry-pick", "revert", "bisect"};
        if (operation) { for (size_t i = 0; i < 5; ++i) if (!strcmp(operation, operations[i])) git.operation = (int)i + 1; assert(git.operation); }
        yyjson_val *status = field(request, "status"), *duration = field(request, "duration");
        assert(yyjson_is_int(status) && (yyjson_is_null(duration) || yyjson_is_uint(duration)));
        int privileged = flag(request, "privileged");
        if (flag(request, "reset")) wsh_renderer_reset(&renderer);
        char *left, *right; uint64_t start = now();
        wsh_render(&renderer, cwd, &git, (int)yyjson_get_sint(status), !yyjson_is_null(duration), yyjson_get_uint(duration), privileged, &left, &right);
        uint64_t elapsed = now() - start;
        start = now(); uint64_t empty = now() - start;
        yyjson_mut_doc *response = yyjson_mut_doc_new(NULL); assert(response);
        yyjson_mut_val *array = yyjson_mut_arr(response); yyjson_mut_doc_set_root(response, array);
        assert(yyjson_mut_arr_add_strcpy(response, array, left) && yyjson_mut_arr_add_strcpy(response, array, right) && yyjson_mut_arr_add_uint(response, array, elapsed) && yyjson_mut_arr_add_uint(response, array, empty));
        char *encoded = yyjson_mut_write(response, 0, NULL); assert(encoded); puts(encoded); fflush(stdout);
        free(encoded); yyjson_mut_doc_free(response); free(left); free(right); free(cwd); free(git.root); yyjson_doc_free(doc);
    }
    free(line); wsh_renderer_free(&renderer); wsh_theme_free(&theme); return 0;
}
