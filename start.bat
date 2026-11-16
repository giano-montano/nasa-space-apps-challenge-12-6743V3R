@echo off
title Drift - visor SPHEREx (NASA Space Apps 2026)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual e instalando dependencias...
  python -m venv .venv || (echo Necesitas Python 3.10+ instalado. & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
)
".venv\Scripts\python.exe" run_app.py
pause
