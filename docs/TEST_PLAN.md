# Test plan

1. **Pure unit tests:** money parsing, reference/hint/amount matching, duplicate detection, outstanding and available balances. These have passed locally.
2. **Flask tests:** health endpoint, invalid JSON, wrong token, match response. Tests exist; Flask not installed in generation sandbox.
3. **Django tests:** login, authorization, CRUD, partial allocation and finalization, reconciliation flow with mocked Flask, audit events, reports. Tests exist; Django not installed in generation sandbox.
4. **MySQL integration:** migrate against MySQL 8.4 and run two concurrent postings targeting the same invoice. Tests exist; run through MySQL CI or local MySQL; SQLite cannot establish InnoDB safety.
5. **Windows smoke:** run PowerShell setup, start Flask/Django separately, create staff account, approve an invoice-payment allocation and export a CSV. Instructions exist; execution pending.
6. **CI:** `sqlite` and `mysql` jobs using GitHub Actions. The workflow has not been executed remotely.

**Acceptance policy:** FAILED remains FAILED, SKIPPED is not PASSED, and NOT EXECUTED is never reported as successful verification.
