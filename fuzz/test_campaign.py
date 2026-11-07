# SPDX-License-Identifier: Apache-2.0
import copy
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
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

    def test_build_timeout_terminates_owned_group(self):
        with tempfile.TemporaryDirectory() as raw:
            pidfile=Path(raw)/'pid'
            source=('import subprocess,sys,time;from pathlib import Path;'
                    'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
                    f'Path({str(pidfile)!r}).write_text(str(p.pid));time.sleep(60)')
            with self.assertRaises(subprocess.TimeoutExpired):
                campaign.command([sys.executable,'-c',source],timeout=.3)
            if pidfile.exists():
                pid=int(pidfile.read_text())
                status=Path(f'/proc/{pid}/stat')
                if status.exists(): self.assertIn(status.read_text().split()[2],('Z','X'))


if __name__=='__main__': unittest.main()
