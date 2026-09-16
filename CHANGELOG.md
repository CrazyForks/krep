# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.1.0] - 2026-09-16

### Performance

- Replace the separate SIMD search loops with a bounded two-byte candidate filter for case-sensitive literals of 2–64 bytes, using NEON, SSE2, AVX2 or AVX-512. Full comparisons run only on surviving candidates; counting skips directly to the next line.
- Compute line numbers and JSON columns with forward-only cursors instead of repeatedly scanning from the beginning of the file. Numbered, contextual and JSON output now scan the text in linear time.
- Stop `-q`, `-l` and `-L` searches at the first match, avoid worker creation and eager mapping population for these checks, and stop quiet recursive traversal once a match is found.
- Add an offline release benchmark that verifies identical output and exit status before comparing interleaved runs with a previous executable. See [the measured results and reproduction instructions](https://github.com/davidesantangelo/krep/blob/v3.1.0/docs/performance-3.1.0.md).

### Fixed

- Preserve whole-word boundaries and line counts across SIMD tails without reading beyond text or pattern buffers.
- Keep whole-word and non-overlapping `-o` matches consistent across file chunks. SIMD `-o` now emits non-overlapping matches, including self-overlapping patterns.
- Return the correct match status for quiet searches on stdin and strings, and honor `-m 0` in existence checks.
- Preserve empty lines when selecting before-context and sort multi-pattern stdin/string matches before formatting output.

### Build and validation

- Add `make PORTABLE=1` for distributable x86-64 binaries using baseline SSE2, without requiring the build host's AVX extensions. Release archives include the license, README and changelog.
- Add deterministic oracle tests with protected memory pages and CLI regression tests covering output, SIMD/scalar agreement, recursion and thread boundaries.
- Add `make sanitize` and Linux/macOS CI coverage for AddressSanitizer and UndefinedBehaviorSanitizer, plus portable x86-64 and AVX2 builds.
- Make CI and release smoke benchmarks independent of external dataset downloads. Fix `make clean` and directory-test header dependencies.

## [3.0.2] - 2026-09-03

### Security

- **Bug 1 (print_matching_items newline cache)**: Fixed heap buffer overflow caused by integer multiplication wraparound when allocating the newline-position cache on 32-bit systems ([#44](https://github.com/davidesantangelo/krep/issues/44)).
- **Bug 2 (print_matching_items trailing newline write)**: Fixed heap buffer overflow by accurately simulating formatted line size accounting for duplicate and overlapping multi-pattern matches ([#44](https://github.com/davidesantangelo/krep/issues/44)).
- **Bug 3 (search_file read loop)**: Fixed heap buffer overflow when reading files with apparent sizes exceeding representation limits by safely validating signed `fstat` file size ([#44](https://github.com/davidesantangelo/krep/issues/44)).
- **Bug 4 (gitignore_add_pattern)**: Fixed heap buffer overflow on allocation failure by updating logical capacity only after successful `realloc` and adding integer overflow checks ([#44](https://github.com/davidesantangelo/krep/issues/44)).
- **Bug 5 (simd_sse42_search)**: Fixed heap buffer over-read in SSE4.2 string search for patterns shorter than 16 bytes by reading through a safe bounded zero-padded buffer ([#44](https://github.com/davidesantangelo/krep/issues/44)).

## [3.0.1] - 2026-08-25

### Fixed

- Fixed a busy loop when a zero-width regex match lands exactly at a line ending, including empty regex patterns on platforms that accept them ([#41](https://github.com/davidesantangelo/krep/issues/41)).
- Added bounded CLI regression tests for empty and end-of-line zero-width regex patterns.

## [3.0.0] - 2026-07-01

### Added

- Support for `-r` / `--recursive` directory search with glob and exclude patterns.
- Hidden file inclusion (`--hidden`) and `.gitignore` file support.
- JSON Lines output mode (`--json`).
- Context display (`-A`, `-B`, `-C`).
- Machine-friendly search stats (`--stats`).
