#include "wsh-completion.c"
#include "wsh-history.c"
#include "wsh-directory.c"

/* Optional Wsh defaults surround Zsh-owned startup; user files stay native. */
static char *wsh_root;
static int wsh_integration;

static void
wsh_prepend_path(char *name, char *directory, char *compiled, char *site)
{
    char **old = getaparam(name), **paths;
    int count = old ? arrlen(old) : 0, i, used = 1;
    paths = (char **)zalloc((count + 2) * sizeof(char *));
    paths[0] = directory;
    for (i = 0; i < count; ++i) {
        if (!strcmp(old[i], directory) || (compiled && !strcmp(old[i], compiled)))
            continue;
#ifdef SITEFPATH_DIR
        if (site && !strcmp(old[i], SITEFPATH_DIR)) {
            paths[used++] = ztrdup(site);
            continue;
        }
#endif
        paths[used++] = ztrdup(old[i]);
    }
    paths[used] = NULL;
    setaparam(name, paths);
}

static void
wsh_resource_paths(void)
{
    if (!wsh_root)
        return;
    wsh_prepend_path("module_path", tricat(wsh_root, "/lib/zsh/", ZSH_VERSION), MODULE_DIR, NULL);
    char *site = tricat(wsh_root, "/share/zsh/", "site-functions");
    /* An explicitly exported FPATH belongs to the user, including its fallbacks. */
    int explicit_fpath = getenv("FPATH") != NULL;
    wsh_prepend_path("fpath", tricat(wsh_root, "/share/zsh/" ZSH_VERSION, "/functions"),
                     explicit_fpath ? NULL : FPATH_DIR, explicit_fpath ? NULL : site);
    zsfree(site);
}

static void
wsh_source(char *name)
{
    char *file;
    int saved_status = lastval;
    if (!wsh_integration)
        return;
    file = tricat(wsh_root, "/share/wsh/", name);
    source(file);
    zsfree(file);
    lastval = saved_status;
}

static void wsh_profile(char *event);
static void wsh_profile_flush_startup(void);
static int wsh_profile_active(void);

static void
wsh_unexport(char *name)
{
    Param parameter = (Param)paramtab->getnode(paramtab, name);
    if (parameter) {
        parameter->node.flags &= ~PM_EXPORTED;
        if (parameter->env)
            delenv(parameter);
    }
}

static void
wsh_profile_parameters(void)
{
    wsh_profile("native-startup-enter");
    if (wsh_profile_active()) {
        char **name;
        static char *names[] = {
            "WSH_PROFILE_DIRECTORY", "WSH_PROFILE_FILE", "WSH_PROFILE_ZPROF_FILE",
            "WSH_PROFILE_REPORTER", "WSH_PROFILE_FUNCTIONS", "WSH_PROFILE_STARTED_UNIX_US",
            "WSH_PROFILE_STARTED_AT", "WSH_TRACE_FILE", NULL
        };
        for (name = names; *name; ++name)
            wsh_unexport(*name);
    }
}

static void
wsh_setup(void)
{
    char *exepath = getsparam("ZSH_EXEPATH"), *slash, *file;
    (void)addbuiltins("wsh", wsh_completion_builtins, 1);
    (void)addbuiltins("wsh", wsh_history_builtins, 1);
    (void)addbuiltins("wsh", wsh_directory_builtins, 1);
    if (!exepath || isset(PRIVILEGED))
        return;
    wsh_root = ztrdup(exepath);
    slash = strrchr(wsh_root, '/');
    if (!slash)
        goto unavailable;
    *slash = '\0';
    slash = strrchr(wsh_root, '/');
    if (!slash)
        goto unavailable;
    *slash = '\0';
    /* Relocation is needed even when rc files and optional defaults are off. */
    wsh_resource_paths();
    if (unset(RCS))
        return;
    file = tricat(wsh_root, "/share/wsh/", "native-before.zsh");
    if (access(unmeta(file), R_OK)) {
        zsfree(file);
        goto unavailable;
    }
    zsfree(file);
    wsh_integration = 1;
    setsparam("WSH_BUNDLE_ROOT", ztrdup(wsh_root));
    wsh_source("native-before.zsh");
    return;

unavailable:
    zsfree(wsh_root);
    wsh_root = NULL;
    {
        char *name = strrchr(argv0, '/');
        name = name ? name + 1 : argv0;
        if (!strcmp(name, "wsh") || !strcmp(name, "-wsh"))
            zwarn("Wsh integration unavailable; starting Zsh without Wsh defaults");
    }
}

static void
wsh_finish(void)
{
    wsh_profile_flush_startup();
    if (!wsh_integration)
        return;
    wsh_unexport("WSH_THEME");
}
