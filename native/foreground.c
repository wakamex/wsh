/* Capture native argv once; argument values are never parsed as shell source. */
static char **wsh_foreground_values;
static int wsh_foreground_count;
static char *wsh_foreground_arguments[5];
static char wsh_foreground_interactive[] = "-i";
static char wsh_foreground_stdin[] = "-s";
static char wsh_foreground_login[] = "-l";

static int
wsh_foreground_parse(int argc, char **arguments)
{
    int first = 2, login = 0, count = 0;
    if (first < argc && !strcmp(arguments[first], "--login")) {
        login = 1;
        ++first;
    }
    if (first >= argc || strcmp(arguments[first], "--") || first + 1 >= argc || !*arguments[first + 1]) {
        fputs("usage: wsh --wsh-run [--login] -- <command> [arguments...]\n", stderr);
        return 2;
    }
    wsh_foreground_count = argc - first - 1;
    wsh_foreground_values = arguments + first + 1;
    wsh_foreground_arguments[count++] = arguments[0];
    wsh_foreground_arguments[count++] = wsh_foreground_interactive;
    wsh_foreground_arguments[count++] = wsh_foreground_stdin;
    if (login)
        wsh_foreground_arguments[count++] = wsh_foreground_login;
    wsh_foreground_arguments[count] = NULL;
    unsetenv("WSH_RUN_FOREGROUND");
    return -1;
}

static void
wsh_foreground_run(void)
{
    char **values;
    int i;
    if (!wsh_foreground_count)
        return;
    values = (char **)zalloc((wsh_foreground_count + 1) * sizeof(char *));
    for (i = 0; i < wsh_foreground_count; ++i)
        values[i] = metafy(wsh_foreground_values[i], -1, META_DUP);
    values[i] = NULL;
    wsh_foreground_count = 0;
    if (!setaparam("_WSH_FOREGROUND_ARGV", values)) {
        lastval = 127;
        return;
    }
    zleentry(ZLE_CMD_PREEXEC);
    execstring("() { builtin emulate -L zsh -o no_aliases; \"${_WSH_FOREGROUND_ARGV[@]}\"; }", 0, 0, "wsh-foreground");
    zleentry(ZLE_CMD_POSTEXEC);
    unsetparam("_WSH_FOREGROUND_ARGV");
}
