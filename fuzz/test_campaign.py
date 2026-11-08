# SPDX-License-Identifier: Apache-2.0
import copy
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import run as campaign


class Campaign(unittest.TestCase):
    def test_seed_combinations_and_framing(self):
        seeds=campaign.corpus()
        self.assertEqual({v['op'] for v in seeds},set(range(5)))
        self.assertEqual({v['a'] for v in seeds if v['op']==0 and v['color']},set(range(1,5)))
        self.assertTrue(any(v['op']==4 and v['live'] and v['a'] for v in seeds))
        for v in seeds:
            self.assertLessEqual(len(campaign.encode([v])),campaign.MAX_BYTES)
            self.assertLessEqual(len(campaign.expected([v])),131077)

    def test_mutations_preserve_driver_schema(self):
        rng=random.Random(42); seeds=campaign.corpus()
        for _ in range(1000):
            v=campaign.mutate(rng,campaign.mutate(rng,rng.choice(seeds)))
            campaign.encode([v])

    def test_mutations_explore_without_changing_seeds(self):
        seeds=campaign.corpus(); saved=copy.deepcopy(seeds)
        rng=random.Random(42)
        for op in range(5):
            seed=next(v for v in seeds if v['op']==op)
            changed=[campaign.mutate(rng,seed) for _ in range(128)]
            self.assertTrue(any(v!=seed for v in changed),f'operation {op} never mutates')
        self.assertEqual(seeds,saved)

    def test_table_seeds_exercise_escaped_padding(self):
        for case in campaign.corpus():
            if case['op']!=1 or case['a']!=2 or len(case['cells'])!=4: continue
            cells=case['cells']
            if cells==[b'\\',b'x',b'y',b'z']:
                # The second row needs padding according to the escaped width
                # of the first column, rather than its raw byte length.
                self.assertIn(b'y  ',campaign.expected([case]))
                break
        else: self.fail('missing heterogeneous escaped-padding table seed')

    def test_relocated_compiler_has_actionable_identity_error(self):
        with patch.object(campaign,'command',side_effect=subprocess.CalledProcessError(128,['git'])):
            with self.assertRaisesRegex(ValueError,'checkout/build/goose'):
                campaign.identity(Path('/relocated/bin/goose'))

    def test_replay_rejects_invalid_driver_encoding(self):
        base=campaign.corpus()[0]
        bad=[dict(base,op=5),dict(base,a=5),dict(base,color=2),dict(base,cells=[b'x'*65537]),
             dict(base,cells=[]),dict(base,columns=1<<63),dict(base,unknown=1),
             dict(campaign.corpus()[1],cells=[b'']*1026)]
        for case in bad:
            with self.assertRaises(ValueError): campaign.encode([case])
        for cases in ([],[base]*33):
            with self.assertRaises(ValueError): campaign.encode(cases)

    def test_failure_bundle_is_case_replayable(self):
        cases=campaign.corpus()[:5]
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw); scratch=path/'scratch';scratch.mkdir()
            (scratch/'input.bin').write_bytes(campaign.encode(cases))
            campaign.failure_bundle(path,scratch,cases,dict(category='api-output-mismatch',mode='asan'))
            values=json.loads((path/'failure/cases.json').read_text())
            restored=[dict(v,cells=[bytes.fromhex(c) for c in v['cells']]) for v in values]
            self.assertEqual(campaign.encode(restored),campaign.encode(cases))
            self.assertEqual((path/'failure/expected.bin').read_bytes(),campaign.expected(cases))

    def test_startup_identity_rejection_is_reported(self):
        with tempfile.TemporaryDirectory() as raw:
            output=Path(raw)/'result'
            with patch.object(sys,'argv',['run','--goose','/absent','--output',str(output)]), patch.object(campaign.platform,'system',return_value='Linux'), patch.object(campaign,'identity',side_effect=ValueError('pin mismatch')):
                with self.assertRaises(SystemExit): campaign.main()
            self.assertEqual(json.loads((output/'results.json').read_text())['failure']['category'],'identity-rejected')

    def test_campaign_rejects_non_linux_platform(self):
        with tempfile.TemporaryDirectory() as raw:
            output=Path(raw)/'result'
            with patch.object(sys,'argv',['run','--goose','/absent','--output',str(output)]), patch.object(campaign.platform,'system',return_value='Darwin'), patch('sys.stderr'):
                with self.assertRaises(SystemExit): campaign.main()
            self.assertFalse(output.exists())

    def test_post_run_identity_error_preserves_report(self):
        with tempfile.TemporaryDirectory() as raw:
            output=Path(raw)/'result'
            def build(args):
                Path(args[-1]).write_bytes(b'driver');return b'compiled'
            def execute(binary,cases,scratch,mode):
                (scratch/'limits.json').write_text('{}');return dict(category='pass',mode=mode,cases=len(cases))
            with patch.object(sys,'argv',['run','--goose','/absent','--output',str(output),'--max-cases','5']), patch.object(campaign.platform,'system',return_value='Linux'), patch.object(campaign,'identity',side_effect=[dict(c_backends={}),ValueError('checkout dirty')]), patch.object(campaign,'command',side_effect=build), patch.object(campaign,'execute',side_effect=execute):
                with self.assertRaises(SystemExit): campaign.main()
            report=json.loads((output/'results.json').read_text())
            self.assertTrue(report['identity_drift']);self.assertIn('checkout dirty',report['identity_error'])
            self.assertEqual(report['cases'],5);self.assertEqual(report['stop_reason'],'identity-drift')

    def test_build_timeout_terminates_owned_group(self):
        with tempfile.TemporaryDirectory() as raw:
            pidfile=Path(raw)/'pid'
            source=('import subprocess,sys,time;from pathlib import Path;'
                    'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
                    f'Path({str(pidfile)!r}).write_text(str(p.pid));time.sleep(60)')
            pid=None
            terminated=False
            def read_pid():
                try: return int(pidfile.read_text())
                except (FileNotFoundError,ValueError): return None
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    campaign.command([sys.executable,'-c',source],timeout=1)
                self.assertTrue(pidfile.exists(),'the descendant must start before timeout')
                pid=read_pid()
                self.assertIsNotNone(pid,'the descendant must publish its PID before timeout')
                status=Path(f'/proc/{pid}/stat')
                # SIGKILL delivery to the group is asynchronous. Waiting for
                # its leader does not reap (or synchronize with) descendants.
                # Observe termination with a deadline, rather than treating a
                # still-scheduled dying process as a leaked live child.
                deadline=time.monotonic()+2
                while True:
                    try:
                        fields=status.read_text().rpartition(')')[2].split()
                        state=fields[0] if fields else 'unavailable'
                    except FileNotFoundError:
                        terminated=True
                        break
                    if state in ('Z','X'):
                        terminated=True
                        break
                    if time.monotonic()>=deadline:
                        self.fail(f'descendant {pid} is still live after group timeout: {state}')
                    time.sleep(.01)
            finally:
                # A broken group-kill implementation must fail the assertion
                # without leaving the test's 60-second child behind.
                if pid is None: pid=read_pid()
                if pid is not None and not terminated:
                    try: os.kill(pid,signal.SIGKILL)
                    except ProcessLookupError: pass


if __name__=='__main__': unittest.main()
