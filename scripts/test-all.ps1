$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $ProjectRoot
python -m pytest backend\tests -q
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:e2e

