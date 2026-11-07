#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the same native implementation with test-only portable syscall shims."""
import argparse
import os
from pathlib import Path
import platform
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    parser.add_argument('--sanitize', action='store_true')
    args = parser.parse_args()
    output = ROOT / '.build' / ('native-sanitize' if args.sanitize else 'native-test')
    output.parent.mkdir(exist_ok=True)
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-pthread']
    if args.sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
        if platform.system() == 'Linux':
            flags += ['-fno-pie', '-no-pie']
    subprocess.run([*shlex.split(args.cc), *flags, str(ROOT/'tests/native.c'), '-o', str(output)],
                   cwd=ROOT, check=True, timeout=120)
    subprocess.run([str(output)], cwd=ROOT, check=True, timeout=30)


if __name__ == '__main__':
    main()
