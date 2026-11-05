$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:USE_SQLITE = '1'
$env:DEBUG = '1'
$env:SECRET_KEY = 'recondesk-local-test-only'
$env:MATCHER_SHARED_TOKEN = 'local-demo-token'
& .\.venv\Scripts\python.exe -m compileall -q config core flask_matcher tests scripts
if ($LASTEXITCODE -ne 0) { throw 'Compile check failed.' }
& .\.venv\Scripts\python.exe -m pytest -q -m 'not mysql'
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
& .\.venv\Scripts\python.exe scripts/evaluate.py
if ($LASTEXITCODE -ne 0) { throw 'Evaluation failed.' }
