#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Real PTY and redirected-output checks for the optional adapter."""
import errno
import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios

DRIVER = os.path.abspath(sys.argv[1])
ENV = {**os.environ, 'TERM': 'xterm-256color', 'NO_COLOR': ''}


def size(fd, columns):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 24, columns, 0, 0))


def drain(fd):
    data = b''
    while select.select([fd], [], [], 0.1)[0]:
        try:
            part = os.read(fd, 65536)
        except OSError as error:
            if error.errno == errno.EIO:
                break
            raise
        if not part:
            break
        data += part
    return data


def probe(columns, **env):
    master, slave = pty.openpty()
    try:
        size(slave, columns)
        proc = subprocess.run([DRIVER, 'probe'], stdout=slave, stderr=subprocess.PIPE,
                              env={**ENV, **env}, timeout=10)
        if proc.returncode or proc.stderr:
            raise AssertionError(proc.stderr)
        return drain(master).strip().split()
    finally:
        os.close(master); os.close(slave)


assert probe(80) == [b'true', b'true', b'true', b'80', b'0']
assert probe(120) == [b'true', b'true', b'true', b'120', b'0']
assert probe(1) == [b'true', b'true', b'false', b'80', b'0']
assert probe(513) == [b'true', b'true', b'false', b'80', b'0']
assert probe(80, NO_COLOR='1') == [b'true', b'false', b'true', b'80', b'0']
assert probe(80, TERM='dumb') == [b'true', b'false', b'false', b'80', b'0']
assert probe(80, TERM='') == [b'true', b'false', b'false', b'80', b'0']
missing_env = dict(ENV); missing_env.pop('TERM', None)
master, slave = pty.openpty()
try:
    size(slave, 80)
    proc = subprocess.run([DRIVER, 'probe'], stdout=slave, stderr=subprocess.PIPE, env=missing_env, timeout=10)
    assert not proc.returncode and not proc.stderr
    assert drain(master).strip().split() == [b'true', b'false', b'false', b'80', b'0']
finally:
    os.close(master); os.close(slave)
for mode in ('probe', 'invalid'):
    proc = subprocess.run([DRIVER, mode], capture_output=True, env=ENV, timeout=10)
    assert not proc.returncode and not proc.stderr
    if mode == 'probe':
        assert proc.stdout == b'false false false 80 0\n'
# Serialize application updates; test shrink fallback and controlled cancellation.
master, slave = pty.openpty()
proc = None
try:
    size(slave, 80)
    proc = subprocess.Popen([DRIVER, 'session'], stdin=subprocess.PIPE, stdout=slave,
                            stderr=subprocess.PIPE, env=ENV)
    def update(command):
        proc.stdin.write(command+b'\n'); proc.stdin.flush()
        assert select.select([proc.stderr], [], [], 10)[0]
        assert proc.stderr.readline() == b'ack\n'
        return drain(master)
    assert update(b'start') == b'\r\x1b[2K| working'
    size(slave, 4)
    assert update(b'update') == b'\r\x1b[2K\r\n'
    size(slave, 100)
    assert update(b'start') == b'\r\x1b[2K| working'
    assert update(b'cancel') == b'\r\x1b[2Kdone cancelled\r\n'
    assert update(b'finish') == b'\r\x1b[2Kdone working\r\n'
    proc.stdin.close(); assert proc.wait(timeout=10) == 0
finally:
    if proc and proc.poll() is None:
        proc.kill(); proc.wait()
    os.close(master); os.close(slave)
print('POSIX adapter: PTY policies, redirect, resize and cancellation passed')
