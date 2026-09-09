/* Private native editor actions and history selection; Zsh retains async adapters. */
#define _GNU_SOURCE 1
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"

static int suggest(char *name, char **args, Options options, int function)
{
    (void)name; (void)options; (void)function;
    pushheap();
    char *prefix = quotestring(args[0], QT_BACKSLASH_PATTERN);
    char *ignore = getsparam("ZSH_AUTOSUGGEST_HISTORY_IGNORE");
    char *pattern = dyncat(prefix, "*");
    if (ignore && *ignore) pattern = zhtricat("(", pattern, zhtricat(")~(", ignore, ")"));
    tokenize(pattern);
    Patprog compiled = patcompile(pattern, 0, NULL);
    char *result = "";
    Histent entry = gethistent(addhistnum(curhist, -1, HIST_FOREIGN), GETHIST_UPWARD);
    for (; entry; entry = up_histent(entry)) {
        /* A failed history subscript pattern leaves native scanning unfiltered. */
        if (!compiled || pattry(compiled, entry->node.nam)) { result = entry->node.nam; break; }
    }
    setsparam("suggestion", ztrdup(result));
    popheap();
    return 0;
}
static char *value(const char *name)
{
    char *s = getsparam((char *)name); return s ? s : "";
}
static void assign(const char *name, const char *text)
{
    setsparam((char *)name, ztrdup(text));
}
static int invoke(const char *name, char **args)
{
    Shfunc fn = (Shfunc)shfunctab->getnode(shfunctab, name);
    if (!fn) return 1;
    LinkList list = newlinklist();
    addlinknode(list, dupstring(name));
    if (args) for (; *args; ++args) addlinknode(list, dupstring(*args));
    return doshfunc(fn, list, 0);
}
static int characters(char *s)
{
    return mb_metastrlenend(s, 0, NULL);
}
static char *after_chars(char *s, zlong count)
{
    mbstate_t state; memset(&state, 0, sizeof(state));
    while (*s && count-- > 0) {
        int n = mb_metacharlenconv_r(s, NULL, &state);
        s += n > 0 ? n : 1;
    }
    return s;
}
static int exists(const char *name)
{
    Param p = (Param)paramtab->getnode(paramtab, name);
    return p && !(p->node.flags & PM_UNSET);
}
static int action_impl(char *name, char **args, Options options, int function)
{
    (void)name; (void)options; (void)function;
    char *action = *args++;
    int result = 0;
    if (!strcmp(action, "suggest")) {
        char *buffer = value("BUFFER"), *s = *args ? *args : "";
        assign("POSTDISPLAY", *buffer && *s ? (strncmp(s, buffer, strlen(buffer)) ? s : s+strlen(buffer)) : "");
        return 0;
    }
    if (!strcmp(action, "fetch")) return invoke("_wsh_autosuggest_reference_fetch", args);
    if (!strcmp(action, "toggle")) action = exists("_ZSH_AUTOSUGGEST_DISABLED") ? "enable" : "disable";
    if (!strcmp(action, "enable")) {
        unsetparam("_ZSH_AUTOSUGGEST_DISABLED");
        return *value("BUFFER") ? invoke("_zsh_autosuggest_fetch", NULL) : 0;
    }
    if (!strcmp(action, "disable")) { assign("_ZSH_AUTOSUGGEST_DISABLED", ""); action = "clear"; }
    if (!strcmp(action, "clear")) {
        assign("POSTDISPLAY", "");
        return invoke("_zsh_autosuggest_invoke_original_widget", args);
    }
    char *original = dupstring(value("BUFFER")), *display = dupstring(value("POSTDISPLAY"));
    int length = characters(original);
    int vi = !strcmp(value("KEYMAP"), "vicmd");
    if (!strcmp(action, "modify")) {
        assign("POSTDISPLAY", "");
        result = invoke("_zsh_autosuggest_invoke_original_widget", args);
        if (getiparam("PENDING") > 0 || getiparam("KEYS_QUEUED_COUNT") > 0) { assign("POSTDISPLAY", display); return result; }
        char *buffer = value("BUFFER");
        if (!strncmp(buffer, original, strlen(original)) && !strncmp(display, buffer+strlen(original), strlen(buffer)-strlen(original))) {
            assign("POSTDISPLAY", display+strlen(buffer)-strlen(original)); return result;
        }
        if (exists("_ZSH_AUTOSUGGEST_DISABLED")) return 0;
        char *maximum = value("ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE");
        if (*buffer && (!*maximum || characters(buffer) <= mathevali(maximum))) invoke("_zsh_autosuggest_fetch", NULL);
        return result;
    }
    if (!strcmp(action, "accept")) {
        if (getiparam("CURSOR") != length-vi || !*display) return invoke("_zsh_autosuggest_invoke_original_widget", args);
        assign("BUFFER", dyncat(original, display)); assign("POSTDISPLAY", "");
        result = invoke("_zsh_autosuggest_invoke_original_widget", args);
        setiparam("CURSOR", characters(value("BUFFER"))-(!strcmp(value("KEYMAP"), "vicmd")));
        return result;
    }
    if (!strcmp(action, "execute")) {
        assign("BUFFER", dyncat(original, display)); assign("POSTDISPLAY", "");
        char *accept[] = {"accept-line", NULL};
        return invoke("_zsh_autosuggest_invoke_original_widget", accept);
    }
    if (!strcmp(action, "partial_accept")) {
        assign("BUFFER", dyncat(original, display));
        result = invoke("_zsh_autosuggest_invoke_original_widget", args);
        zlong cursor = getiparam("CURSOR")+(!strcmp(value("KEYMAP"), "vicmd"));
        if (cursor > length) {
            char *buffer = dupstring(value("BUFFER")), *suffix = after_chars(buffer, cursor);
            assign("POSTDISPLAY", suffix); *suffix = 0; assign("BUFFER", buffer);
        } else assign("BUFFER", original);
        return result;
    }
    return 1;
}
static int action(char *name, char **args, Options options, int function)
{
    pushheap();
    int result = action_impl(name, args, options, function);
    popheap(); return result;
}
static struct builtin builtins[] = {
    BUILTIN("wsh-history-suggest", 0, suggest, 1, 1, 0, NULL, NULL),
    BUILTIN("wsh-autosuggest-action", 0, action, 1, -1, 0, NULL, NULL)
};
static struct features module_features = {builtins, 2, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) { (void)m; return 0; }
int boot_(Module m) { (void)m; return 0; }
int features_(Module m, char ***features) { *features = featuresarray(m, &module_features); return 0; }
int enables_(Module m, int **enables) { return handlefeatures(m, &module_features, enables); }
int cleanup_(Module m) { return setfeatureenables(m, &module_features, NULL); }
int finish_(Module m) { (void)m; return 0; }
