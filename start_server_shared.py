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
    """Checks and installs missing dependencies if needed."""
    try:
        import fastapi
        import uvicorn
        import docx
        import pypdf
        import bs4
        import httpx
    except ImportError:
        print("-> Đang tự động cài đặt các thư viện cần thiết (requirements.txt)...")
        req_path = os.path.join(ROOT_DIR, "requirements.txt")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", req_path])
        print("-> Cài đặt thư viện hoàn tất!")

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
