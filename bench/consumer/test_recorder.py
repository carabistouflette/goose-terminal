# SPDX-License-Identifier: Apache-2.0
"""Regression checks for the recorder's output acceptance contract."""
import unittest
from unittest import mock
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import record


class Acceptance(unittest.TestCase):
    def test_valid_combinations(self):
        for workload in ('check', 'test'):
            summary = b'Check complete' if workload == 'check' else b'All targets passed'
            progress = b'1/2 test\n2/2 test\n' if workload == 'test' else b''
            record.validate(workload, 'never', 0, b'stable', b'', b'stable')
            record.validate(workload, 'plain', 0, b'stable', progress+summary+b'\n', b'stable')
            record.validate(workload, 'pty', 0, b'stable', progress+b'\x1b[32m'+summary+b'\x1b[0m\n', b'stable')

    def test_rejects_nonzero_exit_and_changed_stdout(self):
        for code, stdout in ((1, b'stable'), (0, b'changed')):
            with self.assertRaises(RuntimeError):
                record.validate('check', 'never', code, stdout, b'', b'stable')

    def test_rejects_missing_progress_and_summary(self):
        for stderr in (b'All targets passed\n', b'1/2 test\nAll targets passed\n', b'1/2 test\n2/2 test\n'):
            with self.assertRaises(RuntimeError):
                record.validate('test', 'plain', 0, b'', stderr, b'')

    def test_rejects_terminal_controls_in_redirected_output(self):
        for stderr in (b'\x1b[32mCheck complete\n', b'Check complete\r\n', b'\x1b[2KCheck complete\n'):
            with self.assertRaises(RuntimeError):
                record.validate('check', 'plain', 0, b'', stderr, b'')

    def test_requires_actual_styled_pty_path(self):
        with self.assertRaises(RuntimeError):
            record.validate('check', 'pty', 0, b'', b'Check complete\n', b'')
        with self.assertRaises(RuntimeError):
            record.validate('check', 'never', 0, b'', b'unexpected', b'')


class Cleanup(unittest.TestCase):
    @unittest.skipUnless(Path('/proc').is_dir(), 'Linux process-state assertion')
    def test_exited_leader_with_descendant_held_pipes_is_cleaned(self):
        with tempfile.TemporaryDirectory(prefix='consumer-cleanup-') as raw:
            root = Path(raw); pid_file = root/'child.pid'; launcher = root/'honk'
            launcher.write_text('#!'+sys.executable+'\n'
                                'import os,subprocess,sys\n'
                                'from pathlib import Path\n'
                                'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\n'
                                'Path(os.environ["PID_FILE"]).write_text(str(child.pid))\n')
            launcher.chmod(0o755)
            child = None
            try:
                with mock.patch.object(record, 'COMMAND_TIMEOUT', 0.3):
                    with self.assertRaisesRegex(TimeoutError, 'PTY command timeout'):
                        record.invoke(launcher, root, {**os.environ, 'PID_FILE': str(pid_file)}, 'check', 'pty')
                child = int(pid_file.read_text())
                deadline = time.monotonic()+3
                while time.monotonic() < deadline:
                    try:
                        state = (Path('/proc')/str(child)/'stat').read_text().split(') ', 1)[1].split()[0]
                    except FileNotFoundError:
                        break
                    if state == 'Z':
                        break
                    time.sleep(0.01)
                else:
                    self.fail('descendant retained after its leader exited')
            finally:
                if child is None and pid_file.exists():
                    child = int(pid_file.read_text())
                if child is not None:
                    try:
                        os.kill(child, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == '__main__':
    unittest.main()
