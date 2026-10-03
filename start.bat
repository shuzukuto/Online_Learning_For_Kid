@echo off
chcp 65001 > nul
cd /d "%~dp0"
title EduQuest Pro

:MENU
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║           ⚡  EDUQUEST PRO — KHỞI ĐỘNG                      ║
echo  ║     Thu thập ^& Quản lý Ngân hàng Câu hỏi Thi Trực tuyến    ║
echo  ╠══════════════════════════════════════════════════════════════╣
echo  ║                                                              ║
echo  ║   [1]  Chỉ dùng một mình (localhost)                        ║
echo  ║        Mở trình duyệt tự động — nhanh nhất                  ║
echo  ║                                                              ║
echo  ║   [2]  Chia sẻ qua Cloudflare Tunnel — URL tạm thời         ║
echo  ║        Tạo link https://xxx.trycloudflare.com (miễn phí)    ║
echo  ║        URL thay đổi mỗi lần khởi động                       ║
echo  ║                                                              ║
echo  ║   [3]  Chia sẻ qua ngrok — URL CỐ ĐỊNH (miễn phí)          ║
echo  ║        Link https://xxx.ngrok-free.app không bao giờ đổi    ║
echo  ║        Yêu cầu: đã cấu hình ngrok (xem DEPLOY_GUIDE.md)     ║
echo  ║                                                              ║
echo  ║   [4]  Chia sẻ trong mạng LAN / WiFi nội bộ                 ║
echo  ║        Dùng chung trong nhà hoặc trường — không cần Internet ║
echo  ║                                                              ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
set /p CHOICE="  Nhập số lựa chọn (1/2/3/4): "

if "%CHOICE%"=="1" goto MODE_LOCAL
if "%CHOICE%"=="2" goto MODE_CLOUDFLARE
if "%CHOICE%"=="3" goto MODE_NGROK
if "%CHOICE%"=="4" goto MODE_LAN

echo  [!] Lựa chọn không hợp lệ. Vui lòng nhập 1, 2, 3 hoặc 4.
timeout /t 2 /nobreak > nul
goto MENU

:: ================================================================
:CHECK_PYTHON
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [LỖI] Không tìm thấy Python trên máy tính!
    echo  Cài đặt tại: https://www.python.org
    echo  Khi cài, nhớ tích vào ô: "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
goto :eof

:: ================================================================
:OPEN_FIREWALL
netsh advfirewall firewall add rule name="EduQuest Pro Port 8000" dir=in action=allow protocol=TCP localport=8000 > nul 2>&1
goto :eof

:: ================================================================
:MODE_LOCAL
cls
echo.
echo  ══════════════════════════════════════════
echo   [1] CHẾ ĐỘ CÁ NHÂN — localhost
echo  ══════════════════════════════════════════
echo.
call :CHECK_PYTHON
echo  [→] Khởi động server và mở trình duyệt...
echo  [→] Nhấn Ctrl+C để dừng.
echo.
python start_server.py
pause
goto MENU

:: ================================================================
:MODE_CLOUDFLARE
cls
echo.
echo  ══════════════════════════════════════════════════
echo   [2] CHẾ ĐỘ CHIA SẺ — Cloudflare Tunnel (URL tạm)
echo  ══════════════════════════════════════════════════
echo.
call :CHECK_PYTHON
call :OPEN_FIREWALL

:: Kiểm tra cloudflared
where cloudflared > nul 2>&1
if %errorlevel% neq 0 (
    if not exist "%~dp0cloudflared.exe" (
        echo  [→] Đang tải cloudflared.exe (cần Internet)...
        powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%~dp0cloudflared.exe' -UseBasicParsing"
        if %errorlevel% neq 0 (
            echo  [LỖI] Tải thất bại. Kiểm tra kết nối Internet.
            pause
            goto MENU
        )
        echo  [OK] Tải xong: cloudflared.exe
    )
    set CLOUDFLARED_CMD=%~dp0cloudflared.exe
) else (
    set CLOUDFLARED_CMD=cloudflared
)

echo  [→] Khởi động EduQuest Server...
start "EduQuest Server" python start_server_shared.py
echo  [→] Đợi server sẵn sàng (5 giây)...
timeout /t 5 /nobreak > nul

echo.
echo  ══════════════════════════════════════════════════
echo   Cloudflare đang tạo URL...
echo   URL sẽ hiện bên dưới dạng: https://xxx.trycloudflare.com
echo   Copy URL đó và chia sẻ cho mọi người!
echo   Nhấn Ctrl+C để dừng tunnel.
echo  ══════════════════════════════════════════════════
echo.
%CLOUDFLARED_CMD% tunnel --url http://localhost:8000
pause
goto MENU

:: ================================================================
:MODE_NGROK
cls
echo.
echo  ══════════════════════════════════════════════════
echo   [3] CHẾ ĐỘ CHIA SẺ — ngrok URL CỐ ĐỊNH
echo  ══════════════════════════════════════════════════
echo.
call :CHECK_PYTHON
call :OPEN_FIREWALL

:: Kiểm tra ngrok
set NGROK_CMD=
where ngrok > nul 2>&1
if %errorlevel% equ 0 (
    set NGROK_CMD=ngrok
) else if exist "%~dp0ngrok.exe" (
    set NGROK_CMD=%~dp0ngrok.exe
) else (
    echo  [LỖI] Không tìm thấy ngrok.exe!
    echo.
    echo  Hướng dẫn cài ngrok:
    echo   1. Tải tại: https://ngrok.com/download
    echo   2. Giải nén ngrok.exe vào thư mục này: %~dp0
    echo   3. Chạy lần đầu: ngrok config add-authtoken ^<token-cua-ban^>
    echo   4. Lấy static domain tại: https://dashboard.ngrok.com/domains
    echo   5. Xem chi tiết: DEPLOY_GUIDE.md
    echo.
    pause
    goto MENU
)

echo.
set /p NGROK_DOMAIN="  Nhập static domain ngrok của bạn (vd: abc-xyz.ngrok-free.app): "
if "%NGROK_DOMAIN%"=="" (
    echo  [LỖI] Chưa nhập domain. Quay lại menu.
    timeout /t 2 /nobreak > nul
    goto MENU
)

echo.
echo  [→] Khởi động EduQuest Server...
start "EduQuest Server" python start_server_shared.py
echo  [→] Đợi server sẵn sàng (4 giây)...
timeout /t 4 /nobreak > nul

echo.
echo  ══════════════════════════════════════════════════
echo   URL CỐ ĐỊNH: https://%NGROK_DOMAIN%
echo   Chia sẻ URL này cho mọi người — không bao giờ thay đổi!
echo   Nhấn Ctrl+C để dừng tunnel.
echo  ══════════════════════════════════════════════════
echo.
%NGROK_CMD% http --domain=%NGROK_DOMAIN% 8000
pause
goto MENU

:: ================================================================
:MODE_LAN
cls
echo.
echo  ══════════════════════════════════════════════════
echo   [4] CHẾ ĐỘ CHIA SẺ — Mạng LAN / WiFi nội bộ
echo  ══════════════════════════════════════════════════
echo.
call :CHECK_PYTHON
call :OPEN_FIREWALL

echo  [→] Khởi động EduQuest Server (chế độ chia sẻ LAN)...
echo  [→] Địa chỉ IP LAN sẽ hiện bên dưới sau khi server khởi động.
echo  [→] Nhấn Ctrl+C để dừng.
echo.
python start_server_shared.py
pause
goto MENU
