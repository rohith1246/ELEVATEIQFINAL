# Quick 1-Click Deployment Script for Windows PowerShell
Param(
    [string]$msg = "update: platform enhancement"
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         ElevateIQ 1-Click Deployment Pipeline              " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Staging and Committing Code Changes..." -ForegroundColor Yellow
git add .
git commit -m "$msg"

Write-Host "`n[2/3] Pushing to GitHub (origin main)..." -ForegroundColor Yellow
git push origin main

Write-Host "`n[3/3] Deployment Ready!" -ForegroundColor Green
Write-Host "To trigger instant deployment to Hostinger VPS via Terraform:" -ForegroundColor White
Write-Host "  cd terraform_hostinger" -ForegroundColor Yellow
Write-Host "  terraform apply -auto-approve" -ForegroundColor Yellow
Write-Host "============================================================`n" -ForegroundColor Cyan
