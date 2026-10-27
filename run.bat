@echo off
title IST 210 Lab 2 CRUD Web Application
cd /d "%~dp0"

echo =====================================================================
echo  IST 210 Lab 2 - Cloud Database CRUD Web Application
echo =====================================================================
echo.

set "PY_EXE="

:: Check if Thonny Python exists
if exist "C:\Program Files\Thonny\python.exe" (
    set "PY_EXE=C:\Program Files\Thonny\python.exe"
)

:: Otherwise check PATH
if "%PY_EXE%"=="" (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PY_EXE=python"
)

if "%PY_EXE%"=="" (
    echo [ERROR] Python not found on this computer.
    echo Please make sure Python or Thonny is installed.
    echo.
    pause
    exit /b 1
)

echo Using Python at: "%PY_EXE%"
echo Starting web server...
echo.

"%PY_EXE%" standalone_server.py

echo.
echo Server has stopped.
pause
