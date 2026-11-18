"""WP-S3: phrase suggestions flag collisions, strip generic verbs and never write config."""
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.suggest_phrases import candidates, existing_phrases, suggest

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = [ROOT / f"config/skill_launcher/{m}.diagnostics.json" for m in ("live", "replay")]


def by_phrase(rows):
    return {r["phrase"]: r["collides_with"] for r in rows}


class SuggestPhrasesTests(unittest.TestCase):
    def test_generic_lead_verb_is_not_suggested_and_own_phrases_do_not_collide(self):
        rows = by_phrase(suggest(["B04"])[0]["candidates"])
        self.assertFalse(any(p.split()[0] in ("danh", "gia") for p in rows), rows)
        self.assertEqual(rows["rssi"], [])          # B04 already owns `rssi`
        self.assertIn("rssi snr", rows)

    def test_shared_word_sequences_are_flagged_with_their_owner(self):
        owners = {"chat luong mang": ["intent:laptop.internet_probe"], "dnsx": ["intent:laptop.dns"]}
        rows = by_phrase(candidates("Chất lượng liên kết", owners, "skill:X"))
        self.assertEqual(rows["chat luong"], ["intent:laptop.internet_probe"])
        self.assertEqual(rows["lien ket"], [])
        # Word boundaries: "dnsxy" must not collide with "dnsx"; the same word does.
        self.assertEqual(by_phrase(candidates("Kiểm tra dnsxy", owners, "skill:X"))["dnsxy"], [])
        self.assertEqual(by_phrase(candidates("Kiểm tra dnsx", owners, "skill:X"))["dnsx"],
                         ["intent:laptop.dns"])
        # Single words under 4 characters are never suggested (too broad).
        self.assertNotIn("dns", by_phrase(candidates("Kiểm tra dns", owners, "skill:X")))

    def test_real_collision_with_existing_intent_is_reported(self):
        owners = existing_phrases()
        self.assertTrue(any(o.startswith("intent:") for o in owners["tin hieu"]))
        rows = by_phrase(candidates("Tín hiệu và nhiễu", owners, "skill:X"))
        self.assertTrue(rows["tin hieu"])

    def test_deterministic_unique_and_stoplist_applied(self):
        first = suggest(["G03"])
        self.assertEqual(first, suggest(["G03"]))
        phrases = [c["phrase"] for c in first[0]["candidates"]]
        self.assertEqual(len(phrases), len(set(phrases)))
        for phrase in phrases:
            words = phrase.split()
            self.assertNotIn(words[0], ("co", "va", "la"))
            self.assertNotIn(words[-1], ("co", "va", "la"))

    def test_unknown_skill_fails_and_config_is_never_written(self):
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in CONFIGS if p.exists()]
        with self.assertRaises(KeyError):
            suggest(["ZZ99"])
        bad = subprocess.run([sys.executable, "-m", "scripts.suggest_phrases", "ZZ99"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        ok = subprocess.run([sys.executable, "-m", "scripts.suggest_phrases", "B04"],
                            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in CONFIGS if p.exists()])


if __name__ == "__main__":
    unittest.main()
