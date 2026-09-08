/* The diagnostic child uses normal native startup, then reads owned parameters.
 * Only its bounded, formatted report crosses the pipe; configuration output is
 * discarded. No report file, shell command string, or report parser is needed. */
#include <poll.h>
#include <signal.h>
#include <sys/wait.h>
#include <time.h>

static int wsh_doctor_fd = -1;
static char *wsh_doctor_arguments[5];
static char wsh_doctor_interactive[] = "-i";
static char wsh_doctor_command[] = "-c";
static char wsh_doctor_empty[] = "";
static volatile sig_atomic_t wsh_doctor_signal;

static void
wsh_doctor_interrupted(int signum)
{
    wsh_doctor_signal = signum;
}

static double
wsh_doctor_clock(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now))
        return -1;
    return now.tv_sec + now.tv_nsec / 1000000000.0;
}

static int
wsh_doctor_start(char *program)
{
    int channel[2], status = 0, complete = 0, failure = 0;
    size_t used = 0;
    char report[4096];
    pid_t child;
    double start = wsh_doctor_clock();
    struct sigaction action, old_int, old_term;

    if (start < 0 || pipe(channel)) {
        fputs("error: could not create diagnostic channel\n", stderr);
        return 1;
    }
    child = fork();
    if (child < 0) {
        close(channel[0]);
        close(channel[1]);
        fputs("error: could not start diagnostic shell\n", stderr);
        return 1;
    }
    if (!child) {
        int nullfd;
        close(channel[0]);
        if (setpgid(0, 0) || fcntl(channel[1], F_SETFD, FD_CLOEXEC) < 0)
            _exit(1);
        nullfd = open("/dev/null", O_RDWR);
        if (nullfd < 0)
            _exit(1);
        if (dup2(nullfd, 0) < 0 || dup2(nullfd, 1) < 0 || dup2(nullfd, 2) < 0)
            _exit(1);
        if (nullfd > 2)
            close(nullfd);
        wsh_doctor_fd = channel[1];
        wsh_doctor_arguments[0] = program;
        wsh_doctor_arguments[1] = wsh_doctor_interactive;
        wsh_doctor_arguments[2] = wsh_doctor_command;
        wsh_doctor_arguments[3] = wsh_doctor_empty;
        wsh_doctor_arguments[4] = NULL;
        return -1;
    }
    close(channel[1]);
    /* Either side may establish the group first. Cleanup also kills the direct
     * child in case it exited or changed group before this call. */
    (void)setpgid(child, child);
    memset(&action, 0, sizeof(action));
    action.sa_handler = wsh_doctor_interrupted;
    sigemptyset(&action.sa_mask);
    sigaction(SIGINT, &action, &old_int);
    sigaction(SIGTERM, &action, &old_term);
    while (!complete && !failure && !wsh_doctor_signal) {
        struct pollfd descriptor = {channel[0], POLLIN, 0};
        int ready = poll(&descriptor, 1, 10);
        double now = wsh_doctor_clock();
        if (now < 0 || now - start >= 10) {
            fputs("error: diagnostic shell did not finish within 10 seconds\n", stderr);
            failure = 1;
        } else if (ready < 0 && errno != EINTR) {
            failure = 1;
        } else if (ready > 0 && (descriptor.revents & (POLLIN | POLLHUP))) {
            ssize_t count = read(channel[0], report + used, sizeof(report) - used);
            if (count > 0) {
                used += (size_t)count;
                if (used == sizeof(report))
                    failure = 1;
            } else if (!count) {
                complete = 1;
            } else if (errno != EINTR) {
                failure = 1;
            }
        }
    }
    close(channel[0]);
    while (!failure && !wsh_doctor_signal) {
        pid_t result = waitpid(child, &status, WNOHANG);
        double now;
        if (result == child)
            break;
        if (result < 0 && errno != EINTR) {
            failure = 1;
            break;
        }
        now = wsh_doctor_clock();
        if (now < 0 || now - start >= 10) {
            failure = 1;
            break;
        }
        poll(NULL, 0, 10);
    }
    if (failure || wsh_doctor_signal) {
        kill(child, SIGKILL);
        while (waitpid(child, &status, 0) < 0 && errno == EINTR)
            ;
    }
    kill(-child, SIGKILL);
    sigaction(SIGINT, &old_int, NULL);
    sigaction(SIGTERM, &old_term, NULL);
    if (wsh_doctor_signal)
        return 128 + wsh_doctor_signal;
    if (failure || !WIFEXITED(status) || WEXITSTATUS(status) || !used) {
        fputs("error: diagnostic shell did not return a complete ownership report\n", stderr);
        return 1;
    }
    if (fwrite(report, 1, used, stdout) != used || fflush(stdout) == EOF)
        return 1;
    return 0;
}

