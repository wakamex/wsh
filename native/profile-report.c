/* Bounded saved-report decoding uses the system Jansson parser. */
#include <jansson.h>
#include <ctype.h>
#include <math.h>

static char *
wsh_profile_read(int directory, const char *name, size_t limit, int optional)
{
    int fd = openat(directory, name, O_RDONLY | O_NONBLOCK | O_CLOEXEC | O_NOFOLLOW);
    struct stat st;
    char *buffer;
    size_t used = 0;
    ssize_t count;
    if (fd < 0)
        return optional && errno == ENOENT ? strdup("") : NULL;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != getuid() || (st.st_mode & 077) || st.st_size < 0 || (uintmax_t)st.st_size > limit) {
        close(fd);
        return NULL;
    }
    buffer = malloc((size_t)st.st_size + 2);
    if (!buffer) {
        close(fd);
        return NULL;
    }
    while (used <= (size_t)st.st_size) {
        count = read(fd, buffer + used, (size_t)st.st_size + 1 - used);
        if (count < 0 && errno == EINTR)
            continue;
        if (count < 0)
            goto invalid;
        if (!count)
            break;
        used += (size_t)count;
    }
    close(fd);
    if (used > (size_t)st.st_size || memchr(buffer, 0, used)) {
        free(buffer);
        return NULL;
    }
    buffer[used] = 0;
    return buffer;
invalid:
    close(fd);
    free(buffer);
    return NULL;
}

static const char *
wsh_profile_string(json_t *object, const char *name)
{
    const char *value = json_string_value(json_object_get(object, name));
    return value ? value : "unavailable";
}

static int
wsh_profile_word(const char *value, size_t limit)
{
    size_t length = 0;
    if (!value || !*value)
        return 0;
    for (; *value; ++value, ++length)
        if (length >= limit || !((*value >= 'a' && *value <= 'z') || (*value >= 'A' && *value <= 'Z') || (*value >= '0' && *value <= '9') || strchr("._+-", *value)))
            return 0;
    return 1;
}

static int
wsh_profile_digest(const char *value)
{
    size_t i;
    if (!value || strlen(value) != 64)
        return 0;
    for (i = 0; i < 64; ++i)
        if (!((value[i] >= '0' && value[i] <= '9') || (value[i] >= 'a' && value[i] <= 'f')))
            return 0;
    return 1;
}

static int
wsh_profile_fields(json_t *object, const char *allowed)
{
    const char *key, *letter;
    json_t *value;
    char needle[128];
    if (!json_is_object(object))
        return 0;
    json_object_foreach(object, key, value) {
        (void)value;
        for (letter = key; *letter; ++letter)
            if (!((*letter >= 'a' && *letter <= 'z') || (*letter >= '0' && *letter <= '9') || *letter == '_'))
                return 0;
        if (snprintf(needle, sizeof(needle), "|%s|", key) >= (int)sizeof(needle) || !strstr(allowed, needle))
            return 0;
    }
    return 1;
}

static int
wsh_profile_event_valid(json_t *event)
{
    const char *key, *source, *name;
    json_t *value;
    const char *numbers = "|elapsed_us|generation|duration_us|render_duration_us|response_write_duration_us|repository_discovery_us|git_process_us|parse_duration_us|child_processes|rendered_bytes|";
    const char *strings = "|repaint_cause|theme|wsh_version|bundle_sha256|history_owner|autosuggestions_owner|syntax_owner|";
    char needle[128];
    if (!wsh_profile_fields(event, "|schema_version|source|event|elapsed_us|generation|duration_us|render_duration_us|response_write_duration_us|repository_discovery_us|git_process_us|parse_duration_us|child_processes|rendered_bytes|prompt_changed|repaint_cause|theme|wsh_version|bundle_sha256|history_owner|autosuggestions_owner|syntax_owner|"))
        return 0;
    if (!json_is_integer(json_object_get(event, "schema_version")) || json_integer_value(json_object_get(event, "schema_version")) != 1)
        return 0;
    source = json_string_value(json_object_get(event, "source"));
    name = json_string_value(json_object_get(event, "event"));
    if (!source || (strcmp(source, "manager") && strcmp(source, "zsh") && strcmp(source, "runtime")) || !name || !*name || strlen(name) > 64)
        return 0;
    for (; *name; ++name)
        if (!((*name >= 'a' && *name <= 'z') || *name == '-'))
            return 0;
    if (!json_is_integer(json_object_get(event, "elapsed_us")))
        return 0;
    json_object_foreach(event, key, value) {
        snprintf(needle, sizeof(needle), "|%s|", key);
        if (strstr(numbers, needle) && !json_is_null(value) && (!json_is_integer(value) || json_integer_value(value) < 0))
            return 0;
        if (strstr(strings, needle) && !json_is_null(value) && !wsh_profile_word(json_string_value(value), 128))
            return 0;
        if (!strcmp(key, "prompt_changed") && !json_is_boolean(value) && !json_is_null(value))
            return 0;
    }
    return 1;
}

