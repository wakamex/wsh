#include "theme.h"
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv)
{
    struct wsh_theme theme;
    char error[512];
    if (argc != 3 || strcmp(argv[1], "validate-theme")) {
        fputs("usage: wsh-theme-prototype validate-theme <theme.toml>\n", stderr); return 1;
    }
    if (wsh_theme_load(argv[2], &theme, error, sizeof(error))) { fprintf(stderr, "error: %s\n", error); return 1; }
    puts(wsh_theme_get(&theme, "id").u.s);
    wsh_theme_free(&theme); return 0;
}
