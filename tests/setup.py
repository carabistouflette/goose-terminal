#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise bootstrap trust guards with fake Git/CMake; no network or builds."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def english_locale():
    result = subprocess.run(['locale', '-a'], capture_output=True, text=True, check=True)
    return next((name for name in result.stdout.splitlines()
                 if name.lower().replace('-', '').replace('.', '') == 'en_usutf8'), None)


class Setup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='terminal-setup-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'scripts').mkdir(); (self.root/'tools').mkdir()
        (self.root/'.toolchain/goose/.git').mkdir(parents=True)
        self.script = self.root/'scripts/setup-goose.sh'
        shutil.copyfile(ROOT/'scripts/setup-goose.sh', self.script)
        (self.root/'GOOSE_REVISION').write_text('a'*40+'\n')
        self.log = self.root/'calls.jsonl'
        self.marker = self.root/'checked-out'
        self.bash_env = self.root/'bash-env'
        # Bash <=4.3 uses locale-sensitive glob ranges by default; explicitly
        # disable newer Bash's ASCII-range default to exercise that behavior.
        self.bash_env.write_text('shopt -u globasciiranges 2>/dev/null || true\n')
        common = ('#!'+sys.executable+'\nimport json,os,sys\nfrom pathlib import Path\n'
                  'with Path(os.environ["SETUP_TEST_LOG"]).open("a") as out:\n'
                  ' out.write(json.dumps({"tool":Path(sys.argv[0]).name,"args":sys.argv[1:],"locale":os.environ.get("LC_ALL")})+"\\n")\n')
        git = self.root/'tools/git'
        git.write_text(common+'''
args=sys.argv[1:]
if "ls-files" in args:
    flag=os.environ.get("SETUP_TEST_FLAG","H")
    if Path(os.environ["SETUP_TEST_MARKER"]).exists():
        flag=os.environ.get("SETUP_TEST_AFTER_FLAG",flag)
    print(flag+" compiler.goose")
elif "status" in args:
    print(os.environ.get("SETUP_TEST_DIRTY",""),end="")
elif "checkout" in args:
    Path(os.environ["SETUP_TEST_MARKER"]).touch()
''')
        git.chmod(0o755)
        cmake = self.root/'tools/cmake'; cmake.write_text(common); cmake.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.root/'tools')+os.pathsep+os.environ['PATH'],
                    'BASH_ENV': str(self.bash_env), 'SETUP_TEST_LOG': str(self.log),
                    'SETUP_TEST_MARKER': str(self.marker), 'LC_ALL': 'C'}

    def execute(self, **env):
        result = subprocess.run(['bash', str(self.script)], cwd=self.root,
                                env={**self.env, **env}, capture_output=True, text=True, timeout=10)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def test_plain_h_is_accepted_in_non_ascii_collation(self):
        locale = english_locale()
        if locale is None:
            self.skipTest('English UTF-8 locale unavailable')
        result, calls = self.execute(LC_ALL=locale)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(call['tool'] == 'cmake' for call in calls), 2)
        self.assertTrue(all(call['locale'] == 'C' for call in calls))

    def test_assume_unchanged_and_skip_worktree_are_rejected(self):
        for flag in ('h', 'S'):
            with self.subTest(flag=flag):
                result, calls = self.execute(SETUP_TEST_FLAG=flag)
                self.assertEqual(result.returncode, 1)
                self.assertIn('Compiler index hides source checks', result.stderr)
                self.assertFalse(any(call['tool'] == 'cmake' for call in calls))

    def test_post_checkout_index_is_checked(self):
        result, calls = self.execute(SETUP_TEST_AFTER_FLAG='h')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Compiler index hides source checks', result.stderr)
        self.assertTrue(any('checkout' in call['args'] for call in calls))
        self.assertFalse(any(call['tool'] == 'cmake' for call in calls))

    def test_dirty_source_is_rejected(self):
        result, calls = self.execute(SETUP_TEST_DIRTY=' M compiler.goose\n')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Compiler source is modified', result.stderr)
        self.assertFalse(any(call['tool'] == 'cmake' for call in calls))

    def test_pin_must_be_full_lowercase_sha(self):
        for pin in ('B'*40, 'a'*39, 'a'*41, 'not-a-commit'):
            with self.subTest(pin=pin):
                (self.root/'GOOSE_REVISION').write_text(pin+'\n')
                result, calls = self.execute()
                self.assertEqual(result.returncode, 1)
                self.assertIn('full lowercase 40-character commit hash', result.stderr)
                self.assertFalse(calls)


if __name__ == '__main__':
    unittest.main()
