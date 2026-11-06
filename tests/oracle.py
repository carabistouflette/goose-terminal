#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent deterministic reference; Python integers never overflow."""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MAX = (1 << 63) - 1
MIN = -(1 << 63)
STYLES = [b'', b'\x1b[1m', b'\x1b[32m', b'\x1b[33m', b'\x1b[31m']


def escape(data):
    return b''.join(bytes([c]) if 32 <= c <= 126 and c != 92 else
                    b'\\\\' if c == 92 else f'\\x{c:02x}'.encode() for c in data)


def reference(op, color, live, final, columns, a, b, c, cells):
    if not 2 <= columns <= 512:
        return 1, b''
    if op == 0:
        if len(cells[0]) > 4096:
            return 2, b''
        style = STYLES[a] if color else b''
        return 0, style + escape(cells[0]) + (b'\x1b[0m' if style else b'') + b'\n'
    if op == 1:
        if not 1 <= a <= 16:
            return 1, b''
        if len(cells) > 1024:
            return 2, b''
        if len(cells) % a:
            return 1, b''
        rows = len(cells) // a
        if rows > 256:
            return 2, b''
        if not rows:
            return 0, b''
        if any(len(x) > 4096 for x in cells) or sum(map(len, cells)) > 65536:
            return 2, b''
        escaped = list(map(escape, cells))
        widths = [max(map(len, escaped[j::a])) for j in range(a)]
        row_width = sum(widths) + 2 * (a - 1)
        if row_width >= columns or rows * (row_width + 1) > 131072:
            return 2, b''
        lines = []
        for row in range(rows):
            lines.append(b'  '.join(escaped[row*a+j].ljust(widths[j]) if j+1 < a
                                    else escaped[row*a+j] for j in range(a)) + b'\n')
        return 0, b''.join(lines)
    if op == 2 and (b <= 0 or not 0 <= a <= b or not 1 <= c <= 256):
        return 1, b''
    if op == 3 and a < 0:
        return 1, b''
    if len(cells[0]) > 4096:
        return 2, b''
    label = escape(cells[0])
    if op == 2:
        filled = a * c // b
        body = b'[' + b'#' * filled + b'-' * (c-filled) + f'] {a}/{b} '.encode() + label
    else:
        body = (b'done ' if final else bytes([b'|/-\\'[a % 4]]) + b' ') + label
    if len(body) >= columns:
        return 2, b''
    return 0, (b'\r\x1b[2K' if live else b'') + body + (b'\n' if final or not live else b'')


def fixtures():
    rng = random.Random(0x6005E)
    cases = []
    def add(op, cells, a=0, b=1, c=8, columns=80, color=False, live=False, final=False):
        cases.append((op, color, live, final, columns, a, b, c, cells))
    for value in range(256):
        for style in range(5):
            for color in (False, True):
                add(0, [bytes([value])], a=style, color=color)
    for size in (0, 1, 4095, 4096, 4097, 65536):
        for value in (0, 27, 65, 92, 255):
            for op in (0, 2, 3):
                add(op, [bytes([value])*size])
    for width in range(1, 257):
        for total in (3, MAX):
            for step in (1, width//2, width):
                threshold = (total*step + width-1)//width
                for completed in (max(0, threshold-1), threshold, min(total, threshold+1)):
                    add(2, [b''], a=completed, b=total, c=width, columns=512)
    for total in (1, 2, 3, 100, MAX // 2, MAX-1, MAX):
        for completed in (0, 1, total//2, total-1, total):
            for width in (1, 2, 3, 20, 255, 256):
                for live in (False, True):
                    add(2, [b'job'], a=completed, b=total, c=width, columns=512, live=live, final=completed == total)
    for columns in (MIN, -1, 0, 1, 2, 7, 8, 9, 80, 512, 513, MAX):
        for op in range(4):
            add(op, [b''], a=1 if op == 1 else 0, columns=columns)
    for a in (MIN, -1, 0, 1, 16, 17, MAX):
        for count in (0, 1, 16, 256, 257, 1024, 1025):
            add(1, [b'']*count, a=a)
    for a in (MIN, -1, 0, 1, 10, MAX):
        add(3, [b'OSC\x1b]52;c;data\x07\n'], a=a, live=True, final=bool(a & 1))
        for b in (-1, 0, 1, MAX):
            for c in (MIN, -1, 0, 1, 256, 257, MAX):
                add(2, [b''], a=a, b=b, c=c)
    # Exact aggregate and row budgets; exact widths and post-escape sizing.
    for count in (16, 17):
        add(1, [b'a'*4096]*count, a=1, columns=512)
    for rows in (255, 256, 257):
        add(1, [b'x'*255, b'y'*254]*rows, a=2, columns=512)
    for _ in range(1200):
        op = rng.randrange(4)
        count = rng.randrange(65) if op == 1 else 1
        cells = [rng.randbytes(rng.randrange(65)) for _ in range(count)]
        add(op, cells, a=rng.randrange(1, 17) if op == 1 else rng.randrange(5),
            b=rng.randrange(1, 100), c=rng.randrange(1, 257), columns=rng.randrange(2, 513),
            color=bool(rng.randrange(2)), live=bool(rng.randrange(2)), final=bool(rng.randrange(2)))
    rng.shuffle(cases)
    data = bytearray()
    for case in cases:
        op, color, live, final, columns, a, b, c, cells = case
        error, expected = reference(*case)
        data.extend(struct.pack('<BBBBqqqqIIB3x', op, color, live, final, columns, a, b, c,
                                len(cells), len(expected), error))
        for cell in cells:
            data.extend(struct.pack('<I', len(cell))); data.extend(cell)
        data.extend(expected)
    return data, len(cases)


def main():
    data, count = fixtures()
    with tempfile.TemporaryDirectory(dir=ROOT / '.build', prefix='oracle-') as tmp:
        path = Path(tmp) / 'cases.bin'; path.write_bytes(data)
        for driver in sys.argv[1:]:
            result = subprocess.run([str(Path(driver).resolve()), str(path)], capture_output=True, timeout=60)
            if result.returncode or result.stdout != f'oracle cases passed: {count}\n'.encode() or result.stderr:
                raise SystemExit(f'{driver}: exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}')
            print(result.stdout.decode(), end='')
    print('seed=0x6005e; Python arbitrary-precision reference')


if __name__ == '__main__':
    main()
