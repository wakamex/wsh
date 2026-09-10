/*
 * Autosuggestion behavior ported from zsh-autosuggestions.
 * Copyright (c) 2013 Thiago de Arruda
 * Copyright (c) 2016-2021 Eric Freese
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use,
 * copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following
 * conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
 * OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 * OTHER DEALINGS IN THE SOFTWARE.
 */
/* Private complete autosuggestion controller. Not selected by the installation. */
#define _GNU_SOURCE 1
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <termios.h>
#include <unistd.h>
static int fetch_owned(void);

static int suggest(char *name, char **args, Options options, int function) {
    (void)name;
    (void)options;
    pushheap();
    char *prefix = quotestring(args[0], QT_BACKSLASH_PATTERN);
    char *ignore = getsparam("ZSH_AUTOSUGGEST_HISTORY_IGNORE");
    char *pattern = dyncat(prefix, "*");
    if (ignore && *ignore)
        pattern = zhtricat("(", pattern, zhtricat(")~(", ignore, ")"));
    tokenize(pattern);
    unsigned char extended = opts[EXTENDEDGLOB];
    opts[EXTENDEDGLOB] = 1;
    Patprog compiled = patcompile(pattern, 0, NULL);
    opts[EXTENDEDGLOB] = extended;
    char *result = "";
    Histent entry = gethistent(addhistnum(curhist, -1, HIST_FOREIGN), GETHIST_UPWARD);
    char *previous = entry ? entry->node.nam : "";
    char *escaped = zhalloc(strlen(previous) * 2 + 1), *destination = escaped;
    for (char *p = previous; *p; ++p) {
        if (strchr("\"'\\()[]|*?~", *p))
            *destination++ = '\\';
        *destination++ = *p;
    }
    *destination = 0;
    int found = 0;
    for (; entry; entry = up_histent(entry)) {
        if (!compiled || pattry(compiled, entry->node.nam)) {
            if (!found)
                result = entry->node.nam;
            if (!function)
                break;
            if (++found > 200 || entry->histnum <= 1)
                break;
            Histent before = gethistent(entry->histnum - 1, 0);
            if (before && !strcmp(before->node.nam, escaped)) {
                result = entry->node.nam;
                break;
            }
        }
    }
    setsparam("suggestion", ztrdup(result));
    popheap();
    return 0;
}
static char *value(const char *name) {
    char *s = getsparam((char *)name);
    return s ? s : "";
}
static void assign(const char *name, const char *text) { setsparam((char *)name, ztrdup(text)); }
static int invoke(const char *name, char **args) {
    Shfunc fn = (Shfunc)shfunctab->getnode(shfunctab, name);
    if (!fn)
        return 1;
    LinkList list = newlinklist();
    addlinknode(list, dupstring(name));
    if (args)
        for (; *args; ++args)
            addlinknode(list, dupstring(*args));
    return doshfunc(fn, list, 0);
}
static int characters(char *s) { return mb_metastrlenend(s, 0, NULL); }
static char *after_chars(char *s, zlong count) {
    mbstate_t state;
    memset(&state, 0, sizeof(state));
    while (*s && count-- > 0) {
        int n = mb_metacharlenconv_r(s, NULL, &state);
        s += n > 0 ? n : 1;
    }
    return s;
}
static int exists(const char *name) {
    Param p = (Param)paramtab->getnode(paramtab, name);
    return p && !(p->node.flags & PM_UNSET);
}
static int action_impl(char *name, char **args, Options options, int function) {
    (void)name;
    (void)options;
    (void)function;
    char *action = *args++;
    int result = 0;
    if (!strcmp(action, "suggest")) {
        char *buffer = value("BUFFER"), *s = *args ? *args : "";
        assign("POSTDISPLAY",
               *buffer && *s ? (strncmp(s, buffer, strlen(buffer)) ? s : s + strlen(buffer)) : "");
        return 0;
    }
    if (!strcmp(action, "fetch"))
        return fetch_owned();
    if (!strcmp(action, "toggle"))
        action = exists("_ZSH_AUTOSUGGEST_DISABLED") ? "enable" : "disable";
    if (!strcmp(action, "enable")) {
        unsetparam("_ZSH_AUTOSUGGEST_DISABLED");
        return *value("BUFFER") ? invoke("_zsh_autosuggest_fetch", NULL) : 0;
    }
    if (!strcmp(action, "disable")) {
        assign("_ZSH_AUTOSUGGEST_DISABLED", "");
        action = "clear";
    }
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
        if (getiparam("PENDING") > 0 || getiparam("KEYS_QUEUED_COUNT") > 0) {
            assign("POSTDISPLAY", display);
            return result;
        }
        char *buffer = value("BUFFER");
        if (!strncmp(buffer, original, strlen(original)) &&
            !strncmp(display, buffer + strlen(original), strlen(buffer) - strlen(original))) {
            assign("POSTDISPLAY", display + strlen(buffer) - strlen(original));
            return result;
        }
        if (exists("_ZSH_AUTOSUGGEST_DISABLED"))
            return 0;
        char *maximum = value("ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE");
        if (*buffer && (!*maximum || characters(buffer) <= mathevali(maximum)))
            invoke("_zsh_autosuggest_fetch", NULL);
        return result;
    }
    if (!strcmp(action, "accept")) {
        if (getiparam("CURSOR") != length - vi || !*display)
            return invoke("_zsh_autosuggest_invoke_original_widget", args);
        assign("BUFFER", dyncat(original, display));
        assign("POSTDISPLAY", "");
        result = invoke("_zsh_autosuggest_invoke_original_widget", args);
        setiparam("CURSOR", characters(value("BUFFER")) - (!strcmp(value("KEYMAP"), "vicmd")));
        return result;
    }
    if (!strcmp(action, "execute")) {
        assign("BUFFER", dyncat(original, display));
        assign("POSTDISPLAY", "");
        char *accept[] = {"accept-line", NULL};
        return invoke("_zsh_autosuggest_invoke_original_widget", accept);
    }
    if (!strcmp(action, "partial_accept")) {
        assign("BUFFER", dyncat(original, display));
        result = invoke("_zsh_autosuggest_invoke_original_widget", args);
        zlong cursor = getiparam("CURSOR") + (!strcmp(value("KEYMAP"), "vicmd"));
        if (cursor > length) {
            char *buffer = dupstring(value("BUFFER")), *suffix = after_chars(buffer, cursor);
            assign("POSTDISPLAY", suffix);
            *suffix = 0;
            assign("BUFFER", buffer);
        } else
            assign("BUFFER", original);
        return result;
    }
    return 1;
}
static int action(char *name, char **args, Options options, int function) {
    pushheap();
    int result = action_impl(name, args, options, function);
    popheap();
    return result;
}
struct binding {
    struct binding *next;
    char *name;
    unsigned count;
};
static struct binding *bindings;
static char *pending_prefix;
static char *response;
static size_t response_size;
static int shell_code(char *code) {
    execstring(code, 1, 0, "wsh-autosuggestion-prototype");
    return lastval;
}
static char *quoted(const char *text) { return quotestring((char *)text, QT_SINGLE_OPTIONAL); }
static int zle_call(const char *operation, const char *a, const char *b) {
    char *code = zhtricat("builtin zle ", operation, " ");
    if (a)
        code = dyncat(code, quoted(a));
    if (b)
        code = zhtricat(code, " ", quoted(b));
    return shell_code(code);
}
static int matches(char *pattern, char *text) {
    pattern = dupstring(pattern);
    tokenize(pattern);
    Patprog compiled = patcompile(pattern, 0, NULL);
    return compiled && pattry(compiled, text);
}
static int member(const char *parameter, char *widget, int patterns) {
    char **entries = getaparam((char *)parameter);
    for (; entries && *entries; ++entries)
        if (patterns ? matches(*entries, widget) : matches(widget, *entries))
            return 1;
    return 0;
}
static void highlight(int apply) {
    char **regions = getaparam("region_highlight"),
         *last = value("_ZSH_AUTOSUGGEST_LAST_HIGHLIGHT");
    size_t n = regions ? arrlen(regions) : 0, used = 0;
    char **out = zalloc((n + 2) * sizeof(char *));
    for (size_t i = 0; i < n; ++i)
        if (!*last || !matches(last, regions[i]))
            out[used++] = ztrdup(regions[i]);
    unsetparam("_ZSH_AUTOSUGGEST_LAST_HIGHLIGHT");
    if (apply && *value("POSTDISPLAY")) {
        char region[80];
        int start = characters(value("BUFFER"));
        snprintf(region, sizeof(region), "%d %d ", start, start + characters(value("POSTDISPLAY")));
        char *text = dyncat(region, value("ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE"));
        assign("_ZSH_AUTOSUGGEST_LAST_HIGHLIGHT", text);
        out[used++] = ztrdup(text);
    }
    out[used] = NULL;
    setaparam("region_highlight", out);
}
static void collect(char *prefix) {
    char **strategies = getaparam("ZSH_AUTOSUGGEST_STRATEGY");
    if (!strategies)
        strategies = spacesplit(value("ZSH_AUTOSUGGEST_STRATEGY"), 0, 1, 0);
    strategies = arrdup(strategies);
    assign("suggestion", "");
    for (char **p = strategies; p && *p; ++p) {
        char *args[] = {prefix, NULL};
        if (!strcmp(*p, "history"))
            suggest(NULL, args, NULL, 0);
        else if (!strcmp(*p, "match_prev_cmd"))
            suggest(NULL, args, NULL, 1);
        else
            invoke(dyncat("_zsh_autosuggest_strategy_", *p), args);
        char *result = value("suggestion");
        if (strncmp(result, prefix, strlen(prefix)))
            assign("suggestion", "");
        if (*value("suggestion"))
            break;
    }
}
static void cancel_owned(void) {
    zlong fd = getiparam("_ZSH_AUTOSUGGEST_ASYNC_FD");
    pid_t pid = (pid_t)getiparam("_ZSH_AUTOSUGGEST_CHILD_PID");
    if (fd > 2) {
        char text[32];
        snprintf(text, sizeof(text), "%ld", (long)fd);
        zle_call("-F", text, NULL);
        shell_code("builtin exec {_ZSH_AUTOSUGGEST_ASYNC_FD}<&-");
    }
    if (pid > 1)
        kill(-pid, SIGTERM);
    assign("_ZSH_AUTOSUGGEST_ASYNC_FD", "");
    assign("_ZSH_AUTOSUGGEST_CHILD_PID", "");
    if (pending_prefix)
        zsfree(pending_prefix);
    pending_prefix = NULL;
    free(response);
    response = NULL;
    response_size = 0;
}
static int fetch_owned(void) {
    char *prefix = dupstring(value("BUFFER"));
    if (!exists("ZSH_AUTOSUGGEST_USE_ASYNC")) {
        collect(prefix);
        char *args[] = {"suggest", value("suggestion"), NULL};
        return action_impl(NULL, args, NULL, 0);
    }
    cancel_owned();
    pending_prefix = ztrdup(prefix);
    char *code = zhtricat(
        "builtin exec {_ZSH_AUTOSUGGEST_ASYNC_FD}< <(builtin wsh-autosuggest-service collect ",
        quoted(prefix), ")");
    if (shell_code(code))
        return 1;
    int fd = (int)getiparam("_ZSH_AUTOSUGGEST_ASYNC_FD");
    char pid[32];
    size_t count = 0;
    while (count + 1 < sizeof(pid)) {
        ssize_t n = read(fd, pid + count, 1);
        if (n < 0 && errno == EINTR)
            continue;
        if (n != 1) {
            cancel_owned();
            return 1;
        }
        if (pid[count++] == '\n')
            break;
    }
    pid[count] = 0;
    setiparam("_ZSH_AUTOSUGGEST_CHILD_PID", strtol(pid, NULL, 10));
    if (fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK) < 0) {
        cancel_owned();
        return 1;
    }
    char text[32];
    snprintf(text, sizeof(text), "%d", fd);
    return zle_call("-F", text, "_zsh_autosuggest_async_response");
}
static int response_owned(char **args) {
    int fd = atoi(args[0]);
    if (fd != (int)getiparam("_ZSH_AUTOSUGGEST_ASYNC_FD"))
        return 0;
    char block[4096];
    ssize_t n;
    while ((n = read(fd, block, sizeof(block))) > 0) {
        if (response_size + (size_t)n > 1024 * 1024) {
            cancel_owned();
            return 1;
        }
        char *next = realloc(response, response_size + (size_t)n + 1);
        if (!next) {
            cancel_owned();
            return 1;
        }
        response = next;
        memcpy(response + response_size, block, (size_t)n);
        response_size += (size_t)n;
        response[response_size] = 0;
    }
#ifdef WSH_SUGGEST_DEBUG
    fprintf(stderr, "response fd=%d n=%ld bytes=%zu prefix=%s buffer=%s\n", fd, (long)n,
            response_size, pending_prefix ? pending_prefix : "null", value("BUFFER"));
#endif
    if (n < 0 && (errno == EAGAIN || errno == EINTR))
        return 0;
    if (n == 0 && pending_prefix) {
        char *text = metafy(response ? response : "", (int)response_size, META_HEAPDUP);
        zle_call("autosuggest-suggest", "--", text);
    }
    cancel_owned();
    return 0;
}
static void bind_owned(void) {
    char **names = arrdup(gethkparam("widgets")), **types = arrdup(gethparam("widgets"));
    char *prefix = dupstring(value("ZSH_AUTOSUGGEST_ORIGINAL_WIDGET_PREFIX"));
    for (size_t i = 0; names && names[i]; ++i) {
        char *widget = names[i];
        if (*widget == '.' || *widget == '_' || !strncmp(widget, "autosuggest-", 12) ||
            (*prefix && !strncmp(widget, prefix, strlen(prefix))) ||
            member("ZSH_AUTOSUGGEST_IGNORE_WIDGETS", widget, 1))
            continue;
        struct binding *b = bindings;
        while (b && strcmp(b->name, widget))
            b = b->next;
        if (!b) {
            b = zalloc(sizeof(*b));
            b->name = ztrdup(widget);
            b->count = 0;
            b->next = bindings;
            bindings = b;
        }
        if (strncmp(types[i], "user:_zsh_autosuggest_bound_", 26))
            ++b->count;
        char count[32];
        snprintf(count, sizeof(count), "%u", b->count);
        char *saved = zhtricat(prefix, count, dyncat("-", widget));
        if (strncmp(types[i], "user:_zsh_autosuggest_bound_", 26))
            zle_call("-A", widget, saved);
        const char *action_name = "modify";
        const char *parameters[] = {
            "ZSH_AUTOSUGGEST_CLEAR_WIDGETS", "ZSH_AUTOSUGGEST_ACCEPT_WIDGETS",
            "ZSH_AUTOSUGGEST_EXECUTE_WIDGETS", "ZSH_AUTOSUGGEST_PARTIAL_ACCEPT_WIDGETS"};
        const char *actions[] = {"clear", "accept", "execute", "partial_accept"};
        for (size_t j = 0; j < 4; ++j)
            if (member(parameters[j], widget, 0)) {
                action_name = actions[j];
                break;
            }
        char *function = zhtricat("_zsh_autosuggest_bound_", count, dyncat("_", widget));
        char *body =
            zhtricat("function ", quoted(function), " { builtin wsh-autosuggest-service widget ");
        body = zhtricat(body, action_name, " ");
        body = zhtricat(body, quoted(saved), " \"$@\"; }");
        shell_code(body);
        zle_call("-N --", widget, function);
    }
}
static int capture_owned(void) {
    setiparam("CURSOR", characters(value("BUFFER")));
    char **names = arrdup(gethkparam("widgets")), **types = arrdup(gethparam("widgets"));
    for (size_t i = 0; names && names[i]; ++i)
        if (!strcmp(types[i], "completion:.complete-word:_main_complete")) {
            zle_call("--", names[i], NULL);
            break;
        }
    struct termios settings;
    if (tcgetattr(STDIN_FILENO, &settings) == 0) {
        settings.c_oflag &= ~(ONLCR | OCRNL);
        tcsetattr(STDIN_FILENO, TCSANOW, &settings);
    }
    char *text = dupstring(value("BUFFER"));
    int length;
    unmetafy(text, &length);
    putchar(0);
    fwrite(text, 1, (size_t)length, stdout);
    putchar(0);
    fflush(stdout);
    return 0;
}
static int completion_owned(char *prefix) {
    if (!shfunctab->getnode(shfunctab, "compdef"))
        return 0;
    char *ignore = value("ZSH_AUTOSUGGEST_COMPLETION_IGNORE");
    if (*ignore && matches(ignore, prefix))
        return 0;
    if (shell_code("builtin zmodload zsh/zpty"))
        return 1;
    char *pty = quoted(value("ZSH_AUTOSUGGEST_COMPLETIONS_PTY_NAME"));
    if (zle_call("", NULL, NULL) == 0) {
        if (shell_code(zhtricat("builtin zpty ", pty, " _zsh_autosuggest_capture_completion_sync")))
            return 1;
    } else {
        if (shell_code(zhtricat("builtin zpty ", pty,
                                " _zsh_autosuggest_capture_completion_async \"\\$1\"")))
            return 1;
        shell_code(zhtricat("builtin zpty -w ", pty, " $'\\t'"));
    }
    int result = shell_code(zhtricat("builtin zpty -r ", pty, " line '*'$'\\0''*'$'\\0'"));
    if (!result) {
        char *line = dupstring(value("line"));
        int length;
        unmetafy(line, &length);
        char *first = memchr(line, 0, (size_t)length);
        char *last = first ? memchr(first + 1, 0, (size_t)(line + length - first - 1)) : NULL;
        if (last)
            assign("suggestion", metafy(first + 1, (int)(last - first - 1), META_HEAPDUP));
    }
    shell_code(dyncat("builtin zpty -d ", pty));
    return result;
}
static int service(char *name, char **args, Options options, int function) {
    (void)name;
    (void)options;
    (void)function;
    pushheap();
    char *operation = *args++;
    int result = 0;
    if (!strcmp(operation, "bind"))
        bind_owned();
    else if (!strcmp(operation, "capture"))
        result = capture_owned();
    else if (!strcmp(operation, "postcompletion")) {
        result = shell_code("compstate[insert]=1; builtin unset 'compstate[list]'");
    } else if (!strcmp(operation, "completion-setup")) {
        result = shell_code(
            "builtin zstyle ':completion:*' matcher-list ''; builtin zstyle ':completion:*' "
            "path-completion false; builtin zstyle ':completion:*' max-errors 0 not-numeric; "
            "builtin bindkey '^I' autosuggest-capture-completion");
    } else if (!strcmp(operation, "completion") && *args)
        result = completion_owned(*args);
    else if (!strcmp(operation, "cancel"))
        cancel_owned();
    else if (!strcmp(operation, "response") && *args)
        result = response_owned(args);
    else if (!strcmp(operation, "collect") && *args) {
        /* Establish ownership before publishing the pid to the parent. */
        if (!subsh || setpgid(0, 0) < 0) {
            popheap();
            return 1;
        }
        printf("%ld\n", (long)getpid());
        fflush(stdout);
        collect(*args);
#ifdef WSH_SUGGEST_DEBUG
        fprintf(stderr, "collect prefix=%s result=%s\n", *args, value("suggestion"));
#endif
        char *text = dupstring(value("suggestion"));
        int length;
        unmetafy(text, &length);
        if (fwrite(text, 1, (size_t)length, stdout) != (size_t)length)
            result = 1;
        fflush(stdout);
    } else if (!strcmp(operation, "widget") && *args) {
        if (strcmp(*args, "suggest") || !pending_prefix ||
            !strcmp(value("BUFFER"), pending_prefix)) {
            highlight(0);
            result = action_impl(NULL, args, NULL, 0);
            highlight(1);
            zle_call("-R", NULL, NULL);
        }
    } else if (!strcmp(operation, "fetch"))
        result = fetch_owned();
    else
        result = 1;
    popheap();
    return result;
}
static struct builtin builtins[] = {
    BUILTIN("wsh-autosuggest-service", 0, service, 1, -1, 0, NULL, NULL),
    BUILTIN("wsh-history-suggest", 0, suggest, 1, 1, 0, NULL, NULL),
    BUILTIN("wsh-autosuggest-action", 0, action, 1, -1, 0, NULL, NULL)};
static struct features module_features = {builtins, 3, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) {
    (void)m;
    return 0;
}
int boot_(Module m) {
    (void)m;
    return 0;
}
int features_(Module m, char ***features) {
    *features = featuresarray(m, &module_features);
    return 0;
}
int enables_(Module m, int **enables) { return handlefeatures(m, &module_features, enables); }
int cleanup_(Module m) {
    cancel_owned();
    if (bindings)
        return 1;
    return setfeatureenables(m, &module_features, NULL);
}
int finish_(Module m) {
    (void)m;
    return 0;
}
