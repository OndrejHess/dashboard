@echo off
title Vyrobni Dashboard (FastAPI + SQL)
echo ===================================================
echo   Spousteni Vyrobniho Dashboardu (FastAPI + SQL)
echo ===================================================

cd /d "C:\users\ondrej.novak\dashboard\backend"

echo Port: 8000
echo Otevrete v prohlizeci: http://localhost:8000
echo (Pro ukonceni stisknete CTRL+C)
echo.

"C:\users\ondrej.novak\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
