# Execution report — November 5, 2026

Environment: Python 3.13 Linux sandbox, no Django/Flask package installations, no MySQL server, no Docker, and no PowerShell runtime. A package installation attempt for Django/Flask failed because the package index could not be reached (`Temporary failure in name resolution`). **This is not a verified Windows release.**

| Check | Status | Evidence / cause |
|---|---|---|
| Python AST parsing + compileall | PASSED | All 32 Python files parsed/compiled without syntax errors |
| Pure matching tests | PASSED | `pytest -q tests/test_logic.py tests/test_extended_logic.py`: **26 passed**, one plugin warning |
| Synthetic evaluation | PASSED | `python scripts/evaluate.py`, 150 synthetic payments, CSV saved |
| Django model/migration validation | NOT EXECUTED | Django unavailable; dependency installation blocked by DNS/network |
| Flask endpoint tests | NOT EXECUTED | Flask unavailable |
| Django workflow tests | NOT EXECUTED | Django unavailable |
| MySQL migration/concurrency | NOT EXECUTED | MySQL and mysqlclient unavailable |
| Windows setup `.ps1` execution | NOT EXECUTED | Windows/PowerShell unavailable |
| GitHub Actions | NOT EXECUTED | Requires a GitHub repository and a workflow run |
| Docker Compose | NOT EXECUTED | Docker unavailable, optional only |
| Browser acceptance | NOT EXECUTED | Web app not started |
| Production deployment | NOT EXECUTED | No public deployment attempted |
| Final ZIP integrity | PASSED | `zipfile.ZipFile.testzip()` returned no corruption on generated archive |

Pytest emitted a warning about unknown `DJANGO_SETTINGS_MODULE` because the `pytest-django` plugin was not installed. The 26 isolated tests did not depend on that plugin.

**Do not report the Django, Flask, MySQL, Windows, CI or Docker checks as passed until they run successfully in the target environment.**
