# Requirements (student project)

| ID | Requirement | Implementation | Verification |
|---|---|---|---|
| FR-001 | Authenticated UI, staff-only financial writes | Django auth/decorators/DRF permissions | Django tests written; not executed here |
| FR-002 | Customer CRUD and draft invoice create/list/edit/delete | Views, model forms and templates | Django tests written; not executed here |
| FR-003 | Record payments and preserve allocated receipts | Payment model/form; model immutability on allocated receipts | Django tests written; not executed here |
| FR-004 | Explainable suggestions through a Flask API | `core/logic.py`, `flask_matcher/app.py` | Pure matching tests passed; Flask pending |
| FR-005 | Human confirmation with balance and customer safeguards | `core/services.py`, reconciliation UI | Django tests written; MySQL concurrency pending |
| FR-006 | Invoice/payment dashboards and CSV reports | Django views, DRF summary, Pandas script | Django tests pending |
| FR-007 | Safe endpoint validation and private matcher token | Django + Flask API | Flask tests written; pending |
| FR-008 | Docker-free local setup and reproducible CI | PowerShell scripts and GitHub Actions | Windows + remote CI unverified |

NFR-001 Money handled as `Decimal`, not binary floats for posting. NFR-002 No silent posting of reconciliation suggestions. NFR-003 Authenticated, permission-checked access. NFR-004 Synthetic, reproducible tests. NFR-005 No production accounting or compliance claims.
