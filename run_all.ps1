<#
Starts the STT Service, NLU Service, TTS Service, and Orchestrator together,
waits until all four report healthy, then runs the mic test client - so you
can test the whole chain in one command instead of juggling five terminals
by hand.

REQUIRES:
  - All four projects already set up (venv created, requirements installed,
    .env filled in) exactly as we've been doing manually.
  - start_stt.ps1 copied into your STT project folder.
  - start_nlu.ps1 copied into your NLU project folder.
  - start_tts.ps1 copied into your TTS project folder.
  - start_orchestrator.ps1 copied into your Orchestrator project folder.

Run this from the PARENT folder that contains all four project folders, e.g.:
    D:\Projects\Vapilu>  .\run_all.ps1

If your folder names differ from "STT", "NLU", "TTS", and "Orchestrator",
edit the four lines below before running.
#>

$sttDir  = Join-Path $PSScriptRoot "STT"
$nluDir  = Join-Path $PSScriptRoot "NLU"
$ttsDir  = Join-Path $PSScriptRoot "TTS"
$tenantDir = Join-Path $PSScriptRoot "TenantConfig"
$orchDir = Join-Path $PSScriptRoot "Orchestrator"

function Stop-PortIfInUse($port) {
    $conns = $null
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    } catch {
        $conns = $null
    }
    if (-not $conns) {
        return
    }
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $proc) { continue }

        Write-Host "Port $port is already in use by PID $procId ($($proc.ProcessName)) - stopping it." -ForegroundColor Yellow

        # uvicorn --reload runs as a parent "reloader" process plus a child
        # "server" process. Killing only the child can cause the reloader to
        # immediately notice and respawn a new one on the same port - so stop
        # the parent too if it looks like the same kind of leftover process.
        try {
            $parentId = (Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue).ParentProcessId
            if ($parentId) {
                $parentProc = Get-Process -Id $parentId -ErrorAction SilentlyContinue
                if ($parentProc -and $parentProc.ProcessName -match "python|powershell") {
                    Stop-Process -Id $parentId -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {
            # Best-effort only - not finding the parent isn't fatal.
        }

        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1  # give Windows a moment to actually release the port
}

function Wait-ForHealth($hostName, $port, $name, $timeoutSeconds = 30) {
    Write-Host "Waiting for $name to accept connections on ${hostName}:${port} ..."
    $elapsed = 0
    while ($elapsed -lt $timeoutSeconds) {
        $connected = $false
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $asyncResult = $client.BeginConnect($hostName, $port, $null, $null)
            $waitSuccess = $asyncResult.AsyncWaitHandle.WaitOne(1000)
            if ($waitSuccess -and $client.Connected) {
                $connected = $true
            }
            $client.Close()
        } catch {
            $connected = $false
        }

        if ($connected) {
            Write-Host "$name is accepting connections." -ForegroundColor Green
            return $true
        }

        Start-Sleep -Milliseconds 500
        $elapsed += 0.5
        if ($elapsed % 5 -eq 0) {
            Write-Host "  ... still waiting on $name ($elapsed/$timeoutSeconds s)"
        }
    }
    Write-Host "$name did not accept connections within $timeoutSeconds seconds." -ForegroundColor Red
    Write-Host "Check the separate PowerShell window for $name - the real error will be there." -ForegroundColor Red
    return $false
}

if (-not (Test-Path $sttDir)) {
    Write-Host "Can't find STT project folder at: $sttDir" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $nluDir)) {
    Write-Host "Can't find NLU project folder at: $nluDir" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $ttsDir)) {
    Write-Host "Can't find TTS project folder at: $ttsDir" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $tenantDir)) {
    Write-Host "Can't find TenantConfig project folder at: $tenantDir" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $orchDir)) {
    Write-Host "Can't find Orchestrator project folder at: $orchDir" -ForegroundColor Red
    exit 1
}

$sttLauncher  = Join-Path $sttDir "start_stt.ps1"
$nluLauncher  = Join-Path $nluDir "start_nlu.ps1"
$ttsLauncher  = Join-Path $ttsDir "start_tts.ps1"
$tenantLauncher = Join-Path $tenantDir "start_tenant.ps1"
$orchLauncher = Join-Path $orchDir "start_orchestrator.ps1"

