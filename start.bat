@echo off
setlocal enabledelayedexpansion
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
echo  ╠══════════════════════════════════════════════════════════════╣
echo  ║                                                              ║
echo  ║   [5]  🐳 Docker — Chạy nền, tự khởi động khi bật máy       ║
echo  ║        Không cần Python — server chạy 24/7 ổn định nhất     ║
echo  ║        Yêu cầu: Docker Desktop đã cài                       ║
echo  ║                                                              ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.
set /p CHOICE="  Nhập số lựa chọn (1/2/3/4/5): "

if "%CHOICE%"=="1" goto MODE_LOCAL
if "%CHOICE%"=="2" goto MODE_CLOUDFLARE
if "%CHOICE%"=="3" goto MODE_NGROK
if "%CHOICE%"=="4" goto MODE_LAN
if "%CHOICE%"=="5" goto MODE_DOCKER


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

:: ================================================================
:MODE_DOCKER
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║   🐳  EDUQUEST PRO — DOCKER MODE                            ║
echo  ║   Server chạy nền 24/7, tự restart khi crash/reboot        ║
echo  ╠══════════════════════════════════════════════════════════════╣
echo  ║                                                              ║
echo  ║   [A]  Lần đầu: Build image ^& Khởi động (mất 5-10 phút)    ║
echo  ║   [B]  Khởi động (image đã build sẵn)                       ║
echo  ║   [C]  Dừng container                                       ║
echo  ║   [D]  Xem trạng thái ^& IP LAN                             ║
echo  ║   [E]  Xem log realtime                                     ║
echo  ║   [0]  Quay lại menu chính                                  ║
echo  ║                                                              ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

:: Kiểm tra Docker Desktop đã cài chưa
docker --version > nul 2>&1
if %errorlevel% neq 0 (
    echo  [LỖI] Không tìm thấy Docker trên máy!
    echo.
    echo  Cài Docker Desktop tại: https://www.docker.com/products/docker-desktop
    echo  Sau khi cài xong, khởi động lại máy rồi chạy lại file này.
    echo.
    pause
    goto MENU
)

set /p DCHOICE="  Nhập lựa chọn (A/B/C/D/E/0): "

if /i "%DCHOICE%"=="A" goto DOCKER_BUILD_START
if /i "%DCHOICE%"=="B" goto DOCKER_START
if /i "%DCHOICE%"=="C" goto DOCKER_STOP
if /i "%DCHOICE%"=="D" goto DOCKER_STATUS
if /i "%DCHOICE%"=="E" goto DOCKER_LOGS
if "%DCHOICE%"=="0"   goto MENU
echo  [!] Lựa chọn không hợp lệ.
timeout /t 2 /nobreak > nul
goto MODE_DOCKER

:DOCKER_BUILD_START
cls
echo.
echo  ══════════════════════════════════════════════════════
echo   🐳 [A] BUILD IMAGE ^& KHỞI ĐỘNG LẦN ĐẦU
echo  ══════════════════════════════════════════════════════
echo.
echo  [→] Đang build Docker image EduQuest Pro...
echo      (Lần đầu mất 5-15 phút tùy tốc độ mạng — tải ~1.5GB)
echo.
call :OPEN_FIREWALL
docker compose build
if %errorlevel% neq 0 (
    echo.
    echo  [LỖI] Build thất bại! Kiểm tra:
    echo    - Docker Desktop đang chạy?
    echo    - File Dockerfile có trong thư mục này không?
    pause
    goto MODE_DOCKER
)
echo.
echo  [→] Build xong! Đang khởi động container...
docker compose up -d
if %errorlevel% neq 0 (
    echo  [LỖI] Khởi động thất bại!
    pause
    goto MODE_DOCKER
)
echo.
echo  ══════════════════════════════════════════════════════
echo   ✅ EduQuest Pro đang chạy trong Docker!
echo.
call :SHOW_DOCKER_URL
echo.
echo   Container tự động khởi động lại khi máy reboot.
echo   Dùng tùy chọn [2] hoặc [3] ở menu chính để tạo URL chia sẻ.
echo  ══════════════════════════════════════════════════════
pause
goto MODE_DOCKER

:DOCKER_START
cls
echo.
echo  ══════════════════════════════════════════
echo   🐳 [B] KHỞI ĐỘNG CONTAINER
echo  ══════════════════════════════════════════
echo.
call :OPEN_FIREWALL
docker compose up -d
if %errorlevel% neq 0 (
    echo.
    echo  [LỖI] Khởi động thất bại!
    echo  Nếu chưa build image, hãy chọn [A] trước.
    pause
    goto MODE_DOCKER
)
echo.
echo  ✅ Container đang chạy!
call :SHOW_DOCKER_URL
pause
goto MODE_DOCKER

:DOCKER_STOP
cls
echo.
echo  ══════════════════════════════════════════
echo   🐳 [C] DỪNG CONTAINER
echo  ══════════════════════════════════════════
echo.
docker compose down
echo.
echo  ✅ Container đã dừng. Dữ liệu trong data/ vẫn được giữ nguyên.
pause
goto MODE_DOCKER

:DOCKER_STATUS
cls
echo.
echo  ══════════════════════════════════════════
echo   🐳 [D] TRẠNG THÁI CONTAINER
echo  ══════════════════════════════════════════
echo.
docker compose ps
echo.
call :SHOW_DOCKER_URL
echo.
echo  Dung lượng image:
docker images eduquest-pro --format "  Image: {{.Repository}}:{{.Tag}} — Size: {{.Size}}"
pause
goto MODE_DOCKER

:DOCKER_LOGS
cls
echo.
echo  ══════════════════════════════════════════
echo   🐳 [E] LOG REALTIME (Ctrl+C để thoát)
echo  ══════════════════════════════════════════
echo.
docker compose logs -f --tail=50
pause
goto MODE_DOCKER

:: ── Helper: Hiện địa chỉ truy cập ─────────────
:SHOW_DOCKER_URL
echo.
echo   Truy cập EduQuest Pro tại:
echo     Local:  http://localhost:8000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    set IP=!IP: =!
    echo     LAN:    http://!IP!:8000
    goto :show_done
)
:show_done
echo.
goto :eof
