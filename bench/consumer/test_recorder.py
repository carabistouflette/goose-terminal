# SPDX-License-Identifier: Apache-2.0
"""Regression checks for the recorder's output acceptance contract."""
import unittest
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


if __name__ == '__main__':
    unittest.main()
