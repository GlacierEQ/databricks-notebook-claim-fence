from __future__ import annotations
import unittest
from src.notebook_fence import NotebookClaimFence

class Adv(unittest.TestCase):
    def test_unknown_cell(self):
        ok, reason = NotebookClaimFence().assert_claim("x", "hello")
        self.assertFalse(ok)
        self.assertEqual(reason, "UNKNOWN_CELL")
    def test_bad_eval_receipt(self):
        f = NotebookClaimFence()
        f.record("c1", {"a": 1})
        pr = f.promote("c1", "not-eval", "owner:ada")
        self.assertFalse(pr.ok)
        self.assertEqual(pr.reason, "BAD_EVAL_RECEIPT")
    def test_promote_then_claim(self):
        f = NotebookClaimFence()
        f.record("c1", {"auc": 0.9})
        self.assertTrue(f.promote("c1", "eval:s", "owner:ada").ok)
        ok, reason = f.assert_claim("c1", "production ready")
        self.assertTrue(ok)
        self.assertIsNone(reason)

if __name__ == "__main__":
    unittest.main()
