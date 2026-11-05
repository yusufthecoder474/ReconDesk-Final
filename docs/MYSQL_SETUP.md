# MySQL 8.4 on Windows (no Docker)

**Status:** configuration and CI workflow are included, but a live MySQL 8.4 run was not possible in this generation environment.

MySQL is not necessary for the SQLite demo. To demonstrate the exact EY JD database skill, install MySQL Community Server 8.4 independently on Windows and run this setup.

1. Install MySQL Community Server 8.4 from the official MySQL Community Downloads site. Save your local root password. Configure the server on port `3306`.
2. Open `mysql.exe` or MySQL Command Line Client as an administrator and run:

```sql
CREATE DATABASE recondesk CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'recondesk'@'localhost' IDENTIFIED BY 'replace-with-strong-password';
GRANT ALL PRIVILEGES ON recondesk.* TO 'recondesk'@'localhost';
FLUSH PRIVILEGES;
```

3. Install MySQL support into the same Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-mysql.txt
```

4. Start Flask through `scripts/start_flask.ps1`. In another PowerShell window set MySQL environment settings:

```powershell
$env:USE_SQLITE='0'
$env:DEBUG='1'
$env:SECRET_KEY='local-mysql-demo-not-production'
$env:MYSQL_DATABASE='recondesk'
$env:MYSQL_USER='recondesk'
$env:MYSQL_PASSWORD='replace-with-strong-password'
$env:MYSQL_HOST='127.0.0.1'
$env:MYSQL_PORT='3306'
$env:MATCHER_URL='http://127.0.0.1:5000'
$env:MATCHER_SHARED_TOKEN='local-demo-token'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

5. In another terminal with the **same** environment variables, run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The `tests/test_mysql_integrity.py` test attempts two concurrent payments against one invoice; it **skips itself on SQLite** and must pass against MySQL before claiming that InnoDB locking was verified.

If `mysqlclient` installation fails because no compatible Windows wheel is available, do not claim MySQL works: record the error, use the SQLite demo, and verify MySQL through GitHub Actions after pushing the repository. The CI runner provides its own MySQL service; Docker is not required on your laptop.

MySQL transaction and driver compatibility remain unverified until the commands above succeed.
