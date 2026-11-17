"""CI checks the imported pack without invoking Ollama or its generator."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class Eval1000PackTests(unittest.TestCase):
    def test_frozen_pack_validation_and_offline_scorer_contracts(self):
        root=Path(__file__).resolve().parents[1]
        env={**os.environ,'PYTHONPATH':str(root)}
        valid=subprocess.run([sys.executable,'benchmarks/eval1000/benchmark.py','--mode','validate'],
                             cwd=root,env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(valid.returncode,0,valid.stdout+valid.stderr)
        data=json.loads(valid.stdout)
        self.assertEqual((data['cases'],data['turns'],data['catalog_skill_ids']),(1000,1017,120))
        tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','benchmarks/eval1000/tests','-v'],
                             cwd=root,env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(tests.returncode,0,tests.stdout+tests.stderr)
