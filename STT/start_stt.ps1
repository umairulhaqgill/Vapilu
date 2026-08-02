# Launcher for the STT Service - called by run_all.ps1 in its own window.
Set-Location $PSScriptRoot
Write-Host "Working directory: $(Get-Location)"
venv\Scripts\Activate.ps1
python -m uvicorn stt_service:app --reload --port 8000
