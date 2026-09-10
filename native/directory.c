/* Directory data and queries; Zsh owns hooks, completion, and cd. */
#include <fcntl.h>
#include <math.h>
#include <pwd.h>
#include <sys/stat.h>
#include <time.h>
extern char **paramvalarr(HashTable, int);
extern int chabspath(char **);
extern int getmatch(char **, char *, int, int, char *);

struct wsh_directory_entry { char *path, *rank_text, *time_text; double rank, score; long long when; int group; };
struct wsh_directory_database { struct wsh_directory_entry *rows; size_t count, capacity; };
static int wsh_directory_removed;
static char *wsh_directory_setting(const char *name, const char *legacy, const char *fallback)
{
    char *value = getsparam((char *)name);
    if ((!value || !*value) && legacy) value = getsparam((char *)legacy);
    return value && *value ? value : (char *)fallback;
}
static double wsh_directory_number(const char *text)
{
    mnumber n = matheval(dupstring(text));
    return n.type == MN_INTEGER ? (double)n.u.l : n.u.d;
}
static int wsh_directory_enabled(const char *name, const char *legacy)
{
    return wsh_directory_number(wsh_directory_setting(name, legacy, "0")) != 0;
}
static int wsh_directory_directory(const char *path)
{
    struct stat st;
    return stat(unmeta((char *)path), &st) == 0 && S_ISDIR(st.st_mode);
}
static int wsh_directory_within(const char *path, const char *parent)
{
    size_t n = strlen(parent);
    return !strcmp(parent, "/") || !strcmp(path, parent) || (!strncmp(path, parent, n) && path[n] == '/');
}
static int wsh_directory_in_array(const char *path, const char *name, const char *legacy)
{
    char **items = getaparam((char *)name);
    if ((!items || !*items) && legacy) items = getaparam((char *)legacy);
    if (items) for (; *items; ++items) if (wsh_directory_within(path, *items)) return 1;
    return 0;
}
static char *wsh_directory_canonical(char *path, int resolve)
{
    char *result = dupstring(path);
    if (*result != '/') result = zhtricat(pwd, "/", result);
    chabspath(&result);
    return resolve ? xsymlink(result, 1) : result;
}
static int wsh_directory_owner_path(const char *path)
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
static int wsh_directory_parents(char *path)
{
    char *copy = dupstring(path);
    for (char *p = copy + 1; *p; ++p) if (*p == '/') {
        *p = 0;
        if (mkdir(copy, 0700) && errno != EEXIST) return 1;
        *p = '/';
    }
    return 0;
}
static int wsh_directory_append(struct wsh_directory_database *db, char *path, char *rank, char *when)
{
    if (db->count == db->capacity) {
        size_t cap = db->capacity ? db->capacity * 2 : 64;
        if (cap < db->capacity || cap > SIZE_MAX / sizeof(*db->rows)) return 1;
        void *next = realloc(db->rows, cap * sizeof(*db->rows));
        if (!next) return 1;
        db->rows = next; db->capacity = cap;
    }
    struct wsh_directory_entry *e = &db->rows[db->count++];
    *e = (struct wsh_directory_entry){.path=dupstring(path), .rank_text=dupstring(rank), .time_text=dupstring(when), .rank=wsh_directory_number(rank), .when=strtoll(when, NULL, 10)};
    return errflag != 0;
}
static int wsh_directory_read_database(const char *path, struct wsh_directory_database *db)
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
        if (wsh_directory_append(db, metafy(line, -1, META_HEAPDUP), middle, last)) { failed = 1; break; }
    }
    failed |= ferror(file) != 0;
    free(line); fclose(file); return failed;
}
static int wsh_directory_acquire(const char *path, double timeout, struct passwd *owner, int *result)
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
/* A file mount cannot be replaced. Keep the same lock through an in-place copy. */
static int wsh_directory_copy_mounted(const char *temporary, const char *path, struct passwd *owner)
{
    int input = open(temporary, O_RDONLY | O_CLOEXEC);
    if (input < 0) return 1;
    int output = open(path, O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (output < 0) { close(input); return 1; }
    struct stat st;
    int status = 1;
    if (fstat(output, &st) || !S_ISREG(st.st_mode) ||
        (!owner && st.st_uid != geteuid()) || fchmod(output, 0600) ||
        (owner && fchown(output, owner->pw_uid, owner->pw_gid)) || ftruncate(output, 0)) goto done;
    char buffer[8192];
    for (;;) {
        ssize_t count = read(input, buffer, sizeof(buffer));
        if (count < 0) { if (errno == EINTR && !errflag) continue; goto done; }
        if (!count) break;
        for (ssize_t offset = 0; offset < count;) {
            ssize_t written = write(output, buffer + offset, count - offset);
            if (written < 0 && errno == EINTR && !errflag) continue;
            if (written <= 0) goto done;
            offset += written;
        }
    }
    status = 0;
done:
    if (close(output)) status = 1;
    close(input);
    return status;
}
static int wsh_directory_persist(const char *path, const char *target, int remove_path, int recursive, long long now, struct passwd *owner)
{
    int lockfd = -1;
    char *lockpath = zhtricat((char *)path, ".lock", "");
    int status = wsh_directory_acquire(lockpath, wsh_directory_number(wsh_directory_setting("ZSHZ_LOCK_TIMEOUT", NULL, "1")), owner, &lockfd);
    if (status) return status;
    struct wsh_directory_database db = {0};
    char *temporary = zhtricat((char *)path, ".XXXXXX", "");
    int fd = -1; FILE *output = NULL;
    if (wsh_directory_read_database(path, &db)) { status = 1; goto done; }
    fd = mkstemp(temporary);
    if (fd < 0) { status = 1; goto done; }
    output = fdopen(fd, "w");
    if (!output) { close(fd); status = 1; goto done; }
    int changed = 0, found = 0;
    double total = 0;
    for (size_t i = 0; i < db.count; ++i) {
        struct wsh_directory_entry *e = &db.rows[i];
        if (remove_path) {
            if (!strcmp(e->path, target) || (recursive && wsh_directory_within(e->path, target))) { e->group = -1; changed = 1; }
        } else {
            if (e->rank < 1 || (!wsh_directory_directory(e->path) && !wsh_directory_in_array(e->path, "ZSHZ_KEEP_DIRS", NULL))) { e->group = -1; continue; }
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
        if (wsh_directory_append(&db, (char *)target, "1", stamp)) { status = 1; goto done; }
    }
    int age = !remove_path && total > wsh_directory_number(wsh_directory_setting("ZSHZ_MAX_SCORE", "_Z_MAX_SCORE", "9000"));
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
        struct wsh_directory_entry *e = &db.rows[i];
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
    if (rename(temporary, path) && (errno != EBUSY || wsh_directory_copy_mounted(temporary, path, owner))) { status = 1; goto done; }
    if (remove_path) wsh_directory_removed = 1;
done:
    if (output) fclose(output);
    if (fd >= 0) unlink(temporary);
    close(lockfd); free(db.rows); return status;
}
static char *wsh_directory_common_root(char **paths)
{
    char *shortest = NULL;
    for (char **p = paths; *p; ++p)
        if (!shortest || strlen(*p) < strlen(shortest) || !wsh_directory_within(*p, shortest) || !strcmp(*p, shortest)) shortest = *p;
    if (!shortest || !strcmp(shortest, "/")) return NULL;
    for (char **p = paths; *p; ++p) if (strncmp(*p, shortest, strlen(shortest))) return NULL;
    return shortest;
}
static char *wsh_directory_display(char *path)
{
    if (wsh_directory_enabled("ZSHZ_TILDE", NULL) && !strncmp(path, home, strlen(home))) return zhtricat("~", path+strlen(home), "");
    return path;
}
static int wsh_directory_emit(struct wsh_directory_database *db, int group, char *best, int format, int recent)
{
    char **paths = zhalloc((db->count+1)*sizeof(char *)), **rows = zhalloc((db->count+1)*sizeof(char *));
    size_t count = 0;
    for (size_t i = 0; i < db->count; ++i) {
        struct wsh_directory_entry *e = &db->rows[i];
        if (e->group != group || (format == 'l' && e->score == 0)) continue;
        paths[count] = e->path;
        char score[128];
        if (format == 'c') snprintf(score, sizeof(score), "%.0f|", trunc(e->score*100));
        else snprintf(score, sizeof(score), "%-10.0f ", trunc(e->score));
        rows[count++] = zhtricat(score, format == 'c' ? e->path : wsh_directory_display(e->path), "");
    }
    paths[count] = rows[count] = NULL;
    queue_signals();
    HashTable saved = paramtab, matches = newparamtable(17, "directory matches");
    paramtab = matches;
    for (size_t i = 0; i < count; ++i) {
        Param wsh_directory_entry = (Param)matches->getnode(matches, paths[i]);
        if (!wsh_directory_entry) wsh_directory_entry = createparam(paths[i], PM_SCALAR | PM_HASHELEM);
        wsh_directory_entry->gsu.s->setfn(wsh_directory_entry, ztrdup("1"));
    }
    paramtab = saved;
    char *common = wsh_directory_common_root(paramvalarr(matches, SCANPM_WANTKEYS));
    common = common ? dupstring(common) : NULL;
    deleteparamtable(matches);
    unqueue_signals();
    if (format) {
        if (format == 'l' && common && count > 1) printf("%-10s %s\n", "common:", unmeta(wsh_directory_display(common)));
        strmetasort(rows, SORTIT_NUMERICALLY | ((format == 'c' || recent) ? SORTIT_BACKWARDS : 0), NULL);
        for (size_t i = 0; i < count; ++i) puts(unmeta(format == 'c' ? strchr(rows[i], '|')+1 : rows[i]));
    } else setsparam("REPLY", ztrdup(common && !wsh_directory_enabled("ZSHZ_UNCOMMON", NULL) ? common : best));
    return count ? 0 : 1;
}
static int wsh_directory_command_impl(char *name, char **args, Options options, int function)
{
    (void)name; (void)options; (void)function;
    if (*args && !strcmp(*args, "--can-record")) return wsh_directory_removed ? 1 : 0;
    if (*args && !strcmp(*args, "--changed")) { wsh_directory_removed = 0; return 0; }
    int record = *args && !strcmp(*args, "--record");
    if (record) { if (wsh_directory_removed) return 0; ++args; }
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
    if (rank_mode && recent && !complete) { fprintf(stderr, "%s: options -r and -t cannot be combined.\n", wsh_directory_setting("ZSHZ_CMD", "_Z_CMD", "z")); return 1; }
    if (help) return 64; /* Wrapper prints the pinned usage text. */
    char *query = zjoin(words, ' ', 1);
    setsparam("REPLY", ztrdup(""));
    if (add && (!strcmp(query, home) || wsh_directory_in_array(query, "ZSHZ_EXCLUDE_DIRS", "_Z_EXCLUDE_DIRS"))) return 0;
    if (add && !wsh_directory_directory(query)) return 1;
    char *custom = wsh_directory_setting("ZSHZ_DATA", "_Z_DATA", "");
    if (*custom && !strchr(custom, '/')) { fprintf(stderr, "ERROR: You configured a custom Zsh-z datafile (%s), but have not specified its directory.\n", unmeta(custom)); return 1; }
    char *selected = *custom ? custom : zhtricat(home, "/.z", "");
    char *owner_name = wsh_directory_setting("ZSHZ_OWNER", "_Z_OWNER", "");
    struct passwd *owner = *owner_name ? getpwnam(unmeta(owner_name)) : NULL;
    if (*owner_name && (!owner || wsh_directory_owner_path(wsh_directory_canonical(selected, 0)))) return 1;
    char *datafile = wsh_directory_canonical(selected, 1);
    if (!datafile) return 1;
    char *path = dupstring(unmeta(datafile));
    if (wsh_directory_directory(datafile)) { fprintf(stderr, "ERROR: Zsh-z's datafile (%s) is a directory.\n", path); return 1; }
    if (wsh_directory_parents(path)) return 1;
    int fd = open(path, O_RDWR | O_CREAT | O_CLOEXEC | (owner ? O_NOFOLLOW : 0), 0600);
    if (fd < 0) return 1;
    struct stat st;
    int bad = fstat(fd, &st) || !S_ISREG(st.st_mode) || (!owner && st.st_uid != geteuid()) || (owner && fchown(fd, owner->pw_uid, owner->pw_gid));
    close(fd); if (bad) return 1;
    long long now = (long long)wsh_directory_number(wsh_directory_setting("WSH_QUERY_NOW", NULL, "0"));
    if (!now) now = time(NULL);
    if (add || remove_path) {
        char *target = wsh_directory_canonical(*query ? query : pwd, !wsh_directory_enabled("ZSHZ_NO_RESOLVE_SYMLINKS", "_Z_NO_RESOLVE_SYMLINKS"));
        if (!target) return 1;
        if (add && (!strcmp(target, home) || wsh_directory_in_array(target, "ZSHZ_EXCLUDE_DIRS", "_Z_EXCLUDE_DIRS"))) return 0;
        if (remove_path && recursive && !strcmp(target, "/")) {
            execstring("builtin read -q '?Delete entire Zsh-z database? '", 1, 0, "wsh-directory");
            setsparam("REPLY", ztrdup(""));
            if (lastval || errflag) { putchar('\n'); return 1; }
        }
        return wsh_directory_persist(path, target, remove_path, recursive, now, owner);
    }
    if (!format && !echo && count && *words[count-1] == '/' && wsh_directory_directory(words[count-1])) { setsparam("REPLY", ztrdup(words[count-1])); return 0; }
    struct wsh_directory_database db = {0}; int status = wsh_directory_read_database(path, &db);
    if (status) { free(db.rows); return status; }
    if (!*query && !complete) format = 'l';
    char *pattern = query;
    if (child && strcmp(pwd, "/") && !wsh_directory_within(query, pwd)) pattern = zhtricat(pwd, " ", query);
    pattern = dupstring(pattern);
    for (char *p = pattern; *p; ++p) if (isspace((unsigned char)*p)) *p = '*';
    pattern = zhtricat(child && strcmp(pwd, "/") ? "" : "*", pattern, "*");
    char *lower = casemodify(pattern, CASMOD_LOWER);
    int lower_query = !strcmp(lower, pattern);
    char *sensitive = dupstring(pattern), *insensitive = dupstring(lower);
    tokenize(sensitive); tokenize(insensitive);
    Patprog pats[2] = {patcompile(sensitive, 0, NULL), patcompile(insensitive, 0, NULL)};
    if (!pats[0] || !pats[1]) { free(db.rows); return 1; }
    char *case_mode = wsh_directory_setting("ZSHZ_CASE", NULL, "");
    int ignore = !strcmp(case_mode, "ignore"), smart = !strcmp(case_mode, "smart");
    char *best[2] = {NULL,NULL}; double maximum[2] = {-9999999999.0,-9999999999.0};
    for (size_t i = 0; i < db.count; ++i) {
        struct wsh_directory_entry *e = &db.rows[i]; e->group = -1;
        if (!wsh_directory_directory(e->path) && !wsh_directory_in_array(e->path, "ZSHZ_KEEP_DIRS", NULL)) continue;
        char *match = e->path;
        if (wsh_directory_enabled("ZSHZ_TRAILING_SLASH", NULL)) { match = dupstring(match); size_t n = strlen(match); if (n && match[n-1]=='/') match[n-1]=0; match = zhtricat(match,"/",""); }
        if (smart && lower_query && pattry(pats[1], casemodify(match,CASMOD_LOWER))) e->group=1;
        else if (!ignore && pattry(pats[0],match)) e->group=0;
        else if (!smart && pattry(pats[1],casemodify(match,CASMOD_LOWER))) e->group=1;
        e->score = rank_mode ? e->rank : recent ? (double)e->when-now : 10000*e->rank*(3.75/((0.0001*(now-e->when)+1)+0.25));
        if (e->group >= 0 && e->score > maximum[e->group]) { maximum[e->group] = e->score; best[e->group] = e->path; }
    }
    int group = best[0] ? 0 : 1;
    status = best[group] ? wsh_directory_emit(&db, group, best[group], format, recent) : 1;
    if (!status && !format) {
        char *target = dupstring(getsparam("REPLY"));
        if (wsh_directory_enabled("ZSHZ_UNCOMMON", NULL)) {
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
        if (echo) { puts(unmeta(wsh_directory_display(target))); setsparam("REPLY",ztrdup("")); }
    } else if (status && !format && !echo && wsh_directory_directory(query)) { setsparam("REPLY",ztrdup(query)); status=0; }
    free(db.rows); return status;
}
static int wsh_directory_command(char *name, char **args, Options options, int function)
{
    pushheap();
    int result = wsh_directory_command_impl(name, args, options, function);
    fflush(stdout); fflush(stderr);
    popheap();
    return result;
}
static struct builtin wsh_directory_builtins[] = {BUILTIN("wsh-directory", 0, wsh_directory_command, 0, -1, 0, NULL, NULL)};