static json_t *
wsh_profile_find(json_t *events, const char *name, const char *source, int first_generation)
{
    size_t index;
    json_t *event;
    json_array_foreach(events, index, event)
        if (!strcmp(wsh_profile_string(event, "event"), name) && (!source || !strcmp(wsh_profile_string(event, "source"), source)) && (!first_generation || json_integer_value(json_object_get(event, "generation")) == 1))
            return event;
    return NULL;
}

static void
wsh_profile_duration(const char *label, json_t *value)
{
    if (json_is_integer(value))
        printf("%s: %.3f ms\n", label, (double)json_integer_value(value) / 1000.0);
    else
        printf("%s: unavailable\n", label);
}

static void
wsh_profile_span(json_t *events, const char *label, const char *start, const char *end)
{
    json_t *a = json_object_get(wsh_profile_find(events, start, NULL, 0), "elapsed_us");
    json_t *b = json_object_get(wsh_profile_find(events, end, NULL, 0), "elapsed_us");
    if (a && b && json_integer_value(b) >= json_integer_value(a))
        printf("%s: %.3f ms\n", label, (double)(json_integer_value(b) - json_integer_value(a)) / 1000.0);
    else
        printf("%s: unavailable\n", label);
}

static void
wsh_profile_safe(const char *text)
{
    const unsigned char *p = (const unsigned char *)text;
    for (; *p; ++p)
        if (*p < 32 || *p == 127)
            printf("\\x%02x", *p);
        else
            putchar(*p);
}

static void
wsh_profile_functions(char *text)
{
    struct { double self_ms; char *name; } top[8];
    char *line, *next;
    size_t used = 0, i, j;
    int line_number = 0;
    for (line = text; line && *line; line = next) {
        double self_ms;
        char *fields[10], *token, *context, *end;
        size_t fields_used = 0;
        next = strchr(line, '\n');
        if (next)
            *next++ = 0;
        if (line_number++ < 2)
            continue;
        if (!*line || *line == '-')
            break;
        for (token = strtok_r(line, " \t\r", &context); token && fields_used < 10; token = strtok_r(NULL, " \t\r", &context))
            fields[fields_used++] = token;
        if (fields_used != 9 || fields[0][strlen(fields[0]) - 1] != ')')
            continue;
        errno = 0;
        self_ms = strtod(fields[5], &end);
        if (*end || end == fields[5] || errno || !isfinite(self_ms) || self_ms < 0)
            continue;
        for (i = 0; i < used && top[i].self_ms >= self_ms; ++i) {}
        if (i == 8)
            continue;
        if (used < 8)
            ++used;
        for (j = used - 1; j > i; --j)
            top[j] = top[j - 1];
        top[i].self_ms = self_ms;
        top[i].name = fields[8];
    }
    puts("\nSlowest Zsh functions by self time");
    if (!used)
        puts("unavailable");
    for (i = 0; i < used; ++i) {
        printf("%.3f ms  ", top[i].self_ms);
        wsh_profile_safe(top[i].name);
        putchar('\n');
    }
}

