$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:USE_SQLITE = '1'
$env:DEBUG = '1'
$env:SECRET_KEY = 'recondesk-dev-only-change-before-production'
$env:MATCHER_URL = 'http://127.0.0.1:5000'
$env:MATCHER_SHARED_TOKEN = 'local-demo-token'
$python = '.\.venv\Scripts\python.exe'
& $python manage.py check
if ($LASTEXITCODE -ne 0) { throw 'Django check failed.' }
& $python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Migrations failed.' }
& $python manage.py seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo data creation failed.' }
Write-Host 'If this is your first run, open a SECOND terminal and execute:'
Write-Host ' $env:USE_SQLITE="1"; .\.venv\Scripts\python.exe manage.py createsuperuser'
Write-Host 'Django is at http://127.0.0.1:8000/accounts/login/'
& $python manage.py runserver 127.0.0.1:8000
