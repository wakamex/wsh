/*
 * Copyright (c) 2010-2020 zsh-syntax-highlighting contributors
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 *  * Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation
 * and/or other materials provided with the distribution.
 *  * Neither the name of the zsh-syntax-highlighting contributors nor the names
 * of its contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */
/* Native main highlighter, included by Zsh startup and its private module test.
 */
#include <ctype.h>
#include <dirent.h>
#include <sys/stat.h>

/* WshHlText offsets are ZLE character offsets, never UTF-8 byte offsets. */
typedef struct {
  char *s;
  int n;
  int *byte;
} WshHlText;
typedef struct WshHlRegion {
  int a, b;
  const char *style;
  struct WshHlRegion *next;
} WshHlRegion;
typedef struct {
  WshHlRegion *first, *last;
} WshHlRegions;
typedef struct {
  WshHlRegions regions;
  int end, open;
} WshHlResult;
typedef struct {
  WshHlText buf;
  int offset, has_end, depth;
  int start, end, redirection, glob, array, assigned;
  int aliases, parameter;
  const char *alias_style, *param_style;
  char *arg, *last;
  WshHlRegions regions;
} WshHlParser;
static char *wsh_hl_value(const char *name) {
  char *s = getsparam((char *)name);
  return s ? s : "";
}
static int wsh_hl_history_char(int index) {
  char *s = wsh_hl_value("histchars");
  return (int)strlen(s) > index ? (unsigned char)s[index] : 0;
}
static Param wsh_hl_entry(const char *table, const char *key) {
  Param p = (Param)paramtab->getnode(paramtab, table);
  if (!p || PM_TYPE(p->node.flags) != PM_HASHED)
    return NULL;
  HashTable h = p->gsu.h->getfn(p);
  Param v = h ? (Param)h->getnode(h, key) : NULL;
  return v && !(v->node.flags & PM_UNSET) ? v : NULL;
}
static char *wsh_hl_hash(const char *table, const char *key) {
  Param p = wsh_hl_entry(table, key);
  return p ? p->gsu.s->getfn(p) : NULL;
}
static int wsh_hl_option(const char *key) {
  char *v = wsh_hl_hash("zsyh_user_options", key);
  return v && !strcmp(v, "on");
}
static WshHlText wsh_hl_text(char *s) {
  WshHlText t = {s, 0, zhalloc((strlen(s) + 1) * sizeof(int))};
  mbstate_t state;
  memset(&state, 0, sizeof(state));
  for (char *p = s; *p;) {
    t.byte[t.n++] = (int)(p - s);
    int n = mb_metacharlenconv_r(p, NULL, &state);
    p += n > 0 ? n : 1;
  }
  t.byte[t.n] = (int)strlen(s);
  return t;
}
static int wsh_hl_ch(WshHlText t, int i) {
  return i >= 0 && i < t.n ? (unsigned char)t.s[t.byte[i]] : 0;
}
static char *wsh_hl_slice(WshHlText t, int a, int b) {
  if (a < 0)
    a = 0;
  if (a > t.n)
    a = t.n;
  if (b < a)
    b = a;
  if (b > t.n)
    b = t.n;
  return dupstrpfx(t.s + t.byte[a], t.byte[b] - t.byte[a]);
}
static void wsh_hl_region_add(WshHlRegions *r, int a, int b,
                              const char *style) {
  WshHlRegion *v = zhalloc(sizeof(*v));
  *v = (WshHlRegion){a, b, style, NULL};
  if (r->last)
    r->last->next = v;
  else
    r->first = v;
  r->last = v;
}
static void wsh_hl_append(WshHlRegions *r, WshHlRegions s) {
  if (!s.first)
    return;
  if (r->last)
    r->last->next = s.first;
  else
    r->first = s.first;
  r->last = s.last;
}
static void wsh_hl_emit(WshHlParser *p, int a, int b, const char *style) {
  if (p->aliases) {
    if (!strcmp(style, "unknown-token"))
      p->alias_style = style;
    return;
  }
  if (p->parameter) {
    if (!strcmp(style, "unknown-token") || !p->param_style)
      p->param_style = style;
    return;
  }
  wsh_hl_region_add(&p->regions, a + p->offset, b + p->offset, style);
}
static void wsh_hl_emit_many(WshHlParser *p, WshHlRegions r) {
  for (WshHlRegion *v = r.first; v; v = v->next)
    wsh_hl_emit(p, v->a, v->b, v->style);
}
static int wsh_hl_eq(const char *a, const char *b) { return !strcmp(a, b); }
static int wsh_hl_member(const char *s, const char *list) {
  size_t n = strlen(s);
  for (const char *p = list; *p;) {
    const char *end = strchr(p, ' ');
    if (!end)
      end = p + strlen(p);
    if ((size_t)(end - p) == n && !strncmp(p, s, n))
      return 1;
    p = *end ? end + 1 : end;
  }
  return 0;
}
static char **wsh_hl_lex(char *s) {
  return hlinklist2array(
      bufferwords(NULL, s, NULL,
                  LEXFLAGS_ACTIVE | (wsh_hl_option("interactivecomments")
                                         ? LEXFLAGS_COMMENTS_KEEP
                                         : 0)),
      0);
}
static const char *wsh_hl_type(char *word, int aliases) {
  char *dot = strrchr(word, '.');
  if (aliases && wsh_hl_entry("galiases", word))
    return "global-alias";
  if (aliases && wsh_hl_entry("aliases", word))
    return "alias";
  if (dot && dot != word && wsh_hl_entry("saliases", dot + 1))
    return "suffix-alias";
  char **words = getaparam("reswords");
  for (char **w = words; w && *w; w++)
    if (wsh_hl_eq(*w, word))
      return "reserved-word";
  if (wsh_hl_entry("functions", word))
    return "function";
  if (wsh_hl_entry("builtins", word))
    return "builtin";
  if (wsh_hl_entry("commands", word))
    return "command";
  if (strchr(word, '/')) {
    struct stat st;
    if (!stat(unmeta(word), &st) && !S_ISDIR(st.st_mode) &&
        !access(unmeta(word), X_OK))
      return "command";
  }
  if (strchr(word, '/') && *word != '/' && wsh_hl_option("pathdirs")) {
    char **dirs = getaparam("path");
    for (char **d = dirs; d && *d; d++) {
      char *file = unmeta(zhtricat(*d, "/", word));
      struct stat st;
      if (!stat(file, &st) && !S_ISDIR(st.st_mode) && !access(file, X_OK))
        return "command";
    }
  }
  return "none";
}
static char *wsh_hl_expand(char *s) {
  /* Filename expansion and quote removal only. Never parameter/command
   * substitution. */
  char *v = dupstring(s);
  if (*v == '~')
    v[0] = Tilde;
  else if (*v == '=' && wsh_hl_option("equals"))
    v[0] = Equals;
  int saved = noerrs, errors = errflag;
  noerrs = 1;
  filesub(&v, 0);
  noerrs = saved;
  errflag = errors;
  untokenize(v);
  char *out = zhalloc(strlen(v) + 1), *q = out;
  int quote = 0;
  for (char *p = v; *p; p++) {
    if (*p == Meta && p[1]) {
      *q++ = *p++;
      *q++ = *p;
      continue;
    }
    if (*p == '\\' && quote != '\'' && p[1]) {
      if (!quote || strchr("\\\"$`", p[1])) {
        if (p[1] == '\n') {
          p++;
          continue;
        }
        *q++ = *++p;
        continue;
      }
    }
    if ((*p == '\'' || *p == '"') && (!quote || quote == *p)) {
      quote = quote ? 0 : *p;
      continue;
    }
    *q++ = *p;
  }
  *q = 0;
  return out;
}
static const char *wsh_hl_path_style(WshHlParser *p, char *word, int command) {
  char *expanded = wsh_hl_expand(word), *raw = dupstring(unmeta(expanded));
  struct stat st;
  if (word[0] == '=' && word[1] && word[1] != '(' && wsh_hl_option("equals") &&
      expanded[0] != '/')
    return "unknown-token";
  if (!*expanded)
    return NULL;
  char *absolute = expanded[0] == '/'
                       ? dupstring(expanded)
                       : zhtricat(wsh_hl_value("PWD"), "/", expanded);
  char *normal = dupstring(absolute);
  chabspath(&normal);
  char **black = getaparam("ZSH_HIGHLIGHT_DIRS_BLACKLIST");
  for (char **b = black; b && *b; b++) {
    size_t n = strlen(*b);
    if (n > 1 && !strncmp(normal, *b, n) && (!normal[n] || normal[n] == '/'))
      return NULL;
  }
  const char *style = command ? "arg0" : "path";
  if (command) {
    if (!stat(raw, &st) && !access(raw, X_OK)) {
      if (wsh_hl_option("autocd"))
        return S_ISDIR(st.st_mode) ? "autodirectory" : style;
      if (!S_ISDIR(st.st_mode))
        return style;
    }
  } else if (!lstat(raw, &st))
    return style;
  if (*expanded != '/' && (wsh_hl_option("autocd") || !command)) {
    char **dirs = getaparam("cdpath");
    for (char **d = dirs; d && *d; d++) {
      char *v = unmeta(zhtricat(*d, "/", expanded));
      if (!stat(v, &st) && S_ISDIR(st.st_mode) && !access(v, X_OK))
        return command ? "autodirectory" : style;
    }
  }
  if (p->has_end && p->end == p->buf.n && !p->aliases &&
      !wsh_hl_eq(wsh_hl_value("WIDGET"), "zle-line-finish")) {
    char *copy = dupstring(raw), *slash = strrchr(copy, '/');
    const char *dir = ".", *prefix = copy;
    if (slash) {
      *slash = 0;
      dir = *copy ? copy : "/";
      prefix = slash + 1;
    }
    DIR *d = opendir(dir);
    if (d) {
      struct dirent *e;
      size_t n = strlen(prefix);
      int found = 0;
      while ((e = readdir(d))) {
        if (e->d_name[0] == '.' && prefix[0] != '.')
          continue;
        if (strncmp(e->d_name, prefix, n))
          continue;
        char *v = zhtricat((char *)dir, "/", e->d_name);
        if (!command ||
            (!stat(v, &st) && (S_ISDIR(st.st_mode) || !access(v, X_OK)))) {
          found = 1;
          break;
        }
      }
      closedir(d);
      if (found)
        return "path_prefix";
    }
  }
  return NULL;
}
static int wsh_hl_redirect(char *s) {
  if (isdigit((unsigned char)*s))
    s++;
  return wsh_hl_member(
      s, "< <> > >> >| >>| << <<- <<< <& &< >& >>& >&| >>&| &> &>> "
         "&>| &>>| &>! &>>!");
}
static int wsh_hl_assign(char *s) {
  char *p = s;
  if (isdigit((unsigned char)*p))
    while (isdigit((unsigned char)*p))
      p++;
  else {
    if (*p != '_' && !isalpha((unsigned char)*p))
      return 0;
    while (*p == '_' || isalnum((unsigned char)*p))
      p++;
    if (*p == '[') {
      char *end = strrchr(p, ']');
      if (!end)
        return 0;
      p = end + 1;
    }
  }
  if (*p == '+')
    p++;
  return *p == '=';
}
static WshHlResult wsh_hl_parse(char *, int, const char *, int, int);
static int wsh_hl_quoted(WshHlParser *, WshHlText, int, int, WshHlRegions *);
static int wsh_hl_backtick(WshHlParser *, WshHlText, int, WshHlRegions *);
static int wsh_hl_arithmetic(WshHlParser *, WshHlText, int, WshHlRegions *);
static int wsh_hl_substitution(WshHlParser *p, WshHlText t, int i,
                               int quoted_context, int process,
                               WshHlRegions *r) {
  WshHlResult sub = wsh_hl_parse(wsh_hl_slice(t, i + 2, t.n), p->start + i + 2,
                                 "S", p->has_end, p->depth + 1);
  int end = i + 2 + sub.end;
  const char *body = process          ? "process-substitution"
                     : quoted_context ? "command-substitution-quoted"
                                      : "command-substitution-unquoted";
  const char *delim = process ? "process-substitution-delimiter"
                      : quoted_context
                          ? "command-substitution-delimiter-quoted"
                          : "command-substitution-delimiter-unquoted";
  wsh_hl_region_add(r, p->start + i, p->start + end + 1, body);
  wsh_hl_region_add(r, p->start + i, p->start + i + 2, delim);
  wsh_hl_append(r, sub.regions);
  if (!sub.open)
    wsh_hl_region_add(r, p->start + end, p->start + end + 1, delim);
  return end;
}
static int wsh_hl_parameter_length(WshHlText t, int i) {
  int first = i, c = wsh_hl_ch(t, i);
  if (c == '_' || isalpha(c)) {
    while (wsh_hl_ch(t, i) == '_' || isalnum(wsh_hl_ch(t, i)))
      i++;
  } else if (isdigit(c)) {
    while (isdigit(wsh_hl_ch(t, i)))
      i++;
  }
  return i - first;
}
static int wsh_hl_quoted(WshHlParser *p, WshHlText t, int begin, int kind,
                         WshHlRegions *out) {
  WshHlRegions inner = {0}, base = {0};
  int i = begin + (kind == '$' ? 2 : 1), last = p->start + begin;
  for (; i < t.n; i++) {
    int c = wsh_hl_ch(t, i), next = wsh_hl_ch(t, i + 1), a = p->start + i,
        b = a + 1;
    const char *style = NULL;
    if (c == (kind == '"' ? '"' : '\'')) {
      if (kind == '\'' && wsh_hl_option("rcquotes") && next == '\'') {
        wsh_hl_region_add(&inner, a, b + 1, "rc-quote");
        i++;
        continue;
      }
      break;
    }
    if (kind == '\'')
      continue;
    if (kind == '$') {
      if (c != '\\')
        continue;
      style = "back-dollar-quoted-argument";
      int count = 0, limit = 0, j = i + 1;
      if (next == 'x' || next == 'X')
        limit = 2, j++;
      else if (next == 'u')
        limit = 4, j++;
      else if (next == 'U')
        limit = 8, j++;
      else if (next >= '0' && next <= '7')
        limit = 3;
      if (limit) {
        while (count < limit &&
               (j == i + 1 ? wsh_hl_ch(t, j + count) >= '0' &&
                                 wsh_hl_ch(t, j + count) <= '7'
                           : isxdigit(wsh_hl_ch(t, j + count))))
          count++;
      }
      if (count) {
        int size = j - i - 1 + count;
        b += size;
        i += size;
      } else {
        if (i + 2 < t.n && strchr("xXuU", next))
          style = "unknown-token";
        b++;
        i++;
      }
    } else if (c == '`') {
      i = wsh_hl_backtick(p, t, i, &inner);
      continue;
    } else if (c == '$') {
      style = "dollar-double-quoted-argument";
      int size = wsh_hl_parameter_length(t, i + 1);
      if (size) {
        b += size;
        i += size;
      } else if (next == '{' && (size = wsh_hl_parameter_length(t, i + 2)) &&
                 wsh_hl_ch(t, i + 2 + size) == '}') {
        b += size + 2;
        i += size + 2;
      } else if (next && strchr("$-#*@?", next)) {
        b++;
        i++;
      } else if (next == '(') {
        int end = -1;
        if (wsh_hl_ch(t, i + 2) == '(')
          end = wsh_hl_arithmetic(p, t, i, &inner);
        if (end >= 0) {
          i = end;
          continue;
        }
        wsh_hl_region_add(&base, last, a, "");
        i = wsh_hl_substitution(p, t, i, 1, 0, &inner);
        last = p->start + i + 1;
        continue;
      } else
        continue;
    } else if (c == '\\') {
      char *hist = wsh_hl_value("histchars");
      if (next && (strchr("\\`\"$", next) || next == (unsigned char)*hist)) {
        style = "back-double-quoted-argument";
        b++;
        i++;
      } else
        continue;
    } else if (c == wsh_hl_history_char(0) && next != '=' && next != '(' &&
               next != '{' && next != ' ' && next != '\t')
      style = "history-expansion";
    else
      continue;
    wsh_hl_region_add(&inner, a, b, style);
  }
  int closed = i < t.n;
  if (!closed)
    i--;
  const char *style =
      kind == '\''  ? (closed ? "single-quoted-argument"
                              : "single-quoted-argument-unclosed")
      : kind == '$' ? (closed ? "dollar-quoted-argument"
                              : "dollar-quoted-argument-unclosed")
                    : (closed ? "double-quoted-argument"
                              : "double-quoted-argument-unclosed");
  if (last != p->start + i + 1)
    wsh_hl_region_add(&base, last, p->start + i + 1, style);
  for (WshHlRegion *v = base.first; v; v = v->next)
    v->style = style;
  wsh_hl_append(out, base);
  wsh_hl_append(out, inner);
  return i;
}
static int wsh_hl_backtick(WshHlParser *p, WshHlText t, int begin,
                           WshHlRegions *out) {
  char *buffer = zhalloc(strlen(t.s) + 1), *q = buffer;
  int *map = zhalloc((t.n + 1) * sizeof(int));
  int count = 0, i = begin + 1, closed = 0;
  for (; i < t.n; i++) {
    int c = wsh_hl_ch(t, i);
    if (c == '`') {
      closed = 1;
      break;
    }
    map[count++] = i - begin - 1;
    if (c == '\\' && wsh_hl_ch(t, i + 1) && strchr("$`\\", wsh_hl_ch(t, i + 1)))
      i++;
    int n = t.byte[i + 1] - t.byte[i];
    memcpy(q, t.s + t.byte[i], n);
    q += n;
  }
  *q = 0;
  map[count] = i - begin - 1;
  WshHlResult sub = wsh_hl_parse(
      buffer, 0, "", !closed && p->has_end && p->start + i == p->buf.n,
      p->depth + 1);
  int end = closed ? i : t.n - 1;
  const char *endstyle = "back-quoted-argument-delimiter";
  wsh_hl_region_add(out, p->start + begin, p->start + end + 1,
                    closed ? "back-quoted-argument"
                           : "back-quoted-argument-unclosed");
  wsh_hl_region_add(out, p->start + begin, p->start + begin + 1,
                    "back-quoted-argument-delimiter");
  for (WshHlRegion *v = sub.regions.first; v; v = v->next) {
    int a = v->a < 0       ? 0
            : v->a > count ? count
                           : v->a,
        b = v->b < 0       ? 0
            : v->b > count ? count
                           : v->b;
    wsh_hl_region_add(out, p->start + begin + 1 + map[a],
                      p->start + begin + 1 + map[b], v->style);
    if (wsh_hl_eq(v->style, "back-quoted-argument-unclosed"))
      endstyle = "unknown-token";
  }
  if (closed)
    wsh_hl_region_add(out, p->start + end, p->start + end + 1, endstyle);
  return end;
}
static int wsh_hl_arithmetic(WshHlParser *p, WshHlText t, int begin,
                             WshHlRegions *out) {
  WshHlRegions inner = {0};
  int depth = 0, i;
  for (i = begin + 3; i < t.n; i++) {
    int c = wsh_hl_ch(t, i), next = wsh_hl_ch(t, i + 1);
    const char *style = NULL;
    if (strchr("'\"\\@{}", c))
      style = "unknown-token";
    else if (c == '(') {
      depth++;
      continue;
    } else if (c == ')') {
      if (depth) {
        depth--;
        continue;
      }
      if (next == ')') {
        i++;
        break;
      }
      if (p->has_end && p->buf.n == p->start + i + 1)
        break;
      return -1;
    } else if (c == '`') {
      i = wsh_hl_backtick(p, t, i, &inner);
      continue;
    } else if (c == '$' && next == '(') {
      int end = -1;
      if (wsh_hl_ch(t, i + 2) == '(')
        end = wsh_hl_arithmetic(p, t, i, &inner);
      i = end >= 0 ? end : wsh_hl_substitution(p, t, i, 1, 0, &inner);
      if (end < 0 && inner.last &&
          wsh_hl_eq(inner.last->style, "command-substitution-delimiter-quoted"))
        inner.last->style = "command-substitution-delimiter";
      continue;
    } else if (c == wsh_hl_history_char(0) && next != '=' && next != '(' &&
               next != '{' && next != ' ' && next != '\t')
      style = "history-expansion";
    else
      continue;
    wsh_hl_region_add(&inner, p->start + i, p->start + i + 1, style);
  }
  if (wsh_hl_ch(t, i) != ')')
    i--;
  wsh_hl_region_add(out, p->start + begin, p->start + i + 1,
                    "arithmetic-expansion");
  wsh_hl_append(out, inner);
  return i;
}
static void wsh_hl_argument(WshHlParser *p, int begin, int eligible) {
  WshHlText t = wsh_hl_text(p->arg);
  WshHlRegions inner = {0};
  const char *base = "default";
  int path = 1, i = begin;
  if (wsh_hl_ch(t, i) == '%' && wsh_hl_ch(t, i + 1) == '?')
    i += 2;
  else if (wsh_hl_ch(t, i) == '-' && eligible) {
    base = wsh_hl_ch(t, i + 1) == '-' ? "double-hyphen-option"
                                      : "single-hyphen-option";
    path = 0;
  } else if (wsh_hl_ch(t, i) == '=' && wsh_hl_ch(t, i + 1) == '(')
    i = wsh_hl_substitution(p, t, i, 0, 1, &inner);
  for (; i < t.n; i++) {
    int c = wsh_hl_ch(t, i), next = wsh_hl_ch(t, i + 1);
    if (c == '\\') {
      i++;
      continue;
    }
    if (c == '\'' || c == '"') {
      i = wsh_hl_quoted(p, t, i, c, &inner);
      continue;
    }
    if (c == '`') {
      i = wsh_hl_backtick(p, t, i, &inner);
      continue;
    }
    if (c == '$') {
      if (next == '\'') {
        i = wsh_hl_quoted(p, t, i, '$', &inner);
        continue;
      }
      path = 0;
      if (next == '(') {
        int end = -1;
        if (wsh_hl_ch(t, i + 2) == '(')
          end = wsh_hl_arithmetic(p, t, i, &inner);
        i = end >= 0 ? end : wsh_hl_substitution(p, t, i, 0, 0, &inner);
        continue;
      }
      while (wsh_hl_ch(t, i + 1) && strchr("=~#+'^", wsh_hl_ch(t, i + 1)))
        i++;
      if (wsh_hl_ch(t, i + 1) && strchr("*@#?$!-", wsh_hl_ch(t, i + 1)))
        i++;
      continue;
    }
    if ((c == '<' || c == '>') && next == '(') {
      i = wsh_hl_substitution(p, t, i, 0, 1, &inner);
      continue;
    }
    if (p->glob && (wsh_hl_option("multios") || !p->redirection)) {
      int end = i;
      if (c == '<') {
        end = i + 1;
        while (isdigit(wsh_hl_ch(t, end)))
          end++;
        if (wsh_hl_ch(t, end++) != '-')
          continue;
        while (isdigit(wsh_hl_ch(t, end)))
          end++;
        if (wsh_hl_ch(t, end) != '>')
          continue;
      } else if (c != '*' && c != '?')
        continue;
      wsh_hl_region_add(&inner, p->start + i, p->start + end + 1, "globbing");
      path = 0;
      i = end;
    }
  }
  if (path) {
    char *word = wsh_hl_slice(t, begin, t.n);
    size_t n = strlen(p->last);
    int numeric = *word != 0;
    for (char *q = word; *q; q++)
      if (!isdigit((unsigned char)*q))
        numeric = 0;
    if (p->redirection && n >= 2 && strchr("<>", p->last[n - 2]) &&
        p->last[n - 1] == '&' &&
        (numeric || wsh_hl_eq(word, "p") || wsh_hl_eq(word, "-")))
      base = numeric ? "numeric-fd" : "redirection";
    else {
      const char *style = wsh_hl_path_style(p, word, 0);
      if (style) {
        base = style;
        char *separator = dyncat((char *)base, "_pathseparator"),
             *a = wsh_hl_hash("ZSH_HIGHLIGHT_STYLES", separator),
             *b = wsh_hl_hash("ZSH_HIGHLIGHT_STYLES", base);
        if (a && *a && (!b || !wsh_hl_eq(a, b))) {
          WshHlText buffer = wsh_hl_text(wsh_hl_value("BUFFER"));
          for (int j = p->start - 1; j < p->end; j++)
            if (wsh_hl_ch(buffer, j) == '/')
              wsh_hl_region_add(&inner, j, j + 1, separator);
        }
      }
    }
  }
  wsh_hl_emit(p, p->start + begin, p->end, base);
  wsh_hl_emit_many(p, inner);
}
enum {
  WSH_HL_START = 1,
  WSH_HL_PIPELINE = 2,
  WSH_HL_OPT = 4,
  WSH_HL_OPTARG = 8,
  WSH_HL_REGULAR = 16,
  WSH_HL_ALWAYS = 32
};
typedef struct WshHlWord {
  char *s;
  struct WshHlWord *next;
} WshHlWord;
typedef struct WshHlAliasFrame {
  int count;
  struct WshHlAliasFrame *next;
} WshHlAliasFrame;
typedef struct WshHlSeen {
  char *name;
  int level;
  struct WshHlSeen *next;
} WshHlSeen;
static WshHlWord *wsh_hl_prepend(char **words, WshHlWord *tail) {
  WshHlWord *head = NULL, *last = NULL;
  for (char **w = words; w && *w; w++)
    if (**w) {
      WshHlWord *v = zhalloc(sizeof(*v));
      *v = (WshHlWord){*w, NULL};
      if (last)
        last->next = v;
      else
        head = v;
      last = v;
    }
  if (last)
    last->next = tail;
  return head ? head : tail;
}
static int wsh_hl_countwords(char **words) {
  int n = 0;
  for (; words && *words; words++)
    if (**words)
      n++;
  return n;
}
static int wsh_hl_pop(char **stack, int expected, const char **style,
                      const char *success) {
  if (**stack == expected) {
    (*stack)++;
    if (success)
      *style = success;
    return 1;
  }
  *style = "unknown-token";
  return 0;
}
static const char *wsh_hl_precommand(char *s) {
  static const char *pairs[] = {
      "-",           "",
      "builtin",     "",
      "command",     ":pvV",
      "exec",        "a:cl",
      "noglob",      "",
      "doas",        "aCu:Lns",
      "nice",        "n:",
      "pkexec",      "",
      "sudo",        "Cgprtu:AEHPSbilns:eKkVv",
      "run0",        "ugD:h",
      "stdbuf",      "ioe:",
      "eatmydata",   "",
      "catchsegv",   "",
      "nohup",       "",
      "setsid",      ":wc",
      "env",         "u:i",
      "ionice",      "cn:t:pPu",
      "strace",      "IbeaosXPpEuOS:ACdfhikqrtTvVxyDc",
      "proxychains", "f:q",
      "torsocks",    "idq:upaP",
      "torify",      "idq:upaP",
      "ssh-agent",   "aEPt:csDd:k",
      "tabbed",      "gnprtTuU:cdfhs:v",
      "chronic",     ":ev",
      "ifne",        ":n",
      "grc",         ":se",
      "cpulimit",    "elp:ivz",
      "ktrace",      "fgpt:aBCcdiT",
      "caffeinate",  "tw:dimsu",
      NULL};
  for (int i = 0; pairs[i]; i += 2)
    if (wsh_hl_eq(s, pairs[i]))
      return pairs[i + 1];
  return NULL;
}
static char **wsh_hl_parameter(char *arg, const char *res) {
  if (!wsh_hl_eq(res, "none") || *arg != '$')
    return NULL;
  WshHlText t = wsh_hl_text(arg);
  int i = wsh_hl_ch(t, 1) == '{' ? 2 : 1, n = wsh_hl_parameter_length(t, i);
  if (!n || (i == 2 ? (i + n + 1 != t.n || wsh_hl_ch(t, i + n) != '}')
                    : i + n != t.n))
    return NULL;
  char *name = wsh_hl_slice(t, i, i + n);
  Param param = (Param)paramtab->getnode(paramtab, name);
  if (param && (param->node.flags & PM_SPECIAL))
    return NULL;
  char **words = zhalloc(sizeof(char *));
  words[0] = NULL;
  if (isdigit((unsigned char)*name)) {
    if (atoi(name) == 1) {
      words = zhalloc(2 * sizeof(char *));
      words[0] = arg;
      words[1] = NULL;
    }
    return words;
  }
  if (!param || (param->node.flags & PM_UNSET))
    return words;
  switch (PM_TYPE(param->node.flags)) {
  case PM_ARRAY:
    return arrdup(param->gsu.a->getfn(param));
  case PM_HASHED: {
    HashTable h = param->gsu.h->getfn(param);
    LinkList list = newlinklist();
    for (int j = 0; j < h->hsize; j++)
      for (HashNode v = h->nodes[j]; v; v = v->next)
        if (!(v->flags & PM_UNSET))
          addlinknode(list, dupstring(((Param)v)->gsu.s->getfn((Param)v)));
    return hlinklist2array(list, 0);
  }
  default: {
    char *v = getsparam(name);
    if (!v)
      return words;
    if (wsh_hl_option("shwordsplit"))
      return sepsplit(v, NULL, 0, 1);
    words = zhalloc(2 * sizeof(char *));
    words[0] = dupstring(v);
    words[1] = NULL;
    return words;
  }
  }
}
static WshHlResult wsh_hl_parse(char *buffer, int offset, const char *initial,
                                int has_end, int depth) {
  WshHlParser p = {0};
  p.buf = wsh_hl_text(buffer);
  p.offset = offset;
  p.has_end = has_end;
  p.depth = depth;
  p.glob = 1;
  p.arg = "";
  p.last = "";
  if (depth > 128)
    return (WshHlResult){{0}, p.buf.n - 1, 1};
  char *stack = dupstring(initial);
  char **tokens = wsh_hl_lex(buffer);
  WshHlWord *words = wsh_hl_prepend(tokens, NULL);
  if (wsh_hl_eq(initial, "S") && wsh_hl_countwords(tokens) == 3 &&
      wsh_hl_eq(tokens[2], ")") && strchr(tokens[0], '<') &&
      wsh_hl_redirect(tokens[0]))
    p.glob = 0;
  int this_word = 0, next_word = WSH_HL_START | WSH_HL_PIPELINE, pos = 0,
      steps = 0;
  const char *res = "none", *with = "", *sans = "", *solo = "";
  WshHlAliasFrame *frames = NULL;
  WshHlSeen *seen = NULL;
  while (words && ++steps < 100000) {
    p.last = p.arg;
    p.arg = words->s;
    words = words->next;
    if (frames) {
      frames->count--;
      while (frames && frames->count <= 0) {
        frames = frames->next;
        p.aliases--;
      }
      if (!frames) {
        seen = NULL;
        wsh_hl_emit(&p, p.start, p.end, p.alias_style);
      } else {
        WshHlSeen **s = &seen;
        while (*s) {
          if ((*s)->level >= p.aliases)
            *s = (*s)->next;
          else
            s = &(*s)->next;
        }
      }
    }
    if (p.parameter && --p.parameter == 0) {
      wsh_hl_emit(&p, p.start, p.end,
                  p.param_style ? p.param_style : "default");
      p.param_style = NULL;
    }
    if (!p.redirection) {
      this_word = next_word;
      next_word = WSH_HL_REGULAR;
    } else if (!p.parameter)
      p.redirection--;
    const char *style = "unknown-token";
    if (this_word & WSH_HL_START) {
      p.array = 0;
      if (wsh_hl_eq(p.arg, "noglob"))
        p.glob = 0;
    }
    if (!p.aliases && !p.parameter) {
      while (
          wsh_hl_ch(p.buf, pos) == ' ' || wsh_hl_ch(p.buf, pos) == '\t' ||
          (wsh_hl_ch(p.buf, pos) == '\\' && wsh_hl_ch(p.buf, pos + 1) == '\n'))
        pos += wsh_hl_ch(p.buf, pos) == '\\' ? 2 : 1;
      p.start = pos;
      p.end = pos + wsh_hl_text(p.arg).n;
      if (wsh_hl_eq(p.arg, ";") && wsh_hl_ch(p.buf, pos) == '\n')
        p.arg = "\n";
      pos = p.end;
      if (pos > p.buf.n)
        pos = p.buf.n;
    }
    if (wsh_hl_option("interactivecomments") &&
        p.arg[0] == wsh_hl_history_char(2)) {
      wsh_hl_emit(&p, p.start, p.end,
                  this_word & (WSH_HL_REGULAR | WSH_HL_START)
                      ? "comment"
                      : "unknown-token");
      p.redirection = 1;
      continue;
    }
    if ((this_word & WSH_HL_START) && !p.redirection) {
      int allowed = 1;
      for (WshHlSeen *s = seen; s; s = s->next)
        if (wsh_hl_eq(s->name, p.arg))
          allowed = 0;
      res = wsh_hl_type(p.arg, allowed);
      if (wsh_hl_eq(res, "alias")) {
        if (strchr(p.arg + (*p.arg != 0), '=')) {
          wsh_hl_emit(&p, p.start, p.end, "unknown-token");
          continue;
        }
        WshHlSeen *s = zhalloc(sizeof(*s));
        *s = (WshHlSeen){p.arg, p.aliases, seen};
        seen = s;
        char *expanded = wsh_hl_hash("aliases", p.arg);
        char **args = wsh_hl_lex(expanded ? expanded : "");
        words = wsh_hl_prepend(args, words);
        if (!frames)
          p.alias_style = "alias";
        else
          frames->count--;
        WshHlAliasFrame *f = zhalloc(sizeof(*f));
        *f = (WshHlAliasFrame){wsh_hl_countwords(args) + 1, frames};
        frames = f;
        p.aliases++;
        p.redirection++;
        continue;
      } else if (!wsh_hl_eq(res, "global-alias"))
        res = wsh_hl_type(wsh_hl_expand(p.arg), 0);
    }
    if (wsh_hl_redirect(p.arg)) {
      if (p.redirection == 1)
        wsh_hl_emit(&p, p.start, p.end, "unknown-token");
      else {
        p.redirection = 2;
        wsh_hl_emit(&p, p.start, p.end, "redirection");
      }
      continue;
    }
    WshHlText argtext = wsh_hl_text(p.arg);
    int namelen = wsh_hl_parameter_length(argtext, 1);
    if (wsh_hl_ch(argtext, 0) == '{' && namelen &&
        wsh_hl_ch(argtext, 1 + namelen) == '}' && namelen + 2 == argtext.n &&
        words && wsh_hl_redirect(words->s)) {
      p.redirection = 3;
      wsh_hl_emit(&p, p.start, p.end, "named-fd");
      continue;
    }
    if (!p.parameter) {
      char **args = wsh_hl_parameter(p.arg, res);
      if (args) {
        int n = wsh_hl_countwords(args);
        if (!n && !p.redirection) {
          p.redirection++;
          wsh_hl_emit(&p, p.start, p.end, "comment");
          continue;
        }
        p.parameter = 1 + n;
        words = wsh_hl_prepend(args, words);
        if (words) {
          p.arg = words->s;
          res = wsh_hl_type(p.arg, 0);
        }
      }
    }
    if (!p.redirection) {
      if (this_word & WSH_HL_OPT) {
        const char *q = p.arg + (*p.arg == '-');
        if (*p.arg == '-') {
          while (*q && strchr(sans, *q))
            q++;
          if (*q && strchr(with, *q)) {
            this_word &= ~WSH_HL_START;
            next_word = q[1] ? (WSH_HL_REGULAR | WSH_HL_START | WSH_HL_OPT)
                             : WSH_HL_OPTARG;
          } else if (!*q && *sans) {
            this_word = WSH_HL_OPT;
            next_word = WSH_HL_REGULAR | WSH_HL_START | WSH_HL_OPT;
          } else if (*q && strchr(solo, *q)) {
            this_word = WSH_HL_OPT;
            next_word = WSH_HL_REGULAR;
          } else {
            this_word = WSH_HL_OPT;
            next_word = WSH_HL_REGULAR | WSH_HL_START | WSH_HL_OPT;
          }
        } else
          this_word &= ~WSH_HL_OPT;
      } else if (this_word & WSH_HL_OPTARG)
        next_word |= WSH_HL_OPT | WSH_HL_START;
    }
    if (wsh_hl_member(p.arg, "| || ; & && |& &! &|") ||
        wsh_hl_eq(p.arg, "\n")) {
      if (strchr(stack, 'T') &&
          (wsh_hl_eq(p.arg, "||") || wsh_hl_eq(p.arg, "&&")))
        goto noncommand;
      if (wsh_hl_pop(&stack, 'T', &style, NULL) ||
          wsh_hl_pop(&stack, 'Q', &style, NULL))
        style = "unknown-token";
      else if (p.array)
        style = wsh_hl_eq(p.arg, "\n") ? "commandseparator" : "unknown-token";
      else if ((this_word & WSH_HL_REGULAR) ||
               ((this_word & WSH_HL_START) &&
                (wsh_hl_eq(p.arg, "\n") ||
                 (wsh_hl_eq(p.arg, ";") && p.aliases))))
        style = "commandseparator";
      else
        style = "unknown-token";
      if (p.array && (wsh_hl_eq(p.arg, ";") || wsh_hl_eq(p.arg, "\n")))
        next_word = WSH_HL_REGULAR;
      else {
        next_word = WSH_HL_START;
        p.glob = 1;
        p.assigned = 0;
        WshHlSeen **s = &seen;
        while (*s) {
          if ((*s)->level >= p.aliases)
            *s = (*s)->next;
          else
            s = &(*s)->next;
        }
        if (!wsh_hl_eq(p.arg, "|") && !wsh_hl_eq(p.arg, "|&"))
          next_word |= WSH_HL_PIPELINE;
      }
    } else if (!p.redirection && (this_word & WSH_HL_ALWAYS) &&
               wsh_hl_eq(p.arg, "always")) {
      style = "reserved-word";
      p.glob = 1;
      p.assigned = 0;
      next_word = WSH_HL_START | WSH_HL_PIPELINE;
    } else if (!p.redirection && (this_word & WSH_HL_START)) {
      const char *flags = wsh_hl_precommand(p.arg);
      if (flags && !wsh_hl_eq(wsh_hl_type(p.arg, 1), "none")) {
        style = "precommand";
        char *f = dupstring(flags), *colon = strchr(f, ':');
        with = f;
        sans = solo = "";
        if (colon) {
          *colon = 0;
          sans = colon + 1;
          colon = strchr((char *)sans, ':');
          if (colon) {
            *colon = 0;
            solo = colon + 1;
          }
        }
        next_word = (next_word & ~WSH_HL_REGULAR) | WSH_HL_OPT | WSH_HL_START;
        if (wsh_hl_eq(p.arg, "exec") || wsh_hl_eq(p.arg, "env"))
          next_word |= WSH_HL_REGULAR;
      } else if (wsh_hl_eq(res, "reserved-word")) {
        style = res;
        if (wsh_hl_member(p.arg, "time nocorrect"))
          next_word = (next_word & ~WSH_HL_REGULAR) | WSH_HL_START;
        else if (wsh_hl_eq(p.arg, "{"))
          stack = dyncat("Y", stack);
        else if (wsh_hl_eq(p.arg, "}")) {
          wsh_hl_pop(&stack, 'Y', &style, "reserved-word");
          if (wsh_hl_eq(style, "reserved-word"))
            next_word |= WSH_HL_ALWAYS;
        } else if (wsh_hl_eq(p.arg, "[["))
          stack = dyncat("T", stack);
        else if (wsh_hl_eq(p.arg, "do"))
          stack = dyncat("D", stack);
        else if (wsh_hl_eq(p.arg, "done"))
          wsh_hl_pop(&stack, 'D', &style, "reserved-word");
        else if (wsh_hl_eq(p.arg, "if"))
          stack = dyncat(":?", stack);
        else if (wsh_hl_eq(p.arg, "then"))
          wsh_hl_pop(&stack, ':', &style, "reserved-word");
        else if (wsh_hl_eq(p.arg, "elif")) {
          if (*stack == '?')
            stack = dyncat(":", stack);
          else
            style = "unknown-token";
        } else if (wsh_hl_eq(p.arg, "else")) {
          if (*stack != '?')
            style = "unknown-token";
        } else if (wsh_hl_eq(p.arg, "fi"))
          wsh_hl_pop(&stack, '?', &style, NULL);
        else if (wsh_hl_eq(p.arg, "foreach"))
          stack = dyncat("$", stack);
        else if (wsh_hl_eq(p.arg, "end"))
          wsh_hl_pop(&stack, '$', &style, "reserved-word");
        else if (wsh_hl_eq(p.arg, "repeat")) {
          p.redirection = 2;
          this_word = WSH_HL_START | WSH_HL_REGULAR;
        } else if (wsh_hl_eq(p.arg, "!") && !(this_word & WSH_HL_PIPELINE))
          style = "unknown-token";
        if (p.assigned)
          style = "unknown-token";
      } else if (wsh_hl_member(res,
                               "suffix-alias global-alias function command"))
        style = res;
      else if (wsh_hl_eq(res, "builtin")) {
        style = res;
        if (wsh_hl_eq(p.arg, "["))
          stack = dyncat("Q", stack);
      } else if (wsh_hl_eq(res, "none")) {
        if (!p.parameter && wsh_hl_assign(p.arg)) {
          wsh_hl_emit(&p, p.start, p.end, "assign");
          WshHlText t = wsh_hl_text(p.arg);
          int i = 0;
          while (i < t.n && wsh_hl_ch(t, i) != '=')
            i++;
          i++;
          p.assigned = 1;
          if (wsh_hl_ch(t, i) == '(') {
            p.array = 1;
            wsh_hl_emit(&p, p.start + i, p.start + i + 1, "reserved-word");
          } else {
            next_word |= WSH_HL_START;
            if (i < t.n) {
              int glob = p.glob;
              p.glob = wsh_hl_option("globassign");
              wsh_hl_argument(&p, i, 1);
              p.glob = glob;
            }
          }
          continue;
        } else if (!p.parameter &&
                   ((p.arg[0] == wsh_hl_history_char(0) && p.arg[1]) ||
                    p.arg[0] == wsh_hl_history_char(1)))
          style = "history-expansion";
        else if (!p.parameter && !p.assigned && !strncmp(p.arg, "((", 2)) {
          wsh_hl_emit(&p, p.start, p.start + 2, "reserved-word");
          size_t n = strlen(p.arg);
          if (n >= 2 && wsh_hl_eq(p.arg + n - 2, "))"))
            wsh_hl_emit(&p, p.end - 2, p.end, "reserved-word");
          continue;
        } else if (!p.parameter && wsh_hl_eq(p.arg, "()"))
          style = "reserved-word";
        else if (!p.parameter && !p.assigned && wsh_hl_eq(p.arg, "(")) {
          style = "reserved-word";
          stack = dyncat("R", stack);
        } else if (!p.parameter && wsh_hl_eq(p.arg, ")")) {
          if (wsh_hl_pop(&stack, 'S', &style, NULL))
            return (WshHlResult){p.regions, p.start, 0};
          wsh_hl_pop(&stack, 'R', &style, "reserved-word");
        } else {
          const char *v = wsh_hl_path_style(&p, p.arg, 1);
          style = v ? v : "unknown-token";
        }
      } else if (!wsh_hl_eq(res, "alias"))
        style = dyncat("arg0_", (char *)res);
      if (wsh_hl_member(
              p.arg, "{ ( () while until if then elif else do time coproc !"))
        next_word = WSH_HL_START | WSH_HL_PIPELINE;
    } else if (wsh_hl_entry("galiases", p.arg))
      style = "global-alias";
    else {
    noncommand:
      if (wsh_hl_eq(p.arg, ")")) {
        if (p.array) {
          wsh_hl_emit(&p, p.start, p.end, "assign");
          wsh_hl_emit(&p, p.start, p.end, "reserved-word");
          p.array = 0;
          next_word |= WSH_HL_START;
          continue;
        } else if (!p.redirection) {
          if (wsh_hl_pop(&stack, 'S', &style, NULL))
            return (WshHlResult){p.regions, p.start, 0};
          wsh_hl_pop(&stack, 'R', &style, "reserved-word");
        }
      } else if (wsh_hl_eq(p.arg, "()")) {
        if (!p.redirection && !p.array) {
          if (wsh_hl_option("multifuncdef"))
            next_word |= WSH_HL_START | WSH_HL_PIPELINE;
          style = "reserved-word";
        }
      } else if (wsh_hl_eq(p.arg, "}") && !wsh_hl_option("ignorebraces") &&
                 !wsh_hl_option("ignoreclosebraces")) {
        if (!p.redirection && !p.array) {
          wsh_hl_pop(&stack, 'Y', &style, "reserved-word");
          if (wsh_hl_eq(style, "reserved-word"))
            next_word |= WSH_HL_ALWAYS;
        }
      } else if (p.arg[0] == wsh_hl_history_char(0) && p.arg[1])
        style = "history-expansion";
      else if (wsh_hl_eq(p.arg, "]]") &&
               wsh_hl_pop(&stack, 'T', &style, "reserved-word")) {
      } else if (wsh_hl_eq(p.arg, "]") &&
                 wsh_hl_pop(&stack, 'Q', &style, "builtin")) {
      } else {
        wsh_hl_argument(&p, 0, p.redirection != 1);
        continue;
      }
    }
    wsh_hl_emit(&p, p.start, p.end, style);
  }
  if (p.aliases) {
    p.aliases = 0;
    wsh_hl_emit(&p, p.start, p.end, p.alias_style);
  }
  if (p.parameter == 1) {
    p.parameter = 0;
    wsh_hl_emit(&p, p.start, p.end, p.param_style ? p.param_style : "default");
  }
  int tail = pos;
  while (isspace(wsh_hl_ch(p.buf, tail)) ||
         (wsh_hl_ch(p.buf, tail) == '\\' && wsh_hl_ch(p.buf, tail + 1) == '\n'))
    tail += wsh_hl_ch(p.buf, tail) == '\\' ? 2 : 1;
  return (WshHlResult){
      p.regions, p.end + (tail == p.buf.n ? tail - pos : 0) - 1, *stack != 0};
}
static const char *wsh_hl_fallback(const char *s) {
  if (wsh_hl_member(s, "alias suffix-alias builtin function command precommand "
                       "hashed-command autodirectory") ||
      !strncmp(s, "arg0_", 5))
    return "arg0";
  if (wsh_hl_eq(s, "global-alias"))
    return "dollar-double-quoted-argument";
  if (wsh_hl_eq(s, "path_prefix"))
    return "path";
  if (wsh_hl_eq(s, "path_pathseparator"))
    return "path";
  if (wsh_hl_eq(s, "path_prefix_pathseparator"))
    return "path_prefix";
  size_t n = strlen(s);
  if (n > 9 && wsh_hl_eq(s + n - 9, "-unclosed"))
    return dupstrpfx(s, n - 9);
  if (!strncmp(s, "command-substitution", 20)) {
    if (n > 9 && wsh_hl_eq(s + n - 9, "-unquoted"))
      return dupstrpfx(s, n - 9);
    if (n > 7 && wsh_hl_eq(s + n - 7, "-quoted"))
      return dupstrpfx(s, n - 7);
  }
  if (wsh_hl_member(
          s, "command-substitution-delimiter process-substitution-delimiter "
             "back-quoted-argument-delimiter"))
    return dupstrpfx(s, n - 10);
  return NULL;
}
static int wsh_hl_paint(char *name, char **args, Options options, int func) {
  (void)name;
  int symbolic = args[0] && wsh_hl_eq(args[0], "--symbolic");
  (void)options;
  (void)func;
  if (wsh_hl_member(wsh_hl_value("CONTEXT"), "select vared"))
    return 0;
  pushheap();
  char *pre = dupstring(wsh_hl_value("PREBUFFER")),
       *buffer = dyncat(pre, wsh_hl_value("BUFFER"));
  WshHlResult result = wsh_hl_parse(buffer, -wsh_hl_text(pre).n, "", 1, 0);
  char **old = getaparam("region_highlight");
  int count = old ? arrlen(old) : 0, capacity = count;
  for (WshHlRegion *r = result.regions.first; r; r = r->next)
    capacity++;
  char **out = zalloc((capacity + 1) * sizeof(char *));
  for (int i = 0; i < count; i++)
    out[i] = ztrdup(old[i]);
  for (WshHlRegion *r = result.regions.first; r; r = r->next) {
    if (r->a >= r->b || r->b <= 0)
      continue;
    const char *style = r->style;
    char *definition = symbolic ? (char *)style : NULL;
    if (symbolic) {
      const char *next = wsh_hl_fallback(style);
      while (next) {
        definition = zhtricat(definition, ",", (char *)next);
        next = wsh_hl_fallback(next);
      }
    }
    while (!symbolic && style &&
           !(definition = wsh_hl_hash("ZSH_HIGHLIGHT_STYLES", style)))
      style = wsh_hl_fallback(style);
    if (definition) {
      char positions[80];
      snprintf(positions, sizeof(positions), "%d %d ", r->a < 0 ? 0 : r->a,
               r->b);
      out[count++] =
          ztrdup(zhtricat(positions, definition,
                          symbolic ? "" : ", memo=zsh-syntax-highlighting"));
    }
  }
  out[count] = NULL;
  setaparam("region_highlight", out);
  popheap();
  return 0;
}
static struct builtin wsh_highlight_builtins[] = {
    BUILTIN("wsh-highlight-main", 0, wsh_hl_paint, 0, 1, 0, NULL, NULL)};
