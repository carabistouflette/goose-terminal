#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Retain every raw sample; this is not a cross-language performance claim."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent


def run(args):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=180)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--goose', required=True, type=Path)
    parser.add_argument('--iterations', type=int, default=10000)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 10000000 or not 1 <= args.runs <= 100:
        parser.error('iterations/runs out of range')
    compiler = args.goose.resolve()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    binary = output / 'bench'
    flags = ['-O2', '--cc', 'gcc']
    run([str(compiler), 'build', 'bench/driver.goose', *flags, '-o', str(binary)])
    samples = []
    for batch in range(args.runs):
        raw = run([str(binary), str(args.iterations)])
        (output / f'raw-{batch}.csv').write_text(raw)
        records = list(csv.reader(io.StringIO(raw)))
        if len(records) != 14:
            raise SystemExit('incomplete benchmark')
        for name, mode, iterations, elapsed, checksum in records:
            if int(iterations) != args.iterations or int(elapsed) <= 0 or int(checksum) <= 0:
                raise SystemExit('invalid benchmark sample')
            samples.append(dict(batch=batch, workload=name, mode=mode,
                                iterations=int(iterations), elapsed_ns=int(elapsed), checksum=int(checksum)))
    files = ['terminal.goose', 'bench/driver.goose', 'bench/measure.py', 'GOOSE_REVISION']
    manifest = dict(timestamp_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    source_commit=run(['git', 'rev-parse', 'HEAD']).strip(),
                    source_status=run(['git', 'status', '--porcelain']),
                    sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
                    compiler_revision=(ROOT/'GOOSE_REVISION').read_text().strip(),
                    compiler_version=run([str(compiler), '--version']).strip(),
                    compiler_binary_sha256=hashlib.sha256(compiler.read_bytes()).hexdigest(),
                    c_compiler=run(['gcc', '--version']), flags=flags, platform=platform.platform(),
                    machine=platform.machine(), processor=platform.processor(),
                    cpuinfo=Path('/proc/cpuinfo').read_text() if Path('/proc/cpuinfo').exists() else None,
                    affinity='uncontrolled', samples=samples)
    (output/'results.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(f'Recorded {len(samples)} raw samples in {output}')


if __name__ == '__main__':
    main()
