-- Babel: SQL — notebook artifacts provisional until promoted.
CREATE TABLE IF NOT EXISTS notebook_artifacts (
  cell_id        VARCHAR PRIMARY KEY,
  payload_digest CHAR(64) NOT NULL,
  state          VARCHAR NOT NULL CHECK (state IN ('PROVISIONAL','PROMOTED','REJECTED')),
  eval_receipt   VARCHAR,
  owner_sign     VARCHAR,
  updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- App layer: production claims require state = PROMOTED AND eval_receipt LIKE 'eval:%'
