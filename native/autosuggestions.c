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
/* Shell-lifetime autosuggestion controller; ZLE and completion callbacks remain Zsh-owned. */
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <termios.h>
#include <unistd.h>
static int wsh_sa_fetch_owned(void);

static int wsh_sa_suggest(char *name, char **args, Options options, int function) {
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
static char *wsh_sa_value(const char *name) {
    char *s = getsparam((char *)name);
    return s ? s : "";
}
static void wsh_sa_assign(const char *name, const char *text) { setsparam((char *)name, ztrdup(text)); }
static int wsh_sa_invoke(const char *name, char **args) {
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
static int wsh_sa_characters(char *s) { return mb_metastrlenend(s, 0, NULL); }
static char *wsh_sa_after_chars(char *s, zlong count) {
    mbstate_t state;
    memset(&state, 0, sizeof(state));
    while (*s && count-- > 0) {
        int n = mb_metacharlenconv_r(s, NULL, &state);
        s += n > 0 ? n : 1;
    }
    return s;
}
static int wsh_sa_exists(const char *name) {
    Param p = (Param)paramtab->getnode(paramtab, name);
    return p && !(p->node.flags & PM_UNSET);
}
static int wsh_sa_action_impl(char *name, char **args, Options options, int function) {
    (void)name;
    (void)options;
    (void)function;
    char *wsh_sa_action = *args++;
    int result = 0;
    if (!strcmp(wsh_sa_action, "suggest")) {
        char *buffer = wsh_sa_value("BUFFER"), *s = *args ? *args : "";
        wsh_sa_assign("POSTDISPLAY",
               *buffer && *s ? (strncmp(s, buffer, strlen(buffer)) ? s : s + strlen(buffer)) : "");
        return 0;
    }
    if (!strcmp(wsh_sa_action, "fetch"))
        return wsh_sa_fetch_owned();
    if (!strcmp(wsh_sa_action, "toggle"))
        wsh_sa_action = wsh_sa_exists("_ZSH_AUTOSUGGEST_DISABLED") ? "enable" : "disable";
    if (!strcmp(wsh_sa_action, "enable")) {
        unsetparam("_ZSH_AUTOSUGGEST_DISABLED");
        return *wsh_sa_value("BUFFER") ? wsh_sa_invoke("_zsh_autosuggest_fetch", NULL) : 0;
    }
    if (!strcmp(wsh_sa_action, "disable")) {
        wsh_sa_assign("_ZSH_AUTOSUGGEST_DISABLED", "");
        wsh_sa_action = "clear";
    }
    if (!strcmp(wsh_sa_action, "clear")) {
        wsh_sa_assign("POSTDISPLAY", "");
        return wsh_sa_invoke("_zsh_autosuggest_invoke_original_widget", args);
    }
    char *original = dupstring(wsh_sa_value("BUFFER")), *display = dupstring(wsh_sa_value("POSTDISPLAY"));
    int length = wsh_sa_characters(original);
    int vi = !strcmp(wsh_sa_value("KEYMAP"), "vicmd");
    if (!strcmp(wsh_sa_action, "modify")) {
        wsh_sa_assign("POSTDISPLAY", "");
        result = wsh_sa_invoke("_zsh_autosuggest_invoke_original_widget", args);
        if (getiparam("PENDING") > 0 || getiparam("KEYS_QUEUED_COUNT") > 0) {
            wsh_sa_assign("POSTDISPLAY", display);
            return result;
        }
        char *buffer = wsh_sa_value("BUFFER");
        if (!strncmp(buffer, original, strlen(original)) &&
            !strncmp(display, buffer + strlen(original), strlen(buffer) - strlen(original))) {
            wsh_sa_assign("POSTDISPLAY", display + strlen(buffer) - strlen(original));
            return result;
        }
        if (wsh_sa_exists("_ZSH_AUTOSUGGEST_DISABLED"))
            return 0;
        char *maximum = wsh_sa_value("ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE");
        if (*buffer && (!*maximum || wsh_sa_characters(buffer) <= mathevali(maximum)))
            wsh_sa_invoke("_zsh_autosuggest_fetch", NULL);
        return result;
    }
    if (!strcmp(wsh_sa_action, "accept")) {
        if (getiparam("CURSOR") != length - vi || !*display)
            return wsh_sa_invoke("_zsh_autosuggest_invoke_original_widget", args);
        wsh_sa_assign("BUFFER", dyncat(original, display));
        wsh_sa_assign("POSTDISPLAY", "");
        result = wsh_sa_invoke("_zsh_autosuggest_invoke_original_widget", args);
        setiparam("CURSOR", wsh_sa_characters(wsh_sa_value("BUFFER")) - (!strcmp(wsh_sa_value("KEYMAP"), "vicmd")));
        return result;
    }
    if (!strcmp(wsh_sa_action, "execute")) {
        wsh_sa_assign("BUFFER", dyncat(original, display));
        wsh_sa_assign("POSTDISPLAY", "");
        char *accept[] = {"accept-line", NULL};
        return wsh_sa_invoke("_zsh_autosuggest_invoke_original_widget", accept);
    }
    if (!strcmp(wsh_sa_action, "partial_accept")) {
        wsh_sa_assign("BUFFER", dyncat(original, display));
        result = wsh_sa_invoke("_zsh_autosuggest_invoke_original_widget", args);
        zlong cursor = getiparam("CURSOR") + (!strcmp(wsh_sa_value("KEYMAP"), "vicmd"));
        if (cursor > length) {
            char *buffer = dupstring(wsh_sa_value("BUFFER")), *suffix = wsh_sa_after_chars(buffer, cursor);
            wsh_sa_assign("POSTDISPLAY", suffix);
            *suffix = 0;
            wsh_sa_assign("BUFFER", buffer);
        } else
            wsh_sa_assign("BUFFER", original);
        return result;
    }
    return 1;
}
static int wsh_sa_action(char *name, char **args, Options options, int function) {
    pushheap();
    int result = wsh_sa_action_impl(name, args, options, function);
    popheap();
    return result;
}
struct wsh_sa_binding {
    struct wsh_sa_binding *next;
    char *name;
    unsigned count;
};
static struct wsh_sa_binding *wsh_sa_bindings;
static char *wsh_sa_pending_prefix;
static char *wsh_sa_response;
static size_t wsh_sa_response_size;
static int wsh_sa_shell_code(char *code) {
    execstring(code, 1, 0, "wsh-autosuggestion-prototype");
    return lastval;
}
static char *wsh_sa_quoted(const char *text) { return quotestring((char *)text, QT_SINGLE_OPTIONAL); }
static int wsh_sa_zle_call(const char *operation, const char *a, const char *b) {
    char *code = zhtricat("builtin zle ", operation, " ");
    if (a)
        code = dyncat(code, wsh_sa_quoted(a));
    if (b)
        code = zhtricat(code, " ", wsh_sa_quoted(b));
    return wsh_sa_shell_code(code);
}
static int wsh_sa_matches(char *pattern, char *text) {
    pattern = dupstring(pattern);
    tokenize(pattern);
    Patprog compiled = patcompile(pattern, 0, NULL);
    return compiled && pattry(compiled, text);
}
static int wsh_sa_member(const char *parameter, char *widget, int patterns) {
    char **entries = getaparam((char *)parameter);
    for (; entries && *entries; ++entries)
        if (patterns ? wsh_sa_matches(*entries, widget) : wsh_sa_matches(widget, *entries))
            return 1;
    return 0;
}
static void wsh_sa_highlight(int apply) {
    char **regions = getaparam("region_highlight"),
         *last = wsh_sa_value("_ZSH_AUTOSUGGEST_LAST_HIGHLIGHT");
    size_t n = regions ? arrlen(regions) : 0, used = 0;
    char **out = zalloc((n + 2) * sizeof(char *));
    for (size_t i = 0; i < n; ++i)
        if (!*last || !wsh_sa_matches(last, regions[i]))
            out[used++] = ztrdup(regions[i]);
    unsetparam("_ZSH_AUTOSUGGEST_LAST_HIGHLIGHT");
    if (apply && *wsh_sa_value("POSTDISPLAY")) {
        char region[80];
        int start = wsh_sa_characters(wsh_sa_value("BUFFER"));
        snprintf(region, sizeof(region), "%d %d ", start, start + wsh_sa_characters(wsh_sa_value("POSTDISPLAY")));
        char *text = dyncat(region, wsh_sa_value("ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE"));
        wsh_sa_assign("_ZSH_AUTOSUGGEST_LAST_HIGHLIGHT", text);
        out[used++] = ztrdup(text);
    }
    out[used] = NULL;
    setaparam("region_highlight", out);
}
static void wsh_sa_collect(char *prefix) {
    char **strategies = getaparam("ZSH_AUTOSUGGEST_STRATEGY");
    if (!strategies)
        strategies = spacesplit(wsh_sa_value("ZSH_AUTOSUGGEST_STRATEGY"), 0, 1, 0);
    strategies = arrdup(strategies);
    wsh_sa_assign("suggestion", "");
    for (char **p = strategies; p && *p; ++p) {
        char *args[] = {prefix, NULL};
        if (!strcmp(*p, "history"))
            wsh_sa_suggest(NULL, args, NULL, 0);
        else if (!strcmp(*p, "match_prev_cmd"))
            wsh_sa_suggest(NULL, args, NULL, 1);
        else
            wsh_sa_invoke(dyncat("_zsh_autosuggest_strategy_", *p), args);
        char *result = wsh_sa_value("suggestion");
        if (strncmp(result, prefix, strlen(prefix)))
            wsh_sa_assign("suggestion", "");
        if (*wsh_sa_value("suggestion"))
            break;
    }
}
static void wsh_sa_cancel_owned(void) {
    zlong fd = getiparam("_ZSH_AUTOSUGGEST_ASYNC_FD");
    pid_t pid = (pid_t)getiparam("_ZSH_AUTOSUGGEST_CHILD_PID");
    if (fd > 2) {
        char text[32];
        snprintf(text, sizeof(text), "%ld", (long)fd);
        wsh_sa_zle_call("-F", text, NULL);
        wsh_sa_shell_code("builtin exec {_ZSH_AUTOSUGGEST_ASYNC_FD}<&-");
    }
    if (pid > 1)
        kill(-pid, SIGTERM);
    wsh_sa_assign("_ZSH_AUTOSUGGEST_ASYNC_FD", "");
    wsh_sa_assign("_ZSH_AUTOSUGGEST_CHILD_PID", "");
    if (wsh_sa_pending_prefix)
        zsfree(wsh_sa_pending_prefix);
    wsh_sa_pending_prefix = NULL;
    free(wsh_sa_response);
    wsh_sa_response = NULL;
    wsh_sa_response_size = 0;
}
static int wsh_sa_fetch_owned(void) {
    char *prefix = dupstring(wsh_sa_value("BUFFER"));
    if (!wsh_sa_exists("ZSH_AUTOSUGGEST_USE_ASYNC")) {
        wsh_sa_collect(prefix);
        char *args[] = {"suggest", wsh_sa_value("suggestion"), NULL};
        return wsh_sa_action_impl(NULL, args, NULL, 0);
    }
    wsh_sa_cancel_owned();
    wsh_sa_pending_prefix = ztrdup(prefix);
    char *code = zhtricat(
        "builtin exec {_ZSH_AUTOSUGGEST_ASYNC_FD}< <(builtin wsh-autosuggest-service collect ",
        wsh_sa_quoted(prefix), ")");
    if (wsh_sa_shell_code(code))
        return 1;
    int fd = (int)getiparam("_ZSH_AUTOSUGGEST_ASYNC_FD");
    char pid[32];
    size_t count = 0;
    while (count + 1 < sizeof(pid)) {
        ssize_t n = read(fd, pid + count, 1);
        if (n < 0 && errno == EINTR)
            continue;
        if (n != 1) {
            wsh_sa_cancel_owned();
            return 1;
        }
        if (pid[count++] == '\n')
            break;
    }
    pid[count] = 0;
    setiparam("_ZSH_AUTOSUGGEST_CHILD_PID", strtol(pid, NULL, 10));
    if (fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK) < 0) {
        wsh_sa_cancel_owned();
        return 1;
    }
    char text[32];
    snprintf(text, sizeof(text), "%d", fd);
    return wsh_sa_zle_call("-F", text, "_zsh_autosuggest_async_response");
}
static int wsh_sa_response_owned(char **args) {
    int fd = atoi(args[0]);
    if (fd != (int)getiparam("_ZSH_AUTOSUGGEST_ASYNC_FD"))
        return 0;
    char block[4096];
    ssize_t n;
    while ((n = read(fd, block, sizeof(block))) > 0) {
        if (wsh_sa_response_size + (size_t)n > 1024 * 1024) {
            wsh_sa_cancel_owned();
            return 1;
        }
        char *next = realloc(wsh_sa_response, wsh_sa_response_size + (size_t)n + 1);
        if (!next) {
            wsh_sa_cancel_owned();
            return 1;
        }
        wsh_sa_response = next;
        memcpy(wsh_sa_response + wsh_sa_response_size, block, (size_t)n);
        wsh_sa_response_size += (size_t)n;
        wsh_sa_response[wsh_sa_response_size] = 0;
    }
#ifdef WSH_SUGGEST_DEBUG
    fprintf(stderr, "response fd=%d n=%ld bytes=%zu prefix=%s buffer=%s\n", fd, (long)n,
            wsh_sa_response_size, wsh_sa_pending_prefix ? wsh_sa_pending_prefix : "null", wsh_sa_value("BUFFER"));
#endif
    if (n < 0 && (errno == EAGAIN || errno == EINTR))
        return 0;
    if (n == 0 && wsh_sa_pending_prefix) {
        char *text = metafy(wsh_sa_response ? wsh_sa_response : "", (int)wsh_sa_response_size, META_HEAPDUP);
        wsh_sa_zle_call("autosuggest-suggest", "--", text);
    }
    wsh_sa_cancel_owned();
    return 0;
}
static void wsh_sa_bind_owned(void) {
    char **names = arrdup(gethkparam("widgets")), **types = arrdup(gethparam("widgets"));
    char *prefix = dupstring(wsh_sa_value("ZSH_AUTOSUGGEST_ORIGINAL_WIDGET_PREFIX"));
    for (size_t i = 0; names && names[i]; ++i) {
        char *widget = names[i];
        if (*widget == '.' || *widget == '_' || !strncmp(widget, "autosuggest-", 12) ||
            (*prefix && !strncmp(widget, prefix, strlen(prefix))) ||
            wsh_sa_member("ZSH_AUTOSUGGEST_IGNORE_WIDGETS", widget, 1))
            continue;
        struct wsh_sa_binding *b = wsh_sa_bindings;
        while (b && strcmp(b->name, widget))
            b = b->next;
        if (!b) {
            b = zalloc(sizeof(*b));
            b->name = ztrdup(widget);
            b->count = 0;
            b->next = wsh_sa_bindings;
            wsh_sa_bindings = b;
        }
        if (strncmp(types[i], "user:_zsh_autosuggest_bound_", 26))
            ++b->count;
        char count[32];
        snprintf(count, sizeof(count), "%u", b->count);
        char *saved = zhtricat(prefix, count, dyncat("-", widget));
        if (strncmp(types[i], "user:_zsh_autosuggest_bound_", 26))
            wsh_sa_zle_call("-A", widget, saved);
        const char *action_name = "modify";
        const char *parameters[] = {
            "ZSH_AUTOSUGGEST_CLEAR_WIDGETS", "ZSH_AUTOSUGGEST_ACCEPT_WIDGETS",
            "ZSH_AUTOSUGGEST_EXECUTE_WIDGETS", "ZSH_AUTOSUGGEST_PARTIAL_ACCEPT_WIDGETS"};
        const char *actions[] = {"clear", "accept", "execute", "partial_accept"};
        for (size_t j = 0; j < 4; ++j)
            if (wsh_sa_member(parameters[j], widget, 0)) {
                action_name = actions[j];
                break;
            }
        char *function = zhtricat("_zsh_autosuggest_bound_", count, dyncat("_", widget));
        char *body =
            zhtricat("function ", wsh_sa_quoted(function), " { builtin wsh-autosuggest-service widget ");
        body = zhtricat(body, action_name, " ");
        body = zhtricat(body, wsh_sa_quoted(saved), " \"$@\"; }");
        wsh_sa_shell_code(body);
        wsh_sa_zle_call("-N --", widget, function);
    }
}
static int wsh_sa_capture_owned(void) {
    setiparam("CURSOR", wsh_sa_characters(wsh_sa_value("BUFFER")));
    char **names = arrdup(gethkparam("widgets")), **types = arrdup(gethparam("widgets"));
    for (size_t i = 0; names && names[i]; ++i)
        if (!strcmp(types[i], "completion:.complete-word:_main_complete")) {
            wsh_sa_zle_call("--", names[i], NULL);
            break;
        }
    struct termios settings;
    if (tcgetattr(STDIN_FILENO, &settings) == 0) {
        settings.c_oflag &= ~(ONLCR | OCRNL);
        tcsetattr(STDIN_FILENO, TCSANOW, &settings);
    }
    char *text = dupstring(wsh_sa_value("BUFFER"));
    int length;
    unmetafy(text, &length);
    putchar(0);
    fwrite(text, 1, (size_t)length, stdout);
    putchar(0);
    fflush(stdout);
    return 0;
}
static int wsh_sa_completion_owned(char *prefix) {
    if (!shfunctab->getnode(shfunctab, "compdef"))
        return 0;
    char *ignore = wsh_sa_value("ZSH_AUTOSUGGEST_COMPLETION_IGNORE");
    if (*ignore && wsh_sa_matches(ignore, prefix))
        return 0;
    if (wsh_sa_shell_code("builtin zmodload zsh/zpty"))
        return 1;
    char *pty = wsh_sa_quoted(wsh_sa_value("ZSH_AUTOSUGGEST_COMPLETIONS_PTY_NAME"));
    if (wsh_sa_zle_call("", NULL, NULL) == 0) {
        if (wsh_sa_shell_code(zhtricat("builtin zpty ", pty, " _zsh_autosuggest_capture_completion_sync")))
            return 1;
    } else {
        if (wsh_sa_shell_code(zhtricat("builtin zpty ", pty,
                                " _zsh_autosuggest_capture_completion_async \"\\$1\"")))
            return 1;
        wsh_sa_shell_code(zhtricat("builtin zpty -w ", pty, " $'\\t'"));
    }
    int result = wsh_sa_shell_code(zhtricat("builtin zpty -r ", pty, " line '*'$'\\0''*'$'\\0'"));
    if (!result) {
        char *line = dupstring(wsh_sa_value("line"));
        int length;
        unmetafy(line, &length);
        char *first = memchr(line, 0, (size_t)length);
        char *last = first ? memchr(first + 1, 0, (size_t)(line + length - first - 1)) : NULL;
        if (last)
            wsh_sa_assign("suggestion", metafy(first + 1, (int)(last - first - 1), META_HEAPDUP));
    }
    wsh_sa_shell_code(dyncat("builtin zpty -d ", pty));
    return result;
}
static int wsh_sa_service(char *name, char **args, Options options, int function) {
    (void)name;
    (void)options;
    (void)function;
    pushheap();
    char *operation = *args++;
    int result = 0;
    if (!strcmp(operation, "bind"))
        wsh_sa_bind_owned();
    else if (!strcmp(operation, "capture"))
        result = wsh_sa_capture_owned();
    else if (!strcmp(operation, "postcompletion")) {
        result = wsh_sa_shell_code("compstate[insert]=1; builtin unset 'compstate[list]'");
    } else if (!strcmp(operation, "completion-setup")) {
        result = wsh_sa_shell_code(
            "builtin zstyle ':completion:*' matcher-list ''; builtin zstyle ':completion:*' "
            "path-completion false; builtin zstyle ':completion:*' max-errors 0 not-numeric; "
            "builtin bindkey '^I' autosuggest-capture-completion");
    } else if (!strcmp(operation, "completion") && *args)
        result = wsh_sa_completion_owned(*args);
    else if (!strcmp(operation, "cancel"))
        wsh_sa_cancel_owned();
    else if (!strcmp(operation, "response") && *args)
        result = wsh_sa_response_owned(args);
    else if (!strcmp(operation, "collect") && *args) {
        /* Establish ownership before publishing the pid to the parent. */
        if (!subsh || setpgid(0, 0) < 0) {
            popheap();
            return 1;
        }
        printf("%ld\n", (long)getpid());
        fflush(stdout);
        wsh_sa_collect(*args);
#ifdef WSH_SUGGEST_DEBUG
        fprintf(stderr, "collect prefix=%s result=%s\n", *args, wsh_sa_value("suggestion"));
#endif
        char *text = dupstring(wsh_sa_value("suggestion"));
        int length;
        unmetafy(text, &length);
        if (fwrite(text, 1, (size_t)length, stdout) != (size_t)length)
            result = 1;
        fflush(stdout);
    } else if (!strcmp(operation, "widget") && *args) {
        if (strcmp(*args, "suggest") || !wsh_sa_pending_prefix ||
            !strcmp(wsh_sa_value("BUFFER"), wsh_sa_pending_prefix)) {
            wsh_sa_highlight(0);
            result = wsh_sa_action_impl(NULL, args, NULL, 0);
            wsh_sa_highlight(1);
            wsh_sa_zle_call("-R", NULL, NULL);
        }
    } else if (!strcmp(operation, "fetch"))
        result = wsh_sa_fetch_owned();
    else
        result = 1;
    popheap();
    return result;
}
static struct builtin wsh_sa_builtins[] = {
    BUILTIN("wsh-autosuggest-service", 0, wsh_sa_service, 1, -1, 0, NULL, NULL),
    BUILTIN("wsh-history-suggest", 0, wsh_sa_suggest, 1, 1, 0, NULL, NULL),
    BUILTIN("wsh-autosuggest-action", 0, wsh_sa_action, 1, -1, 0, NULL, NULL)};
