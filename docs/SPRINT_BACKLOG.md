# Agile-inspired sprint plan

Two *logical planning scopes* are documented; these are not historical claims about sprint duration, team participation or standups.

**Sprint A – Basic business records:** FR-001/002/003; login, customer/invoice/payment forms, database constraints and role permissions. Acceptance: staff can enter synthetic records, viewers cannot change them, invalid amounts are rejected.

**Sprint B – Reconciliation and evidence:** FR-004/005/006/007/008; Flask matching service, confirmation UI, reports, API tests, Docker-free setup and CI. Acceptance: suggestions never auto-post money, reconciled totals match stored allocations, malformed API inputs are rejected, MySQL concurrency test passes on real InnoDB.

**Current verification:** Standalone matching tests and evaluation run locally. Django/Flask/UI/MySQL/CI acceptance checks are pending. Issues can be tracked in GitHub using the included templates. Do not claim team meetings or actual sprints occurred unless independently documented later.