static const char *
wsh_doctor_parameter(char *name)
{
    char *value = getsparam(name);
    return value ? value : "unset";
}

static int
wsh_doctor_finding(const char *owner, const char *replaced)
{
    if ((!strcmp(owner, "wsh") && !strcmp(replaced, "1")) ||
        ((!strcmp(owner, "external-active") || !strcmp(owner, "external-exact")) && !strcmp(replaced, "0")))
        return 1;
    if (!strcmp(owner, "external-unknown") && !strcmp(replaced, "0"))
        return 2;
    if ((!strcmp(owner, "wsh") || !strcmp(owner, "disabled")) && !strcmp(replaced, "0"))
        return 0;
    return -1;
}

static void
wsh_doctor_finish(void)
{
    FILE *output;
    const char *owners[3], *replaced[3], *prompt, *theme;
    const char *names[] = {"zsh-history-substring-search", "zsh-autosuggestions", "zsh-syntax-highlighting"};
    int findings[3], i, count = 0, unsupported = 1;
    if (wsh_doctor_fd < 0)
        return;
    owners[0] = wsh_doctor_parameter("WSH_HISTORY_SUBSTRING_SEARCH_OWNER");
    owners[1] = wsh_doctor_parameter("WSH_AUTOSUGGESTIONS_OWNER");
    owners[2] = wsh_doctor_parameter("WSH_SYNTAX_HIGHLIGHTING_OWNER");
    replaced[0] = wsh_doctor_parameter("WSH_HISTORY_SUBSTRING_SEARCH_REPLACED");
    replaced[1] = wsh_doctor_parameter("WSH_AUTOSUGGESTIONS_REPLACED");
    replaced[2] = "0";
    if (!strcmp(owners[2], "disabled") && !strcmp(wsh_doctor_parameter("_WSH_SYNTAX_HIGHLIGHTING_LOAD"), "1"))
        owners[2] = "wsh";
    for (i = 0; i < 3; ++i) {
        if (strcmp(owners[i], "unset") || (i < 2 && strcmp(replaced[i], "unset")))
            unsupported = 0;
        findings[i] = wsh_doctor_finding(owners[i], replaced[i]);
        if (findings[i] > 0)
            ++count;
    }
    prompt = wsh_doctor_parameter("WSH_PROMPT_OWNER");
    theme = getsparam("ZSH_THEME");
    if (!unsupported && (findings[0] < 0 || findings[1] < 0 || findings[2] < 0 ||
        (strcmp(prompt, "wsh") && strcmp(prompt, "existing") && strcmp(prompt, "unset"))))
        _exit(1);
    output = fdopen(wsh_doctor_fd, "w");
    if (!output)
        _exit(1);
    if (unsupported) {
        fputs("Plugin compatibility: this bundle does not expose plugin ownership diagnostics.\n", output);
    } else {
        fputs(count ? "Plugin compatibility:\n" : "Plugin compatibility: no redundant or unrecognized external implementations detected.\n", output);
        for (i = 0; i < 3; ++i) {
            if (findings[i] == 1)
                fprintf(output, "- %s: an exact external copy is redundant. Wsh supplies the tested copy. If you also use regular Zsh, load the external copy conditionally outside Wsh; otherwise remove its startup declaration.\n", names[i]);
            else if (findings[i] == 2)
                fprintf(output, "- %s: a modified or unrecognized external implementation was preserved. No removal is suggested.\n", names[i]);
        }
        if (!strcmp(prompt, "wsh") && theme && *theme && shfunctab->getnode(shfunctab, "_omz_source"))
            fputs("Prompt compatibility: Wsh owns the prompt and Oh My Zsh has a theme configured.\n"
                  "To keep your theme in regular Zsh, add this after setting ZSH_THEME and before sourcing oh-my-zsh.sh:\n"
                  "  if [[ -n ${WSH_THEME-} ]]; then\n    ZSH_THEME=\"\"\n  fi\n"
                  "Setting WSH_THEME alone does not skip the OMZ theme. Alternatively, use WSH_THEME= wsh to keep the existing prompt.\n", output);
    }
    _exit(fclose(output) ? 1 : 0);
}
