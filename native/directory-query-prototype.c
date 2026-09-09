/* Private matching-kernel comparison; Zsh-z retains data and editor ownership. */
#define _GNU_SOURCE 1
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"
#include <sys/stat.h>

static int greater(mnumber a, mnumber b)
{
    if (a.type == MN_INTEGER && b.type == MN_INTEGER) return a.u.l > b.u.l;
    double x = a.type == MN_INTEGER ? (double)a.u.l : a.u.d;
    double y = b.type == MN_INTEGER ? (double)b.u.l : b.u.d;
    return x > y;
}
static int keep_path(char *path, char **keep)
{
    struct stat st;
    if (!stat(unmeta(path), &st) && S_ISDIR(st.st_mode)) return 1;
    if (keep) for (; *keep; ++keep) {
        size_t n = strlen(*keep);
        if (!strcmp(*keep, "/") || !strcmp(path, *keep) || (!strncmp(path, *keep, n) && path[n] == '/')) return 1;
    }
    return 0;
}
static int query(char *name, char **args, Options options, int function)
{
    (void)name; (void)args; (void)options; (void)function;
    char **entries = getaparam("lines"), **keep = getaparam("ZSHZ_KEEP_DIRS");
    char *q = getsparam("q"), *lower = getsparam("q_lower"), *method = getsparam("method");
    char *case_mode = getsparam("ZSHZ_CASE");
    if (!entries || !q || !lower || !method) return 1;
    if (!case_mode) case_mode = "";
    int ignore = !strcmp(case_mode, "ignore"), smart = !strcmp(case_mode, "smart");
    int lowercase_query = getiparam("is_lowercase_query") != 0, trail = getiparam("trail") != 0;
    pushheap();
    char *pattern = dupstring(q), *lower_pattern = dupstring(lower);
    tokenize(pattern); tokenize(lower_pattern);
    Patprog sensitive = patcompile(pattern, 0, NULL), insensitive = patcompile(lower_pattern, 0, NULL);
    if (!sensitive || !insensitive) { popheap(); return 1; }
    size_t count = (size_t)arrlen(entries), used[2] = {0, 0};
    if (count > (SIZE_MAX / sizeof(char *) - 1) / 2) { popheap(); return 1; }
    char **values[2] = {(char **)zshcalloc((count * 2 + 1) * sizeof(char *)), (char **)zshcalloc((count * 2 + 1) * sizeof(char *))};
    char *best[2] = {NULL, NULL};
    mnumber highest[2]; highest[0].type = highest[1].type = MN_INTEGER; highest[0].u.l = highest[1].u.l = -9999999999LL;
    int failed = 0;
    for (size_t i = 0; i < count; ++i) {
        pushheap();
        char *path = dupstring(entries[i]), *first = strchr(path, '|'), *last = strrchr(path, '|');
        if (!first || first == last) { popheap(); continue; }
        *first++ = 0; *last++ = 0;
        if (!keep_path(path, keep)) { popheap(); continue; }
        if (!*first || strspn(first, "0123456789.,") != strlen(first) || !*last || strspn(last, "0123456789") != strlen(last)) { popheap(); continue; }
        setsparam("rank_field", ztrdup(first)); setsparam("time_field", ztrdup(last));
        const char *expression = !strcmp(method, "rank") ? "rank_field" : !strcmp(method, "time") ? "time_field - now" : "10000 * rank_field * (3.75 / ((0.0001 * (now - time_field) + 1) + 0.25))";
        mnumber rank = matheval(dupstring(expression));
        if (errflag) { popheap(); failed = 1; break; }
        char *normalized = path;
        if (trail) {
            normalized = zhalloc(strlen(path) + 2); strcpy(normalized, path);
            size_t n = strlen(normalized); if (n && normalized[n - 1] == '/') --n;
            normalized[n++] = '/'; normalized[n] = 0;
        }
        char *lower_path = casemodify(normalized, CASMOD_LOWER); int group = -1;
        if (smart && lowercase_query && pattry(insensitive, lower_path)) group = 1;
        else if (!ignore && pattry(sensitive, normalized)) group = 0;
        else if (!smart && pattry(insensitive, lower_path)) group = 1;
        if (group >= 0) {
            char number[64], *score;
            if (!strcmp(method, "rank")) score = first;
            else if (rank.type == MN_INTEGER) { snprintf(number, sizeof(number), "%lld", (long long)rank.u.l); score = number; }
            else score = convfloat(rank.u.d, 0, 0, NULL);
            values[group][used[group]++] = ztrdup(path); values[group][used[group]++] = ztrdup(score);
            if (greater(rank, highest[group])) {
                highest[group] = rank;
                if (best[group]) zsfree(best[group]);
                best[group] = ztrdup(path);
            }
        }
        popheap();
    }
    if (!failed) {
        sethparam("matches", values[0]); sethparam("imatches", values[1]);
        setsparam("best_match", best[0] ? best[0] : ztrdup("")); setsparam("ibest_match", best[1] ? best[1] : ztrdup(""));
    } else { freearray(values[0]); freearray(values[1]); if (best[0]) zsfree(best[0]); if (best[1]) zsfree(best[1]); }
    popheap(); return failed;
}
static struct builtin builtins[] = {BUILTIN("wsh-directory-query", 0, query, 0, 0, 0, NULL, NULL)};
static struct features module_features = {builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) { (void)m; return 0; }
int boot_(Module m) { (void)m; return 0; }
int features_(Module m, char ***features) { *features = featuresarray(m, &module_features); return 0; }
int enables_(Module m, int **enables) { return handlefeatures(m, &module_features, enables); }
int cleanup_(Module m) { return setfeatureenables(m, &module_features, NULL); }
int finish_(Module m) { (void)m; return 0; }
