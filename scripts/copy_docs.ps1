# Копирует docx из AO_BARS_GRUP в data/docs
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$src = Join-Path $root "AO_BARS_GRUP\Additional"
$dst = Join-Path (Split-Path $PSScriptRoot -Parent) "data\docs"

if (-not (Test-Path $src)) {
    Write-Error "Не найдена папка: $src"
    exit 1
}

New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Path (Join-Path $src "*.docx") -Destination $dst -Force
Write-Host "Скопировано в $dst"
Get-ChildItem $dst -Filter *.docx
