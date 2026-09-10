/* Private command-list parser prototype. Deliberately has no legacy fallback. */
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"
#include <ctype.h>

static int call(const char *name, char **args) {
    Shfunc fn = (Shfunc)shfunctab->getnode(shfunctab, name);
    if (!fn)
        return 1;
    LinkList list = newlinklist();
    addlinknode(list, dupstring(name));
    for (; args && *args; ++args)
        addlinknode(list, dupstring(*args));
    return doshfunc(fn, list, 0);
}
static char *value(const char *name) {
    char *s = getsparam((char *)name);
    return s ? s : "";
}
static void set(const char *name, const char *text) { setsparam((char *)name, ztrdup(text)); }
static int chars(char *text, size_t bytes) {
    char *copy = dupstrpfx(text, (int)bytes);
    return mb_metastrlenend(copy, 0, NULL);
}
static void region(int start, int end, const char *style) {
    char a[32], b[32];
    snprintf(a, sizeof(a), "%d", start);
    snprintf(b, sizeof(b), "%d", end);
    char *args[] = {a, b, (char *)style, NULL};
    call("_zsh_highlight_main_add_region_highlight", args);
}
static int one_of(const char *word, const char *const *words) {
    for (; *words; ++words)
        if (!strcmp(word, *words))
            return 1;
    return 0;
}
static int assignment(char *word) {
    unsigned char *p = (unsigned char *)word;
    if (*p != '_' && !isalpha(*p))
        return 0;
    while (*p == '_' || isalnum(*p))
        ++p;
    if (*p == '+')
        ++p;
    return *p == '=';
}
static int parse(char *name, char **args, Options options, int function) {
    (void)name;
    (void)options;
    (void)function;
    pushheap();
    char *buffer = dupstring(args[3]);
    set("_wsh_highlight_input", buffer);
    /* Zsh's own lexical splitting never executes the input. */
    execstring("_wsh_highlight_words=(\"${(z)_wsh_highlight_input}\")", 1, 0,
               "wsh-highlight-lexer");
    if (errflag) {
        popheap();
        return 1;
    }
    char **words = arrdup(getaparam("_wsh_highlight_words"));
    const char *const delimiters[] = {";", "|", "||", "&&", "&", "&!", "&|", "|&", "\n", NULL};
    const char *const starters[] = {"if", "then", "elif", "else", "while", "until",
                                    "do", "!",    "{",    "(",    NULL};
    const char *const closers[] = {"fi", "done", "}", ")", NULL};
    const char *const precommands[] = {"command", "builtin", "exec", "noglob", "nocorrect", NULL};
    int command = 1, redirect = 0, for_name = 0, for_list = 0, depth = (int)strlen(args[1]);
    size_t position = 0;
    int end = 0, failed = 0;
    for (char **p = words; p && *p; ++p) {
        char *word = *p, *located = strstr(buffer + position, word);
        if (!located) {
            failed = 1;
            break;
        }
        size_t offset = (size_t)(located - buffer), length = strlen(word);
        position = offset + length;
        int start = chars(buffer, offset);
        end = chars(buffer, position);
        set("arg", word);
        setiparam("start_pos", start);
        setiparam("end_pos", end);
        const char *style = NULL;
        if (one_of(word, delimiters)) {
            style = redirect ? "unknown-token" : "commandseparator";
            command = 1;
            redirect = 0;
            for_list = 0;
        } else if (!strcmp(word, "for") || !strcmp(word, "select")) {
            style = "reserved-word";
            for_name = 1;
            command = 0;
            ++depth;
        } else if (for_name) {
            style = "default";
            for_name = 0;
            for_list = 1;
        } else if (for_list && !strcmp(word, "in")) {
            style = "reserved-word";
        } else if (one_of(word, starters)) {
            style = "reserved-word";
            command = 1;
            for_list = 0;
            if (!strcmp(word, "if") || !strcmp(word, "while") || !strcmp(word, "until") ||
                !strcmp(word, "{") || !strcmp(word, "("))
                ++depth;
        } else if (one_of(word, closers)) {
            style = depth > 0 ? "reserved-word" : "unknown-token";
            if (depth > 0)
                --depth;
            command = 0;
        } else if (!strcmp(word, "<") || !strcmp(word, ">") || !strcmp(word, ">>") ||
                   !strcmp(word, "<<") || !strcmp(word, "<<<") || !strcmp(word, "<>") ||
                   !strcmp(word, ">|")) {
            style = "redirection";
            redirect = 1;
        } else if (!redirect && command && assignment(word)) {
            style = "assign";
        } else if (!redirect && command && one_of(word, precommands)) {
            style = "precommand";
        } else if (!redirect && command) {
            char *type_args[] = {word, "1", NULL};
            call("_zsh_highlight_main__type", type_args);
            char *type = value("REPLY");
            if (!strcmp(type, "reserved"))
                style = "reserved-word";
            else if (!strcmp(type, "global alias"))
                style = "global-alias";
            else if (!strcmp(type, "suffix alias"))
                style = "suffix-alias";
            else if (!strcmp(type, "none") || !*type)
                style = "unknown-token";
            else if (!strcmp(type, "hashed"))
                style = "hashed-command";
            else
                style = dupstring(type);
            command = 0;
        } else {
            set("this_word", command ? ":start:" : ":regular:");
            set("highlight_glob", "true");
            char *argument_args[] = {"1", redirect ? "0" : "1", NULL};
            call("_zsh_highlight_main_highlighter_highlight_argument", argument_args);
            redirect = 0;
            continue;
        }
        region(start, end, style);
    }
    char **highlights = getaparam("list_highlights");
    char **result = highlights ? zarrdup(highlights) : zalloc(sizeof(char *));
    if (!highlights)
        result[0] = NULL;
    setaparam("reply", result);
    setiparam("REPLY", chars(buffer, strlen(buffer)) - 1);
    popheap();
    return failed || depth > 0 || redirect;
}
static struct builtin builtins[] = {BUILTIN("wsh-highlight-list", 0, parse, 4, 4, 0, NULL, NULL)};
static struct features features = {builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) {
    (void)m;
    return 0;
}
int boot_(Module m) {
    (void)m;
    return 0;
}
int features_(Module m, char ***f) {
    *f = featuresarray(m, &features);
    return 0;
}
int enables_(Module m, int **e) { return handlefeatures(m, &features, e); }
int cleanup_(Module m) { return setfeatureenables(m, &features, NULL); }
int finish_(Module m) {
    (void)m;
    return 0;
}
