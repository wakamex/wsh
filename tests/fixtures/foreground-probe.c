#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <termios.h>
#include <unistd.h>

static int report_fd = -1;

static void append_bytes(const char *value, size_t remaining) {
    while (remaining > 0) {
        ssize_t written = write(report_fd, value, remaining);
        if (written < 0 && errno == EINTR) {
            continue;
        }
        if (written <= 0) {
            _exit(125);
        }
        value += written;
        remaining -= (size_t)written;
    }
}

static void append_literal(const char *value) { append_bytes(value, strlen(value)); }

static void record_signal(int signal_number) {
    int saved_errno = errno;
    if (signal_number == SIGINT) {
        const char value[] = "signal\tint\n";
        append_bytes(value, sizeof(value) - 1);
    } else if (signal_number == SIGCONT) {
        const char value[] = "signal\tcont\n";
        append_bytes(value, sizeof(value) - 1);
    }
    errno = saved_errno;
}

static void record_arguments(int argc, char **argv) {
    dprintf(report_fd, "process\t%ld\t%ld\t%ld\t%d\n", (long)getpid(),
            (long)getpgrp(), (long)tcgetpgrp(STDIN_FILENO), argc);
    for (int index = 0; index < argc; ++index) {
        dprintf(report_fd, "arg\t%d\t", index);
        const unsigned char *byte = (const unsigned char *)argv[index];
        while (*byte != '\0') {
            dprintf(report_fd, "%02x", *byte++);
        }
        append_literal("\n");
    }
    fsync(report_fd);
}

static void wait_for_quit(void) {
    char byte;
    for (;;) {
        ssize_t count = read(STDIN_FILENO, &byte, 1);
        if (count == 1 && byte == 'q') {
            return;
        }
        if (count < 0 && errno != EINTR) {
            _exit(124);
        }
    }
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fputs("usage: foreground-probe REPORT MODE [ARGUMENTS...]\n", stderr);
        return 2;
    }
    report_fd = open(argv[1], O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0600);
    if (report_fd < 0) {
        perror("open report");
        return 2;
    }

    record_arguments(argc, argv);
    const char *mode = argv[2];
    struct sigaction action = {0};
    action.sa_handler = record_signal;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGCONT, &action, NULL) != 0) {
        perror("sigaction SIGCONT");
        return 2;
    }

    if (strcmp(mode, "nested") == 0) {
        pid_t child = fork();
        if (child < 0) {
            perror("fork");
            return 2;
        }
        if (child == 0) {
            for (;;) {
                pause();
            }
        }
        dprintf(report_fd, "child\t%ld\t%ld\n", (long)child, (long)getpgid(child));
        fsync(report_fd);
    } else if (strcmp(mode, "consume-int") == 0) {
        if (sigaction(SIGINT, &action, NULL) != 0) {
            perror("sigaction SIGINT");
            return 2;
        }
    } else if (strcmp(mode, "termios") == 0) {
        struct termios settings;
        if (tcgetattr(STDIN_FILENO, &settings) != 0) {
            perror("tcgetattr");
            return 2;
        }
        settings.c_lflag &= (tcflag_t)~(ECHO | ICANON);
        if (tcsetattr(STDIN_FILENO, TCSANOW, &settings) != 0) {
            perror("tcsetattr");
            return 2;
        }
    }

    dprintf(STDOUT_FILENO, "WSH_FOREGROUND_READY\t%ld\t%ld\t%ld\n", (long)getpid(),
            (long)getpgrp(), (long)tcgetpgrp(STDIN_FILENO));

    if (strcmp(mode, "exit0") == 0 || strcmp(mode, "termios") == 0) {
        return 0;
    }
    if (strcmp(mode, "exit7") == 0) {
        return 7;
    }
    if (strcmp(mode, "consume-int") == 0) {
        wait_for_quit();
        return 0;
    }
    if (strcmp(mode, "wait") == 0 || strcmp(mode, "nested") == 0) {
        for (;;) {
            pause();
        }
    }

    fprintf(stderr, "unknown mode: %s\n", mode);
    return 2;
}
