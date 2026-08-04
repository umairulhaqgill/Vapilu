# Launcher for the Connector Gateway - called by run_all.ps1 in its own window.
Set-Location $PSScriptRoot
Write-Host "Working directory: $(Get-Location)"
venv\Scripts\Activate.ps1
python -m uvicorn connector_gateway_service:app --reload --host 0.0.0.0 --port 8005
