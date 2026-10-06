# Stop InvoicePilot Mock Applications running on ports 8001 and 8002
# Usage: .\stop_apps.ps1

Write-Host "Stopping mock application servers..."

$pidFile = Join-Path "logs" "pids.json"

# Step 1: Stop saved process IDs from logs/pids.json
if (Test-Path $pidFile) {
    try {
        $pidsJson = Get-Content $pidFile | ConvertFrom-Json
        if ($pidsJson.portal) {
            Stop-Process -Id $pidsJson.portal -Force -ErrorAction SilentlyContinue
        }
        if ($pidsJson.finance) {
            Stop-Process -Id $pidsJson.finance -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # Ignore JSON read errors
    }
}

# Step 2: Stop any remaining processes listening on TCP ports 8001 and 8002
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

# Step 3: Check Win32_Process for any remaining uvicorn mock_apps processes
$mockProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*mock_apps*" }
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
