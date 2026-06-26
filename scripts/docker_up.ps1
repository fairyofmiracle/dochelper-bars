# Поднять только Qdrant + Redis + Ollama (данные на D:)
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

$env:DATA_ROOT = "D:/bars-support-bot-data"

Write-Host "Docker: qdrant + redis + ollama -> D:\bars-support-bot-data" -ForegroundColor Cyan
docker compose down 2>$null
docker compose up -d qdrant redis ollama

Write-Host "Ждём Ollama (10 сек)..."
Start-Sleep -Seconds 10

Write-Host "Скачиваем LLM на D:\bars-support-bot-data\ollama ..."
docker compose exec ollama ollama pull qwen2.5:7b-instruct

Write-Host "`nГотово. Запуск бота локально:" -ForegroundColor Green
Write-Host "  .\scripts\setup_d_drive.ps1   # один раз"
Write-Host "  .\scripts\start_local.ps1"