static int
wsh_profile_report(const char *directory)
{
    int fd = -1, result = 1, schema;
    struct stat st;
    char *metadata_text = NULL, *trace = NULL, *functions = NULL, *line, *next;
    json_t *metadata = NULL, *events = NULL, *event, *launch, *worker, *snapshot, *ownership;
    const char *identity, *field;
    size_t count = 0, index;
    static const char *spans[][3] = {
        {"User .zshenv", "user-zshenv-start", "user-zshenv-end"},
        {"User .zprofile", "user-zprofile-start", "user-zprofile-end"},
        {"User .zshrc", "user-zshrc-start", "user-zshrc-end"},
        {"User .zlogin", "user-zlogin-start", "user-zlogin-end"},
        {"Directory jumping", "directory-jump-start", "directory-jump-end"},
        {"History substring search", "history-start", "history-end"},
        {"Autosuggestions", "autosuggestions-start", "autosuggestions-end"},
        {"Syntax highlighting", "syntax-highlighting-start", "syntax-highlighting-end"},
        {"Wsh integration", "integration-start", "integration-end"},
        {"Wsh first precmd hook", "precmd-start", "precmd-end"}
    };
    static const char *provider[][2] = {
        {"Repository discovery", "repository_discovery_us"}, {"Git process", "git_process_us"},
        {"Git output parsing", "parse_duration_us"}, {"Provider total", "duration_us"}
    };
    fd = open(directory, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0 || fstat(fd, &st) || st.st_uid != getuid() || (st.st_mode & 077))
        goto done;
    metadata_text = wsh_profile_read(fd, "metadata.json", 4096, 0);
    trace = wsh_profile_read(fd, "trace.jsonl", 8 * 1024 * 1024, 0);
    functions = wsh_profile_read(fd, "zprof.txt", 1024 * 1024, 1);
    if (!metadata_text || !trace || !functions)
        goto done;
    event = json_string(functions);
    if (!event)
        goto done;
    json_decref(event);
    metadata = json_loads(metadata_text, JSON_REJECT_DUPLICATES, NULL);
    if (!json_is_object(metadata) || !json_is_integer(json_object_get(metadata, "schema_version")))
        goto done;
    if (json_integer_value(json_object_get(metadata, "schema_version")) != 1 && json_integer_value(json_object_get(metadata, "schema_version")) != 2)
        goto done;
    schema = (int)json_integer_value(json_object_get(metadata, "schema_version"));
    if (schema == 1) {
        if (!wsh_profile_fields(metadata, "|schema_version|bundle_root|bundle_sha256|") || !json_is_string(json_object_get(metadata, "bundle_root")))
            goto done;
        identity = json_string_value(json_object_get(metadata, "bundle_sha256"));
    } else if (schema == 2) {
        static const char *names[] = {"wsh_version", "source_revision", "native_inputs_sha256", "zsh_version", "zsh_source_revision", "target"};
        if (!wsh_profile_fields(metadata, "|schema_version|wsh_version|source_revision|native_inputs_sha256|zsh_version|zsh_source_revision|target|"))
            goto done;
        for (index = 0; index < sizeof(names) / sizeof(*names); ++index)
            if (!wsh_profile_word(json_string_value(json_object_get(metadata, names[index])), 128))
                goto done;
        identity = json_string_value(json_object_get(metadata, "native_inputs_sha256"));
    } else
        goto done;
    if (!wsh_profile_digest(identity) || !(events = json_array()))
        goto done;
    for (line = trace; *line; line = next + 1) {
        next = strchr(line, '\n');
        if (!next || next - line + 1 > 64 * 1024 || ++count > 100000)
            goto done;
        event = json_loadb(line, (size_t)(next - line), JSON_REJECT_DUPLICATES, NULL);
        if (!wsh_profile_event_valid(event)) {
            json_decref(event);
            goto done;
        }
        if (json_array_append_new(events, event))
            goto done;
    }
    launch = wsh_profile_find(events, "launch-ready", "manager", 0);
    if (!launch || !json_is_string(json_object_get(launch, "wsh_version")) || strcmp(wsh_profile_string(launch, "bundle_sha256"), identity))
        goto done;
    if (schema == 2 && strcmp(wsh_profile_string(launch, "wsh_version"), wsh_profile_string(metadata, "wsh_version")))
        goto done;
    puts("Wsh profile");
    if (schema == 2) {
        printf("Build: wsh %s (recorded native development identity)\n", wsh_profile_string(metadata, "wsh_version"));
        printf("Zsh: %s at %.12s\nSource: %.12s  Target: %s  Native inputs: %.12s\n", wsh_profile_string(metadata, "zsh_version"), wsh_profile_string(metadata, "zsh_source_revision"), wsh_profile_string(metadata, "source_revision"), wsh_profile_string(metadata, "target"), identity);
    } else
        printf("Build: wsh %s (recorded legacy identity)\nBundle: %s\n", wsh_profile_string(launch, "wsh_version"), identity);
    puts("Identity is recorded in this profile; installed resources are not verified.\n\nStartup");
    wsh_profile_duration("Wsh ZLE initialization hook", json_object_get(wsh_profile_find(events, "editor-ready", NULL, 0), "elapsed_us"));
    event = schema == 2 ? wsh_profile_find(events, "native-startup-enter", NULL, 0) : NULL;
    if (!event)
        event = wsh_profile_find(events, "zsh-startup-enter", NULL, 0);
    wsh_profile_duration(schema == 2 ? "Native entry to Zsh startup" : "Launcher to Zsh startup", json_object_get(event, "elapsed_us"));
    for (index = 0; index < sizeof(spans) / sizeof(*spans); ++index)
        wsh_profile_span(events, spans[index][0], spans[index][1], spans[index][2]);
    wsh_profile_duration("Runtime ready", json_object_get(wsh_profile_find(events, "runtime-ready", NULL, 0), "elapsed_us"));
    puts("\nInitial asynchronous prompt");
    worker = wsh_profile_find(events, "worker-completed", "runtime", 1);
    snapshot = wsh_profile_find(events, "snapshot-published", "runtime", 1);
    for (index = 0; index < sizeof(provider) / sizeof(*provider); ++index)
        wsh_profile_duration(provider[index][0], json_object_get(worker, provider[index][1]));
    event = json_object_get(worker, "child_processes");
    if (json_is_integer(event))
        printf("Child processes: %lld\n", (long long)json_integer_value(event));
    else
        puts("Child processes: unavailable");
    wsh_profile_duration("Prompt rendering", json_object_get(snapshot, "render_duration_us"));
    wsh_profile_duration("Response write", json_object_get(snapshot, "response_write_duration_us"));
    event = json_object_get(snapshot, "rendered_bytes");
    if (json_is_integer(event))
        printf("Rendered prompt bytes: %lld\n", (long long)json_integer_value(event));
    event = json_object_get(snapshot, "prompt_changed");
    if (json_is_boolean(event))
        printf("Prompt changed: %s\n", json_is_true(event) ? "true" : "false");
    if (json_is_string(json_object_get(snapshot, "repaint_cause")))
        printf("Repaint cause: %s\n", wsh_profile_string(snapshot, "repaint_cause"));
    wsh_profile_duration("Snapshot published", json_object_get(snapshot, "elapsed_us"));
    wsh_profile_duration("Snapshot applied and repainted", json_object_get(wsh_profile_find(events, "snapshot-applied", "zsh", 1), "elapsed_us"));
    ownership = wsh_profile_find(events, "builtin-ownership", NULL, 0);
    if (ownership)
        printf("\nBuilt-in ownership\nHistory substring search: %s\nAutosuggestions: %s\nSyntax highlighting: %s\n", wsh_profile_string(ownership, "history_owner"), wsh_profile_string(ownership, "autosuggestions_owner"), wsh_profile_string(ownership, "syntax_owner"));
    json_array_foreach(events, index, event) {
        field = json_string_value(json_object_get(event, "theme"));
        if (field) {
            printf("Theme: %s\n", field);
            break;
        }
    }
    wsh_profile_functions(functions);
    fputs("\nTrace: ", stdout);
    wsh_profile_safe(directory);
    putchar('\n');
    result = fflush(stdout) == EOF || ferror(stdout) ? 1 : 0;
done:
    if (fd >= 0)
        close(fd);
    free(metadata_text);
    free(trace);
    free(functions);
    json_decref(metadata);
    json_decref(events);
    if (result)
        fputs("wsh: profile requires bounded private files, supported schemas and consistent identity\n", stderr);
    return result;
}
