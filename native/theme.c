#define _GNU_SOURCE
#include "theme.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define THEME_LIMIT (64 * 1024)
struct field { const char *path; char kind; int required; };
#define SEGMENT(name) {"segments." name, 't', 0}, {"segments." name ".background", 'c', 1}, {"segments." name ".dirty-background", 'c', 0}
static const struct field fields[] = {
    {"schema-version", 'u', 1}, {"id", 's', 1}, {"name", 's', 1},
    {"left", 'a', 1}, {"right", 'a', 1},
    {"context", 't', 1}, {"context.enabled", 'b', 1}, {"context.show-local", 'b', 1},
    {"context.show-ssh", 'b', 1}, {"context.prefix", 's', 1}, {"context.separator", 's', 1},
    {"context.suffix", 's', 1}, {"context.color", 'c', 1},
    {"cwd", 't', 1}, {"cwd.enabled", 'b', 1}, {"cwd.style", 'S', 1},
    {"cwd.show-on-change", 'b', 1}, {"cwd.max-length", 'u', 1}, {"cwd.home-symbol", 's', 1}, {"cwd.color", 'c', 1},
    {"git", 't', 1}, {"git.enabled", 'b', 1}, {"git.compact", 'b', 1}, {"git.hide-branches", 'a', 1},
    {"git.prefix", 's', 1}, {"git.separator", 's', 1}, {"git.color", 'c', 1}, {"git.label-suffix", 's', 0},
    {"git.symbols", 't', 1}, {"git.symbols.branch", 's', 1}, {"git.symbols.detached", 's', 1},
    {"git.symbols.tag", 's', 1}, {"git.symbols.clean", 's', 1}, {"git.symbols.staged", 's', 1},
    {"git.symbols.modified", 's', 1}, {"git.symbols.untracked", 's', 1}, {"git.symbols.ahead", 's', 1},
    {"git.symbols.behind", 's', 1}, {"git.symbols.diverged", 's', 1}, {"git.symbols.rebase", 's', 1},
    {"git.symbols.merge", 's', 1}, {"git.symbols.cherry-pick", 's', 1}, {"git.symbols.revert", 's', 1},
    {"git.symbols.bisect", 's', 1},
    {"duration", 't', 1}, {"duration.enabled", 'b', 1}, {"duration.threshold-ms", 'u', 1},
    {"duration.format", 'F', 1}, {"duration.prefix", 's', 1}, {"duration.suffix", 's', 1}, {"duration.color", 'c', 1},
    {"prompt-character", 't', 1}, {"prompt-character.enabled", 'b', 1}, {"prompt-character.success", 's', 1},
    {"prompt-character.failure", 's', 1}, {"prompt-character.privileged", 's', 1},
    {"prompt-character.success-color", 'c', 1}, {"prompt-character.failure-color", 'c', 1},
    {"prompt-character.privileged-color", 'c', 1},
    {"segments", 't', 0}, SEGMENT("context"), SEGMENT("cwd"), SEGMENT("git"), SEGMENT("duration"), SEGMENT("prompt-character")
};
static const char *components[] = {"context", "cwd", "git", "duration", "prompt-character"};
static const char *colors[] = {"default", "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright-black", "bright-red", "bright-green", "bright-yellow", "bright-blue", "bright-magenta", "bright-cyan", "bright-white"};
static int lookup(const char *name, const char **names, size_t count)
{
    for (size_t i = 0; i < count; ++i) if (!strcmp(name, names[i])) return (int)i;
    return -1;
}
int wsh_theme_component(const char *name) { return lookup(name, components, sizeof(components) / sizeof(*components)); }
int wsh_theme_color(const char *name) { return lookup(name, colors, sizeof(colors) / sizeof(*colors)); }
toml_datum_t wsh_theme_get(const struct wsh_theme *theme, const char *path) { return toml_seek(theme->parsed.toptab, path); }
uint64_t wsh_theme_uint(toml_datum_t value) { return value.type == TOML_UINT64 ? value.u.uint64 : (uint64_t)value.u.int64; }
void wsh_theme_free(struct wsh_theme *theme) { toml_free(theme->parsed); memset(theme, 0, sizeof(*theme)); }
static int reject(char *error, size_t capacity, const char *reason, const char *path)
{
    snprintf(error, capacity, "%s%s%s", reason, *path ? ": " : "", path);
    return -1;
}
static int literal(toml_datum_t value)
{
    if (value.type != TOML_STRING) return 0;
    size_t characters = 0;
    const unsigned char *p = (const unsigned char *)value.u.str.ptr;
    for (int i = 0; i < value.u.str.len; ++i) {
        if (p[i] < 0x20 || p[i] == 0x7f || (p[i] == 0xc2 && i + 1 < value.u.str.len && p[i + 1] >= 0x80 && p[i + 1] <= 0x9f)) return 0;
        if ((p[i] & 0xc0) != 0x80) ++characters;
    }
    return characters <= 128;
}
static int validate_fields(toml_datum_t table, const char *prefix, char *error, size_t capacity)
{
    for (int i = 0; i < table.u.tab.size; ++i) {
        const char *key = table.u.tab.key[i];
        char path[128];
        int length = snprintf(path, sizeof(path), "%s%s%s", prefix, *prefix ? "." : "", key);
        if (strlen(key) != (size_t)table.u.tab.len[i] || strchr(key, '.') || length < 0 || (size_t)length >= sizeof(path)) return reject(error, capacity, "unknown theme field", key);
        const struct field *field = NULL;
        for (size_t j = 0; j < sizeof(fields) / sizeof(*fields); ++j) if (!strcmp(path, fields[j].path)) { field = &fields[j]; break; }
        if (!field) return reject(error, capacity, "unknown theme field", path);
        toml_datum_t value = table.u.tab.value[i];
        int valid = 0;
        switch (field->kind) {
        case 't': valid = value.type == TOML_TABLE; break;
        case 'b': valid = value.type == TOML_BOOLEAN; break;
        case 'u': valid = value.type == TOML_UINT64 || (value.type == TOML_INT64 && value.u.int64 >= 0); break;
        case 's': valid = literal(value); break;
        case 'c': valid = literal(value) && wsh_theme_color(value.u.s) >= 0; break;
        case 'S': valid = literal(value) && (!strcmp(value.u.s, "full") || !strcmp(value.u.s, "short")); break;
        case 'F': valid = literal(value) && (!strcmp(value.u.s, "human") || !strcmp(value.u.s, "milliseconds")); break;
        case 'a':
            valid = value.type == TOML_ARRAY && value.u.arr.size <= (!strcmp(path, "git.hide-branches") ? 16 : 5);
            if (valid) for (int j = 0; j < value.u.arr.size; ++j) if (!literal(value.u.arr.elem[j])) valid = 0;
            break;
        }
        if (!valid) return reject(error, capacity, "invalid theme value", path);
        if (field->kind == 't' && validate_fields(value, path, error, capacity)) return -1;
    }
    return 0;
}
static int validate(struct wsh_theme *theme, char *error, size_t capacity)
{
    if (validate_fields(theme->parsed.toptab, "", error, capacity)) return -1;
    for (size_t i = 0; i < sizeof(fields) / sizeof(*fields); ++i) {
        if (!fields[i].required || wsh_theme_get(theme, fields[i].path).type != TOML_UNKNOWN) continue;
        char parent[128]; snprintf(parent, sizeof(parent), "%s", fields[i].path);
        char *dot = strrchr(parent, '.');
        if (dot) { *dot = 0; if (wsh_theme_get(theme, parent).type == TOML_UNKNOWN) continue; }
        return reject(error, capacity, "missing theme field", fields[i].path);
    }
    if (wsh_theme_uint(wsh_theme_get(theme, "schema-version")) != 1) return reject(error, capacity, "unsupported theme schema version", "");
    const char *id = wsh_theme_get(theme, "id").u.s;
    size_t length = strlen(id);
    if (!length || length > 64 || strspn(id, "abcdefghijklmnopqrstuvwxyz0123456789-") != length) return reject(error, capacity, "invalid theme identifier", "id");
    if (wsh_theme_uint(wsh_theme_get(theme, "cwd.max-length")) > 4096) return reject(error, capacity, "cwd.max-length exceeds 4096 characters", "");
    unsigned mask = 0;
    const char *layouts[] = {"left", "right"};
    for (size_t i = 0; i < 2; ++i) {
        toml_datum_t layout = wsh_theme_get(theme, layouts[i]);
        for (int j = 0; j < layout.u.arr.size; ++j) {
            int component = wsh_theme_component(layout.u.arr.elem[j].u.s);
            if (component < 0 || (mask & (1U << component))) return reject(error, capacity, "invalid or repeated layout component", layouts[i]);
            mask |= 1U << component;
        }
    }
    if (!(mask & (1U << 4))) return reject(error, capacity, "prompt-character must be present", "");
    for (size_t i = 0; i < 5; ++i) {
        char path[128]; snprintf(path, sizeof(path), "%s.enabled", components[i]);
        if (!!(mask & (1U << i)) != wsh_theme_get(theme, path).u.boolean) return reject(error, capacity, "layout and enabled state disagree", components[i]);
        snprintf(path, sizeof(path), "segments.%s", components[i]);
        if (wsh_theme_get(theme, path).type == TOML_UNKNOWN) continue;
        if (!(mask & (1U << i))) return reject(error, capacity, "segment style requires an enabled component", components[i]);
        snprintf(path, sizeof(path), "segments.%s.dirty-background", components[i]);
        if (i != 2 && wsh_theme_get(theme, path).type != TOML_UNKNOWN) return reject(error, capacity, "dirty-background is supported only for Git", components[i]);
    }
    return 0;
}
int wsh_theme_parse(const char *source, size_t length, struct wsh_theme *theme, char *error, size_t capacity)
{
    memset(theme, 0, sizeof(*theme));
    if (length > THEME_LIMIT) return reject(error, capacity, "theme exceeds 65536 bytes", "");
    toml_option_t options = toml_default_option();
    options.check_utf8 = true; options.allow_uint64 = true;
    toml_set_option(options);
    theme->parsed = toml_parse(source, (int)length);
    if (!theme->parsed.ok) {
        reject(error, capacity, "invalid theme", theme->parsed.errmsg);
        wsh_theme_free(theme); return -1;
    }
    if (validate(theme, error, capacity)) { wsh_theme_free(theme); return -1; }
    return 0;
}
int wsh_theme_load(const char *path, struct wsh_theme *theme, char *error, size_t capacity)
{
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    struct stat st;
    if (fd < 0) return reject(error, capacity, "could not open regular theme", path);
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size > THEME_LIMIT) { close(fd); return reject(error, capacity, "theme must be a regular file of at most 65536 bytes", ""); }
    char *source = malloc(THEME_LIMIT + 1);
    if (!source) { close(fd); return reject(error, capacity, "out of memory", ""); }
    size_t used = 0; ssize_t count;
    while (used <= THEME_LIMIT) {
        count = read(fd, source + used, THEME_LIMIT + 1 - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) { close(fd); free(source); return reject(error, capacity, "could not read theme", path); }
        if (!count) break;
        used += (size_t)count;
    }
    close(fd);
    int status = wsh_theme_parse(source, used, theme, error, capacity);
    free(source); return status;
}
