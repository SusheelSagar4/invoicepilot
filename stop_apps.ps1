# Stop InvoicePilot Mock Applications running on ports 8001 and 8002
# Usage: .\stop_apps.ps1

Write-Host "Stopping mock application servers..."

# Stop processes listening on TCP ports 8001 and 8002
$connections = Get-NetTCPConnection -LocalPort 8001, 8002 -ErrorAction SilentlyContinue
if ($connections) {
    $pidsToKill = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pidsToKill) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped process ID $procId listening on application port." -ForegroundColor Yellow
        } catch {
            # Process may already be stopped
        }
    }
}

# Also check Win32_Process for any remaining uvicorn mock_apps processes
$mockProcs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*mock_apps*" }
if ($mockProcs) {
    foreach ($proc in $mockProcs) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped mock app process ID $($proc.ProcessId)." -ForegroundColor Yellow
        } catch {
            # Process may already be stopped
        }
    }
}

Write-Host "Applications stopped." -ForegroundColor Green
