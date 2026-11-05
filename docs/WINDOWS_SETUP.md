# Windows 11 setup without Docker

**Status:** scripts created and syntax-reviewed; not executed on a Windows host in the generation environment.

## Requirements

- Windows 11 and PowerShell 5.1 or 7
- Python **3.12** with the `py` launcher (`py -3.12 --version`)
- Internet connection for the first `pip` dependency installation
- No Docker, MySQL, Linux, or paid cloud account is required for the SQLite demo

## Start

Extract `ReconDesk-Final.zip`, open the extracted `ReconDesk-Final` folder in File Explorer, enter `powershell` in the address bar.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

Open PowerShell window **A** in the same folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start_flask.ps1
```

Open PowerShell window **B**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start_django.ps1
```

For the first run, open a third PowerShell in the same folder and create an admin user:

```powershell
$env:USE_SQLITE='1'
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Visit <http://127.0.0.1:8000/accounts/login/>. Flask health is <http://127.0.0.1:5000/health> and Django health is <http://127.0.0.1:8000/health/>.

The local scripts set **development-only** demo environment values, bind both servers to `127.0.0.1`, and are not safe for internet exposure.

## Test

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\test_windows.ps1
```

This runs SQLite/Django and Flask tests, if dependencies are installed, and the synthetic benchmark. MySQL concurrency is *not* verified by these tests.

## Reconciliation demo

1. Sign in as a superuser/staff member.
2. Open **Customers**. A demo customer already exists after `seed_demo`.
3. Open **Invoices** and **Payments** to inspect the synthetic records.
4. Open **Reconcile** and click **Run matching**. Keep the Flask terminal open.
5. Review the suggested invoice, payment, amount, and reason; confirm safe suggestions individually or reject them.
6. Open **Dashboard** and export the CSV report to see posted totals.

## Troubleshooting

- `py -3.12` not found: install Python 3.12 from python.org and check the launcher option.
- PowerShell refuses `.ps1` files: run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal (does not permanently change the machine policy).
- `ModuleNotFoundError: django`: rerun `scripts/setup_windows.ps1` and inspect pip errors.
- Port 5000 or 8000 in use: stop the other process or use another port and set `MATCHER_URL` correspondingly.
- Matching returns unavailable: start Flask in the second terminal, confirm `/health` is reachable, and ensure the token matches between scripts.
- MySQL errors: ensure `USE_SQLITE=1` is set, or follow `docs/MYSQL_SETUP.md` for a deliberate MySQL run.
- Never commit `.env`, SQLite database files, or secret credentials to GitHub.
