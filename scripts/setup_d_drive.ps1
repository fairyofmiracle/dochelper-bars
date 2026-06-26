# Setup data on D: drive (ASCII-only to avoid encoding issues)
$DataRoot = "D:\bars-support-bot-data"
$ProjectRoot = Split-Path $PSScriptRoot -Parent

$dirs = @(
    "$DataRoot\ollama",
    "$DataRoot\huggingface",
    "$DataRoot\qdrant",
    "$DataRoot\redis",
    "$DataRoot\pip-cache"
)

Write-Host "=== Data on D: ===" -ForegroundColor Cyan
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    Write-Host "  OK $d"
}

Set-Location $ProjectRoot
if (-not (Test-Path ".venv")) {
    Write-Host "Creating venv..."
    python -m venv .venv
}

$env:PIP_CACHE_DIR = "$DataRoot\pip-cache"
$env:HF_HOME = "$DataRoot\huggingface"
$env:TRANSFORMERS_CACHE = "$DataRoot\huggingface"
$env:SENTENCE_TRANSFORMERS_HOME = "$DataRoot\huggingface"

Write-Host "Installing Python deps (pip cache on D:)..."
.\.venv\Scripts\pip install -r requirements.txt

Write-Host "Downloading embeddings to D:\..."
.\.venv\Scripts\python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

& "$PSScriptRoot\copy_docs.ps1"

Write-Host ""
Write-Host "Done. Data: $DataRoot" -ForegroundColor Green
Write-Host "Next: .\scripts\start_local.ps1"
