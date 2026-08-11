import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = json.loads((ROOT / "machine" / "excellence-state.json").read_text(encoding="utf-8"))
POSITION = json.loads((ROOT / "machine" / "canonical-position.json").read_text(encoding="utf-8"))
TARGET = json.loads((ROOT / "machine" / "target-contract.json").read_text(encoding="utf-8"))
RECEIPT_PATH = ROOT / "machine" / "evolution-receipts" / "2026-08-11-policy-quorum-artifact-promotion.json"
RECEIPT = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


class EvolutionContractTests(unittest.TestCase):
    def test_consumed_cursor_is_exact_proof_bound(self):
        self.assertEqual(RECEIPT["result"], "PASS")
        self.assertEqual(RECEIPT["candidate_source_sha"], "7918388dcc2b1adc5bcaaf785db75078130c33c7")
        self.assertEqual(RECEIPT["workflow_run"], 31465174449)
        event = STATE["evolution_history"][-1]
        self.assertEqual(event["consumed_cursor"], RECEIPT["consumed_cursor"])
        self.assertEqual(event["receipt"], str(RECEIPT_PATH.relative_to(ROOT)))

    def test_next_cursor_is_consistent(self):
        expected = "next:cryptographically_authenticated_owner_evaluator_identity_external_notebook_source_attestation_and_promotion_revocation"
        self.assertEqual(STATE["evolution_cursor"], expected)
        self.assertEqual(TARGET["next_evolution"], expected)
        self.assertEqual(RECEIPT["next_cursor"], expected)
        self.assertIn("externally attest notebook source identity", POSITION["next_evolution"])
        self.assertIn("promotion revocation", POSITION["next_evolution"])

    def test_claim_ceiling_and_identity_boundaries_do_not_inflate(self):
        self.assertEqual(STATE["claim_ceiling"], "PROMOTED")
        boundary = " ".join(TARGET["nonclaims"]).lower()
        self.assertIn("no databricks affiliation", boundary)
        self.assertIn("owner and evaluator identities are not cryptographically authenticated", boundary)
        self.assertIn("promotion revocation is not implemented", boundary)


if __name__ == "__main__":
    unittest.main()
