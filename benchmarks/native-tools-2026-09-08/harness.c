#include <stdio.h>
#include <string.h>
#include <assert.h>
#define ZSH_VERSION "test"
#include "tools.c"
int main(void) {
  unsigned int state = 71031; char bytes[128]; char *args[] = {"wsh", bytes, 0};
  for (int i=0; i<10000; ++i) {
    for (int j=0; j<127; ++j) { state = state*1664525u+1013904223u; bytes[j]=(char)(1+state%255); }
    bytes[127]=0; assert(wsh_cli(2,args)==-1);
  }
  args[1]="--wsh-version"; assert(wsh_cli(2,args)==0);
  args[1]="--wsh-help"; assert(wsh_cli(2,args)==0);
  assert(wsh_cli(0,args)==-1); return 0;
}
