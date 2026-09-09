/* Private matching/navigation owner; Zsh retains editor and highlight adapters. */
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
static char *scalar(const char *name)
{
    char *s = getsparam((char *)name);
    return s ? s : "";
}
static void scalar_set(const char *name, const char *value)
{
    setsparam((char *)name, ztrdup(value));
}
static void empty_array(const char *name)
{
    char **a = zalloc(sizeof(char *)); *a = NULL;
    setaparam((char *)name, a);
}
static int begin(char *name, char **args, Options options, int function)
{
    (void)name; (void)args; (void)options; (void)function;
    pushheap();
    char *buffer = dupstring(scalar("BUFFER"));
    scalar_set(PREFIX "refresh_display", "");
    scalar_set(PREFIX "query_highlight", "");
    if (*buffer && !strcmp(buffer, scalar(PREFIX "result"))) { popheap(); return 0; }
    scalar_set(PREFIX "result", "");
    scalar_set(PREFIX "query", buffer);
    char **parts;
    if (*scalar("HISTORY_SUBSTRING_SEARCH_FUZZY")) parts = spacesplit(buffer, 0, 1, 0);
    else { parts = zhalloc(2*sizeof(char *)); parts[0] = *buffer ? buffer : NULL; parts[1] = NULL; }
    setaparam(PREFIX "query_parts", zarrdup(parts));
    size_t n = (size_t)arrlen(parts);
    char **escaped = zhalloc((n+1)*sizeof(char *));
    for (size_t i = 0; i < n; ++i) escaped[i] = quotestring(parts[i], QT_BACKSLASH_PATTERN);
    escaped[n] = NULL;
    char *pattern = zhtricat("(#", scalar("HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS"), ")");
    pattern = dyncat(pattern, *scalar("HISTORY_SUBSTRING_SEARCH_PREFIXED") ? "" : "*");
    pattern = zhtricat(pattern, zjoin(escaped, '*', 1), "*");
    tokenize(pattern);
    Patprog compiled = patcompile(pattern, 0, NULL);
    char **keys = NULL; size_t count = 0, capacity = 0;
    if (*buffer) for (Histent h = gethistent(addhistnum(curhist, -1, HIST_FOREIGN), GETHIST_UPWARD); h; h = up_histent(h)) {
        if (compiled && !pattry(compiled, h->node.nam)) continue;
        if (count == capacity) {
            size_t cap = capacity ? capacity*2 : 64;
            if (cap < capacity || cap > SIZE_MAX/sizeof(char *)) { free(keys); popheap(); return 1; }
            void *next = realloc(keys, cap*sizeof(char *));
            if (!next) { free(keys); popheap(); return 1; }
            keys = next; capacity = cap;
        }
        char key[32]; snprintf(key, sizeof(key), "%lld", (long long)h->histnum);
        keys[count++] = dupstring(key);
    }
    char **raw = zalloc((count+1)*sizeof(char *));
    for (size_t i = 0; i < count; ++i) raw[i] = ztrdup(keys[i]);
    raw[count] = NULL; free(keys);
    setaparam(PREFIX "raw_matches", raw);
    setiparam(PREFIX "raw_match_index", 0);
    empty_array(PREFIX "matches");
    char **empty = zalloc(sizeof(char *)); *empty = NULL;
    sethparam(PREFIX "unique_filter", empty);
    setiparam(PREFIX "match_index", !strcmp(scalar("WIDGET"), "history-substring-search-down") ? 1 : 0);
    popheap(); return 0;
}
static int navigate(char *name, char **args, Options options, int function)
{
    (void)name; (void)options; (void)function;
    int down = !strcmp(args[0], "down");
    scalar_set(PREFIX "refresh_display", "1");
    for (;;) {
        zlong index = getiparam(PREFIX "match_index");
        char **matches = getaparam(PREFIX "matches");
        zlong count = matches ? arrlen(matches) : 0;
        int found = 0;
        if (down) {
            if (index >= 1) { found = index > 1; --index; }
        } else if (index <= count) {
            found = index < count || next_match(NULL, NULL, NULL, 0) == 0;
            ++index;
            matches = getaparam(PREFIX "matches");
        }
        setiparam(PREFIX "match_index", index);
        if (found) {
            Param hp = (Param)paramtab->getnode(paramtab, "history");
            if (!hp || PM_TYPE(hp->node.flags) != PM_HASHED) return 1;
            pushheap();
            HashTable ht = hp->gsu.h->getfn(hp);
            Param entry = ht ? (Param)ht->getnode(ht, matches[index-1]) : NULL;
            scalar_set("BUFFER", entry ? entry->gsu.s->getfn(entry) : "");
            popheap();
            scalar_set(PREFIX "query_highlight", scalar("HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND"));
        } else {
            scalar_set("BUFFER", scalar(PREFIX "query"));
            scalar_set(PREFIX "query_highlight", scalar("HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_NOT_FOUND"));
        }
        if (!found || isset(HISTIGNOREALLDUPS) || *scalar("HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE") ||
            !isset(HISTFINDNODUPS) || strcmp(scalar("BUFFER"), scalar(PREFIX "result"))) return 0;
    }
}
static struct builtin builtins[] = {
    BUILTIN("wsh-history-next", 0, next_match, 0, 0, 0, NULL, NULL),
    BUILTIN("wsh-history-begin", 0, begin, 0, 0, 0, NULL, NULL),
    BUILTIN("wsh-history-navigate", 0, navigate, 1, 1, 0, NULL, NULL)
};
static struct features module_features = {builtins, 3, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) { (void)m; return 0; }
int boot_(Module m) { (void)m; return 0; }
int features_(Module m, char ***features) { *features = featuresarray(m, &module_features); return 0; }
int enables_(Module m, int **enables) { return handlefeatures(m, &module_features, enables); }
int cleanup_(Module m) { return setfeatureenables(m, &module_features, NULL); }
int finish_(Module m) { (void)m; return 0; }
