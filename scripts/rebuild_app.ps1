# Rebuild ONLY app container — Ollama/Qdrant/Redis/models on D: are NOT touched
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

$env:DATA_ROOT = "D:/bars-support-bot-data"

Write-Host "=== Rebuild app only (no model download) ===" -ForegroundColor Cyan
Write-Host "Ollama model stays in D:\bars-support-bot-data\ollama"

docker compose --profile full stop app 2>$null
docker compose --profile full build app
docker compose --profile full up -d app

Write-Host ""
Write-Host "App: http://127.0.0.1:8026" -ForegroundColor Green
Write-Host "Do NOT run start_local.ps1 at the same time (Telegram Conflict 409)"
Write-Host "Check: docker compose logs app --tail 30"
