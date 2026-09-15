$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot '..')

Write-Host 'Building and starting red-tide-risk-web...'
docker compose up -d --build

Write-Host ''
Write-Host 'Deployment finished.'
Write-Host 'Local URL: http://127.0.0.1:8080/red-tide-risk/'
Write-Host 'Health:    http://127.0.0.1:8080/healthz'
