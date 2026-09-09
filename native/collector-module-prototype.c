/* Disposable ownership probe, not a shipped Zsh module. */
#define _GNU_SOURCE 1
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "git.h"
#include "zsh.mdh"
#include <pthread.h>
#include <stdatomic.h>

static struct sigaction saved_sigchld;
static int suppressed;
static pthread_t worker;
static atomic_int completed, cancel_request;
static int active;
static char *directory;
static struct wsh_git_result result;
static int cancelled(void *unused)
{
    (void)unused;
    return atomic_load(&cancel_request);
}
static void *collect(void *unused)
{
    (void)unused;
    wsh_git_collect(directory, "git", cancelled, NULL, &result);
    atomic_store(&completed, 1);
    return NULL;
}
static int probe(char *name, char **args, Options options, int function)
{
    (void)name;
    (void)options;
    (void)function;
    if (!strcmp(args[0], "start") && args[1] && !args[2] && !active) {
        directory = strdup(unmeta(args[1]));
        if (!directory)
            return 1;
        atomic_store(&completed, 0);
        atomic_store(&cancel_request, 0);
        if (pthread_create(&worker, NULL, collect, NULL)) {
            free(directory);
            directory = NULL;
            return 1;
        }
        active = 1;
        return 0;
    }
    if (!strcmp(args[0], "poll") && !args[1]) {
        if (!active || !atomic_load(&completed))
            return 1;
        pthread_join(worker, NULL);
        active = 0;
        printf("WSH_PROBE:%d:%llu:%s\n", result.found, (unsigned long long)result.child_processes,
               result.error ? result.error : "ok");
        wsh_git_free(&result);
        free(directory);
        directory = NULL;
        return 0;
    }
    if (!strcmp(args[0], "cancel") && !args[1] && active) {
        atomic_store(&cancel_request, 1);
        return 0;
    }
    return 1;
}
static struct builtin builtins[] = {BUILTIN("wsh-collector-probe", 0, probe, 1, 2, 0, NULL, NULL)};
static struct features module_features = {builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module module)
{
    (void)module;
    if (getenv("WSH_PROBE_NO_SIGCHLD")) {
        struct sigaction action = {0};
        action.sa_handler = SIG_DFL;
        sigemptyset(&action.sa_mask);
        if (sigaction(SIGCHLD, &action, &saved_sigchld))
            return 1;
        suppressed = 1;
    }
    return 0;
}
int boot_(Module module)
{
    (void)module;
    return 0;
}
int features_(Module module, char ***features)
{
    *features = featuresarray(module, &module_features);
    return 0;
}
int enables_(Module module, int **enables)
{
    return handlefeatures(module, &module_features, enables);
}
int cleanup_(Module module)
{
    if (active)
        return 1;
    return setfeatureenables(module, &module_features, NULL);
}
int finish_(Module module)
{
    (void)module;
    if (active)
        return 1;
    if (suppressed)
        sigaction(SIGCHLD, &saved_sigchld, NULL);
    return 0;
}
