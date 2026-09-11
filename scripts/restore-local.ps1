param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackupRoot = (Resolve-Path -LiteralPath (Join-Path $ProjectRoot 'data\backups')).Path
$Source = (Resolve-Path -LiteralPath $BackupFile).Path
$Target = Join-Path $ProjectRoot 'data\sports_meet.db'

if (-not $Source.StartsWith($BackupRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw '只允许恢复 data\backups 目录内的备份文件。'
}
if (-not $Force) {
    $Answer = Read-Host "恢复会覆盖当前本地数据库。确认恢复 $Source ? 输入 RESTORE"
    if ($Answer -ne 'RESTORE') { Write-Host '已取消。'; exit 0 }
}
Copy-Item -LiteralPath $Source -Destination $Target -Force
Write-Host "恢复完成：$Target" -ForegroundColor Green
