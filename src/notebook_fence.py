"""Notebook claim fence — content-bound artifact promotion with policy/quorum authority."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(obj: object) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def _token(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name)
    return value


def _string_set(name: str, values: Iterable[str]) -> frozenset[str]:
    try:
        result = frozenset(values)
    except TypeError as exc:
        raise ValueError(name) from exc
    if not result:
        raise ValueError(name)
    for value in result:
        _token(name, value)
    return result


class ArtifactState(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"


class ClaimTier(str, Enum):
    BOUNDED = "BOUNDED"
    PRODUCTION = "PRODUCTION"


@dataclass(frozen=True)
class NotebookLineage:
    notebook_id: str
    notebook_source_sha: str
    cell_id: str
    payload_digest: str
    lineage_mode: str = "EXACT_SOURCE"

    def __post_init__(self) -> None:
        for name in ("notebook_id", "notebook_source_sha", "cell_id", "payload_digest", "lineage_mode"):
            _token(name, getattr(self, name))

    def fingerprint(self) -> str:
        return digest(
            {
                "notebook_id": self.notebook_id,
                "notebook_source_sha": self.notebook_source_sha,
                "cell_id": self.cell_id,
                "payload_digest": self.payload_digest,
                "lineage_mode": self.lineage_mode,
            }
        )


@dataclass(frozen=True)
class PromotionPolicy:
    policy_id: str
    claim_tier: ClaimTier
    required_checks: frozenset[str]
    owner_quorum: int

    def __post_init__(self) -> None:
        _token("policy_id", self.policy_id)
        if not isinstance(self.claim_tier, ClaimTier):
            raise TypeError("claim_tier")
        object.__setattr__(self, "required_checks", _string_set("required_check", self.required_checks))
        if not isinstance(self.owner_quorum, int) or isinstance(self.owner_quorum, bool) or self.owner_quorum <= 0:
            raise ValueError("owner_quorum")

    def fingerprint(self) -> str:
        return digest(
            {
                "policy_id": self.policy_id,
                "claim_tier": self.claim_tier.value,
                "required_checks": sorted(self.required_checks),
                "owner_quorum": self.owner_quorum,
            }
        )


@dataclass(frozen=True)
class EvaluationReceipt:
    receipt_id: str
    artifact_digest: str
    policy_id: str
    evaluator_id: str
    checks_passed: frozenset[str]

    def __post_init__(self) -> None:
        for name in ("receipt_id", "artifact_digest", "policy_id", "evaluator_id"):
            _token(name, getattr(self, name))
        object.__setattr__(self, "checks_passed", _string_set("checks_passed", self.checks_passed))

    def fingerprint(self) -> str:
        return digest(
            {
                "receipt_id": self.receipt_id,
                "artifact_digest": self.artifact_digest,
                "policy_id": self.policy_id,
                "evaluator_id": self.evaluator_id,
                "checks_passed": sorted(self.checks_passed),
            }
        )


@dataclass(frozen=True)
class OwnerApproval:
    owner_id: str
    artifact_digest: str
    policy_id: str

    def __post_init__(self) -> None:
        for name in ("owner_id", "artifact_digest", "policy_id"):
            _token(name, getattr(self, name))

    def fingerprint(self) -> str:
        return digest(
            {
                "owner_id": self.owner_id,
                "artifact_digest": self.artifact_digest,
                "policy_id": self.policy_id,
            }
        )


@dataclass
class CellOutput:
    cell_id: str
    payload: Any
    lineage: NotebookLineage
    state: ArtifactState = ArtifactState.PROVISIONAL
    promotion_policy_id: str | None = None
    promotion_policy_fingerprint: str | None = None
    promotion_claim_tier: ClaimTier | None = None
    promotion_receipt_fingerprint: str | None = None
    evaluation_fingerprints: tuple[str, ...] = ()
    owner_approval_fingerprints: tuple[str, ...] = ()

    def content_digest(self) -> str:
        return digest(
            {
                "cell_id": self.cell_id,
                "payload": self.payload,
                "lineage_fingerprint": self.lineage.fingerprint(),
            }
        )


@dataclass(frozen=True)
class PromotionResult:
    ok: bool
    reason: str | None
    artifact_digest: str
    state: ArtifactState
    policy_id: str | None = None
    owner_count: int = 0
    promotion_fingerprint: str | None = None


class NotebookClaimFence:
    def __init__(self):
        self._cells: dict[str, CellOutput] = {}

    def record(self, cell_id: str, payload: Any) -> CellOutput:
        """Legacy provenance helper; strict promotion refuses this unbound lineage mode."""
        return self._record(
            notebook_id="legacy-notebook",
            notebook_source_sha="legacy-unbound-source",
            cell_id=cell_id,
            payload=payload,
            lineage_mode="LEGACY_UNBOUND",
        )

    def record_artifact(
        self,
        notebook_id: str,
        notebook_source_sha: str,
        cell_id: str,
        payload: Any,
    ) -> CellOutput:
        return self._record(notebook_id, notebook_source_sha, cell_id, payload, "EXACT_SOURCE")

    def _record(
        self,
        notebook_id: str,
        notebook_source_sha: str,
        cell_id: str,
        payload: Any,
        lineage_mode: str,
    ) -> CellOutput:
        for name, value in (("notebook_id", notebook_id), ("notebook_source_sha", notebook_source_sha), ("cell_id", cell_id)):
            _token(name, value)
        materialized = copy.deepcopy(payload)
        payload_digest = digest(materialized)
        lineage = NotebookLineage(notebook_id, notebook_source_sha, cell_id, payload_digest, lineage_mode)
        candidate = CellOutput(cell_id, materialized, lineage)
        existing = self._cells.get(cell_id)
        if existing is not None:
            if existing.content_digest() != candidate.content_digest():
                raise ValueError("CELL_ID_REBOUND")
            return existing
        self._cells[cell_id] = candidate
        return candidate

    def promote(
        self,
        cell_id: str,
        policy: PromotionPolicy,
        evaluation_receipts: Iterable[EvaluationReceipt],
        owner_approvals: Iterable[OwnerApproval],
    ) -> PromotionResult:
        cell = self._cells.get(cell_id)
        if cell is None:
            return PromotionResult(False, "UNKNOWN_CELL", "", ArtifactState.REJECTED)
        if not isinstance(policy, PromotionPolicy):
            return PromotionResult(False, "BAD_POLICY", cell.content_digest(), ArtifactState.REJECTED)
        if cell.lineage.lineage_mode != "EXACT_SOURCE":
            return PromotionResult(False, "NOTEBOOK_LINEAGE_UNBOUND", cell.content_digest(), ArtifactState.REJECTED)

        artifact_digest = cell.content_digest()
        receipts = tuple(evaluation_receipts)
        approvals = tuple(owner_approvals)
        if any(not isinstance(receipt, EvaluationReceipt) for receipt in receipts):
            return PromotionResult(False, "BAD_EVAL_RECEIPT", artifact_digest, ArtifactState.REJECTED)
        if any(not isinstance(approval, OwnerApproval) for approval in approvals):
            return PromotionResult(False, "BAD_OWNER_APPROVAL", artifact_digest, ArtifactState.REJECTED)

        receipt_ids: set[str] = set()
        passed_checks: set[str] = set()
        eval_fingerprints: list[str] = []
        for receipt in receipts:
            if receipt.receipt_id in receipt_ids:
                return PromotionResult(False, "DUPLICATE_EVAL_RECEIPT", artifact_digest, ArtifactState.REJECTED)
            receipt_ids.add(receipt.receipt_id)
            if receipt.artifact_digest != artifact_digest:
                return PromotionResult(False, "EVAL_ARTIFACT_MISMATCH", artifact_digest, ArtifactState.REJECTED)
            if receipt.policy_id != policy.policy_id:
                return PromotionResult(False, "EVAL_POLICY_MISMATCH", artifact_digest, ArtifactState.REJECTED)
            passed_checks.update(receipt.checks_passed)
            eval_fingerprints.append(receipt.fingerprint())

        missing_checks = sorted(policy.required_checks - passed_checks)
        if missing_checks:
            return PromotionResult(
                False,
                "EVALUATION_CHECKS_MISSING:" + ",".join(missing_checks),
                artifact_digest,
                ArtifactState.REJECTED,
                policy.policy_id,
            )

        unique_owners: dict[str, OwnerApproval] = {}
        for approval in approvals:
            if approval.artifact_digest != artifact_digest:
                return PromotionResult(False, "OWNER_ARTIFACT_MISMATCH", artifact_digest, ArtifactState.REJECTED, policy.policy_id)
            if approval.policy_id != policy.policy_id:
                return PromotionResult(False, "OWNER_POLICY_MISMATCH", artifact_digest, ArtifactState.REJECTED, policy.policy_id)
            unique_owners.setdefault(approval.owner_id, approval)

        if len(unique_owners) < policy.owner_quorum:
            return PromotionResult(False, "OWNER_QUORUM_UNMET", artifact_digest, ArtifactState.REJECTED, policy.policy_id, len(unique_owners))

        owner_fingerprints = sorted(approval.fingerprint() for approval in unique_owners.values())
        eval_fingerprints = sorted(eval_fingerprints)
        promotion_body = {
            "artifact_digest": artifact_digest,
            "lineage_fingerprint": cell.lineage.fingerprint(),
            "policy_fingerprint": policy.fingerprint(),
            "evaluation_fingerprints": eval_fingerprints,
            "owner_approval_fingerprints": owner_fingerprints,
        }
        promotion_fingerprint = digest(promotion_body)

        if cell.state is ArtifactState.PROMOTED:
            if cell.promotion_receipt_fingerprint != promotion_fingerprint:
                return PromotionResult(False, "PROMOTION_ALREADY_BOUND", artifact_digest, ArtifactState.REJECTED, cell.promotion_policy_id, len(unique_owners), cell.promotion_receipt_fingerprint)
            return PromotionResult(True, None, artifact_digest, ArtifactState.PROMOTED, policy.policy_id, len(unique_owners), promotion_fingerprint)

        cell.state = ArtifactState.PROMOTED
        cell.promotion_policy_id = policy.policy_id
        cell.promotion_policy_fingerprint = policy.fingerprint()
        cell.promotion_claim_tier = policy.claim_tier
        cell.promotion_receipt_fingerprint = promotion_fingerprint
        cell.evaluation_fingerprints = tuple(eval_fingerprints)
        cell.owner_approval_fingerprints = tuple(owner_fingerprints)
        return PromotionResult(True, None, artifact_digest, ArtifactState.PROMOTED, policy.policy_id, len(unique_owners), promotion_fingerprint)

    def assert_claim(
        self,
        cell_id: str,
        claim: str,
        required_policy_id: str | None = None,
    ) -> tuple[bool, str | None]:
        cell = self._cells.get(cell_id)
        if cell is None:
            return False, "UNKNOWN_CELL"
        _token("claim", claim)
        production = "production" in claim.lower()
        if production and cell.state is not ArtifactState.PROMOTED:
            return False, "UNPROMOTED_PRODUCTION_CLAIM"
        if production and cell.promotion_claim_tier is not ClaimTier.PRODUCTION:
            return False, "NONPRODUCTION_POLICY_CEILING"
        if required_policy_id is not None and cell.promotion_policy_id != required_policy_id:
            return False, "PROMOTION_POLICY_MISMATCH"
        return True, None
