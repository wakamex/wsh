#ifndef WSH_THEME_H
#define WSH_THEME_H
#include "tomlc17.h"
#include <stddef.h>
#include <stdint.h>

struct wsh_theme { toml_result_t parsed; };
int wsh_theme_parse(const char *source, size_t length, struct wsh_theme *theme, char *error, size_t capacity);
int wsh_theme_load(const char *path, struct wsh_theme *theme, char *error, size_t capacity);
void wsh_theme_free(struct wsh_theme *theme);
toml_datum_t wsh_theme_get(const struct wsh_theme *theme, const char *path);
uint64_t wsh_theme_uint(toml_datum_t value);
int wsh_theme_component(const char *name);
int wsh_theme_color(const char *name);
#endif
