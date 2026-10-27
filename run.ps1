# IST 210 Lab 2 PowerShell Launcher
Set-Location $PSScriptRoot

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " IST 210 Lab 2 - Cloud Database CRUD Web Application" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan

$py = $null
if (Test-Path "C:\Program Files\Thonny\python.exe") {
    $py = "C:\Program Files\Thonny\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $py = "python"
} else {
    Write-Error "Python was not found. Please verify Python or Thonny is installed."
    exit 1
}

Write-Host "`nUsing Python: $py" -ForegroundColor Green
Write-Host "Starting web server on http://localhost:5000 ..." -ForegroundColor Green

& $py standalone_server.py
