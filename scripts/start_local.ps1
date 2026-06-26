# Local dev: infra in Docker, bot in Python venv
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$DataRoot = "D:\bars-support-bot-data"

Set-Location $ProjectRoot

Write-Host "Stopping Docker app (only ONE Telegram bot allowed)..." -ForegroundColor Yellow
docker compose --profile full stop app 2>$null

$env:DATA_ROOT = "D:/bars-support-bot-data"
$env:PIP_CACHE_DIR = "$DataRoot\pip-cache"
$env:HF_HOME = "$DataRoot\huggingface"
$env:TRANSFORMERS_CACHE = "$DataRoot\huggingface"
$env:SENTENCE_TRANSFORMERS_HOME = "$DataRoot\huggingface"
if (Test-Path "$DataRoot\huggingface\models--intfloat--multilingual-e5-base") {
    $env:HF_HUB_OFFLINE = "1"
}
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:QDRANT_URL = "http://127.0.0.1:6333"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:TELEGRAM_ENABLED = "true"

Write-Host "Starting DocHelper: http://127.0.0.1:8026 + Telegram (local)" -ForegroundColor Cyan
Write-Host "Models on: $DataRoot"
.\.venv\Scripts\python main.py
