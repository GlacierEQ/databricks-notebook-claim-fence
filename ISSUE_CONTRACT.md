# ISSUE CONTRACT

## Pain
Notebook outputs can be presented as stronger features or models even when the notebook source, artifact content, evaluation policy, and approving owners are not bound to the same evidence object.

## Success
- Exact notebook source and payload identity produce a one-shot provisional artifact.
- Promotion requires policy-specific evaluation checks bound to the exact artifact digest.
- Distinct owner approvals bind the same artifact and policy and must satisfy a positive quorum.
- Promotion proof content-addresses notebook lineage, policy, evaluations, and owner approvals.
- Exact promotion replay is idempotent; changed proof cannot rebind a completed promotion.
- BOUNDED-tier promotion cannot support a production claim.
- Legacy unbound notebook outputs cannot promote.

## Boundaries
- Notebook source SHA is caller-supplied rather than externally attested.
- Owner and evaluator IDs are structured claims rather than cryptographically authenticated identities.
- Promotion revocation is not implemented.
- No Databricks affiliation, adoption, or production notebook-governance claim.
