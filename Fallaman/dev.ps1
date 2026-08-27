#Requires -Version 5.1
<#
.SYNOPSIS
  Lance Fallaman dans Docker, comme `make dev` sur Gabomazone.

.EXAMPLES
  .\dev.ps1
  .\dev.ps1 prod
  .\dev.ps1 down
  .\dev.ps1 logs
  .\dev.ps1 seed
  .\dev.ps1 superuser
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("dev", "prod", "down", "logs", "ps", "migrate", "seed", "shell", "superuser", "test", "clean", "build")]
    [string]$Command = "dev"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$ComposeDev = @("compose", "-f", "docker-compose.dev.yml")
$ComposeProd = @("compose")

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker n'est pas installe ou pas dans le PATH."
    }
    docker info 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop n'est pas demarre. Ouvrez Docker Desktop puis relancez .\dev.ps1"
    }
}

Assert-Docker

switch ($Command) {
    "dev" {
        Write-Host ">>> Fallaman (dev) — http://localhost:8000" -ForegroundColor Cyan
        Write-Host ">>> Code OTP de developpement : 123456"
        docker @ComposeDev up --build
    }
    "prod" {
        Write-Host ">>> Fallaman (prod locale) — http://localhost:8000" -ForegroundColor Cyan
        docker @ComposeProd up -d --build
        docker @ComposeProd ps
    }
    "build" {
        docker @ComposeDev build --no-cache
    }
    "down" {
        docker @ComposeDev down
        docker @ComposeProd down
    }
    "logs" {
        docker @ComposeDev logs -f
    }
    "ps" {
        docker @ComposeDev ps
    }
    "migrate" {
        docker @ComposeDev exec web python manage.py migrate
    }
    "seed" {
        docker @ComposeDev exec web python manage.py seed_demo --with-accounts
    }
    "shell" {
        docker @ComposeDev exec web python manage.py shell
    }
    "superuser" {
        docker @ComposeDev run --rm web python manage.py createsuperuser
    }
    "test" {
        docker @ComposeDev exec web python -m pytest
    }
    "clean" {
        docker @ComposeDev down -v
        docker @ComposeProd down -v
        Write-Host ">>> Conteneurs et volumes Fallaman supprimes." -ForegroundColor Yellow
    }
}
