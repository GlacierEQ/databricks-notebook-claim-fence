
from __future__ import annotations
import unittest
from src.notebook_fence import NotebookClaimFence

class FenceTests(unittest.TestCase):
    def test_blocks_unpromoted_production_claim(self):
        f = NotebookClaimFence()
        f.record("c1", {"auc": 0.99})
        ok, reason = f.assert_claim("c1", "production model ready")
        self.assertFalse(ok)
        self.assertEqual(reason, "UNPROMOTED_PRODUCTION_CLAIM")

    def test_promote_then_claim(self):
        f = NotebookClaimFence()
        f.record("c1", {"auc": 0.99})
        pr = f.promote("c1", "eval:suite-v1", "owner:ada")
        self.assertTrue(pr.ok)
        ok, reason = f.assert_claim("c1", "production model ready")
        self.assertTrue(ok)

if __name__ == "__main__":
    unittest.main()
