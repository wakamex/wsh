#ifndef WSH_RENDER_H
#define WSH_RENDER_H
#include "theme.h"
#include "git.h"
struct wsh_renderer {
    const struct wsh_theme *theme;
    char *home, *user, *host, *last_cwd, *last_git;
    int ssh;
};
void wsh_renderer_init(struct wsh_renderer *renderer, const struct wsh_theme *theme);
void wsh_renderer_reset(struct wsh_renderer *renderer);
void wsh_renderer_free(struct wsh_renderer *renderer);
void wsh_render(struct wsh_renderer *renderer, const char *cwd, const struct wsh_git_result *git,
                int exit_status, int has_duration, uint64_t duration_ms, int privileged,
                char **left, char **right);
#endif
