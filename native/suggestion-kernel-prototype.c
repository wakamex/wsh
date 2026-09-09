/* Private history strategy; the existing plugin retains async and ZLE state. */
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
static struct builtin builtins[] = {BUILTIN("wsh-history-suggest", 0, suggest, 1, 1, 0, NULL, NULL)};
static struct features module_features = {builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) { (void)m; return 0; }
int boot_(Module m) { (void)m; return 0; }
int features_(Module m, char ***features) { *features = featuresarray(m, &module_features); return 0; }
int enables_(Module m, int **enables) { return handlefeatures(m, &module_features, enables); }
int cleanup_(Module m) { return setfeatureenables(m, &module_features, NULL); }
int finish_(Module m) { (void)m; return 0; }
