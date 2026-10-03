@echo off
chcp 65001 > nul
title EduQuest Pro - Shared Mode Server

echo ========================================================
echo   EDUQUEST PRO - KHOI DONG CHE DO CHIA SE
echo ========================================================
echo.

:: Kiểm tra cloudflared đã cài chưa
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo [BUOC 1] Tai cloudflared.exe...
    echo Dang tai Cloudflare Tunnel...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe'"
    echo Tai xong! File cloudflared.exe da duoc tao.
) else (
    echo [OK] cloudflared da duoc cai dat.
)

echo.
echo [BUOC 2] Mo port 8000 trong Windows Firewall...
netsh advfirewall firewall add rule name="EduQuest Pro Port 8000" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
echo [OK] Firewall da mo port 8000.

echo.
echo [BUOC 3] Khoi dong EduQuest Pro Server (Shared Mode)...
echo Server se chay tai: http://localhost:8000
echo Nhan Ctrl+C de dung.
echo.

start "EduQuest Server" python start_server_shared.py

echo [BUOC 4] Doi server khoi dong (5 giay)...
timeout /t 5 /nobreak > nul

echo.
echo [BUOC 4] Khoi dong Cloudflare Tunnel...
echo Cloudflare se cap URL mien phi (https://xxxxx.trycloudflare.com)
echo URL nay se hien thi ben duoi. Chia se URL do cho moi nguoi!
echo.
echo Nhan Ctrl+C de dung Tunnel.
echo ========================================================

cloudflared tunnel --url http://localhost:8000

pause
