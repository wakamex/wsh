#include <assert.h>
#include <string.h>
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

int main(void) {
    unsigned int state=90231;
    char owner[256], replaced[256];
    const char *owners[]={"wsh","external-active","external-exact","external-unknown","disabled","unset","", "wsh\033"};
    const char *replacements[]={"0","1","unset","", "0\n"};
    const int expected[8][5]={{0,1,-1,-1,-1},{1,-1,-1,-1,-1},{1,-1,-1,-1,-1},{2,-1,-1,-1,-1},{0,-1,-1,-1,-1},{-1,-1,-1,-1,-1},{-1,-1,-1,-1,-1},{-1,-1,-1,-1,-1}};
    for (int i=0;i<8;i++) for(int j=0;j<5;j++) assert(wsh_doctor_finding(owners[i],replacements[j])==expected[i][j]);
    for (int i=0;i<10000;i++) {
        for(int j=0;j<255;j++) {
            state=state*1664525u+1013904223u;owner[j]=(char)(1+state%255);
            state=state*1664525u+1013904223u;replaced[j]=(char)(1+state%255);
        }
        owner[255]=replaced[255]=0;
        assert(wsh_doctor_finding(owner,replaced)==-1);
    }
    return 0;
}
