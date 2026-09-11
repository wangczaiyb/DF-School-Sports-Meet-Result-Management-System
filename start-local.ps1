$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

# Windows PowerShell 5.1 的 Start-Process 无法处理同时存在 Path/PATH 的环境块。
$EffectivePath = [Environment]::GetEnvironmentVariable('Path', 'Process')
if ([string]::IsNullOrWhiteSpace($EffectivePath)) {
    $EffectivePath = [Environment]::GetEnvironmentVariable('PATH', 'Process')
}
[Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[Environment]::SetEnvironmentVariable('Path', $EffectivePath, 'Process')

function Test-ServiceReady([string]$Url) {
    try {
        $Response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
        return $Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Wait-ServiceReady([string]$Url, [int]$TimeoutSeconds = 90) {
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        if (Test-ServiceReady $Url) { return $true }
        Start-Sleep -Milliseconds 750
    }
    return $false
}

function Test-BackendCurrent {
    try {
        $Response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
        return $Response.status -eq 'ok' -and $Response.features -contains 'college-team-roster'
    } catch {
        return $false
    }
}

function Open-SystemBrowser([string]$Url) {
    if ($env:SPORTS_MEET_NO_BROWSER -eq '1') { return }
    try {
        Start-Process $Url -ErrorAction Stop
    } catch {
        Write-Warning "浏览器未能自动打开，请手动访问：$Url"
    }
}

$FrontendUrl = 'http://127.0.0.1:5173'
$BackendHealthUrl = 'http://127.0.0.1:8000/health'
$FrontendReady = Test-ServiceReady $FrontendUrl
$BackendReady = Test-ServiceReady $BackendHealthUrl
$BackendCurrent = Test-BackendCurrent

if ($FrontendReady -and $BackendCurrent) {
    Write-Host "系统已经在运行：$FrontendUrl" -ForegroundColor Green
    Open-SystemBrowser $FrontendUrl
    exit 0
}

if ($FrontendReady -or $BackendReady) {
    if ($BackendReady -and -not $BackendCurrent) {
        Write-Host '检测到旧版本后台，正在关闭并加载最新功能……' -ForegroundColor Yellow
    } else {
        Write-Host '检测到上次未完整关闭的服务，正在清理后重新启动……' -ForegroundColor Yellow
    }
    & (Join-Path $ProjectRoot 'stop-local.ps1')
    Start-Sleep -Seconds 1
}

if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host '已创建 .env，请在正式使用前修改密码和 SECRET_KEY。' -ForegroundColor Yellow
}

Write-Host '正在使用项目内 SQLite 数据库启动系统……' -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw '未检测到 Python，请安装 Python 3.12 或更高版本。'
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw '未检测到 Node.js/npm，请安装 Node.js 22 或更高版本。'
}
$env:DATABASE_URL = "sqlite:///$($ProjectRoot.Replace('\','/'))/data/sports_meet.db"
$env:EXPORT_DIR = "$ProjectRoot\data\exports"
python -c "import fastapi, sqlalchemy, openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '正在安装后端依赖……' -ForegroundColor Cyan
    python -m pip install -r backend\requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw '后端依赖安装失败，请检查网络连接和 Python pip。'
    }
}
if (-not (Test-Path -LiteralPath 'frontend\node_modules')) {
    Write-Host '正在安装前端依赖……' -ForegroundColor Cyan
    npm --prefix frontend install
    if ($LASTEXITCODE -ne 0) {
        throw '前端依赖安装失败，请检查网络连接和 npm。'
    }
}
New-Item -ItemType Directory -Force -Path 'data' | Out-Null
try {
    if (-not (Test-BackendCurrent)) {
        $Backend = Start-Process -FilePath 'python' -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000','--reload' -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput 'data\backend.log' -RedirectStandardError 'data\backend-error.log' -PassThru
        Set-Content -LiteralPath 'data\backend.pid' -Value $Backend.Id
    }
    if (-not (Test-ServiceReady $FrontendUrl)) {
        $Frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList '--prefix','frontend','run','dev' -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput 'data\frontend.log' -RedirectStandardError 'data\frontend-error.log' -PassThru
        Set-Content -LiteralPath 'data\frontend.pid' -Value $Frontend.Id
    }
} catch {
    & (Join-Path $ProjectRoot 'stop-local.ps1')
    throw
}
if (-not (Wait-ServiceReady $BackendHealthUrl 90)) {
    & (Join-Path $ProjectRoot 'stop-local.ps1')
    throw '后端启动超时，请查看 data\backend-error.log。'
}
if (-not (Wait-ServiceReady $FrontendUrl 90)) {
    & (Join-Path $ProjectRoot 'stop-local.ps1')
    throw '服务启动超时，请查看 data\backend-error.log 和 data\frontend-error.log。'
}
Write-Host "系统已启动：$FrontendUrl" -ForegroundColor Green
Write-Host "数据库文件：$ProjectRoot\data\sports_meet.db" -ForegroundColor DarkGray
Open-SystemBrowser $FrontendUrl
