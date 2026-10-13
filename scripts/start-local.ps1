param(
    [switch]$Check,
    [switch]$NoBrowser,
    [int]$Port = 8000,
    [switch]$NoPortFallback
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

# Prefer the project environment, then an installed Python. Avoid Store stubs.
$candidates = @()
foreach ($relativePath in @('.venv\Scripts\python.exe', 'venv\Scripts\python.exe')) {
    $candidatePath = Join-Path $projectRoot $relativePath
    if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
        $candidates += @{ Path = $candidatePath; Prefix = @() }
    }
}
foreach ($commandName in @('python.exe', 'py.exe')) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*\WindowsApps\*') {
        $prefix = @()
        if ($commandName -eq 'py.exe') { $prefix = @('-3') }
        $candidates += @{ Path = $command.Source; Prefix = $prefix }
    }
}

try {
    $selectedPython = $null
    foreach ($candidate in $candidates) {
        $prefixArgs = @($candidate.Prefix)
        & $candidate.Path @prefixArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $selectedPython = $candidate
            break
        }
    }
    if (-not $selectedPython) {
        Write-Host 'Python 3.12+ was not found. Install Python with the PATH option enabled.' -ForegroundColor Red
        exit 1
    }
    $prefixArgs = @($selectedPython.Prefix)
    $launchArgs = @((Join-Path $projectRoot 'main.py'), '--port', [string]$Port)
    if ($Check) { $launchArgs += '--check' }
    if ($NoBrowser) { $launchArgs += '--no-browser' }
    if ($NoPortFallback) { $launchArgs += '--no-port-fallback' }
    & $selectedPython.Path @prefixArgs @launchArgs
    exit $LASTEXITCODE
} catch {
    Write-Host ('Startup failed: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
