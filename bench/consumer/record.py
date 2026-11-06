#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Paired real Honk commands; no fake compiler, network or speed threshold."""
import argparse
import csv
import io
import datetime as dt
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import pty
import random
import selectors
import signal
import struct
import subprocess
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[2]
SEED = 0x7465726D
MODES = ('never', 'plain', 'pty')
SKIP = {'.git', '.build', '.toolchain', 'target', '__pycache__', 'node_modules'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def captured(args, *, cwd=None, env=None):
    proc = subprocess.Popen([str(x) for x in args], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=180)
    except BaseException:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate(timeout=10)
        raise
    return proc.returncode, stdout, stderr


def command(args, *, cwd=None, env=None):
    code, stdout, stderr = captured(args, cwd=cwd, env=env)
    if code:
        raise RuntimeError(f'command failed ({code}): {args}\n{stdout!r}\n{stderr!r}')
    return stdout


def source_identity(root):
    files = {}
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP)
        for name in sorted(names):
            path = Path(folder)/name
            if path.suffix in ('.goose', '.c', '.h', '.build', '.toml', '.lock', '.json') or name in ('GOOSE_REVISION', 'Makefile') or path.parent == ROOT/'bench/consumer':
                files[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return dict(commit=command(['git', '-C', root, 'rev-parse', 'HEAD']).decode().strip(),
                status=command(['git', '-C', root, 'status', '--porcelain']).decode(), files=files)


def identity(honk, honk_source, goose):
    return dict(library=source_identity(ROOT), honk=source_identity(honk_source),
                honk_binary_sha256=digest(honk.read_bytes()),
                goose_binary_sha256=digest(goose.read_bytes()),
                goose_version=command([goose, 'version']).decode().strip(),
                expected_goose_revision=(ROOT/'GOOSE_REVISION').read_text().strip())


def invoke(honk, project, env, workload, mode):
    args = [str(honk), workload, '--frozen', '--progress',
            'never' if mode == 'never' else 'always' if mode == 'plain' else 'auto']
    if mode != 'pty':
        start = time.perf_counter_ns()
        code, stdout, stderr = captured(args, cwd=project, env=env)
        return code, stdout, stderr, time.perf_counter_ns()-start
    master, slave = pty.openpty()
    attrs = termios.tcgetattr(slave)
    attrs[1] &= ~termios.OPOST
    termios.tcsetattr(slave, termios.TCSANOW, attrs)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
    proc = None
    chunks = {'stdout': bytearray(), 'stderr': bytearray()}
    selector = selectors.DefaultSelector()
    try:
        start = time.perf_counter_ns()
        proc = subprocess.Popen(args, cwd=project, env=env, stdout=subprocess.PIPE, stderr=slave, start_new_session=True)
        os.close(slave); slave = -1
        for fd, name in ((proc.stdout.fileno(), 'stdout'), (master, 'stderr')):
            os.set_blocking(fd, False); selector.register(fd, selectors.EVENT_READ, name)
        deadline = time.monotonic()+180
        while selector.get_map():
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError('PTY command timeout')
            for key, _ in selector.select(min(remaining, 1)):
                try:
                    data = os.read(key.fd, 65536)
                except OSError as error:
                    if key.fd == master and error.errno == errno.EIO:
                        data = b''
                    elif error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        continue
                    else:
                        raise
                if data:
                    chunks[key.data].extend(data)
                else:
                    selector.unregister(key.fd)
        code = proc.wait(timeout=max(1, deadline-time.monotonic()))
        elapsed = time.perf_counter_ns()-start
        return code, bytes(chunks['stdout']), bytes(chunks['stderr']), elapsed
    finally:
        selector.close()
        if proc:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=10)
            proc.stdout.close()
        if slave >= 0:
            os.close(slave)
        os.close(master)


