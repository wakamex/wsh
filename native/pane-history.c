/* Included by hist.c: reuse Zsh's history parser, contexts and locking. */
void wsh_pane_history_prepare(void);
void wsh_pane_history_start(void);
void wsh_pane_history_exit(void);
static char *wsh_pane_file, *wsh_pane_pending, *wsh_pane_shared, *wsh_pane_parameter;
static HashTable wsh_pane_context;
static int wsh_pane_owner_fd = -1;

static int
wsh_pane_uuid(const char *s)
{
    int i;
    if (!s || strlen(s) != 36)
        return 0;
    for (i = 0; i < 36; ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (s[i] != '-') return 0;
        } else if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f')))
            return 0;
    }
    return 1;
}

static int
wsh_pane_enabled(void)
{
    char *skip = getsparam("WAKTERM_SHELL_SKIP_PANE_HISTORY");
    char *owner = getsparam("WAKTERM_PANE_HISTORY_OWNER"), pid[32];
    snprintf(pid, sizeof(pid), "%ld", (long)getpid());
    return interact && isset(RCS) && unset(PRIVILEGED) && !subsh &&
        !(skip && *skip) && (!owner || !*owner || !strcmp(owner, pid)) &&
        wsh_pane_uuid(getsparam("WAKTERM_PANE_TOKEN"));
}

void
wsh_pane_history_prepare(void)
{
    /* The capability belongs to this shell, never to an inherited environment. */
    unsetparam("WSH_NATIVE_PANE_HISTORY");
    if (wsh_pane_enabled()) {
        Param pm = setsparam("WSH_NATIVE_PANE_HISTORY", ztrdup("1"));
        if (pm) {
            pm->node.flags &= ~PM_EXPORTED;
            if (pm->env) delenv(pm);
        }
    }
}

static int
wsh_pane_directory(char *path)
{
    char *raw = ztrdup(unmeta(path)), *p;
    struct stat st;
    int ok = *raw == '/';
    for (p = raw + 1; ok; ++p) {
        if (*p && *p != '/') continue;
        char saved = *p;
        *p = 0;
        if ((mkdir(raw, 0700) && errno != EEXIST) ||
            lstat(raw, &st) || !S_ISDIR(st.st_mode)) ok = 0;
        *p = saved;
        if (!saved) break;
    }
    /* The final directory must be private and owned by this account. */
    if (ok && (st.st_uid != geteuid() || (st.st_mode & 0077))) ok = 0;
    zsfree(raw);
    return ok;
}

static int
wsh_pane_open(char *path)
{
    struct stat st;
    int fd = open(unmeta(path), O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK, 0600);
    if (fd < 0) return -1;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != geteuid() ||
        st.st_nlink != 1 || (st.st_mode & 0077)) {
        close(fd);
        return -1;
    }
    return fd;
}

/* Keep HISTFILE visible and inheritable as the user's original shared path.
 * Only automatic writes in the owning history context go to the journal. */
static char *
wsh_pane_history_target(void)
{
    char *current = getsparam("HISTFILE");
    if (wsh_pane_context && histtab == wsh_pane_context && wsh_pane_enabled() &&
        savehistsiz > 0 && !nohistsave && current && *current &&
        !strcmp(current, wsh_pane_parameter) && unset(SHAREHISTORY))
        return wsh_pane_pending;
    return NULL;
}

/* Each destination is locked across read/merge/rewrite. A crash between the
 * two destinations may replay entries; retaining pending data prevents loss. */
static int
wsh_pane_merge_into(char *destination)
{
    int saved_error = errflag, saved_active = histactive, ok;
    struct stat st;
    if (stat(unmeta(destination), &st) && errno != ENOENT) return 0;
    if (lockhistfile(destination, 0)) return 0;
    errflag = 0;
    histactive = 0;
    pushhiststack(NULL, savehistsiz, savehistsiz, -1);
    readhistfile(destination, 1, 0);
    if (!errflag) readhistfile(wsh_pane_pending, 1, 0);
    if (!errflag) savehistfile(destination, 1, 0);
    ok = !errflag;
    pophiststack();
    histactive = saved_active;
    errflag = saved_error;
    unlockhistfile(destination);
    return ok;
}

