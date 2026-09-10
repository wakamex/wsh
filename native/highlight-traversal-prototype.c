/*
 * Copyright (c) 2010-2020 zsh-syntax-highlighting contributors
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without modification, are permitted
 * provided that the following conditions are met:
 *
 *  * Redistributions of source code must retain the above copyright notice, this list of conditions
 *    and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright notice, this list of
 *    conditions and the following disclaimer in the documentation and/or other materials provided
 *    with the distribution.
 *  * Neither the name of the zsh-syntax-highlighting contributors nor the names of its contributors
 *    may be used to endorse or promote products derived from this software without specific prior
 *    written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
 * FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
 * IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
 * OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
/* Private faithful port of upstream per-word position accounting.
 * The upstream Zsh highlighter retains grammar and expansion semantics. */
#define MODULE 1
#define IMPORTING_MODULE_zshQsmain 1
#include "zsh.mdh"

static char *text(const char *name) {
    char *s = getsparam((char *)name);
    return s ? s : "";
}

static char *advance(char *p, int count) {
    mbstate_t state;
    memset(&state, 0, sizeof(state));
    while (*p && count-- > 0) {
        int length = mb_metacharlenconv_r(p, NULL, &state);
        p += length > 0 ? length : 1;
    }
    return p;
}

static int position(char *name, char **args, Options options, int function) {
    (void)name;
    (void)args;
    (void)options;
    (void)function;
    pushheap();
    char *buffer = dupstring(text("proc_buf"));
    char *p = buffer;
    while (*p == ' ' || *p == '\t' || (*p == '\\' && p[1] == '\n'))
        p += *p == '\\' ? 2 : 1;
    char *whitespace = dupstrpfx(buffer, (int)(p - buffer));
    zlong start = getiparam("end_pos") + mb_metastrlenend(whitespace, 0, NULL);
    char *arg = text("arg");
    int length = mb_metastrlenend(arg, 0, NULL);
    if (!strcmp(arg, ";") && *p == '\n')
        setsparam("arg", ztrdup("\n"));
    setiparam("start_pos", start);
    setiparam("end_pos", start + length);
    setsparam("proc_buf", ztrdup(advance(p, length)));
    popheap();
    return 0;
}

static struct builtin builtins[] = {
    BUILTIN("wsh-highlight-position", 0, position, 0, 0, 0, NULL, NULL)
};
static struct features features = {builtins, 1, NULL, 0, NULL, 0, NULL, 0, 0};
int setup_(Module m) { (void)m; return 0; }
int boot_(Module m) { (void)m; return 0; }
int features_(Module m, char ***f) { *f = featuresarray(m, &features); return 0; }
int enables_(Module m, int **e) { return handlefeatures(m, &features, e); }
int cleanup_(Module m) { return setfeatureenables(m, &features, NULL); }
int finish_(Module m) { (void)m; return 0; }
