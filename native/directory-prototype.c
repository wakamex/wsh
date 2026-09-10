/* Complete Linux directory data/query prototype. Zsh owns hooks and cd. */
#define _GNU_SOURCE 1
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"
#include <fcntl.h>
#include <math.h>
#include <pwd.h>
#include <sys/stat.h>
#include <time.h>
extern char **paramvalarr(HashTable, int);
extern int chabspath(char **);
extern int getmatch(char **, char *, int, int, char *);

struct entry { char *path, *rank_text, *time_text; double rank, score; long long when; int group; };
struct database { struct entry *rows; size_t count, capacity; };
static int removed;
static char *setting(const char *name, const char *legacy, const char *fallback)
{
    char *value = getsparam((char *)name);
    if ((!value || !*value) && legacy) value = getsparam((char *)legacy);
    return value && *value ? value : (char *)fallback;
}
static double number(const char *text)
{
    mnumber n = matheval(dupstring(text));
    return n.type == MN_INTEGER ? (double)n.u.l : n.u.d;
}
static int enabled(const char *name, const char *legacy)
{
    return number(setting(name, legacy, "0")) != 0;
}
static int directory(const char *path)
{
    struct stat st;
    return stat(unmeta((char *)path), &st) == 0 && S_ISDIR(st.st_mode);
}
static int within(const char *path, const char *parent)
{
    size_t n = strlen(parent);
    return !strcmp(parent, "/") || !strcmp(path, parent) || (!strncmp(path, parent, n) && path[n] == '/');
}
static int in_array(const char *path, const char *name, const char *legacy)
{
    char **items = getaparam((char *)name);
    if ((!items || !*items) && legacy) items = getaparam((char *)legacy);
    if (items) for (; *items; ++items) if (within(path, *items)) return 1;
    return 0;
}
static char *canonical(char *path, int resolve)
{
    char *result = dupstring(path);
    if (*result != '/') result = zhtricat(pwd, "/", result);
    chabspath(&result);
    return resolve ? xsymlink(result, 1) : result;
}
static int owner_path(const char *path)
{
    char *copy = dupstring(unmeta((char *)path));
    for (char *p = copy + 1; ; ++p) {
        if (*p && *p != '/') continue;
        char saved = *p; *p = 0;
        struct stat st;
        int unsafe = !lstat(copy, &st) && S_ISLNK(st.st_mode) && st.st_uid != 0;
        *p = saved;
        if (unsafe) return 1;
        if (!saved) return 0;
    }
}
static int parents(char *path)
{
    char *copy = dupstring(path);
    for (char *p = copy + 1; *p; ++p) if (*p == '/') {
        *p = 0;
        if (mkdir(copy, 0700) && errno != EEXIST) return 1;
        *p = '/';
    }
    return 0;
}
static int append(struct database *db, char *path, char *rank, char *when)
{
    if (db->count == db->capacity) {
        size_t cap = db->capacity ? db->capacity * 2 : 64;
        if (cap < db->capacity || cap > SIZE_MAX / sizeof(*db->rows)) return 1;
        void *next = realloc(db->rows, cap * sizeof(*db->rows));
        if (!next) return 1;
        db->rows = next; db->capacity = cap;
    }
    struct entry *e = &db->rows[db->count++];
    *e = (struct entry){.path=dupstring(path), .rank_text=dupstring(rank), .time_text=dupstring(when), .rank=number(rank), .when=strtoll(when, NULL, 10)};
    return errflag != 0;
}
static int read_database(const char *path, struct database *db)
{
    FILE *file = fopen(path, "r");
    if (!file) return 1;
    char *line = NULL; size_t cap = 0; ssize_t length; int failed = 0;
    while ((length = getline(&line, &cap, file)) >= 0) {
        if (memchr(line, 0, (size_t)length)) continue;
        if (length && line[length-1] == '\n') line[--length] = 0;
        char *last = strrchr(line, '|');
        if (!last) continue;
        *last++ = 0;
        char *middle = strrchr(line, '|');
        if (!middle) continue;
        *middle++ = 0;
        if (*line != '/' || !*middle || !*last || strspn(middle, "0123456789.,") != strlen(middle) || strspn(last, "0123456789") != strlen(last)) continue;
        if (append(db, metafy(line, -1, META_HEAPDUP), middle, last)) { failed = 1; break; }
    }
    failed |= ferror(file) != 0;
    free(line); fclose(file); return failed;
}
static int acquire(const char *path, double timeout, struct passwd *owner, int *result)
{
    int fd = open(path, O_RDWR | O_CREAT | O_CLOEXEC | (owner ? O_NOFOLLOW : 0), 0600);
    if (fd < 0) return 1;
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || (owner && fchown(fd, owner->pw_uid, owner->pw_gid))) { close(fd); return 1; }
    struct flock lock = {.l_type=F_WRLCK, .l_whence=SEEK_SET, .l_start=0, .l_len=0};
    struct timespec start, now, pause = {.tv_nsec=1000000};
    clock_gettime(CLOCK_MONOTONIC, &start);
    while (fcntl(fd, F_SETLK, &lock)) {
        if (errflag || (errno != EACCES && errno != EAGAIN && errno != EINTR)) { close(fd); return 1; }
        clock_gettime(CLOCK_MONOTONIC, &now);
        double elapsed = now.tv_sec-start.tv_sec + (now.tv_nsec-start.tv_nsec)/1e9;
        if (elapsed >= timeout) { close(fd); return 2; }
        nanosleep(&pause, NULL);
    }
    *result = fd; return 0;
}
static int persist(const char *path, const char *target, int remove_path, int recursive, long long now, struct passwd *owner)
{
    int lockfd = -1;
    char *lockpath = zhtricat((char *)path, ".lock", "");
    int status = acquire(lockpath, number(setting("ZSHZ_LOCK_TIMEOUT", NULL, "1")), owner, &lockfd);
    if (status) return status;
    struct database db = {0};
    char *temporary = zhtricat((char *)path, ".XXXXXX", "");
    int fd = -1; FILE *output = NULL;
    if (read_database(path, &db)) { status = 1; goto done; }
    fd = mkstemp(temporary);
    if (fd < 0) { status = 1; goto done; }
    output = fdopen(fd, "w");
    if (!output) { close(fd); status = 1; goto done; }
    int changed = 0, found = 0;
    double total = 0;
    for (size_t i = 0; i < db.count; ++i) {
        struct entry *e = &db.rows[i];
        if (remove_path) {
            if (!strcmp(e->path, target) || (recursive && within(e->path, target))) { e->group = -1; changed = 1; }
        } else {
            if (e->rank < 1 || (!directory(e->path) && !in_array(e->path, "ZSHZ_KEEP_DIRS", NULL))) { e->group = -1; continue; }
            total += e->rank;
            if (!strcmp(e->path, target)) {
                mnumber incremented = matheval(dyncat(e->rank_text, "+1"));
                char integer[32];
                if (incremented.type == MN_INTEGER) {
                    snprintf(integer, sizeof(integer), "%lld", (long long)incremented.u.l);
                    e->rank_text = dupstring(integer);
                    e->rank = incremented.u.l;
                } else {
                    e->rank = incremented.u.d;
                    e->rank_text = dupstring(convfloat(e->rank, 0, 0, NULL));
                }
                e->when = now; found = 1;
            }
        }
    }
    if (remove_path && !changed) { status = 1; goto done; }
    if (!remove_path && !found) {
        char stamp[32]; snprintf(stamp, sizeof(stamp), "%lld", now);
        if (append(&db, (char *)target, "1", stamp)) { status = 1; goto done; }
    }
    int age = !remove_path && total > number(setting("ZSHZ_MAX_SCORE", "_Z_MAX_SCORE", "9000"));
    HashTable updated = newparamtable(17, "directory updated");
    if (!remove_path) {
        queue_signals();
        HashTable saved = paramtab; paramtab = updated;
        Param p = createparam(quotestring((char *)target, QT_BACKSLASH), PM_SCALAR | PM_HASHELEM);
        paramtab = saved;
        p->gsu.s->setfn(p, ztrdup(""));
        unqueue_signals();
    }
    int wrote = 0;
    for (size_t i = 0; i < db.count; ++i) {
        struct entry *e = &db.rows[i];
        if (e->group == -1) continue;
        wrote = 1;
        if (remove_path) fprintf(output, "%s|%s|%s\n", unmeta(e->path), e->rank_text, e->time_text);
        else {
            char *rank = age ? convfloat(0.99*e->rank, 0, 0, NULL) : e->rank_text;
            char stamp[32]; snprintf(stamp, sizeof(stamp), "%lld", e->when);
            char *line = zhtricat(e->path, "|", zhtricat(rank, "|", stamp));
            char *key = quotestring(e->path, QT_BACKSLASH);
            queue_signals();
            HashTable saved = paramtab; paramtab = updated;
            Param p = (Param)updated->getnode(updated, key);
            if (!p) p = createparam(key, PM_SCALAR | PM_HASHELEM);
            paramtab = saved;
            p->gsu.s->setfn(p, ztrdup(line));
            unqueue_signals();
        }
    }
    if (remove_path && !wrote) fputc('\n', output);
    if (!remove_path) {
        char **rows = paramvalarr(updated, SCANPM_WANTVALS);
        for (; *rows; ++rows) fprintf(output, "%s\n", unmeta(*rows));
    }
    deleteparamtable(updated);
    if (fflush(output) || ferror(output) || (owner && fchown(fd, owner->pw_uid, owner->pw_gid))) { status = 1; goto done; }
    if (fclose(output)) { output = NULL; status = 1; goto done; }
    output = NULL;
    if (rename(temporary, path)) { status = 1; goto done; }
    if (remove_path) removed = 1;
done:
    if (output) fclose(output);
    if (fd >= 0) unlink(temporary);
    close(lockfd); free(db.rows); return status;
}
static char *common_root(char **paths)
{
    char *shortest = NULL;
    for (char **p = paths; *p; ++p)
        if (!shortest || strlen(*p) < strlen(shortest) || !within(*p, shortest) || !strcmp(*p, shortest)) shortest = *p;
    if (!shortest || !strcmp(shortest, "/")) return NULL;
    for (char **p = paths; *p; ++p) if (strncmp(*p, shortest, strlen(shortest))) return NULL;
    return shortest;
}
static char *display(char *path)
{
    if (enabled("ZSHZ_TILDE", NULL) && !strncmp(path, home, strlen(home))) return zhtricat("~", path+strlen(home), "");
    return path;
}
static int emit(struct database *db, int group, char *best, int format, int recent)
{
    char **paths = zhalloc((db->count+1)*sizeof(char *)), **rows = zhalloc((db->count+1)*sizeof(char *));
    size_t count = 0;
    for (size_t i = 0; i < db->count; ++i) {
        struct entry *e = &db->rows[i];
        if (e->group != group || (format == 'l' && e->score == 0)) continue;
        paths[count] = e->path;
        char score[128];
        if (format == 'c') snprintf(score, sizeof(score), "%.0f|", trunc(e->score*100));
        else snprintf(score, sizeof(score), "%-10.0f ", trunc(e->score));
        rows[count++] = zhtricat(score, format == 'c' ? e->path : display(e->path), "");
    }
    paths[count] = rows[count] = NULL;
    queue_signals();
    HashTable saved = paramtab, matches = newparamtable(17, "directory matches");
    paramtab = matches;
    for (size_t i = 0; i < count; ++i) {
        Param entry = (Param)matches->getnode(matches, paths[i]);
        if (!entry) entry = createparam(paths[i], PM_SCALAR | PM_HASHELEM);
        entry->gsu.s->setfn(entry, ztrdup("1"));
    }
    paramtab = saved;
    char *common = common_root(paramvalarr(matches, SCANPM_WANTKEYS));
    common = common ? dupstring(common) : NULL;
    deleteparamtable(matches);
    unqueue_signals();
    if (format) {
        if (format == 'l' && common && count > 1) printf("%-10s %s\n", "common:", unmeta(display(common)));
        strmetasort(rows, SORTIT_NUMERICALLY | ((format == 'c' || recent) ? SORTIT_BACKWARDS : 0), NULL);
        for (size_t i = 0; i < count; ++i) puts(unmeta(format == 'c' ? strchr(rows[i], '|')+1 : rows[i]));
    } else setsparam("REPLY", ztrdup(common && !enabled("ZSHZ_UNCOMMON", NULL) ? common : best));
    return count ? 0 : 1;
}
static int command_impl(char *name, char **args, Options options, int function)
{
    (void)name; (void)options; (void)function;
    if (*args && !strcmp(*args, "--can-record")) return removed ? 1 : 0;
    if (*args && !strcmp(*args, "--changed")) { removed = 0; return 0; }
    int record = *args && !strcmp(*args, "--record");
    if (record) { if (removed) return 0; ++args; }
    int add = record, remove_path = 0, recursive = 0, format = 0, rank_mode = 0, recent = 0, echo = 0, child = 0, help = 0, complete = 0;
    char **words = zhalloc((arrlen(args)+1)*sizeof(char *)); int count = 0, stopped = 0;
    for (; *args; ++args) {
        if (!stopped && !strcmp(*args, "--")) { stopped = 1; continue; }
        if (!stopped && !strcmp(*args, "--add")) { add = 1; continue; }
        if (!stopped && !strcmp(*args, "--complete")) { complete = 1; continue; }
        if (!stopped && !strcmp(*args, "--help")) { help = 1; continue; }
        if (!stopped && **args == '-' && (*args)[1]) {
            for (char *p = *args+1; *p; ++p) switch (*p) {
                case 'c': child = 1; break; case 'e': echo = 1; break;
                case 'h': help = 1; break; case 'l': format = 'l'; break;
                case 'r': rank_mode = 1; break; case 't': recent = 1; break;
                case 'x': remove_path = 1; break; case 'R': recursive = 1; break;
                default: return 1;
            }
        } else words[count++] = *args;
    }
    words[count] = NULL;
    if (complete) { format = 'c'; add = remove_path = help = 0; }
    if (rank_mode && recent && !complete) { fprintf(stderr, "%s: options -r and -t cannot be combined.\n", setting("ZSHZ_CMD", "_Z_CMD", "z")); return 1; }
    if (help) return 64; /* Wrapper prints the pinned usage text. */
    char *query = zjoin(words, ' ', 1);
    setsparam("REPLY", ztrdup(""));
    if (add && (!strcmp(query, home) || in_array(query, "ZSHZ_EXCLUDE_DIRS", "_Z_EXCLUDE_DIRS"))) return 0;
    if (add && !directory(query)) return 1;
    char *custom = setting("ZSHZ_DATA", "_Z_DATA", "");
    if (*custom && !strchr(custom, '/')) { fprintf(stderr, "ERROR: You configured a custom Zsh-z datafile (%s), but have not specified its directory.\n", unmeta(custom)); return 1; }
    char *selected = *custom ? custom : zhtricat(home, "/.z", "");
    char *owner_name = setting("ZSHZ_OWNER", "_Z_OWNER", "");
    struct passwd *owner = *owner_name ? getpwnam(unmeta(owner_name)) : NULL;
    if (*owner_name && (!owner || owner_path(canonical(selected, 0)))) return 1;
    char *datafile = canonical(selected, 1);
    if (!datafile) return 1;
    char *path = dupstring(unmeta(datafile));
    if (directory(datafile)) { fprintf(stderr, "ERROR: Zsh-z's datafile (%s) is a directory.\n", path); return 1; }
    if (parents(path)) return 1;
    int fd = open(path, O_RDWR | O_CREAT | O_CLOEXEC | (owner ? O_NOFOLLOW : 0), 0600);
    if (fd < 0) return 1;
    struct stat st;
    int bad = fstat(fd, &st) || !S_ISREG(st.st_mode) || (!owner && st.st_uid != geteuid()) || (owner && fchown(fd, owner->pw_uid, owner->pw_gid));
    close(fd); if (bad) return 1;
    long long now = (long long)number(setting("WSH_QUERY_NOW", NULL, "0"));
    if (!now) now = time(NULL);
    if (add || remove_path) {
        char *target = canonical(*query ? query : pwd, !enabled("ZSHZ_NO_RESOLVE_SYMLINKS", "_Z_NO_RESOLVE_SYMLINKS"));
        if (!target) return 1;
        if (add && (!strcmp(target, home) || in_array(target, "ZSHZ_EXCLUDE_DIRS", "_Z_EXCLUDE_DIRS"))) return 0;
        if (remove_path && recursive && !strcmp(target, "/")) {
            execstring("builtin read -q '?Delete entire Zsh-z database? '", 1, 0, "wsh-directory");
            setsparam("REPLY", ztrdup(""));
            if (lastval || errflag) { putchar('\n'); return 1; }
        }
        return persist(path, target, remove_path, recursive, now, owner);
    }
    if (!format && !echo && count && *words[count-1] == '/' && directory(words[count-1])) { setsparam("REPLY", ztrdup(words[count-1])); return 0; }
    struct database db = {0}; int status = read_database(path, &db);
    if (status) { free(db.rows); return status; }
    if (!*query && !complete) format = 'l';
    char *pattern = query;
    if (child && strcmp(pwd, "/") && !within(query, pwd)) pattern = zhtricat(pwd, " ", query);
    pattern = dupstring(pattern);
    for (char *p = pattern; *p; ++p) if (isspace((unsigned char)*p)) *p = '*';
    pattern = zhtricat(child && strcmp(pwd, "/") ? "" : "*", pattern, "*");
    char *lower = casemodify(pattern, CASMOD_LOWER);
    int lower_query = !strcmp(lower, pattern);
    char *sensitive = dupstring(pattern), *insensitive = dupstring(lower);
    tokenize(sensitive); tokenize(insensitive);
    Patprog pats[2] = {patcompile(sensitive, 0, NULL), patcompile(insensitive, 0, NULL)};
    if (!pats[0] || !pats[1]) { free(db.rows); return 1; }
    char *case_mode = setting("ZSHZ_CASE", NULL, "");
    int ignore = !strcmp(case_mode, "ignore"), smart = !strcmp(case_mode, "smart");
    char *best[2] = {NULL,NULL}; double maximum[2] = {-9999999999.0,-9999999999.0};
    for (size_t i = 0; i < db.count; ++i) {
        struct entry *e = &db.rows[i]; e->group = -1;
        if (!directory(e->path) && !in_array(e->path, "ZSHZ_KEEP_DIRS", NULL)) continue;
        char *match = e->path;
        if (enabled("ZSHZ_TRAILING_SLASH", NULL)) { match = dupstring(match); size_t n = strlen(match); if (n && match[n-1]=='/') match[n-1]=0; match = zhtricat(match,"/",""); }
        if (smart && lower_query && pattry(pats[1], casemodify(match,CASMOD_LOWER))) e->group=1;
        else if (!ignore && pattry(pats[0],match)) e->group=0;
        else if (!smart && pattry(pats[1],casemodify(match,CASMOD_LOWER))) e->group=1;
        e->score = rank_mode ? e->rank : recent ? (double)e->when-now : 10000*e->rank*(3.75/((0.0001*(now-e->when)+1)+0.25));
        if (e->group >= 0 && e->score > maximum[e->group]) { maximum[e->group] = e->score; best[e->group] = e->path; }
    }
    int group = best[0] ? 0 : 1;
    status = best[group] ? emit(&db, group, best[group], format, recent) : 1;
    if (!status && !format) {
        char *target = dupstring(getsparam("REPLY"));
        if (enabled("ZSHZ_UNCOMMON", NULL)) {
            char *q = dupstring(query); for (char *p=q; *p; ++p) if (isspace((unsigned char)*p)) *p='*';
            size_t n = strlen(q); if (n && q[n-1]=='/') q[n-1]=0;
            if (group) q = casemodify(q, CASMOD_LOWER);
            tokenize(q);
            char *text = dupstring(group ? casemodify(target,CASMOD_LOWER) : target);
            getmatch(&text,q,SUB_GLOBAL|SUB_REST|SUB_SUBSTR|SUB_LONG,0,"");
            size_t matched = strlen(target)-strlen(text);
            for (;;) {
                char *parent = dupstring(target), *slash = strrchr(parent,'/');
                if (!slash || !strcmp(parent,"/")) break;
                if (slash==parent) slash[1]=0; else *slash=0;
                text = dupstring(group ? casemodify(parent,CASMOD_LOWER) : parent);
                getmatch(&text,q,SUB_GLOBAL|SUB_REST|SUB_SUBSTR|SUB_LONG,0,"");
                if (strlen(parent)-strlen(text) != matched) break;
                target=parent;
            }
            setsparam("REPLY",ztrdup(target));
        }
        if (echo) { puts(unmeta(display(target))); setsparam("REPLY",ztrdup("")); }
    } else if (status && !format && !echo && directory(query)) { setsparam("REPLY",ztrdup(query)); status=0; }
    free(db.rows); return status;
}
static int command(char *name, char **args, Options options, int function)
{
    pushheap();
    int result = command_impl(name, args, options, function);
    fflush(stdout); fflush(stderr);
    popheap();
    return result;
}
static struct builtin builtins[] = {BUILTIN("wsh-directory", 0, command, 0, -1, 0, NULL, NULL)};
static struct features features = {builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) { (void)m; return 0; }
int boot_(Module m) { (void)m; return 0; }
int features_(Module m, char ***f) { *f=featuresarray(m,&features); return 0; }
int enables_(Module m, int **e) { return handlefeatures(m,&features,e); }
int cleanup_(Module m) { return setfeatureenables(m,&features,NULL); }
int finish_(Module m) { (void)m; return 0; }
