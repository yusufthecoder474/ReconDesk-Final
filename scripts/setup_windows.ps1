$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python launcher not found. Install Python 3.12 from python.org.' }
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 virtual environment creation failed.' }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Installed dependencies. Use scripts/start_flask.ps1 and scripts/start_django.ps1 in separate windows.'
