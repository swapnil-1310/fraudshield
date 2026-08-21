@echo off
setlocal
echo ========================================================
echo   Starting FraudShield-SEBI Pro Unified Platform
echo   Dual Visual Deepfake & Audio SEBI Compliance System
echo ========================================================

set "ROOT=%~dp0"

:: Start FastAPI Backend on Port 8000
start "FraudShield Backend API" /D "%ROOT%backend" cmd /k "python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000"

:: Start React Vite Frontend on Port 3000
start "FraudShield Frontend UI" /D "%ROOT%frontend" cmd /k "npm run dev"

echo.
echo Platform successfully launched!
echo Backend API: http://127.0.0.1:8000
echo Frontend UI: http://localhost:3000
echo.
endlocal
