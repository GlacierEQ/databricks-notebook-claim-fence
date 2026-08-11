-- Babel: SQL — notebook artifacts remain provisional until lineage, policy evaluation,
-- and distinct owner quorum are all bound to the exact artifact digest.
CREATE TABLE IF NOT EXISTS notebook_artifacts (
  cell_id                    VARCHAR PRIMARY KEY,
  notebook_id                VARCHAR NOT NULL,
  notebook_source_sha        VARCHAR NOT NULL,
  lineage_mode               VARCHAR NOT NULL CHECK (lineage_mode IN ('EXACT_SOURCE','LEGACY_UNBOUND')),
  payload_digest             CHAR(64) NOT NULL,
  lineage_fingerprint        CHAR(64) NOT NULL,
  artifact_digest            CHAR(64) NOT NULL UNIQUE,
  state                      VARCHAR NOT NULL CHECK (state IN ('PROVISIONAL','PROMOTED','REJECTED')),
  promotion_policy_id        VARCHAR,
  promotion_policy_fingerprint CHAR(64),
  promotion_claim_tier       VARCHAR CHECK (promotion_claim_tier IN ('BOUNDED','PRODUCTION')),
  promotion_receipt_fingerprint CHAR(64),
  updated_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS promotion_policies (
  policy_id          VARCHAR PRIMARY KEY,
  claim_tier         VARCHAR NOT NULL CHECK (claim_tier IN ('BOUNDED','PRODUCTION')),
  owner_quorum       INTEGER NOT NULL CHECK (owner_quorum > 0),
  policy_fingerprint CHAR(64) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS promotion_policy_checks (
  policy_id       VARCHAR NOT NULL REFERENCES promotion_policies(policy_id),
  required_check  VARCHAR NOT NULL,
  PRIMARY KEY (policy_id, required_check)
);

CREATE TABLE IF NOT EXISTS artifact_evaluation_receipts (
  receipt_id          VARCHAR PRIMARY KEY,
  artifact_digest     CHAR(64) NOT NULL,
  policy_id           VARCHAR NOT NULL REFERENCES promotion_policies(policy_id),
  evaluator_id        VARCHAR NOT NULL,
  receipt_fingerprint CHAR(64) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS artifact_evaluation_checks (
  receipt_id    VARCHAR NOT NULL REFERENCES artifact_evaluation_receipts(receipt_id),
  check_name    VARCHAR NOT NULL,
  PRIMARY KEY (receipt_id, check_name)
);

CREATE TABLE IF NOT EXISTS artifact_owner_approvals (
  artifact_digest      CHAR(64) NOT NULL,
  policy_id            VARCHAR NOT NULL REFERENCES promotion_policies(policy_id),
  owner_id             VARCHAR NOT NULL,
  approval_fingerprint CHAR(64) NOT NULL UNIQUE,
  PRIMARY KEY (artifact_digest, policy_id, owner_id)
);

-- Application-layer promotion authority remains responsible for verifying that:
-- 1. lineage_mode = EXACT_SOURCE;
-- 2. evaluation receipts bind the exact artifact_digest and policy_id;
-- 3. the union of evaluation checks covers the policy's required checks;
-- 4. COUNT(DISTINCT owner_id) meets owner_quorum for the same artifact/policy;
-- 5. production claims use a PRODUCTION-tier policy;
-- 6. the promotion receipt content-addresses lineage, policy, evaluations, and approvals.
