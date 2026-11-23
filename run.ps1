# IssueSnap Quick Start Script (PowerShell)
# ============================================
# Run this script to set up and start IssueSnap in one go.

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  IssueSnap - Quick Start" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Create virtual environment
if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "[1/6] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
} else {
    Write-Host "[1/6] Virtual environment exists." -ForegroundColor Green
}

$python = ".\venv\Scripts\python.exe"
$pip = ".\venv\Scripts\pip.exe"

# 2. Install dependencies
Write-Host "[2/6] Installing dependencies..." -ForegroundColor Yellow
& $pip install --upgrade pip 2>&1 | Out-Null
& $pip install -r requirements.txt 2>&1 | Out-Null
Write-Host "      Dependencies installed." -ForegroundColor Green

# 3. Create .env from example
if (-not (Test-Path ".env")) {
    Write-Host "[3/6] Creating .env file..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "      Edit .env with your MySQL credentials if using MySQL." -ForegroundColor Yellow
} else {
    Write-Host "[3/6] .env file exists." -ForegroundColor Green
}

# 4. Run migrations
Write-Host "[4/6] Running migrations..." -ForegroundColor Yellow
& $python manage.py migrate --noinput 2>&1 | Out-Null
Write-Host "      Migrations complete." -ForegroundColor Green

# 5. Seed data
Write-Host "[5/6] Seeding categories and demo users..." -ForegroundColor Yellow
& $python scripts\seed.py 2>&1 | Out-Null
Write-Host "      Data seeded." -ForegroundColor Green

# 6. Start server
Write-Host "[6/6] Starting development server..." -ForegroundColor Yellow
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  IssueSnap is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n  App URL:    http://127.0.0.1:8000/" -ForegroundColor White
Write-Host "  Admin Panel: http://127.0.0.1:8000/admin-panel/dashboard/" -ForegroundColor White
Write-Host "`n  Demo Admin:    admin@issuesnap.com / AdminPass2026!" -ForegroundColor White
Write-Host "  Demo Citizen:   citizen@issuesnap.com / CitizenPass2026!" -ForegroundColor White
Write-Host "`n  Press Ctrl+C to stop.`n" -ForegroundColor Gray

& $python manage.py runserver 127.0.0.1:8000
