/* Private lazy-filter comparison. Zsh retains matching and editor ownership. */
#define _GNU_SOURCE 1
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"

#define PREFIX "_history_substring_search_"
static int next_match(char *name, char **args, Options options, int function)
{
    (void)name; (void)args; (void)options; (void)function;
    char **raw = getaparam(PREFIX "raw_matches");
    zlong index = getiparam(PREFIX "raw_match_index");
    char *unique = getsparam("HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE");
    int filter_enabled = !isset(HISTIGNOREALLDUPS) && unique && *unique;
    Param history = (Param)paramtab->getnode(paramtab, "history");
    Param filter = (Param)paramtab->getnode(paramtab, PREFIX "unique_filter");
    if (!raw || index < 0 || !history || !filter ||
        PM_TYPE(history->node.flags) != PM_HASHED || PM_TYPE(filter->node.flags) != PM_HASHED) return 1;
    HashTable entries = history->gsu.h->getfn(history);
    HashTable seen = filter->gsu.h->getfn(filter);
    if (!entries) return 1;
    if (filter_enabled && !seen) {
        seen = newparamtable(17, filter->node.nam);
        filter->gsu.h->setfn(filter, seen);
    }
    size_t count = (size_t)arrlen(raw);
    while ((size_t)index < count) {
        char *key = raw[index++];
        setiparam(PREFIX "raw_match_index", index);
        if (filter_enabled) {
            pushheap();
            Param entry = (Param)entries->getnode(entries, key);
            char *text = entry ? entry->gsu.s->getfn(entry) : "";
            Param old = (Param)seen->getnode(seen, text);
            if (old && *old->gsu.s->getfn(old)) { popheap(); continue; }
            queue_signals();
            HashTable saved = paramtab;
            paramtab = seen;
            Param item = old ? old : createparam(text, PM_SCALAR | PM_HASHELEM);
            paramtab = saved;
            if (item) item->gsu.s->setfn(item, ztrdup("1"));
            unqueue_signals();
            popheap();
            if (!item) return 1;
        }
        char **matches = getaparam(PREFIX "matches");
        size_t n = matches ? (size_t)arrlen(matches) : 0;
        char **updated = zalloc((n + 2) * sizeof(char *));
        for (size_t i = 0; i < n; ++i) updated[i] = ztrdup(matches[i]);
        updated[n] = ztrdup(key); updated[n + 1] = NULL;
        setaparam(PREFIX "matches", updated);
        return 0;
    }
    return 1;
}
static struct builtin builtins[] = {BUILTIN("wsh-history-next", 0, next_match, 0, 0, 0, NULL, NULL)};
static struct features module_features = {builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) { (void)m; return 0; }
int boot_(Module m) { (void)m; return 0; }
int features_(Module m, char ***features) { *features = featuresarray(m, &module_features); return 0; }
int enables_(Module m, int **enables) { return handlefeatures(m, &module_features, enables); }
int cleanup_(Module m) { return setfeatureenables(m, &module_features, NULL); }
int finish_(Module m) { (void)m; return 0; }
