@echo off
title EduQuest Pro - Online Question Bank
color 0b

:: Navigate to batch file folder
cd /d "%~dp0"

echo ======================================================================
echo          EDUQUEST PRO - QUAN LY VA THU THAP CAU HOI THI
echo      Ho tro: VioEdu, Trang Nguyen Toan, TIMO, HKIMO, ASMO
echo ======================================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Khong tim thay Python tren may tinh cua ban!
    echo Vui long cai dat Python 3.10 tro len tu: https://www.python.org
    echo Khi cai dat, nho tich vao o: "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: Run all-in-one launcher
python start_server.py

if %errorlevel% neq 0 (
    echo.
    echo [THONG BAO] Ung dung da dung.
    pause
)
