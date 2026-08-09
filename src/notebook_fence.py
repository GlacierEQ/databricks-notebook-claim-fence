
"""Notebook claim fence — provisional outputs vs promoted artifacts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class ArtifactState(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"


@dataclass
class CellOutput:
    cell_id: str
    payload: Any
    state: ArtifactState = ArtifactState.PROVISIONAL
    eval_receipt: str | None = None
    owner_sign: str | None = None

    def content_digest(self) -> str:
        return digest({"cell": self.cell_id, "payload": self.payload})


@dataclass(frozen=True)
class PromotionResult:
    ok: bool
    reason: str | None
    artifact_digest: str
    state: ArtifactState


class NotebookClaimFence:
    def __init__(self):
        self._cells: dict[str, CellOutput] = {}

    def record(self, cell_id: str, payload: Any) -> CellOutput:
        out = CellOutput(cell_id, payload)
        self._cells[cell_id] = out
        return out

    def promote(self, cell_id: str, eval_receipt: str, owner_sign: str) -> PromotionResult:
        cell = self._cells.get(cell_id)
        if cell is None:
            return PromotionResult(False, "UNKNOWN_CELL", "", ArtifactState.REJECTED)
        if not eval_receipt.startswith("eval:"):
            return PromotionResult(False, "BAD_EVAL_RECEIPT", cell.content_digest(), ArtifactState.REJECTED)
        if not owner_sign.startswith("owner:"):
            return PromotionResult(False, "BAD_OWNER_SIGN", cell.content_digest(), ArtifactState.REJECTED)
        cell.state = ArtifactState.PROMOTED
        cell.eval_receipt = eval_receipt
        cell.owner_sign = owner_sign
        return PromotionResult(True, None, cell.content_digest(), ArtifactState.PROMOTED)

    def assert_claim(self, cell_id: str, claim: str) -> tuple[bool, str | None]:
        cell = self._cells.get(cell_id)
        if cell is None:
            return False, "UNKNOWN_CELL"
        if "production" in claim.lower() and cell.state is not ArtifactState.PROMOTED:
            return False, "UNPROMOTED_PRODUCTION_CLAIM"
        return True, None
