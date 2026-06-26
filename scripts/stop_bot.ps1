# Stop all bot instances (fix Telegram Conflict 409)
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Stopping Docker app..."
docker compose --profile full stop app 2>$null

Write-Host "If start_local.ps1 is running — press Ctrl+C in that terminal."
Write-Host "Then start ONE mode:"
Write-Host "  Local:  .\scripts\start_local.ps1"
Write-Host "  Docker: .\scripts\rebuild_app.ps1"
