$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:MATCHER_SHARED_TOKEN = 'local-demo-token'
& .\.venv\Scripts\python.exe -m flask --app flask_matcher.app run --host 127.0.0.1 --port 5000
