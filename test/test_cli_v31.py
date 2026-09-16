#!/usr/bin/env python3
"""Independent CLI regression checks for the 3.1 search and output paths."""
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile

BIN = str(Path(os.environ.get('KREP_BIN', './krep')).resolve())
ENV = dict(os.environ, LC_ALL='C')
CHECKS = 0


def run(args, data=None):
    global CHECKS
    result = subprocess.run([BIN, '--color=never', *args], input=data,
                            capture_output=True, env=ENV, timeout=15)
    CHECKS += 1
    assert result.returncode in (0, 1), (args, result.returncode, result.stderr)
    assert not result.stderr, (args, result.stderr)
    return result


def positions(line, pattern, whole_word=False, nonoverlap=False):
    result = []
    start = 0
    word = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
    while True:
        start = line.find(pattern, start)
        if start < 0:
            return result
        end = start + len(pattern)
        valid = not whole_word or ((not start or line[start - 1] not in word) and
                                    (end == len(line) or line[end] not in word))
        if valid:
            result.append((start, end))
        start += len(pattern) if valid and nonoverlap else 1


def check_fixture(path, data, pattern, whole_word=False):
    path.write_bytes(data)
    lines = data.split(b'\n')
    if data.endswith(b'\n'):
        lines.pop()
    spans = [positions(line, pattern, whole_word) for line in lines]
    selected = [i for i, matches in enumerate(spans) if matches]
    flags = ['-w'] if whole_word else []
    target = [pattern.decode(), str(path)]
    status = 0 if selected else 1
    for extra in ([], ['--no-simd'], ['--algo=bm'], ['--algo=kmp'], ['--algo=two']):
        result = run(['-c', *extra, *flags, *target])
        assert result.returncode == status
        assert result.stdout == f'{path}:{len(selected)}\n'.encode(), (pattern, extra, result.stdout, selected)
    result = run(['-n', *flags, *target])
    expected = b''.join(f'{path}:{i + 1}:'.encode() + lines[i] + b'\n' for i in selected)
    assert result.stdout == expected, ('numbered', pattern, result.stdout, expected)
    result = run(['--json', *flags, *target])
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(records) == len(selected)
    offsets = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line) + 1
    for record, i in zip(records, selected):
        assert record == {
            'type': 'line', 'path': str(path), 'line_number': i + 1,
            'byte_start': offsets[i], 'byte_end': offsets[i] + len(lines[i]),
            'text': lines[i].decode(),
            'matches': [{'column_start': a + 1, 'column_end': b + 1,
                         'byte_start': offsets[i] + a, 'byte_end': offsets[i] + b}
                        for a, b in spans[i]],
        }, (pattern, record, spans[i])
    result = run(['--json', '-o', *flags, *target])
    records = [json.loads(line) for line in result.stdout.splitlines()]
    expected = []
    for i, line in enumerate(lines):
        for a, b in positions(line, pattern, whole_word, nonoverlap=True):
            expected.append({'type': 'match', 'path': str(path), 'line_number': i + 1,
                             'byte_start': offsets[i] + a, 'byte_end': offsets[i] + b,
                             'column_start': a + 1, 'column_end': b + 1,
                             'match': pattern.decode()})
    assert records == expected, ('JSON matches', pattern, records, expected)


