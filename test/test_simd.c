/* Independent bytewise oracle and protected-page coverage for literal search. */
#include "../krep.h"
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <inttypes.h>

extern int tests_passed;
extern int tests_failed;

static uint32_t random_state = 0x31c0ffee;
static uint32_t next_random(void)
{
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}

static bool word_byte(unsigned char c)
{
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_';
}

static uint64_t reference_search(const search_params_t *p, const char *text,
                                 size_t n, match_position_t *positions)
{
    uint64_t count = 0;
    size_t line = 0, last_line = SIZE_MAX;
    for (size_t i = 0; i < n && p->pattern_len <= n - i && count < p->max_count; ++i)
    {
        if (i && text[i - 1] == '\n')
            ++line;
        if (memcmp(text + i, p->pattern, p->pattern_len) != 0)
            continue;
        size_t end = i + p->pattern_len;
        if (p->whole_word && ((i && word_byte((unsigned char)text[i - 1])) ||
                             (end < n && word_byte((unsigned char)text[end]))))
            continue;
        if (p->count_lines_mode && last_line == line)
            continue;
        positions[count++] = (match_position_t){i, end};
        last_line = line;
    }
    return count;
}

void run_simd_regression_tests(void)
{
    const size_t page = (size_t)sysconf(_SC_PAGESIZE);
    char *mapping = mmap(NULL, page * 3, PROT_NONE, MAP_PRIVATE | MAP_ANON, -1, 0);
    char *pattern_mapping = mmap(NULL, page * 3, PROT_NONE, MAP_PRIVATE | MAP_ANON, -1, 0);
    if (mapping == MAP_FAILED || pattern_mapping == MAP_FAILED ||
        mprotect(mapping + page, page, PROT_READ | PROT_WRITE) != 0 ||
        mprotect(pattern_mapping + page, page, PROT_READ | PROT_WRITE) != 0)
    {
        fprintf(stderr, "FAIL: cannot allocate SIMD guard pages\n");
        ++tests_failed;
        if (mapping != MAP_FAILED) munmap(mapping, page * 3);
        if (pattern_mapping != MAP_FAILED) munmap(pattern_mapping, page * 3);
        return;
    }

    size_t cases = 0;
    bool ok = true;
    const size_t limits[] = {0, 1, 3, SIZE_MAX};
    for (size_t length = 1; length <= 64 && ok; ++length)
    {
        char *pattern = pattern_mapping + page * 2 - length;
        for (size_t j = 0; j < length; ++j)
            pattern[j] = (char)('a' + j % 3);
        // Exercise a zero byte in the pattern, including in a filter position.
        if (length % 7 == 0) pattern[length - 1] = '\0';
        search_params_t p = {.pattern = pattern, .pattern_len = length,
                             .num_patterns = 1, .case_sensitive = true};
        search_func_t functions[] = {
            select_search_algorithm(&p),
#if defined(__ARM_NEON)
            neon_search,
#endif
#if defined(__SSE2__)
            simd_sse42_search,
#endif
#if defined(__AVX2__)
            simd_avx2_search,
#endif
#if defined(__AVX512F__) && defined(__AVX512BW__)
            simd_avx512_search,
#endif
        };
        for (size_t n = 0; n <= length + 128 && ok; ++n)
        {
            // Alternate a guard immediately after the text and before it.
            char *text = (n % 2) ? mapping + page * 2 - n : mapping + page;
            for (size_t j = 0; j < n; ++j)
            {
                static const char alphabet[] = "abc _\n\0\xff";
                text[j] = alphabet[next_random() % (sizeof(alphabet) - 1)];
            }
            if (n >= length)
            {
                size_t start = next_random() % (n - length + 1);
                memcpy(text + start, pattern, length);
                memcpy(text + n - length, pattern, length);
            }
            for (size_t mode = 0; mode < 4 && ok; ++mode)
            {
                p.whole_word = (mode & 1) != 0;
                p.count_lines_mode = (mode & 2) != 0;
                p.track_positions = !p.count_lines_mode;
                p.max_count = limits[(n + mode) % 4];
                match_position_t expected[256];
                uint64_t wanted = reference_search(&p, text, n, expected);
                for (size_t f = 0; f < sizeof(functions) / sizeof(functions[0]); ++f)
                {
                    match_result_t *result = match_result_init(8);
                    uint64_t actual = functions[f](&p, text, n, result);
                    ok = actual == wanted && result != NULL &&
                         result->count == (p.track_positions ? wanted : 0);
                    for (uint64_t j = 0; ok && p.track_positions && j < wanted; ++j)
                        ok = result->positions[j].start_offset == expected[j].start_offset &&
                             result->positions[j].end_offset == expected[j].end_offset;
                    match_result_free(result);
                    ++cases;
                    if (!ok)
                    {
                        fprintf(stderr, "FAIL: literal oracle length=%zu bytes=%zu mode=%zu limit=%zu algorithm=%s expected=%" PRIu64 " actual=%" PRIu64 "\n",
                                length, n, mode, p.max_count, get_algorithm_name(functions[f]), wanted, actual);
                        break;
                    }
                }
            }
        }
    }
    munmap(mapping, page * 3);
    munmap(pattern_mapping, page * 3);
    printf("%s: %zu literal oracle/guard-page cases\n", ok ? "PASS" : "FAIL", cases);
    if (ok) ++tests_passed; else ++tests_failed;
}