static int
wsh_pane_merge(void)
{
    struct stat st;
    if (stat(unmeta(wsh_pane_pending), &st)) return errno == ENOENT;
    if (!st.st_size) return 1;
    if (!wsh_pane_merge_into(wsh_pane_shared) || !wsh_pane_merge_into(wsh_pane_file)) {
        zwarn("pane history merge incomplete; pending commands retained in %s", wsh_pane_pending);
        return 0;
    }
    return unlink(unmeta(wsh_pane_pending)) == 0;
}

void
wsh_pane_history_start(void)
{
    char *shared = getsparam("HISTFILE"), *state, *directory, *lockpath, pid[32];
    int fd, saved_error = errflag;
    struct flock lock;
    if (!getsparam("WSH_NATIVE_PANE_HISTORY")) return;
    if (!wsh_pane_enabled() || !shared || !*shared || savehistsiz <= 0 ||
        histsave_stack_pos || nohistsave) goto disabled;
    wsh_pane_parameter = ztrdup(shared);
    wsh_pane_shared = *shared == '/' ? ztrdup(shared) : tricat(pwd, "/", shared);
    state = getsparam("XDG_STATE_HOME");
    if (state && *state == '/') state = ztrdup(state);
    else {
        state = getsparam("HOME");
        if (!state || *state != '/') goto disabled;
        state = dyncat(state, "/.local/state");
        state = ztrdup(state);
    }
    directory = tricat(state, "/wsh/history/", "panes");
    zsfree(state);
    if (!wsh_pane_directory(directory)) { zsfree(directory); goto disabled; }
    wsh_pane_file = tricat(directory, "/", getsparam("WAKTERM_PANE_TOKEN"));
    zsfree(directory);
    state = wsh_pane_file;
    wsh_pane_file = bicat(state, ".zsh");
    zsfree(state);
    wsh_pane_pending = bicat(wsh_pane_file, ".pending");
    lockpath = bicat(wsh_pane_file, ".owner");
    fd = wsh_pane_open(lockpath);
    zsfree(lockpath);
    if (fd < 0) goto disabled;
    memset(&lock, 0, sizeof(lock));
    lock.l_type = F_WRLCK;
    lock.l_whence = SEEK_SET;
    /* movefd closes the original descriptor, which releases POSIX locks. */
    wsh_pane_owner_fd = movefd(fd);
    if (wsh_pane_owner_fd < 0) goto disabled;
    if (fcntl(wsh_pane_owner_fd, F_SETLK, &lock)) goto disabled;
    fdtable[wsh_pane_owner_fd] = FDT_INTERNAL;
    fcntl(wsh_pane_owner_fd, F_SETFD, FD_CLOEXEC);
    fd = wsh_pane_open(wsh_pane_file);
    if (fd < 0) goto disabled;
    close(fd);
    fd = wsh_pane_open(wsh_pane_pending);
    if (fd < 0) goto disabled;
    close(fd);
    /* Refuse to add new work to a journal whose previous merge failed. */
    if (!wsh_pane_merge()) goto disabled;
    readhistfile(wsh_pane_file, 1, 0);
    if (errflag) { errflag = saved_error; goto disabled; }
    opts[SHAREHISTORY] = 0;
    if (isset(INCAPPENDHISTORYTIME)) opts[INCAPPENDHISTORY] = 0;
    else opts[INCAPPENDHISTORY] = 1;
    zsfree(lasthist.text);
    memset(&lasthist, 0, sizeof(lasthist));
    histfile_linect = 0;
    wsh_pane_context = histtab;
    snprintf(pid, sizeof(pid), "%ld", (long)getpid());
    {
        Param pm = setsparam("WAKTERM_PANE_HISTORY_OWNER", ztrdup(pid));
        if (pm) { pm->node.flags |= PM_EXPORTED; addenv(pm, pid); }
    }
    return;

disabled:
    unsetparam("WSH_NATIVE_PANE_HISTORY");
    if (wsh_pane_owner_fd >= 0) { close(wsh_pane_owner_fd); wsh_pane_owner_fd = -1; }
    zsfree(wsh_pane_file); wsh_pane_file = NULL;
    zsfree(wsh_pane_pending); wsh_pane_pending = NULL;
    zsfree(wsh_pane_shared); wsh_pane_shared = NULL;
    zsfree(wsh_pane_parameter); wsh_pane_parameter = NULL;
}

void
wsh_pane_history_exit(void)
{
    if (wsh_pane_history_target()) (void)wsh_pane_merge();
}
