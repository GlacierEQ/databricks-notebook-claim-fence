#!/usr/bin/env python3
"""Cold-start: NotebookClaimFence blocks unpromoted production claim."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from notebook_fence import NotebookClaimFence

def main() -> int:
    f = NotebookClaimFence()
    f.record("c1", {"auc": 0.99})
    ok_claim, reason = f.assert_claim("c1", "production model ready")
    out = {
        "claim_ok": ok_claim,
        "reason": reason,
        "expected_reason": "UNPROMOTED_PRODUCTION_CLAIM",
        "ok": (not ok_claim) and reason == "UNPROMOTED_PRODUCTION_CLAIM",
    }
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1
if __name__ == "__main__":
    raise SystemExit(main())
