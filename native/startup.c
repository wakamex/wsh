/* Optional Wsh defaults surround Zsh-owned startup; user files stay native. */
static char *wsh_root;
static int wsh_integration;

static void
wsh_prepend_path(char *name, char *directory)
{
    char **old = getaparam(name), **paths;
    int count = old ? arrlen(old) : 0, i, used = 1;
    paths = (char **)zalloc((count + 2) * sizeof(char *));
    paths[0] = directory;
    for (i = 0; i < count; ++i)
        if (strcmp(old[i], directory))
            paths[used++] = ztrdup(old[i]);
    paths[used] = NULL;
    setaparam(name, paths);
}

static void
wsh_resource_paths(void)
{
    if (!wsh_root)
        return;
    wsh_prepend_path("module_path", tricat(wsh_root, "/lib/zsh/", ZSH_VERSION));
    wsh_prepend_path("fpath", tricat(wsh_root, "/share/zsh/" ZSH_VERSION, "/functions"));
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

static void
wsh_profile(char *event)
{
    char *command;
    int saved_status = lastval;
    if (!wsh_integration || !shfunctab->getnode(shfunctab, "_wsh_profile_event"))
        return;
    command = bicat("_wsh_profile_event ", event);
    execstring(command, 1, 0, "wsh-profile");
    zsfree(command);
    lastval = saved_status;
}

static void
wsh_setup(void)
{
    char *exepath = getsparam("ZSH_EXEPATH"), *slash, *file;
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
    Param theme;
    if (!wsh_integration)
        return;
    theme = (Param)paramtab->getnode(paramtab, "WSH_THEME");
    if (theme) {
        theme->node.flags &= ~PM_EXPORTED;
        if (theme->env)
            delenv(theme);
    }
}
