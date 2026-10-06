# Start InvoicePilot Mock Applications as background processes
# Usage: .\start_apps.ps1

Write-Host "Starting Invoice Portal (Port 8001) and Finance System (Port 8002)..."

# Create logs directory if missing
$logDir = "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$portalOut = Join-Path $logDir "portal.out.log"
$portalErr = Join-Path $logDir "portal.err.log"
$financeOut = Join-Path $logDir "finance.out.log"
$financeErr = Join-Path $logDir "finance.err.log"
$pidFile    = Join-Path $logDir "pids.json"

# Step 1: Clean up any existing processes listening on ports 8001 or 8002
$existingConns = Get-NetTCPConnection -LocalPort 8001, 8002 -ErrorAction SilentlyContinue
if ($existingConns) {
    $pidsToKill = $existingConns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pId in $pidsToKill) {
        Stop-Process -Id $pId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

# Step 2: Start background processes with separate stdout and stderr log files
$portalProc = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn mock_apps.invoice_portal.app:app --host 127.0.0.1 --port 8001 --reload" `
    -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $portalOut `
    -RedirectStandardError $portalErr

$financeProc = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn mock_apps.finance_system.app:app --host 127.0.0.1 --port 8002 --reload" `
    -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $financeOut `
    -RedirectStandardError $financeErr

# Save process IDs to JSON file
@{
    portal  = $portalProc.Id
    finance = $financeProc.Id
} | ConvertTo-Json | Set-Content -Path $pidFile

# Wait 3 seconds for server initialization
Start-Sleep -Seconds 3

# Step 3: Health Verification (Must be process-alive AND HTTP 200)
$portalAlive = Get-Process -Id $portalProc.Id -ErrorAction SilentlyContinue
$portalUrlOk = $false

if ($portalAlive) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8001" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) { $portalUrlOk = $true }
    } catch {
        $portalUrlOk = $false
    }
}

if ($portalAlive -and $portalUrlOk) {
    Write-Host "Portal OK" -ForegroundColor Green
} else {
    Write-Host "Portal Failed to start on port 8001!" -ForegroundColor Red
    if (Test-Path $portalErr) {
        Write-Host "Last lines of $portalErr :" -ForegroundColor Yellow
        Get-Content $portalErr -Tail 10 | Write-Host
    }
}

$financeAlive = Get-Process -Id $financeProc.Id -ErrorAction SilentlyContinue
$financeUrlOk = $false

if ($financeAlive) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8002" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) { $financeUrlOk = $true }
    } catch {
        $financeUrlOk = $false
    }
}

if ($financeAlive -and $financeUrlOk) {
    Write-Host "Finance OK" -ForegroundColor Green
} else {
    Write-Host "Finance Failed to start on port 8002!" -ForegroundColor Red
    if (Test-Path $financeErr) {
        Write-Host "Last lines of $financeErr :" -ForegroundColor Yellow
        Get-Content $financeErr -Tail 10 | Write-Host
    }
}

# Step 4: Reset applications to clean initial state
Write-Host "Resetting applications to clean initial state..."
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/admin/reset" -Method Get | Out-Null
    Invoke-RestMethod -Uri "http://127.0.0.1:8002/admin/reset" -Method Get | Out-Null
    Write-Host "Reset complete." -ForegroundColor Cyan
} catch {
    Write-Host "Reset failed for one or both applications." -ForegroundColor Yellow
}
