#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
/* Capture native argv once; argument values are never parsed as shell source. */
static char **wsh_foreground_values;
static int wsh_foreground_count;
static char *wsh_foreground_arguments[5];
static char wsh_foreground_interactive[] = "-i";
static char wsh_foreground_stdin[] = "-s";
static char wsh_foreground_login[] = "-l";

static int
wsh_foreground_parse(int argc, char **arguments)
{
    int first = 2, login = 0, count = 0;
    if (first < argc && !strcmp(arguments[first], "--login")) {
        login = 1;
        ++first;
    }
    if (first >= argc || strcmp(arguments[first], "--") || first + 1 >= argc || !*arguments[first + 1]) {
        fputs("usage: wsh --wsh-run [--login] -- <command> [arguments...]\n", stderr);
        return 2;
    }
    wsh_foreground_count = argc - first - 1;
    wsh_foreground_values = arguments + first + 1;
    wsh_foreground_arguments[count++] = arguments[0];
    wsh_foreground_arguments[count++] = wsh_foreground_interactive;
    wsh_foreground_arguments[count++] = wsh_foreground_stdin;
    if (login)
        wsh_foreground_arguments[count++] = wsh_foreground_login;
    wsh_foreground_arguments[count] = NULL;
    unsetenv("WSH_RUN_FOREGROUND");
    return -1;
}

int main(void) {
    unsigned int state=32175; char bytes[256];
    char *valid[]={"wsh","--wsh-run","--","program","", "a\377",0};
    char *login[]={"wsh","--wsh-run","--login","--","program",0};
    char *invalid[]={"wsh","--wsh-run",bytes,0};
    assert(wsh_foreground_parse(6,valid)==-1);
    assert(wsh_foreground_count==3 && wsh_foreground_values==valid+3);
    assert(wsh_foreground_arguments[3]==0);
    assert(wsh_foreground_parse(5,login)==-1);
    assert(wsh_foreground_count==1 && wsh_foreground_arguments[4]==0);
    for(int i=0;i<10000;i++) {
        bytes[0]='x';
        for(int j=1;j<255;j++) {state=state*1664525u+1013904223u;bytes[j]=(char)(1+state%255);}
        bytes[255]=0; assert(wsh_foreground_parse(3,invalid)==2);
    }
    return 0;
}
