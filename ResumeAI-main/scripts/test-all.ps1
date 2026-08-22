$ErrorActionPreference = "Stop"
$workspaceRoot = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $workspaceRoot "ml-service")
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

npm --prefix (Join-Path $workspaceRoot "backend") test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm --prefix (Join-Path $workspaceRoot "frontend") test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
