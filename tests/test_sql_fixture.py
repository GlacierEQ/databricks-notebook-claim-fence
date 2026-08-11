from __future__ import annotations
import unittest
from pathlib import Path

SQL = Path(__file__).resolve().parents[1] / "sql" / "artifacts.sql"


class SQLFixtureTests(unittest.TestCase):
    def test_promotion_evidence_is_normalized_and_truth_bounded(self):
        text = SQL.read_text(encoding="utf-8")
        for required in (
            "PROVISIONAL",
            "PROMOTED",
            "notebook_source_sha",
            "lineage_fingerprint",
            "promotion_policies",
            "promotion_policy_checks",
            "artifact_evaluation_receipts",
            "artifact_evaluation_checks",
            "artifact_owner_approvals",
            "COUNT(DISTINCT owner_id)",
            "PRODUCTION-tier policy",
        ):
            self.assertIn(required, text)
        self.assertNotIn("eval_receipt LIKE 'eval:%'", text)
        self.assertNotIn("owner_sign", text)


if __name__ == "__main__":
    unittest.main()