def main():
    rng = random.Random(310)
    with tempfile.TemporaryDirectory(prefix='krep-cli-v31-') as tmp:
        path = Path(tmp) / 'fixture.txt'
        for length in (2, 3, 4, 8, 9, 16, 17, 31, 32, 33, 63, 64):
            for repetition in range(3):
                pattern = bytes(rng.choice(b'abc') for _ in range(length))
                lines = []
                for i in range(25):
                    line = bytes(rng.choice(b'abc xyz_ ') for _ in range(rng.randrange(100)))
                    if i % 3 == 0:
                        line += b' ' + pattern + b' ' + pattern + b'!'
                    lines.append(line)
                data = b'\n'.join(lines) + (b'\n' if repetition % 2 else b'')
                check_fixture(path, data, pattern, whole_word=bool(repetition % 2))
        for pattern in (b'aa', b'aba', b'abcabcabc', b' '):
            check_fixture(path, b'\n' + pattern * 40 + b'\n\n' + pattern * 2, pattern)

        # Sparse numbered/context records: blank lines, merged and separate blocks.
        data = b'zero\n\nneedle\nthree\nneedle\nfive\nsix\nseven\nneedle\nlast'
        path.write_bytes(data)
        result = run(['-C', '1', 'needle', str(path)])
        expected = ''.join(f'{path}{sep}{n}{sep}{line}\n' if n else '--\n'
                           for n, sep, line in [(2, '-', ''), (3, ':', 'needle'),
                            (4, '-', 'three'), (5, ':', 'needle'), (6, '-', 'five'),
                            (0, '', ''), (8, '-', 'seven'), (9, ':', 'needle'), (10, '-', 'last')])
        assert result.stdout.decode() == expected, (result.stdout, expected)
        for pattern, expected_status in [('needle', 0), ('absent', 1)]:
            for mode in ('-q', '-l', '-L'):
                result = run([mode, pattern, str(path)])
                assert result.returncode == expected_status
                emitted = (mode == '-l' and expected_status == 0) or (mode == '-L' and expected_status == 1)
                assert result.stdout == (f'{path}\n'.encode() if emitted else b'')
                result = run([mode, pattern], data=data)
                assert result.returncode == expected_status and result.stdout == b''
            result = run(['-q', '-s', pattern, data.decode()])
            assert result.returncode == expected_status and result.stdout == b''
        for options in ([], ['-E'], ['-e', 'absent']):
            result = run(['-q', *options, '-e', 'needle', str(path)])
            assert result.returncode == 0 and result.stdout == b''
        result = run(['-q', '-m', '0', 'needle', str(path)])
        assert result.returncode == 1 and result.stdout == b''

        # Match output ordering for overlapping multi-pattern input from stdin.
        data = b'abc\n\nabcabc\n'
        result = run(['--json', '-e', 'b', '-e', 'abc'], data=data)
        records = [json.loads(line) for line in result.stdout.splitlines()]
        assert [r['line_number'] for r in records] == [1, 3]
        assert [m['byte_start'] for r in records for m in r['matches']] == [0, 1, 5, 6, 8, 9]

        # Cross file chunks and mmap boundaries with sparse and dense matches.
        large = (b'padding ' * 131071 + b' needle needle\n') * 10 + b'needle'
        path.write_bytes(large)
        for threads in ('1', '2', '4', None):
            thread_flags = ['-t', threads] if threads else []
            for flags in ([], ['-w']):
                result = run([*thread_flags, '-c', *flags, 'needle', str(path)])
                assert result.stdout == f'{path}:11\n'.encode()
                result = run([*thread_flags, '-c', '-m', '3', *flags, 'needle', str(path)])
                assert result.stdout == f'{path}:3\n'.encode()
            result = run([*thread_flags, '--json', '-o', 'needle', str(path)])
            records = [json.loads(line) for line in result.stdout.splitlines()]
            assert len(records) == 21
            assert [r['line_number'] for r in records] == [n for n in range(1, 11) for _ in range(2)] + [11]

        # Word and non-overlap state must survive an exact chunk boundary.
        boundary = 2 * 1024 * 1024
        data = bytearray(b' ' * (boundary * 2))
        data[boundary - 1:boundary + 7] = b'xneedle '
        path.write_bytes(data)
        for threads in ('1', '2'):
            result = run(['-t', threads, '-w', '--json', 'needle', str(path)])
            assert result.returncode == 1 and result.stdout == b''
        data[boundary - 2:boundary + 10] = b'aaaaaaaaaaaa'
        path.write_bytes(data)
        outputs = [run(['-t', threads, '--json', '-o', 'aaa', str(path)]).stdout
                   for threads in ('1', '2')]
        assert outputs[0] == outputs[1]
        assert len(outputs[0].splitlines()) == 4

        # Quiet recursion must stop at the first match; stats reveal visited files.
        repo = Path(tmp) / 'tree'
        repo.mkdir()
        for i in range(20):
            (repo / f'{i}.txt').write_text('needle\n' * 10)
        result = subprocess.run([BIN, '-rq', '--stats', 'needle', str(repo)],
                                capture_output=True, timeout=15, env=ENV)
        assert result.returncode == 0 and result.stdout == b''
        assert b'files=1 matched=1' in result.stderr, result.stderr
    print(f'krep CLI 3.1 regression tests passed ({CHECKS} subprocess checks)')


if __name__ == '__main__':
    main()
