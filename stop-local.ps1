$ErrorActionPreference = 'SilentlyContinue'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$ProcessIds = New-Object 'System.Collections.Generic.HashSet[int]'
foreach ($PidFile in @('data\backend.pid','data\frontend.pid')) {
    if (Test-Path -LiteralPath $PidFile) {
        $ProcessId = [int](Get-Content -LiteralPath $PidFile)
        if ($ProcessId -gt 0) { [void]$ProcessIds.Add($ProcessId) }
        Remove-Item -LiteralPath $PidFile -Force
    }
}

Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 8000,5173 } |
    ForEach-Object { if ($_.OwningProcess -gt 0) { [void]$ProcessIds.Add([int]$_.OwningProcess) } }

foreach ($LogFile in @('data\backend-error.log','data\backend.log')) {
    if (Test-Path -LiteralPath $LogFile) {
        Select-String -LiteralPath $LogFile -Pattern 'Started (?:server|reloader) process \[(\d+)\]' -AllMatches |
            ForEach-Object { $_.Matches } |
            ForEach-Object { [void]$ProcessIds.Add([int]$_.Groups[1].Value) }
    }
}

foreach ($ProcessId in $ProcessIds) {
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
        if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
            Stop-Process -Id $ProcessId -Force
        }
    }
}
Write-Host '本地服务已停止。'
