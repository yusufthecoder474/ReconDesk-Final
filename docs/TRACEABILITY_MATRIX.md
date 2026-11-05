# Requirements traceability matrix

| ID | User story | Implementation | Tests/evidence |
|---|---|---|---|
| FR-001 | US-04 | `core/views.py`, `core/api.py`, `config/urls.py` | `tests/test_django.py`, `test_workflow.py` (unexecuted) |
| FR-002 | US-01 | `core/forms.py`, `core/models.py`, `templates/core/list.html` | `test_workflow.py` (unexecuted) |
| FR-003 | US-02 | `core/forms.py`, `core/views.py` | `test_workflow.py` (unexecuted) |
| FR-004 | US-03 | `core/logic.py`, `flask_matcher/app.py` | `test_logic.py`, `test_extended_logic.py` (26 passed), Flask unexecuted |
| FR-005 | US-03 | `core/services.py`, `templates/core/reconcile.html` | `test_workflow.py`, `test_mysql_integrity.py` (unexecuted) |
| FR-006 | US-05 | `core/views.py`, `core/api.py`, `scripts/report.py` | `test_django.py` (unexecuted) |
| FR-007 | US-03 | `flask_matcher/app.py` | `test_flask.py` (unexecuted) |
| FR-008 | – | `scripts/*.ps1`, `.github/workflows/ci.yml` | Windows and GitHub Actions execution pending |

This maps requirements to actual files and distinguishes written tests from completed evidence.
