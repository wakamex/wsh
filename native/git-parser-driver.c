/* Standalone sanitizer driver, never linked into a runtime. */
#include "git.c"

static void hex(const char *value)
{
    for (const unsigned char *p = (const unsigned char *)value; *p; ++p) printf("%02x", *p);
}
int main(void)
{
    char *line = NULL;
    size_t capacity = 0;
    ssize_t length;
    while ((length = getline(&line, &capacity, stdin)) >= 0) {
        if (length && line[length - 1] == '\n') --length;
        if (length % 2 || length > 65536) abort();
        size_t bytes = (size_t)length / 2;
        unsigned char *data = allocate(bytes + 1);
        for (size_t i = 0; i < bytes; ++i) {
            unsigned value;
            if (sscanf(line + 2 * i, "%2x", &value) != 1) abort();
            data[i] = (unsigned char)value;
        }
        data[bytes] = 0;
        struct wsh_git_result result = {0};
        int status = parse_status(data, bytes, &result);
        printf("%d %d %d %d %llu %llu|", status, result.staged, result.modified, result.untracked,
               (unsigned long long)result.ahead, (unsigned long long)result.behind);
        /* Filename conversion and metadata trimming use C strings. */
        char *converted = lossy((char *)data);
        hex(converted); putchar('|');
        trim(converted); hex(converted); putchar('|');
        FILE *packed = fmemopen(data, bytes, "r");
        if (!packed) abort();
        struct context context = {&result, NULL, NULL, now_ns() + TIMEOUT_NS};
        char record[TEXT_LIMIT + 1];
        int status_line, records = 0;
        while ((status_line = next_line(packed, record, &context)) > 0) ++records;
        printf("%d\n", status_line < 0 ? -1 : records); fflush(stdout);
        fclose(packed); wsh_git_free(&result);
        free(converted); free(data);
    }
    free(line);
    return ferror(stdin) ? 1 : 0;
}
