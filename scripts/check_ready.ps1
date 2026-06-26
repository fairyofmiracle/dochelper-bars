# Check if stack is ready to run the bot
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "=== DocHelper readiness ===" -ForegroundColor Cyan

Write-Host "`n[Docker]"
docker compose ps

Write-Host "`n[Ollama models on D:]"
docker compose exec ollama ollama list

Write-Host "`n[Docs]"
Get-ChildItem data\docs -Filter *.docx -ErrorAction SilentlyContinue | Select-Object Name

Write-Host "`n---"
Write-Host "Model is READY when 'ollama list' shows qwen2.5:7b-instruct with ~4.7 GB"
Write-Host "Then run: .\scripts\start_local.ps1"
