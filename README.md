# krep

A high-performance string search utility for the command line. Fast, multi-threaded, and grep-compatible.

## Features

- Smart algorithm selection (Boyer-Moore, KMP, Two-Way, Shift-Or, Aho-Corasick)
- SIMD acceleration (SSE2, AVX2, AVX-512, NEON) and memory-mapped I/O
- Multi-threaded search across CPU cores
- POSIX regular expressions and multiple pattern search
- Recursive directory search with globs, exclusions, and `.gitignore` support
- Grep-compatible context (`-A`, `-B`, `-C`, `-n`, `-o`, `-c`, `-l`, `-L`, `-q`)
- JSON Lines output (`--json`) for automation
- Colored output

## Installation

```bash
# macOS (Homebrew)
brew install krep

# From source
git clone https://github.com/davidesantangelo/krep.git
cd krep
make
sudo make install
```

Requirements: GCC or compatible C compiler, POSIX system (Linux, macOS, BSD), pthread.

Use `make PORTABLE=1` for distributable binaries, or `make NATIVE=1` to tune a build for your own CPU. Run `make clean` before changing build flags. Published Linux x86-64 binaries use baseline SSE2; source builds can enable wider vectors supported by the build machine.

## Usage

```bash
krep [OPTIONS] PATTERN [FILE | DIRECTORY]
krep [OPTIONS] -e PATTERN -e PATTERN ...
krep [OPTIONS] -f FILE               # patterns from file (- for stdin)
krep [OPTIONS] -s PATTERN STRING     # search in a string instead of a file
cat FILE | krep PATTERN
```

## Examples

```bash
krep -F "value: 100%" config.ini              # fixed string
krep -r "function" ./project                  # recursive search
krep -r --gitignore "TODO" ./project          # respect .gitignore
krep -r --glob '*.c' --exclude '*/vendor/*' "TODO" .
krep -n -C 2 "panic" app.log                  # line numbers + context
krep -w 'cat' file.txt                        # whole words only
krep -r -l "DeprecatedAPI" .                  # list files with matches
krep -q "required" config.ini                # quiet existence check
krep --json "needle" ./src/main.c             # JSON Lines output
echo 'pattern' | krep -f - target.txt         # patterns from stdin
```

## Options

- `-i, --ignore-case` Case-insensitive search
- `-c, --count` Count matching lines only
- `-o, --only-matching` Print only the matched parts
- `-n, --line-number` Prefix lines with line numbers
- `-A, -B, -C NUM` Context after, before, or around matches
- `-l, -L` Files with / without matches
- `-q, --quiet` Exit status only
- `-e PATTERN` Specify pattern(s), repeatable
- `-f FILE` Read patterns from file (`-` for stdin)
- `-m NUM` Max matching lines per file
- `-E` POSIX extended regex
- `-F` Fixed strings (default)
- `-r, --recursive` Recursively search directories
- `--glob=GLOB`, `--exclude=GLOB` Include/exclude paths
- `--hidden` Include hidden files
- `--gitignore` Respect `.gitignore`
- `--algo=ALGO` Force algorithm: `auto`, `bm`, `kmp`, `bndm`, `two`
- `-t NUM, --threads=NUM` Thread count (default: auto)
- `-s STRING` Search in a string instead of files
- `-w, --word-regexp` Whole words only
- `--json, --jsonl` JSON Lines output
- `--stats` Print summary to stderr
- `--color[=WHEN]` Color control (`always`, `never`, `auto`)
- `--no-simd` Disable SIMD
- `-v, --version`, `-h, --help`

## Performance and testing

Version 3.1.0 adds two-byte SIMD filtering for literals, linear-time line numbering and JSON output, and early exit for existence checks. Measurements against 3.0.2, including hardware, raw samples and limitations, are in [the performance report](docs/performance-3.1.0.md).

```bash
make ci             # unit, protected-page, directory and CLI tests (Python 3 required)
make sanitize       # rebuild and test with ASan + UBSan (Clang required)
make clean && make  # restore an optimized build after sanitizer testing
make bench-release  # generated local dataset; no download required
python3 test/benchmark_release.py --baseline /path/to/krep-3.0.2 --runs 5
```

`--stats` reports matches encountered; `-q`, `-l` and `-L` stop after the first match, so their match totals are intentionally capped at one per searched file. Input byte totals describe the supplied file or buffer sizes, not physical I/O. Stdin is buffered before searching.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

- **Davide Santangelo** - [GitHub](https://github.com/davidesantangelo)

## License

BSD-2 License - see the LICENSE file for details.
