/* Included by Zsh's init.c before zsh_main; also tested standalone. */
#include "wsh-build.h"
#ifndef WSH_CLI_STANDALONE
#include "wsh-doctor.c"
#include "wsh-foreground.c"
#endif

static int
wsh_cli(int argc, char **arguments)
{
    const char *option = argc > 1 ? arguments[1] : "";

#ifndef WSH_CLI_STANDALONE
    if (!strcmp(option, "--wsh-run"))
        return wsh_foreground_parse(argc, arguments);
    if (!strcmp(option, "--wsh-doctor")) {
        if (argc != 2) {
            fputs("usage: wsh --wsh-doctor\n", stderr);
            return 2;
        }
        return wsh_doctor_start(arguments[0]);
    }
#endif
    if (!strcmp(option, "--wsh-version")) {
        if (argc != 2) {
            fputs("usage: wsh --wsh-version\n", stderr);
            return 2;
        }
        printf("wsh %s (unsigned development artifact)\n"
               "wsh source: %s\n"
               "native inputs sha256: %s\n"
               "zsh: %s\n"
               "zsh source: %s\n"
               "target: %s\n"
               "identity: compiled build; installed resources not verified\n",
               WSH_VERSION, WSH_SOURCE_REVISION, WSH_INPUTS_SHA256,
               ZSH_VERSION, WSH_ZSH_SOURCE_REVISION, WSH_TARGET);
        return fflush(stdout) == EOF || ferror(stdout) ? 1 : 0;
    }
    if (!strcmp(option, "--wsh-help")) {
        if (argc != 2) {
            fputs("usage: wsh --wsh-help\n", stderr);
            return 2;
        }
        fputs("usage: wsh [native Zsh arguments]\n"
              "       wsh --wsh-version\n"
              "       wsh --wsh-doctor\n"
              "       wsh --wsh-run [--login] -- <command> [arguments...]\n"
              "       wsh --wsh-help\n"
              "Ordinary script names and -- retain their Zsh meanings.\n",
              stdout);
        return fflush(stdout) == EOF || ferror(stdout) ? 1 : 0;
    }
    return -1;
}
