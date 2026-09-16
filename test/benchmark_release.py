#!/usr/bin/env python3
"""Offline, repeatable release benchmark; compare identical output before timing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', default='./krep')
    parser.add_argument('--baseline', help='previous release executable')
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--size-mib', type=int, default=64)
    parser.add_argument('--output-lines', type=int, default=12000)
    parser.add_argument('--json', type=Path, help='write measurements as JSON')
    args = parser.parse_args()
    if min(args.runs, args.size_mib, args.output_lines) < 1:
        parser.error('runs, size-mib and output-lines must be positive')
    binaries = {'current': str(Path(args.binary).resolve())}
    if args.baseline:
        binaries['baseline'] = str(Path(args.baseline).resolve())
    env = dict(os.environ, LC_ALL='C')
    versions = {label: subprocess.check_output([binary, '--version'], text=True).strip()
                for label, binary in binaries.items()}
    results = []
    with tempfile.TemporaryDirectory(prefix='krep-bench-') as tmp:
        large = Path(tmp) / 'logs.txt'
        line = b'2026-09-16 INFO request=123456 needle authentication_failed user=alice duration=12ms\n'
        block = line * 8192
        with large.open('wb') as f:
            for _ in range(max(1, (args.size_mib * 1024 * 1024 + len(block) - 1) // len(block))):
                f.write(block)
        output = Path(tmp) / 'output.txt'
        output.write_bytes(line * args.output_lines)
        cases = [
            ('short literal count, 1 thread', ['-t', '1', '-c', 'needle', str(large)]),
            ('long literal count, 1 thread', ['-t', '1', '-c', 'authentication_failed', str(large)]),
            ('absent literal, 1 thread', ['-t', '1', '-c', 'authorization_denied', str(large)]),
            ('short literal count, auto threads', ['-c', 'needle', str(large)]),
            ('quiet early match', ['-q', 'needle', str(large)]),
            ('numbered output', ['-n', 'needle', str(output)]),
            ('context output', ['-C', '1', 'needle', str(output)]),
            ('JSON lines', ['--json', 'needle', str(output)]),
            ('JSON matches', ['--json', '-o', 'needle', str(output)]),
        ]
        for name, options in cases:
            # Hash output in bounded chunks, including status, to check equivalence.
            fingerprints = []
            for binary in binaries.values():
                digest = hashlib.sha256()
                with tempfile.TemporaryFile() as captured:
                    process = subprocess.run([binary, '--color=never', *options], env=env,
                                             stdout=captured, timeout=60)
                    captured.seek(0)
                    for chunk in iter(lambda: captured.read(65536), b''):
                        digest.update(chunk)
                    status = process.returncode
                if status not in (0, 1):
                    raise RuntimeError(f'{name}: exit {status}')
                fingerprints.append((status, digest.hexdigest()))
            if len(set(fingerprints)) != 1:
                raise RuntimeError(f'{name}: baseline/current output mismatch')
            timings = {label: [] for label in binaries}
            for run in range(args.runs):
                labels = list(binaries)
                if run % 2:
                    labels.reverse()
                for label in labels:
                    started = time.perf_counter()
                    result = subprocess.run([binaries[label], '--color=never', *options],
                                            env=env, stdout=subprocess.DEVNULL, timeout=60)
                    timings[label].append(time.perf_counter() - started)
                    if result.returncode != fingerprints[0][0]:
                        raise RuntimeError(f'{name}: unstable exit status')
            medians = {label: statistics.median(values) for label, values in timings.items()}
            row = {'case': name, 'median_seconds': medians, 'samples_seconds': timings,
                   'exit_status': fingerprints[0][0]}
            if 'baseline' in medians:
                row['speedup'] = medians['baseline'] / medians['current']
            results.append(row)
            comparison = f"  {row['speedup']:.2f}x" if 'speedup' in row else ''
            print(f"{name:36} {medians['current'] * 1000:9.3f} ms{comparison}", flush=True)
        report = {'platform': platform.platform(), 'machine': platform.machine(),
                  'versions': versions, 'runs': args.runs, 'dataset_bytes': large.stat().st_size,
                  'output_lines': args.output_lines, 'results': results}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
