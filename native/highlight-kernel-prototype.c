/* Private command classifier; the reference owns grammar, styles and fallback. */
#define _GNU_SOURCE 1
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"

static int contains(char *table, char *key)
{
    Param parameter = (Param)paramtab->getnode(paramtab, table);
    if (!parameter || PM_TYPE(parameter->node.flags) != PM_HASHED) return 0;
    HashTable values = parameter->gsu.h->getfn(parameter);
    if (!values) return 0;
    HashNode value = values->getnode(values, key);
    return value && !(value->flags & PM_UNSET);
}
static int classify(char *name, char **args, Options options, int function)
{
    (void)name; (void)options; (void)function;
    pushheap();
    char *word = args[0], *type = NULL;
    int aliases_allowed = strcmp(args[1], "0") != 0;
    if (contains("aliases", word)) setiparam("may_cache", 0);
    char *dot = strrchr(word, '.');
    if (aliases_allowed && contains("galiases", word)) type = "global alias";
    else if (aliases_allowed && contains("aliases", word)) type = "alias";
    else if (dot && dot != word && contains("saliases", dot + 1)) type = "suffix alias";
    else {
        char **words = getaparam("reswords");
        if (words) for (; *words; ++words) if (!strcmp(*words, word)) { type = "reserved"; break; }
        if (!type && contains("functions", word)) type = "function";
        if (!type && contains("builtins", word)) type = "builtin";
        if (!type && contains("commands", word)) type = "command";
    }
    if (type) setsparam("REPLY", ztrdup(type));
    popheap();
    return type ? 0 : 1;
}
static struct builtin builtins[] = {BUILTIN("wsh-highlight-type", 0, classify, 2, 2, 0, NULL, NULL)};
static struct features module_features = {builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) { (void)m; return 0; }
int boot_(Module m) { (void)m; return 0; }
int features_(Module m, char ***features) { *features = featuresarray(m, &module_features); return 0; }
int enables_(Module m, int **enables) { return handlefeatures(m, &module_features, enables); }
int cleanup_(Module m) { return setfeatureenables(m, &module_features, NULL); }
int finish_(Module m) { (void)m; return 0; }
