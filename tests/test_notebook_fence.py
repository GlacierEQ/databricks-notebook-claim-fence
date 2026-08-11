from __future__ import annotations
import unittest
from src.notebook_fence import (
    ArtifactState,
    ClaimTier,
    EvaluationReceipt,
    NotebookClaimFence,
    OwnerApproval,
    PromotionPolicy,
)


class FenceTests(unittest.TestCase):
    def setUp(self):
        self.policy = PromotionPolicy(
            "prod-policy-v2",
            ClaimTier.PRODUCTION,
            frozenset({"quality", "safety", "lineage"}),
            owner_quorum=2,
        )

    def record_exact(self, fence: NotebookClaimFence, cell_id: str = "c1"):
        return fence.record_artifact(
            "nb-1",
            "source-sha-123",
            cell_id,
            {"auc": 0.99, "model": "candidate"},
        )

    def proof(self, artifact_digest: str):
        evaluations = [
            EvaluationReceipt(
                "eval-1",
                artifact_digest,
                self.policy.policy_id,
                "eval-a",
                frozenset({"quality", "lineage"}),
            ),
            EvaluationReceipt(
                "eval-2",
                artifact_digest,
                self.policy.policy_id,
                "eval-b",
                frozenset({"safety"}),
            ),
        ]
        approvals = [
            OwnerApproval("owner-a", artifact_digest, self.policy.policy_id),
            OwnerApproval("owner-b", artifact_digest, self.policy.policy_id),
        ]
        return evaluations, approvals

    def test_blocks_unpromoted_production_claim(self):
        fence = NotebookClaimFence()
        self.record_exact(fence)
        ok, reason = fence.assert_claim("c1", "production model ready")
        self.assertFalse(ok)
        self.assertEqual(reason, "UNPROMOTED_PRODUCTION_CLAIM")

    def test_legacy_unbound_record_cannot_promote(self):
        fence = NotebookClaimFence()
        cell = fence.record("c1", {"auc": 0.99})
        evaluations, approvals = self.proof(cell.content_digest())
        result = fence.promote("c1", self.policy, evaluations, approvals)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "NOTEBOOK_LINEAGE_UNBOUND")
        self.assertEqual(cell.state, ArtifactState.PROVISIONAL)

    def test_policy_checks_and_unique_owner_quorum_promote_exact_artifact(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        evaluations, approvals = self.proof(cell.content_digest())
        result = fence.promote("c1", self.policy, evaluations, approvals)
        self.assertTrue(result.ok)
        self.assertEqual(result.state, ArtifactState.PROMOTED)
        self.assertEqual(result.owner_count, 2)
        self.assertEqual(len(result.promotion_fingerprint or ""), 64)
        self.assertEqual(cell.promotion_policy_id, self.policy.policy_id)
        self.assertEqual(cell.promotion_claim_tier, ClaimTier.PRODUCTION)
        self.assertEqual(len(cell.evaluation_fingerprints), 2)
        self.assertEqual(len(cell.owner_approval_fingerprints), 2)
        ok, reason = fence.assert_claim(
            "c1",
            "production model ready",
            required_policy_id=self.policy.policy_id,
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_missing_policy_specific_evaluation_check_blocks(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        evaluations = [
            EvaluationReceipt(
                "eval-1",
                cell.content_digest(),
                self.policy.policy_id,
                "eval-a",
                frozenset({"quality", "lineage"}),
            )
        ]
        _, approvals = self.proof(cell.content_digest())
        result = fence.promote("c1", self.policy, evaluations, approvals)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "EVALUATION_CHECKS_MISSING:safety")
        self.assertEqual(cell.state, ArtifactState.PROVISIONAL)

    def test_wrong_artifact_or_policy_evaluation_receipt_blocks(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        _, approvals = self.proof(cell.content_digest())
        wrong_artifact = [
            EvaluationReceipt(
                "eval-wrong-artifact",
                "f" * 64,
                self.policy.policy_id,
                "eval-a",
                self.policy.required_checks,
            )
        ]
        result = fence.promote("c1", self.policy, wrong_artifact, approvals)
        self.assertEqual(result.reason, "EVAL_ARTIFACT_MISMATCH")

        wrong_policy = [
            EvaluationReceipt(
                "eval-wrong-policy",
                cell.content_digest(),
                "other-policy",
                "eval-a",
                self.policy.required_checks,
            )
        ]
        result = fence.promote("c1", self.policy, wrong_policy, approvals)
        self.assertEqual(result.reason, "EVAL_POLICY_MISMATCH")
        self.assertEqual(cell.state, ArtifactState.PROVISIONAL)

    def test_duplicate_evaluation_receipt_identity_blocks(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        receipt = EvaluationReceipt(
            "eval-1",
            cell.content_digest(),
            self.policy.policy_id,
            "eval-a",
            self.policy.required_checks,
        )
        _, approvals = self.proof(cell.content_digest())
        result = fence.promote("c1", self.policy, [receipt, receipt], approvals)
        self.assertEqual(result.reason, "DUPLICATE_EVAL_RECEIPT")

    def test_duplicate_owner_identity_does_not_satisfy_quorum(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        evaluations, _ = self.proof(cell.content_digest())
        same_owner = OwnerApproval(
            "owner-a", cell.content_digest(), self.policy.policy_id
        )
        result = fence.promote(
            "c1", self.policy, evaluations, [same_owner, same_owner]
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "OWNER_QUORUM_UNMET")
        self.assertEqual(result.owner_count, 1)

    def test_owner_artifact_and_policy_mismatch_block(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        evaluations, _ = self.proof(cell.content_digest())
        wrong_artifact = [
            OwnerApproval("owner-a", "f" * 64, self.policy.policy_id),
            OwnerApproval("owner-b", cell.content_digest(), self.policy.policy_id),
        ]
        result = fence.promote("c1", self.policy, evaluations, wrong_artifact)
        self.assertEqual(result.reason, "OWNER_ARTIFACT_MISMATCH")

        wrong_policy = [
            OwnerApproval("owner-a", cell.content_digest(), "other-policy"),
            OwnerApproval("owner-b", cell.content_digest(), self.policy.policy_id),
        ]
        result = fence.promote("c1", self.policy, evaluations, wrong_policy)
        self.assertEqual(result.reason, "OWNER_POLICY_MISMATCH")

    def test_bounded_policy_cannot_support_production_claim(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        bounded = PromotionPolicy(
            "bounded-v1",
            ClaimTier.BOUNDED,
            frozenset({"quality"}),
            owner_quorum=1,
        )
        evaluations = [
            EvaluationReceipt(
                "eval-bounded",
                cell.content_digest(),
                bounded.policy_id,
                "eval-a",
                frozenset({"quality"}),
            )
        ]
        approvals = [
            OwnerApproval("owner-a", cell.content_digest(), bounded.policy_id)
        ]
        result = fence.promote("c1", bounded, evaluations, approvals)
        self.assertTrue(result.ok)
        ok, reason = fence.assert_claim("c1", "production model ready")
        self.assertFalse(ok)
        self.assertEqual(reason, "NONPRODUCTION_POLICY_CEILING")
        ok, reason = fence.assert_claim("c1", "bounded validation result")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_cell_identity_is_one_shot_but_exact_rerecord_is_idempotent(self):
        fence = NotebookClaimFence()
        first = self.record_exact(fence)
        second = self.record_exact(fence)
        self.assertIs(first, second)
        with self.assertRaisesRegex(ValueError, "CELL_ID_REBOUND"):
            fence.record_artifact(
                "nb-1",
                "source-sha-123",
                "c1",
                {"auc": 0.5, "model": "changed"},
            )
        with self.assertRaisesRegex(ValueError, "CELL_ID_REBOUND"):
            fence.record_artifact(
                "nb-1",
                "different-source-sha",
                "c1",
                {"auc": 0.99, "model": "candidate"},
            )

    def test_exact_promotion_replay_is_idempotent_but_different_proof_cannot_rebind(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        evaluations, approvals = self.proof(cell.content_digest())
        first = fence.promote("c1", self.policy, evaluations, approvals)
        second = fence.promote(
            "c1", self.policy, list(reversed(evaluations)), list(reversed(approvals))
        )
        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertEqual(first.promotion_fingerprint, second.promotion_fingerprint)

        changed_evidence = [
            EvaluationReceipt(
                "eval-different",
                cell.content_digest(),
                self.policy.policy_id,
                "eval-a",
                self.policy.required_checks,
            )
        ]
        rebound = fence.promote("c1", self.policy, changed_evidence, approvals)
        self.assertFalse(rebound.ok)
        self.assertEqual(rebound.reason, "PROMOTION_ALREADY_BOUND")
        self.assertEqual(
            rebound.promotion_fingerprint, first.promotion_fingerprint
        )

    def test_policy_specific_claim_assertion_fails_closed(self):
        fence = NotebookClaimFence()
        cell = self.record_exact(fence)
        evaluations, approvals = self.proof(cell.content_digest())
        self.assertTrue(fence.promote("c1", self.policy, evaluations, approvals).ok)
        ok, reason = fence.assert_claim(
            "c1", "production model ready", required_policy_id="other-policy"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "PROMOTION_POLICY_MISMATCH")

    def test_invalid_quorum_fails_policy_construction(self):
        with self.assertRaises(ValueError):
            PromotionPolicy(
                "bad", ClaimTier.PRODUCTION, frozenset({"quality"}), 0
            )


if __name__ == "__main__":
    unittest.main()
