# Demarrage API (utilise le Python du venv si present)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Test-Path "..\venv\Scripts\python.exe") {
    $py = "..\venv\Scripts\python.exe"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $py = ".\venv\Scripts\python.exe"
} else {
    $py = "python"
}

Write-Host "Demarrage API sur http://127.0.0.1:8000"
Write-Host "Swagger: http://127.0.0.1:8000/docs"
Write-Host "Commande: $py -m uvicorn main:app --reload --host 127.0.0.1 --port 8000"

& $py -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
