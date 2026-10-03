"""
EduQuest Pro - Chế độ Chia sẻ (Shared Mode)
=============================================
Script khởi động server cho phép nhiều người dùng truy cập từ xa.

Thay đổi so với start_server.py (local):
- Lắng nghe trên 0.0.0.0 (tất cả giao diện mạng) thay vì 127.0.0.1
- Không tự động mở trình duyệt (vì chạy trên máy chủ)
- Hiển thị địa chỉ IP LAN để kết nối nội bộ
- Tương thích với Cloudflare Tunnel để truy cập Internet

Cách dùng:
    python start_server_shared.py
"""

import os
import sys
import socket
import subprocess

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

PORT = 8000

def ensure_dependencies():
    """Cài thư viện core bắt buộc; thử cài optional (OCR/Playwright) nếu có thể."""
    # ── Core (bắt buộc) ────────────────────────────────────────────
    try:
        import fastapi, uvicorn, docx, pypdf, bs4, httpx, aiofiles
    except ImportError:
        print("-> Đang cài thư viện core (requirements.txt)...")
        req_core = os.path.join(ROOT_DIR, "requirements.txt")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", req_core])
        print("-> Cài core hoàn tất!")

    # ── Optional: OCR + Playwright (chỉ Python < 3.13) ────────────
    req_opt = os.path.join(ROOT_DIR, "requirements-optional.txt")
    if os.path.exists(req_opt):
        try:
            import rapidocr_onnxruntime, playwright
        except ImportError:
            print("-> Đang thử cài thư viện OCR/Playwright tùy chọn...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", req_opt],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print("-> Cài OCR/Playwright hoàn tất! Tính năng OCR và Auto-Hunter đầy đủ.")
            else:
                py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
                print(f"-> [!] Bỏ qua OCR/Playwright (Python {py_ver} chưa được hỗ trợ).")
                print(f"->     Tính năng OCR và Auto-Hunter sẽ bị tắt — các tính năng khác OK.")

def get_lan_ip():
    """Lấy địa chỉ IP LAN của máy chủ."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    ensure_dependencies()
    import uvicorn

    lan_ip = get_lan_ip()

    print("=" * 70)
    print("     EDUQUEST PRO - CHẾ ĐỘ CHIA SẺ (SHARED MODE)")
    print("     Mọi người dùng chung 1 ngân hàng câu hỏi")
    print("=" * 70)
    print(f"  -> Máy chủ đang lắng nghe tất cả kết nối mạng (0.0.0.0:{PORT})")
    print(f"")
    print(f"  [LOCAL]   Trên máy này:         http://localhost:{PORT}")
    print(f"  [LAN]     Trong mạng nội bộ:    http://{lan_ip}:{PORT}")
    print(f"  [INTERNET] Qua Cloudflare Tunnel: Xem hướng dẫn DEPLOY_GUIDE.md")
    print(f"")
    print(f"  LƯU Ý: Đảm bảo Firewall Windows cho phép port {PORT}")
    print(f"         (xem DEPLOY_GUIDE.md -> Bước 2)")
    print("=" * 70)
    print("  Nhấn Ctrl + C để dừng máy chủ.")
    print("=" * 70)

    # Chạy Uvicorn trên 0.0.0.0 để nhận kết nối từ tất cả IP
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",   # <-- Khác với start_server.py (127.0.0.1)
        port=PORT,
        reload=False,
        log_level="info"
    )
