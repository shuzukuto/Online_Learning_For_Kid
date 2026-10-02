import os
import sys
import time
import threading
import webbrowser
import subprocess

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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
        req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", req_path])
        print("-> Cài đặt thư viện hoàn tất!")

def open_browser():
    """Opens browser after server starts."""
    time.sleep(1.8)
    url = "http://localhost:8000"
    print(f"-> Đang mở trình duyệt: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    ensure_dependencies()
    import uvicorn

    print("=" * 66)
    print("        EDUQUEST PRO - QUẢN LÝ & THU THẬP CÂU HỎI THI")
    print("    Hỗ trợ: VioEdu, Trạng Nguyên Toán, TIMO, HKIMO, ASMO, SASMO")
    print("=" * 66)
    print("-> Máy chủ Web Dashboard: http://localhost:8000")
    print("-> Nhấn Ctrl + C để dừng máy chủ.")
    print("=" * 66)

    # Launch browser automatically in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start Uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
