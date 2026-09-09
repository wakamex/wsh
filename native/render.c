#define _GNU_SOURCE
#include "render.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct buffer { char *data; size_t size, capacity; };
static void append_n(struct buffer *b, const char *value, size_t length)
{
    if (length > SIZE_MAX - b->size - 1) abort();
    size_t needed = b->size + length + 1;
    if (needed > b->capacity) {
        size_t capacity = needed > SIZE_MAX / 2 ? needed : needed * 2;
        char *data = realloc(b->data, capacity);
        if (!data) abort();
        b->data = data; b->capacity = capacity;
    }
    memcpy(b->data + b->size, value, length); b->size += length; b->data[b->size] = 0;
}
static void append(struct buffer *b, const char *value) { append_n(b, value, strlen(value)); }
static char *copy(const char *value) { char *p = strdup(value); if (!p) abort(); return p; }
static char *take(struct buffer *b) { return b->data ? b->data : copy(""); }
/* Valid widths or invalid-prefix lengths match the collector's Rust UTF-8 contract. */
static int width(const unsigned char *p, size_t length)
{
    if (*p < 0x80) return 1;
    unsigned n = *p >= 0xc2 && *p <= 0xdf ? 2 : *p >= 0xe0 && *p <= 0xef ? 3 : *p >= 0xf0 && *p <= 0xf4 ? 4 : 0;
    if (!n) return -1;
    for (unsigned i = 1; i < n; ++i) {
        if (i >= length || (p[i] & 0xc0) != 0x80) return -(int)i;
        if (i == 1 && ((*p == 0xe0 && p[i] < 0xa0) || (*p == 0xed && p[i] >= 0xa0) || (*p == 0xf0 && p[i] < 0x90) || (*p == 0xf4 && p[i] >= 0x90))) return -1;
    }
    return (int)n;
}
static char *display(const char *value, int strict)
{
    struct buffer b = {0}; size_t length = strlen(value);
    for (size_t i = 0; i < length;) {
        int n = width((const unsigned char *)value + i, length - i);
        if (n > 0) { append_n(&b, value + i, (size_t)n); i += (size_t)n; }
        else if (strict) { free(b.data); return NULL; }
        else { append(&b, "�"); i += (size_t)-n; }
    }
    return take(&b);
}
static void escaped(struct buffer *b, const char *value)
{
    size_t length = strlen(value);
    for (size_t i = 0; i < length;) {
        unsigned char ch = (unsigned char)value[i];
        int n = width((const unsigned char *)value + i, length - i);
        if (n < 0) { append(b, "�"); i += (size_t)-n; continue; }
        if (ch < 0x20 || ch == 0x7f || (ch == 0xc2 && i + 1 < length && (unsigned char)value[i + 1] <= 0x9f)) append(b, "�");
        else if (ch == '%') append(b, "%%");
        else { if (ch == '$' || ch == '`' || ch == '\\') append(b, "\\"); append_n(b, value + i, (size_t)n); }
        i += (size_t)n;
    }
}
static const char *string(const struct wsh_renderer *r, const char *path)
{
    toml_datum_t v = wsh_theme_get(r->theme, path); return v.type == TOML_STRING ? v.u.s : "";
}
static int boolean(const struct wsh_renderer *r, const char *path) { return wsh_theme_get(r->theme, path).u.boolean; }
static const char *color_name(const char *name)
{
    static const char *bright[] = {"8", "9", "10", "11", "12", "13", "14", "15"};
    int index = wsh_theme_color(name); return index >= 9 ? bright[index - 9] : name;
}
static void styled(struct buffer *out, const char *body, const char *color)
{
    if (!strcmp(color, "default")) { append(out, body); return; }
    append(out, "%F{"); append(out, color_name(color)); append(out, "}"); append(out, body); append(out, "%f");
}
/* Path equality removes repeated separators and '.' without resolving '..'. */
static char *normalized(const char *path)
{
    struct buffer b = {0}; const char *p = path;
    if (*p == '/') append(&b, "/");
    while (*p) {
        while (*p == '/') ++p;
        const char *start = p; while (*p && *p != '/') ++p;
        size_t n = (size_t)(p - start); if (!n || (n == 1 && *start == '.')) continue;
        if (b.size && b.data[b.size - 1] != '/') append(&b, "/");
        append_n(&b, start, n);
    }
    return take(&b);
}
void wsh_renderer_reset(struct wsh_renderer *r) { free(r->last_cwd); free(r->last_git); r->last_cwd = r->last_git = NULL; }
void wsh_renderer_init(struct wsh_renderer *r, const struct wsh_theme *theme)
{
    memset(r, 0, sizeof(*r)); r->theme = theme;
    const char *home = getenv("HOME"), *user = getenv("USER"), *host = getenv("HOST");
    r->home = home ? normalized(home) : NULL;
    r->user = user ? display(user, 1) : NULL; if (!r->user) r->user = copy("");
    r->host = host ? display(host, 1) : NULL; if (!r->host) r->host = copy("localhost");
    r->ssh = getenv("SSH_CONNECTION") != NULL || getenv("SSH_TTY") != NULL;
}
void wsh_renderer_free(struct wsh_renderer *r) { wsh_renderer_reset(r); free(r->home); free(r->user); free(r->host); memset(r, 0, sizeof(*r)); }
static char *git_key(const struct wsh_git_result *g)
{
    if (!g->found) return copy("");
    struct buffer b = {0}; const unsigned char *p = (const unsigned char *)(g->root ? g->root : "");
    for (; *p; ++p) { char hex[3]; snprintf(hex, sizeof(hex), "%02x", *p); append(&b, hex); }
    append(&b, ":"); append(&b, g->branch ? g->branch : g->exact_tag ? g->exact_tag : g->detached_sha ? g->detached_sha : "");
    return take(&b);
}
static int hidden(const struct wsh_renderer *r, const char *branch)
{
    toml_datum_t names = wsh_theme_get(r->theme, "git.hide-branches");
    for (int i = 0; i < names.u.arr.size; ++i) if (!strcmp(branch, names.u.arr.elem[i].u.s)) return 1;
    return 0;
}
static void component(struct buffer *out, const char *name, const struct wsh_renderer *r, const char *cwd,
                      const struct wsh_git_result *g, int cwd_changed, int git_changed,
                      int status, int has_duration, uint64_t duration, int privileged)
{
    struct buffer raw = {0}, body = {0}; const char *color = "default";
    if (!strcmp(name, "context")) {
        if ((!boolean(r, "context.show-local") && !r->ssh) || (!boolean(r, "context.show-ssh") && r->ssh)) return;
        append(&raw, string(r, "context.prefix")); append(&raw, r->user); append(&raw, string(r, "context.separator"));
        append(&raw, r->host); append(&raw, string(r, "context.suffix")); color = string(r, "context.color");
    } else if (!strcmp(name, "cwd")) {
        if (boolean(r, "cwd.show-on-change") && !cwd_changed) return;
        char *visible = display(cwd, 0), *path = normalized(visible);
        const char *text = visible;
        if (r->home && !strcmp(r->home, path)) text = string(r, "cwd.home-symbol");
        else if (!strcmp(string(r, "cwd.style"), "short")) {
            const char *slash = strrchr(path, '/'); text = slash ? slash + 1 : path;
            if (!*text || !strcmp(text, "..")) text = "/";
        }
        size_t length = strlen(text), characters = 0;
        for (size_t i = 0; i < length; ++i) if (((unsigned char)text[i] & 0xc0) != 0x80) ++characters;
        uint64_t maximum = wsh_theme_uint(wsh_theme_get(r->theme, "cwd.max-length"));
        if (maximum && characters > maximum) {
            size_t skip = characters - (maximum > 2 ? (size_t)maximum - 2 : 0), offset = 0;
            while (offset < length && skip) { offset += (size_t)width((const unsigned char *)text + offset, length - offset); --skip; }
            append(&raw, ".."); append(&raw, text + offset);
        } else append(&raw, text);
        free(path); free(visible); color = string(r, "cwd.color");
    } else if (!strcmp(name, "git")) {
        if (!g->found) return;
        const char *parts[8]; size_t count = 0; struct buffer label = {0}; int has_label = 0;
        const char *value = NULL, *prefix = NULL;
        if (g->branch) { if (!hidden(r, g->branch)) { value = g->branch; prefix = "git.symbols.branch"; } }
        else if (g->exact_tag) { value = g->exact_tag; prefix = "git.symbols.tag"; }
        else if (g->detached_sha) { value = g->detached_sha; prefix = "git.symbols.detached"; }
        if (value) { append(&label, string(r, prefix)); append(&label, value); append(&label, string(r, "git.label-suffix")); has_label = 1; }
        if (g->staged) parts[count++] = string(r, "git.symbols.staged");
        if (g->modified) parts[count++] = string(r, "git.symbols.modified");
        if (g->untracked) parts[count++] = string(r, "git.symbols.untracked");
        if (g->ahead || g->behind) parts[count++] = string(r, g->ahead && g->behind ? "git.symbols.diverged" : g->ahead ? "git.symbols.ahead" : "git.symbols.behind");
        static const char *operations[] = {"", "git.symbols.rebase", "git.symbols.merge", "git.symbols.cherry-pick", "git.symbols.revert", "git.symbols.bisect"};
        if (g->operation > 0 && g->operation < 6) parts[count++] = string(r, operations[g->operation]);
        const char *first = NULL;
        if (boolean(r, "git.compact")) {
            if (!count) parts[count++] = git_changed && has_label ? label.data : string(r, "git.symbols.clean");
            else if (git_changed && g->branch && !hidden(r, g->branch)) first = g->branch;
        } else if (has_label) first = label.data;
        if (!count && !first) { free(label.data); return; }
        append(&raw, string(r, "git.prefix"));
        if (first) append(&raw, first);
        for (size_t i = 0; i < count; ++i) { if (i || first) append(&raw, string(r, "git.separator")); append(&raw, parts[i]); }
        append(&raw, " "); free(label.data); color = string(r, "git.color");
    } else if (!strcmp(name, "duration")) {
        if (!has_duration || duration < wsh_theme_uint(wsh_theme_get(r->theme, "duration.threshold-ms"))) return;
        append(&raw, string(r, "duration.prefix")); char number[128];
        if (!strcmp(string(r, "duration.format"), "milliseconds")) { snprintf(number, sizeof(number), "%llums", (unsigned long long)duration); append(&raw, number); }
        else {
            uint64_t seconds = duration / 1000; uint64_t values[] = {seconds / 86400, seconds / 3600 % 24, seconds / 60 % 60, seconds % 60};
            const char *suffix[] = {"d", "h", "m", "s"}; int emitted = 0;
            for (size_t i = 0; i < 4; ++i) if (values[i] || (i == 3 && !emitted)) {
                snprintf(number, sizeof(number), "%s%llu%s", emitted ? " " : "", (unsigned long long)values[i], suffix[i]); append(&raw, number); emitted = 1;
            }
        }
        append(&raw, string(r, "duration.suffix")); color = string(r, "duration.color");
    } else {
        const char *kind = privileged ? "privileged" : status ? "failure" : "success"; char key[80];
        snprintf(key, sizeof(key), "prompt-character.%s", kind); append(&raw, string(r, key));
        snprintf(key, sizeof(key), "prompt-character.%s-color", kind); color = string(r, key);
    }
    escaped(&body, raw.data ? raw.data : ""); styled(out, body.data ? body.data : "", color);
    if (!strcmp(name, "cwd") || !strcmp(name, "prompt-character")) append(out, " ");
    free(raw.data); free(body.data);
}
void wsh_render(struct wsh_renderer *r, const char *cwd, const struct wsh_git_result *g,
                int status, int has_duration, uint64_t duration, int privileged, char **left, char **right)
{
    int cwd_changed = !r->last_cwd || strcmp(r->last_cwd, cwd);
    char *key = git_key(g); int git_changed = !r->last_git || strcmp(r->last_git, key);
    const char *layouts[] = {"left", "right"}; char **results[] = {left, right};
    toml_datum_t segments = wsh_theme_get(r->theme, "segments");
    int segmented = segments.type == TOML_TABLE && segments.u.tab.size;
    for (size_t side = 0; side < 2; ++side) {
        struct buffer out = {0}; const char *previous = NULL;
        toml_datum_t layout = wsh_theme_get(r->theme, layouts[side]);
        for (int i = 0; i < layout.u.arr.size; ++i) {
            const char *name = layout.u.arr.elem[i].u.s; struct buffer body = {0};
            component(&body, name, r, cwd, g, cwd_changed, git_changed, status, has_duration, duration, privileged);
            if (!segmented) { append(&out, body.data ? body.data : ""); free(body.data); continue; }
            if (!body.size) { free(body.data); continue; }
            char path[80]; snprintf(path, sizeof(path), "segments.%s", name); toml_datum_t style = wsh_theme_get(r->theme, path);
            if (style.type == TOML_TABLE) {
                toml_datum_t background = toml_get(style, "background"), dirty = toml_get(style, "dirty-background");
                if (!strcmp(name, "git") && (g->staged || g->modified || g->untracked) && dirty.type == TOML_STRING) background = dirty;
                append(&out, "%K{"); append(&out, color_name(background.u.s)); append(&out, "}");
                if (previous) styled(&out, "", previous);
                append(&out, " "); append(&out, body.data); previous = background.u.s;
            } else { if (previous) { append(&out, "%k"); styled(&out, "", previous); previous = NULL; } append(&out, body.data); }
            free(body.data);
        }
        if (previous) { append(&out, "%k"); styled(&out, "", previous); append(&out, " "); }
        *results[side] = take(&out);
    }
    free(r->last_cwd); r->last_cwd = copy(cwd); free(r->last_git); r->last_git = key;
}
