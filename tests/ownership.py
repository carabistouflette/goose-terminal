#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Positive control plus compiler rejection of each input/output alias form."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
compiler = str(Path(sys.argv[1]).resolve())
calls = {
    'line': 'terminal::line(caps, terminal::Style.Plain, input, out);',
    'spinner': 'terminal::spinner(caps, 0, input, false, out);',
    'progress': 'terminal::progress(caps, 0, 1, 8, input, false, out);',
    'table': 'let cells = [terminal::Cell { bytes: input }]; terminal::table(caps, cells, 1, out);',
}
with tempfile.TemporaryDirectory(dir=root / '.build', prefix='ownership-') as tmp:
    for alias in (False, True):
        for name, call in calls.items():
            source = Path(tmp) / f'{name}-{alias}.goose'
            source.write_text('import terminal from "../.."; import std; fn main() { '
                              'let caps = terminal::Capabilities { .. }; var out = str("payload"); '
                              + ('let input: const u8[:] = out; ' if alias else 'let input = "payload"; ')
                              + call + ' }\n')
            result = subprocess.run([compiler, 'check', str(source)], capture_output=True, text=True, timeout=30)
            diagnostics = result.stdout + result.stderr
            if not alias and result.returncode:
                raise SystemExit(f'{name}: valid control rejected\n{diagnostics}')
            if alias and (result.returncode != 1 or not any(x in diagnostics for x in ('cannot clear', 'shrinks out'))):
                raise SystemExit(f'{name}: wrong alias rejection\n{diagnostics}')
    print('ownership: four controls accepted; four aliases rejected')
