#ifndef WSH_GIT_H
#define WSH_GIT_H
#include <stdint.h>

/* Temporary typed bridge: the existing runtime still owns protocol and rendering. */
struct wsh_git_result {
    char *root, *branch, *detached_sha, *exact_tag, *error;
    uint64_t ahead, behind, discovery_ns, process_ns, parsing_ns, child_processes;
    int found, staged, modified, untracked, operation, worktree, cancelled;
};

int wsh_git_collect(const char *cwd, const char *git, int (*cancel)(void *), void *context,
                    struct wsh_git_result *result);
int wsh_git_operation(const char *directory);
void wsh_git_free(struct wsh_git_result *result);
#endif