if (-not (Test-Path $sttLauncher)) {
    Write-Host "Missing $sttLauncher - copy start_stt.ps1 into your STT folder first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $nluLauncher)) {
    Write-Host "Missing $nluLauncher - copy start_nlu.ps1 into your NLU folder first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $ttsLauncher)) {
    Write-Host "Missing $ttsLauncher - copy start_tts.ps1 into your TTS folder first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $tenantLauncher)) {
    Write-Host "Missing $tenantLauncher - copy start_tenant.ps1 into your TenantConfig folder first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $orchLauncher)) {
    Write-Host "Missing $orchLauncher - copy start_orchestrator.ps1 into your Orchestrator folder first." -ForegroundColor Red
    exit 1
}

Write-Host "Freeing ports 8000-8004 if anything is already using them..."
Stop-PortIfInUse 8000
Stop-PortIfInUse 8001
Stop-PortIfInUse 8002
Stop-PortIfInUse 8003
Stop-PortIfInUse 8004
Write-Host ""

Write-Host "Starting STT Service (port 8000) in a new window..."
Start-Process powershell -ArgumentList "-NoExit", "-File", $sttLauncher

Write-Host "Starting NLU Service (port 8002) in a new window..."
Start-Process powershell -ArgumentList "-NoExit", "-File", $nluLauncher

Write-Host "Starting TTS Service (port 8003) in a new window..."
Start-Process powershell -ArgumentList "-NoExit", "-File", $ttsLauncher

Write-Host "Starting Tenant Config Service (port 8004) in a new window..."
Start-Process powershell -ArgumentList "-NoExit", "-File", $tenantLauncher

Write-Host "Starting Orchestrator (port 8001) in a new window..."
Start-Process powershell -ArgumentList "-NoExit", "-File", $orchLauncher

# Fail fast: don't bother waiting on the next service if an earlier one
# never came up - the Orchestrator needs all three anyway.
# STT Service has heavier imports (deepgram-sdk, scipy, numpy, soundfile)
# than the others, so it can genuinely take longer to start on a cold run
# (especially with antivirus scanning new modules the first time) - giving
# it more headroom than the rest.
$sttOk = Wait-ForHealth "127.0.0.1" 8000 "STT Service" 60
if (-not $sttOk) {
    Write-Host ""
    Write-Host "Stopping here since STT Service isn't healthy - Orchestrator needs it anyway." -ForegroundColor Red
    exit 1
}

$nluOk = Wait-ForHealth "127.0.0.1" 8002 "NLU Service" 45
if (-not $nluOk) {
    Write-Host ""
    Write-Host "Stopping here since NLU Service isn't healthy - Orchestrator needs it anyway." -ForegroundColor Red
    exit 1
}

# TTS Service loads a neural voice model into memory at startup - give it
# a bit more room than NLU/Orchestrator, similar reasoning to STT.
$ttsOk = Wait-ForHealth "127.0.0.1" 8003 "TTS Service" 45
if (-not $ttsOk) {
    Write-Host ""
    Write-Host "Stopping here since TTS Service isn't healthy." -ForegroundColor Red
    exit 1
}

$tenantOk = Wait-ForHealth "127.0.0.1" 8004 "Tenant Config Service" 30
if (-not $tenantOk) {
    Write-Host ""
    Write-Host "Stopping here since Tenant Config Service isn't healthy." -ForegroundColor Red
    exit 1
}

$orchOk = Wait-ForHealth "127.0.0.1" 8001 "Orchestrator" 30
if (-not $orchOk) {
    exit 1
}

Write-Host ""
Write-Host "All five services are healthy. Starting the mic test client..." -ForegroundColor Cyan
Write-Host "Speak into your mic. Press Ctrl+C here to end the test." -ForegroundColor Cyan
Write-Host "(The five service windows will keep running after this ends - close them manually when you're done.)"
Write-Host ""

Set-Location $orchDir
venv\Scripts\Activate.ps1
python test_call_mic.py
