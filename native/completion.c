/* Bundled compinit registration; audit, dump policy and completion stay in Zsh. */
#include <fcntl.h>
#include <dirent.h>
#include <sys/stat.h>

static int wsh_completion_header(char *name, char **args, Options options, int function)
{
    (void)name; (void)options; (void)function;
    int fd = open(unmeta(args[0]), O_RDONLY | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) return 1;
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode)) { close(fd); return 1; }
    char bytes[4096];
    ssize_t length;
    do { length = read(fd, bytes, sizeof(bytes)); } while (length < 0 && errno == EINTR && !errflag);
    close(fd);
    if (length <= 0) return 1;
    char *end = memchr(bytes, '\n', (size_t)length);
    if (!end) return 1;
    for (char *p = bytes; p < end; ++p) if (!*p || (unsigned char)*p >= 128) return 1;
    *end = 0;
    size_t count = 0;
    char *parts[2049], *p = bytes;
    while (*p) {
        while (*p == ' ' || *p == '\t') ++p;
        if (!*p) break;
        parts[count++] = p;
        while (*p && *p != ' ' && *p != '\t') ++p;
        if (*p) *p++ = 0;
    }
    if (!count || (end > bytes && (end[-1] == 0 || end[-1] == ' ' || end[-1] == '\t'))) parts[count++] = "";
    char **result = zalloc((count+1)*sizeof(char *));
    for (size_t i = 0; i < count; ++i) result[i] = metafy(parts[i], -1, META_DUP);
    result[count] = NULL;
    setaparam(args[1], result);
    return 0;
}

static int wsh_completion_call(const char *name, char **args)
{
    Shfunc fn = (Shfunc)shfunctab->getnode(shfunctab, name);
    if (!fn) return 1;
    LinkList list = newlinklist(); addlinknode(list, dupstring(name));
    for (; *args; ++args) addlinknode(list, dupstring(*args));
    return doshfunc(fn, list, 0);
}
static int wsh_completion_listed(char *pattern, const char *array)
{
    char **items = getaparam((char *)array);
    if (!items) return 0;
    char *copy = dupstring(pattern); tokenize(copy);
    Patprog compiled = patcompile(copy, 0, NULL);
    if (!compiled) return 0;
    for (; *items; ++items) if (pattry(compiled, *items)) return 1;
    return 0;
}
static void wsh_completion_put(HashTable table, const char *key, const char *value)
{
    queue_signals();
    HashTable saved = paramtab; paramtab = table;
    Param p = (Param)table->getnode(table, key);
    if (!p) p = createparam((char *)key, PM_SCALAR | PM_HASHELEM);
    paramtab = saved;
    p->gsu.s->setfn(p, ztrdup(value));
    unqueue_signals();
}
static int wsh_completion_scan(char *name, char **args, Options options, int function)
{
    (void)name; (void)args; (void)options; (void)function;
    pushheap();
    char **directories = getaparam("fpath");
    if (!directories) { popheap(); return 1; }
    directories = arrdup(directories);
    HashTable seen = newparamtable(17, "completion seen");
    int result = 0;
    for (char **dir = directories; *dir && !errflag; ++dir) {
        if (!strcmp(*dir, ".") || wsh_completion_listed(*dir, "_i_wdirs")) continue;
        DIR *stream = opendir(unmeta(*dir));
        if (!stream) continue;
        LinkList paths = newlinklist(); struct dirent *entry;
        while ((entry = readdir(stream))) {
            char *n = entry->d_name; size_t length = strlen(n);
            if (n[0] != '_' || strpbrk(n, ";|&") || n[length-1] == '~' || (length >= 4 && !strcmp(n+length-4, ".zwc"))) continue;
            addlinknode(paths, metafy(n, -1, META_HEAPDUP));
        }
        closedir(stream);
        size_t count = countlinknodes(paths), i = 0;
        char **names = zhalloc((count+1)*sizeof(char *)); LinkNode node;
        for (node=firstnode(paths); node; incnode(node)) names[i++] = getdata(node);
        names[i] = NULL; strmetasort(names, 0, NULL);
        for (i=0; i<count && !errflag; ++i) {
            char *file = zhtricat(*dir, "/", names[i]);
            if (seen->getnode(seen, names[i]) || wsh_completion_listed(file, "_i_wfiles")) continue;
            wsh_completion_put(seen, names[i], "yes");
            char *read_args[] = {file, "_i_line", NULL};
            if (wsh_completion_header(NULL, read_args, NULL, 0)) wsh_completion_call("_wsh_completion_read", read_args);
            char **fields = getaparam("_i_line");
            if (!fields || !*fields) continue;
            size_t n = (size_t)arrlen(fields);
            char **arguments = zhalloc((n+3)*sizeof(char *));
            if (!strcmp(fields[0], "#compdef")) {
                int special = n > 1 && fields[1][0] == '-' && strchr("pPkK", fields[1][1]) && fields[1][1] && (!fields[1][2] || (fields[1][2]=='n' && !fields[1][3]));
                size_t used = 0;
                arguments[used++] = special ? dyncat(fields[1], "na") : "-na";
                arguments[used++] = names[i];
                for (size_t j = special ? 2 : 1; j < n; ++j) arguments[used++] = fields[j];
                arguments[used] = NULL; wsh_completion_call("compdef", arguments);
            } else if (!strcmp(fields[0], "#autoload")) {
                size_t used = 0;
                for (size_t j=1; j<n; ++j) arguments[used++] = fields[j];
                arguments[used++] = names[i]; arguments[used] = NULL;
                /* Finish reading the parameter before callbacks can replace it. */
                char *joined = zjoin(fields+1, ' ', 1);
                wsh_completion_call("_wsh_completion_autoload", arguments);
                Param auto_param = (Param)paramtab->getnode(paramtab, "_compautos");
                if (auto_param && PM_TYPE(auto_param->node.flags) == PM_HASHED && strcmp(joined," #")) {
                    HashTable ht = auto_param->gsu.h->getfn(auto_param);
                    if (!ht) { ht = newparamtable(17, auto_param->node.nam); auto_param->gsu.h->setfn(auto_param, ht); }
                    wsh_completion_put(ht, names[i], joined);
                }
            }
        }
    }
    if (errflag) result = 1;
    deleteparamtable(seen); popheap(); return result;
}
static struct builtin wsh_completion_builtins[] = {BUILTIN("wsh-completion-scan", 0, wsh_completion_scan, 0, 0, 0, NULL, NULL)};
