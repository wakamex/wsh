#define _POSIX_C_SOURCE 200809L
#include "theme.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
static uint64_t now(void)
{
    struct timespec value;
    clock_gettime(CLOCK_MONOTONIC, &value);
    return (uint64_t)value.tv_sec * 1000000000 + (uint64_t)value.tv_nsec;
}
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (!file) return 2;
    char source[65537], error[512], request[8];
    size_t length = fread(source, 1, sizeof(source), file);
    if (ferror(file) || length == sizeof(source)) { fclose(file); return 2; }
    fclose(file);
    while (fgets(request, sizeof(request), stdin)) {
        uint64_t started = now();
        if (request[0] == 'p') {
            struct wsh_theme theme;
            if (wsh_theme_parse(source, length, &theme, error, sizeof(error))) { fprintf(stderr, "%s\n", error); return 1; }
            wsh_theme_free(&theme);
        }
        uint64_t elapsed = now() - started;
        printf("%llu\n", (unsigned long long)elapsed); fflush(stdout);
    }
    return 0;
}
