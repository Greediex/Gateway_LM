"""Run the actual frontend rendering functions with the small Node DOM harness."""
from pathlib import Path
import shutil
import subprocess
import unittest


class ChatPresentationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend verification')
    def test_measurement_badges_and_collapsed_technical_details(self):
        root=Path(__file__).resolve().parents[2]
        result=subprocess.run(['node',str(root/'scripts/check_chat_presentation.cjs')],
                              capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
