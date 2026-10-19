@echo off
setlocal enabledelayedexpansion
title FraudShield Platform Runner

echo ========================================================
echo   Starting FraudShield - AI Deepfake & Scam Detector
echo ========================================================
echo.

:: 1. Detect Python executable
set "PYTHON_CMD=python"
if exist "%~dp0.venv_gpu\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0.venv_gpu\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
)

echo [1/4] Checking Ollama Service...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting local Ollama server in background...
    start "Ollama Server" /B ollama serve
    timeout /t 3 /nobreak >nul
) else (
    echo Ollama service is already running.
)

echo.
echo [2/4] Starting FraudShield Backend API on http://localhost:8000...
start "FraudShield Backend (Port 8000)" %PYTHON_CMD% app.py

echo.
echo [3/4] Starting FraudShield Frontend Dashboard on http://localhost:3000...
start "FraudShield Frontend (Port 3000)" %PYTHON_CMD% run_frontend.py

echo.
echo [4/4] Opening Web Dashboard in default browser...
timeout /t 3 /nobreak >nul
start http://localhost:3000

echo.
echo ========================================================
echo   FraudShield is up and running!
echo   - Web UI:     http://localhost:3000
echo   - Backend API: http://localhost:8000
echo   - API Docs:    http://localhost:8000/docs
echo   Run stop.bat to terminate both servers.
echo ========================================================
