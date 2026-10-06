# Start InvoicePilot Mock Applications as background processes
# Usage: .\start_apps.ps1

Write-Host "Starting Invoice Portal (Port 8001) and Finance System (Port 8002)..."

$portalOut = Join-Path $env:TEMP "uvicorn_portal_out.log"
$portalErr = Join-Path $env:TEMP "uvicorn_portal_err.log"
$financeOut = Join-Path $env:TEMP "uvicorn_finance_out.log"
$financeErr = Join-Path $env:TEMP "uvicorn_finance_err.log"

# Launch Invoice Portal on Port 8001 as background process
$portalProc = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn mock_apps.invoice_portal.app:app --host 127.0.0.1 --port 8001 --reload" `
    -PassThru -WindowStyle Hidden -RedirectStandardOutput $portalOut -RedirectStandardError $portalErr

# Launch Finance System on Port 8002 as background process
$financeProc = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn mock_apps.finance_system.app:app --host 127.0.0.1 --port 8002 --reload" `
    -PassThru -WindowStyle Hidden -RedirectStandardOutput $financeOut -RedirectStandardError $financeErr

# Wait 3 seconds for server initialization
Start-Sleep -Seconds 3

# Verify Portal health (Port 8001)
try {
    $portalResp = Invoke-WebRequest -Uri "http://127.0.0.1:8001" -UseBasicParsing -TimeoutSec 5
    if ($portalResp.StatusCode -eq 200) {
        Write-Host "Portal OK" -ForegroundColor Green
    } else {
        Write-Host "Portal Failed (HTTP $($portalResp.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "Portal Failed: Could not connect to http://127.0.0.1:8001" -ForegroundColor Red
}

# Verify Finance System health (Port 8002)
try {
    $financeResp = Invoke-WebRequest -Uri "http://127.0.0.1:8002" -UseBasicParsing -TimeoutSec 5
    if ($financeResp.StatusCode -eq 200) {
        Write-Host "Finance OK" -ForegroundColor Green
    } else {
        Write-Host "Finance Failed (HTTP $($financeResp.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "Finance Failed: Could not connect to http://127.0.0.1:8002" -ForegroundColor Red
}

# Call /admin/reset on both apps to guarantee a clean slate
Write-Host "Resetting applications to clean initial state..."
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8001/admin/reset" -Method Get | Out-Null
    Invoke-RestMethod -Uri "http://127.0.0.1:8002/admin/reset" -Method Get | Out-Null
    Write-Host "Reset complete." -ForegroundColor Cyan
} catch {
    Write-Host "Reset failed for one or both applications." -ForegroundColor Yellow
}