def validate(workload, mode, code, stdout, stderr, baseline):
    if code or stdout != baseline:
        raise RuntimeError(f'{workload}/{mode}: exit={code}; changed stdout={stdout!r}; stderr={stderr!r}')
    if mode == 'never':
        if stderr:
            raise RuntimeError(f'unexpected disabled presentation stderr: {stderr!r}')
        return
    summary = b'Check complete' if workload == 'check' else b'All targets passed'
    if summary not in stderr:
        raise RuntimeError(f'missing real command summary: {stderr!r}')
    if workload == 'test' and (b'1/2 test' not in stderr or b'2/2 test' not in stderr):
        raise RuntimeError(f'missing completed target progress: {stderr!r}')
    if b'\r' in stderr or b'\x1b[2K' in stderr:
        raise RuntimeError('Honk complete snapshots must not erase child diagnostics')
    if mode == 'plain' and b'\x1b' in stderr:
        raise RuntimeError('redirected progress contains ANSI')
    if mode == 'pty' and b'\x1b[32m' not in stderr:
        raise RuntimeError('PTY presentation did not exercise styled output')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--honk', type=Path, required=True)
    parser.add_argument('--honk-source', type=Path, required=True)
    parser.add_argument('--goose', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--phase-iterations', type=int, default=10000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.runs <= 100 or not 1 <= args.phase_iterations <= 10000000:
        parser.error('runs must be in 1..100 and phase-iterations in 1..10000000')
    honk, source, goose = args.honk.resolve(), args.honk_source.resolve(), args.goose.resolve()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    before = identity(honk, source, goose)
    phase_binary = output/'phases'
    phase_flags = ['-O2', '--cc', 'gcc']
    command([goose, 'build', ROOT/'bench/consumer/phases.goose', *phase_flags, '-o', phase_binary])
    phase_binary_hash = digest(phase_binary.read_bytes())
    phase_samples = []
    phase_cc = command(['gcc', '--version']).decode()
    for batch in range(args.runs):
        with open(os.devnull, 'wb') as sink:
            result = subprocess.run([str(phase_binary), str(args.phase_iterations)], stdout=sink,
                                    stderr=subprocess.PIPE, timeout=60)
        (output/f'phases-{batch:03d}.csv').write_bytes(result.stderr)
        rows = list(csv.reader(io.StringIO(result.stderr.decode())))
        if result.returncode or len(rows) != 3 or [row[0] for row in rows] != ['render', 'probe-nontty', 'write-devnull']:
            raise RuntimeError(f'phase driver failed: {result.returncode}: {result.stderr!r}')
        for name, iterations, elapsed, checksum in rows:
            if int(iterations) != args.phase_iterations or int(elapsed) <= 0 or int(checksum) <= 0:
                raise RuntimeError('invalid phase result')
            phase_samples.append(dict(batch=batch, phase=name, iterations=int(iterations),
                                      elapsed_ns=int(elapsed), checksum=int(checksum)))
    rng = random.Random(SEED)
    samples = []
    fixture_hashes = {}
    with tempfile.TemporaryDirectory(prefix='goose-terminal-consumer-') as raw:
        directory = Path(raw); project = directory/'project'
        (project/'src').mkdir(parents=True); (project/'tests').mkdir()
        (project/'src/main.goose').write_text('fn main() {}\n')
        (project/'Honk.toml').write_text('[package]\nname="consumer"\nversion="0.1.0"\nentry="src/main.goose"\n'
                                       '[toolchain]\nrevision="'+before['expected_goose_revision']+'"\n')
        for name in ('one', 'two'):
            (project/'tests'/f'{name}.goose').write_text('fn main() { print("target '+name+'"); }\n')
        env = {**os.environ, 'GOOSE': str(goose), 'HONK_HOME': str(directory/'cache'),
               'TERM': 'xterm-256color', 'NO_COLOR': ''}
        command([honk, 'fetch'], cwd=project, env=env)
        baselines = {}
        for workload in ('check', 'test'):
            code, stdout, stderr, _ = invoke(honk, project, env, workload, 'never')
            if code or stderr or (workload == 'test' and
                                 (b'target one\n' not in stdout or b'target two\n' not in stdout or
                                  b'Passed 2 test targets\n' not in stdout)):
                raise RuntimeError(f'fixture warmup failed: {code}, {stdout!r}, {stderr!r}')
            baselines[workload] = stdout
        for path in sorted(project.rglob('*')):
            if path.is_file() and (path.name in ('Honk.toml', 'Honk.lock') or path.suffix == '.goose') and '.honk' not in path.parts and 'target' not in path.parts:
                fixture_hashes[path.relative_to(project).as_posix()] = digest(path.read_bytes())
        for batch in range(args.runs):
            pairs = [(workload, mode) for workload in ('check', 'test') for mode in MODES]
            rng.shuffle(pairs)
            for index, (workload, mode) in enumerate(pairs):
                code, stdout, stderr, elapsed = invoke(honk, project, env, workload, mode)
                validate(workload, mode, code, stdout, stderr, baselines[workload])
                stem = f'{batch:03d}-{index}-{workload}-{mode}'
                (output/f'{stem}.stdout').write_bytes(stdout)
                (output/f'{stem}.stderr').write_bytes(stderr)
                sample = dict(batch=batch, order=index, workload=workload, mode=mode,
                              elapsed_ns=elapsed, exit_status=code, stdout_sha256=digest(stdout),
                              stderr_sha256=digest(stderr), stdout_bytes=len(stdout), stderr_bytes=len(stderr))
                samples.append(sample)
                with (output/'raw.jsonl').open('a') as stream:
                    stream.write(json.dumps(sample)+'\n')
    if identity(honk, source, goose) != before or digest(phase_binary.read_bytes()) != phase_binary_hash:
        raise RuntimeError('source/compiler/binary identity changed; raw samples retained, no accepted manifest')
    manifest = dict(identity=before, samples=samples, phases=phase_samples, phase_flags=phase_flags,
                    phase_c_compiler=phase_cc, phase_binary_sha256=phase_binary_hash,
                    seed=SEED, fixture_sha256=fixture_hashes,
                    timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    platform=platform.platform(), machine=platform.machine(), processor=platform.processor(),
                    cpuinfo=Path('/proc/cpuinfo').read_text() if Path('/proc/cpuinfo').exists() else None,
                    cpu_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
                    affinity_policy='not pinned; no environmental isolation',
                    build_provenance='externally supplied Honk/Goose binaries; flags are not inferred',
                    environment={'TERM': 'xterm-256color', 'NO_COLOR': '', 'GOOSE': 'supplied pinned compiler',
                                 'HONK_HOME': 'fresh private temporary cache; no credentials captured'},
                    scope='warm local invocations; includes staging, real compiler and child processes; network-free fixture')
    (output/'results.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(f'Recorded {len(samples)} real consumer samples in {output}')


if __name__ == '__main__':
    main()
