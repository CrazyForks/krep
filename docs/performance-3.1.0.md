# krep 3.1.0 performance

Measured on 2026-09-16 against krep 3.0.2, on an Apple M4 running macOS 27.0 (arm64), using Apple Clang 21.0.0. Both versions were built with their default `make` flags (`-O3`, LTO, NEON), without `NATIVE=1`. The baseline's search sources match the `v3.0.2` tag.

The benchmark generates 67,543,040 bytes of repeated ASCII log records for search cases and 12,000 records for output cases. Each record contains `needle` and `authentication_failed`; `authorization_denied` is absent. Timings are medians of seven warmed process invocations with stdout redirected to `/dev/null`. Baseline and current runs alternate order. Before timing each case, the script checks that both binaries emit byte-identical output and return the same exit status.

| Workload | 3.0.2 (ms) | 3.1.0 (ms) | Speedup |
| --- | ---: | ---: | ---: |
| short literal count, 1 thread | 40.29 | 20.22 | 1.99x |
| long literal count, 1 thread | 77.19 | 20.29 | 3.81x |
| absent literal, 1 thread | 131.41 | 10.15 | 12.95x |
| short literal count, auto threads | 10.51 | 9.94 | 1.06x |
| quiet early match | 9.96 | 4.66 | 2.14x |
| numbered output | 876.29 | 10.28 | 85.28x |
| context output | 883.13 | 10.40 | 84.90x |
| JSON lines | 505.65 | 40.27 | 12.56x |
| JSON matches | 455.60 | 38.59 | 11.81x |

[Raw timings and environment](benchmark-3.1.0-macos-arm64.json) include every sample. These are synthetic, cached workloads on one machine, not a claim about every search. Process startup contributes to short timings. Cold storage, other CPUs, case-insensitive and regular-expression searches can behave differently; automatic threading already makes the baseline faster than its single-thread path. No universal performance threshold is enforced in CI.

## What changed

- **Literal search:** SIMD compares the first pattern byte and a second byte across candidate positions. It verifies the full pattern only for surviving positions. All supported SIMD backends now handle 2–64-byte literals; counting jumps forward after the first match on a line. Vector and tail accesses stay within the original buffer, including whole-word boundary checks.
- **Output:** forward-only cursors retain the current line number and line start. Numbered, context and JSON formatting no longer recount the entire preceding file for every record. Sorting and storing matches still have their own costs.
- **Existence checks:** `-q`, `-l` and `-L` stop after one match per file and do not create search workers or eagerly populate mappings. Quiet recursive searches stop visiting files after a match. Stdin remains buffered before the search.
- **Distribution:** `make PORTABLE=1` avoids build-host x86 AVX flags; Linux release binaries use baseline SSE2. Optimized source builds can use AVX2 or AVX-512 where enabled by the compiler and build host.

## Reproduce

From a checkout with the release tags available:

```sh
baseline_dir="$(mktemp -d)"
git archive v3.0.2 | tar -x -C "$baseline_dir"
make -C "$baseline_dir"
make clean && make
python3 test/benchmark_release.py \
  --baseline "$baseline_dir/krep" --runs 7 \
  --json benchmark-results.json
```

The benchmark uses Python's standard library and generates its own dataset. Use `--size-mib`, `--output-lines` and `--runs` to change workload sizes. `make bench-release` measures the current binary without a baseline.

## Correctness checks

`make ci` runs the existing unit and directory suites, the v3 CLI regressions, and the new 3.1 tests. The new literal tests compare results and offsets against an independent bytewise oracle, with inaccessible memory pages immediately beside text/pattern buffers. On ARM64 they execute 82,688 cases covering lengths 1–64, alignment, tails, embedded NUL bytes, whole-word checks, line counts and count limits. The number varies by the compiled SIMD entry points.

The CLI suite performs 364 subprocess checks, including scalar/SIMD count agreement, JSON byte offsets and columns, overlapping patterns, empty context lines, stdin/string existence status, recursion, and thread boundaries. `make sanitize` repeats all suites with AddressSanitizer and UndefinedBehaviorSanitizer. CI covers optimized Linux/macOS builds, portable x86-64, AVX2 when available, and sanitizers on both operating systems. Release jobs retest the portable binaries before packaging them.
