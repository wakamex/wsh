/* Private module harness for the installed native main highlighter. */
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"
#include "highlight.c"
static struct features features = {
    wsh_highlight_builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) {
  (void)m;
  return 0;
}
int boot_(Module m) {
  (void)m;
  return 0;
}
int features_(Module m, char ***f) {
  *f = featuresarray(m, &features);
  return 0;
}
int enables_(Module m, int **e) { return handlefeatures(m, &features, e); }
int cleanup_(Module m) { return setfeatureenables(m, &features, NULL); }
int finish_(Module m) {
  (void)m;
  return 0;
}
