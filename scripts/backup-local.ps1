param([string]$Label = 'manual')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DatabasePath = Join-Path $ProjectRoot 'data\sports_meet.db'
$BackupRoot = Join-Path $ProjectRoot 'data\backups'
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

if (-not (Test-Path -LiteralPath $DatabasePath)) {
    throw '未找到 SQLite 数据库，请先运行一键启动脚本创建数据库。'
}
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$SafeLabel = $Label -replace '[^a-zA-Z0-9_-]', '_'
$Destination = Join-Path $BackupRoot "sports_meet_${Timestamp}_${SafeLabel}.db"
@'
import sqlite3
import sys

source_path, destination_path = sys.argv[1], sys.argv[2]
with sqlite3.connect(source_path, timeout=30) as source:
    with sqlite3.connect(destination_path) as destination:
        source.backup(destination)
'@ | python - $DatabasePath $Destination
if ($LASTEXITCODE -ne 0) {
    throw 'SQLite 数据库备份失败。'
}
Write-Host "备份完成：$Destination" -ForegroundColor Green
