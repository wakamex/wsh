/* Native search state and editor behavior; public settings remain Zsh parameters. */
static struct {
    char *query, *result;
    char **parts;
    zlong *raw, *matches, index;
    size_t count, wsh_history_next, used;
    HashTable seen;
    int active;
} wsh_history_search;
static char *wsh_history_value(const char *name)
{
    char *s = getsparam((char *)name);
    return s ? s : "";
}
static void wsh_history_set_value(const char *name, const char *s)
{
    setsparam((char *)name, ztrdup(s));
}
static void wsh_history_reset(void)
{
    zsfree(wsh_history_search.query); zsfree(wsh_history_search.result);
    if (wsh_history_search.parts) freearray(wsh_history_search.parts);
    free(wsh_history_search.raw); free(wsh_history_search.matches);
    if (wsh_history_search.seen) deleteparamtable(wsh_history_search.seen);
    wsh_history_search.query = wsh_history_search.result = NULL; wsh_history_search.parts = NULL;
    wsh_history_search.raw = wsh_history_search.matches = NULL; wsh_history_search.seen = NULL;
    wsh_history_search.count = wsh_history_search.wsh_history_next = wsh_history_search.used = 0; wsh_history_search.index = 0;
}
static char *wsh_history_entry(zlong key)
{
    Histent h = gethistent(key, 0);
    return h && h->histnum == key ? h->node.nam : "";
}
static void wsh_history_begin(void)
{
    char *buffer = wsh_history_value("BUFFER");
    if (*buffer && wsh_history_search.result && !strcmp(buffer, wsh_history_search.result)) return;
    wsh_history_reset();
    wsh_history_search.query = ztrdup(buffer);
    char **parts;
    if (*wsh_history_value("HISTORY_SUBSTRING_SEARCH_FUZZY")) parts = spacesplit(buffer, 0, 1, 0);
    else { parts = zhalloc(2*sizeof(char *)); parts[0] = *buffer ? buffer : NULL; parts[1] = NULL; }
    wsh_history_search.parts = zarrdup(parts);
    size_t n = arrlen(parts);
    char **escaped = zhalloc((n+1)*sizeof(char *));
    for (size_t i=0; i<n; ++i) escaped[i] = quotestring(parts[i], QT_BACKSLASH_PATTERN);
    escaped[n] = NULL;
    char *pattern = zhtricat("(#", wsh_history_value("HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS"), ")");
    pattern = dyncat(pattern, *wsh_history_value("HISTORY_SUBSTRING_SEARCH_PREFIXED") ? "" : "*");
    pattern = zhtricat(pattern, zjoin(escaped, '*', 1), "*");
    tokenize(pattern);
    Patprog compiled = patcompile(pattern, 0, NULL);
    LinkList keys = newlinklist();
    if (*buffer) for (Histent h=gethistent(addhistnum(curhist,-1,HIST_FOREIGN),GETHIST_UPWARD); h; h=up_histent(h)) {
        if (compiled && !pattry(compiled,h->node.nam)) continue;
        zlong *key = zhalloc(sizeof(*key)); *key = h->histnum;
        addlinknode(keys,key);
    }
    wsh_history_search.count = countlinknodes(keys);
    wsh_history_search.raw = zalloc((wsh_history_search.count+1)*sizeof(zlong));
    wsh_history_search.matches = zalloc((wsh_history_search.count+1)*sizeof(zlong));
    size_t i=0;
    for (LinkNode node=firstnode(keys); node; incnode(node)) wsh_history_search.raw[i++] = *(zlong *)getdata(node);
    wsh_history_search.seen = newparamtable(17,"history seen");
    wsh_history_search.index = !strcmp(wsh_history_value("WIDGET"),"history-substring-search-down") ? 1 : 0;
}
static int wsh_history_next(void)
{
    while (wsh_history_search.wsh_history_next < wsh_history_search.count) {
        zlong key = wsh_history_search.raw[wsh_history_search.wsh_history_next++];
        if (!isset(HISTIGNOREALLDUPS) && *wsh_history_value("HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE")) {
            char *text = wsh_history_entry(key);
            if (wsh_history_search.seen->getnode(wsh_history_search.seen,text)) continue;
            queue_signals();
            HashTable saved=paramtab; paramtab=wsh_history_search.seen;
            Param p=createparam(text,PM_SCALAR|PM_HASHELEM); paramtab=saved;
            p->gsu.s->setfn(p,ztrdup("1"));
            unqueue_signals();
        }
        wsh_history_search.matches[wsh_history_search.used++]=key;
        return 1;
    }
    return 0;
}
static const char *wsh_history_navigate(int down)
{
    for (;;) {
        int found=0;
        if (down) {
            if (wsh_history_search.index >= 1) { found=wsh_history_search.index>1; --wsh_history_search.index; }
        } else if (wsh_history_search.index <= (zlong)wsh_history_search.used) {
            found=wsh_history_search.index<(zlong)wsh_history_search.used || wsh_history_next(); ++wsh_history_search.index;
        }
        wsh_history_set_value("BUFFER",found ? wsh_history_entry(wsh_history_search.matches[wsh_history_search.index-1]) : wsh_history_search.query);
        if (!found || isset(HISTIGNOREALLDUPS) || *wsh_history_value("HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE") ||
            !isset(HISTFINDNODUPS) || !wsh_history_search.result || strcmp(wsh_history_value("BUFFER"),wsh_history_search.result))
            return found ? "HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND" : "HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_NOT_FOUND";
    }
}
static int wsh_history_count_lines(const char *text)
{
    int count=0, nonempty=0;
    for (; *text; ++text) {
        if (*text=='\n') { count+=nonempty; nonempty=0; }
        else nonempty=1;
    }
    return count+nonempty;
}
static void wsh_history_clear_highlight(void)
{
    char **old=getaparam("region_highlight");
    size_t count=old ? arrlen(old) : 0, used=0;
    char **updated=zalloc((count+1)*sizeof(char *));
    for (size_t i=0;i<count;++i)
        if (!strstr(old[i],"memo=history-substring-search")) updated[used++]=ztrdup(old[i]);
    updated[used]=NULL; setaparam("region_highlight",updated);
}
static void wsh_history_finish(int refresh, const char *style_name)
{
    zsfree(wsh_history_search.result); wsh_history_search.result=ztrdup(wsh_history_value("BUFFER"));
    char *style=dupstring(style_name ? wsh_history_value(style_name) : "");
    if (refresh) { wsh_history_clear_highlight(); setiparam("CURSOR",MB_METASTRLEN(wsh_history_value("BUFFER"))); }
    Shfunc fn=(Shfunc)shfunctab->getnode(shfunctab,"_zsh_highlight");
    if (fn) { LinkList args=newlinklist(); addlinknode(args,dupstring("_zsh_highlight")); doshfunc(fn,args,0); }
    if (*style) {
        char *buffer=dupstring(wsh_history_value("BUFFER")), *tail=buffer;
        int offset=0;
        for (char **part=wsh_history_search.parts; *part; ++part) {
            char *pattern=zhtricat("(#",wsh_history_value("HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS"),")");
            pattern=dyncat(pattern,quotestring(*part,QT_BACKSLASH_PATTERN)); tokenize(pattern);
            char *matched=dupstring(tail);
            if (!getmatch(&matched,pattern,SUB_SUBSTR|SUB_LONG|SUB_BIND,1,NULL)) continue;
            int index=atoi(matched);
            if (index<1 || index>MB_METASTRLEN(tail)) continue;
            offset+=index;
            char region[80]; snprintf(region,sizeof(region),"%d %d ",offset-1,offset-1+MB_METASTRLEN(*part));
            char **old=getaparam("region_highlight"); size_t count=old ? arrlen(old) : 0;
            char **updated=zalloc((count+2)*sizeof(char *));
            for (size_t i=0;i<count;++i) updated[i]=ztrdup(old[i]);
            updated[count]=ztrdup(zhtricat(region,style,",memo=history-substring-search"));
            updated[count+1]=NULL; setaparam("region_highlight",updated);
            tail=buffer; int remaining=offset;
            while (*tail && remaining--) tail+=MB_METACHARLEN(tail);
        }
    }
    execstring("zle -R; read -k -t ${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_TIMEOUT:-1} && zle -U -- \"$REPLY\"",1,0,"wsh-history");
    wsh_history_clear_highlight();
}
static int wsh_history_command(char *name, char **args, Options options, int function)
{
    (void)name; (void)options; (void)function;
    if (wsh_history_search.active) return 1;
    if (!strcmp(args[0],"reset")) { wsh_history_reset(); return 0; }
    int down=!strcmp(args[0],"down");
    if (!down && strcmp(args[0],"up")) return 1;
    wsh_history_search.active=1; pushheap();
    int saved=opts[EXTENDEDGLOB]; opts[EXTENDEDGLOB]=1;
    wsh_history_begin();
    int refresh=0; const char *style=NULL;
    char *motion=down ? "zle down-line-or-history" : "zle up-line-or-history";
    if (!*wsh_history_search.query) {
        if (getiparam("HISTNO")==1 && (!down || !*wsh_history_value("BUFFER"))) {
            wsh_history_set_value("BUFFER",down ? wsh_history_entry(1) : ""); refresh=down;
        } else execstring(motion,1,0,"wsh-history");
    } else {
        char *side=down ? dyncat("x",wsh_history_value("RBUFFER")) : dyncat(wsh_history_value("LBUFFER"),"x");
        if (wsh_history_count_lines(wsh_history_value("BUFFER"))>1 && getiparam("CURSOR")!=MB_METASTRLEN(wsh_history_value("BUFFER")) && wsh_history_count_lines(side)!=1)
            execstring(motion,1,0,"wsh-history");
        else { style=wsh_history_navigate(down); refresh=1; }
    }
    wsh_history_finish(refresh,style);
    opts[EXTENDEDGLOB]=saved; popheap(); wsh_history_search.active=0;
    return 0;
}
static struct builtin wsh_history_builtins[]={BUILTIN("wsh-history",0,wsh_history_command,1,1,0,NULL,NULL)};
