@echo off
chcp 65001 >nul
title seovisi
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo.
  echo  Python bulunamadi. https://www.python.org/downloads/ adresinden Python 3 kurun
  echo  ve kurulumda "Add python.exe to PATH" kutusunu isaretleyin.
  echo.
  pause
  exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" || (echo Python 3.8 veya daha yeni bir surum gerekli. & pause & exit /b 1)
%PY% app.py
if errorlevel 1 pause
