#ifndef WSH_PORTABLE_H
#define WSH_PORTABLE_H
/* The few Linux interfaces the runtime uses, with their portable equivalents elsewhere. */
#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif

/* Linux sets close-on-exec atomically; elsewhere a fork between pipe() and fcntl() can
 * inherit the descriptors, which an exec then closes anyway. */
static inline int wsh_pipe(int pair[2], int nonblocking)
{
#ifdef __linux__
    return pipe2(pair, O_CLOEXEC | (nonblocking ? O_NONBLOCK : 0));
#else
    int i;
    if (pipe(pair)) return -1;
    for (i = 0; i < 2; ++i)
        if (fcntl(pair[i], F_SETFD, FD_CLOEXEC) < 0 || (nonblocking && fcntl(pair[i], F_SETFL, O_NONBLOCK) < 0)) {
            close(pair[0]); close(pair[1]); return -1;
        }
    return 0;
#endif
}

/* Ask for a signal when the parent exits. Without it the runtime still stops at end of input,
 * and Git children stay bounded by the collector's deadline. */
static inline int wsh_parent_death_signal(int signal_number)
{
#ifdef __linux__
    return prctl(PR_SET_PDEATHSIG, (unsigned long)signal_number, 0UL, 0UL, 0UL);
#else
    (void)signal_number;
    return 0;
#endif
}

#ifdef __APPLE__
#define WSH_MTIME(st) ((st).st_mtimespec)
#else
#define WSH_MTIME(st) ((st).st_mtim)
#endif
#endif
