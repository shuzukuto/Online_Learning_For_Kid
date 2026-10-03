# 🚀 Hướng dẫn Chia sẻ EduQuest Pro cho Nhiều Người Dùng

> **Mục tiêu:** Mọi người truy cập cùng 1 ngân hàng câu hỏi qua Internet, không cần cài đặt gì trên máy người dùng.

---

## 📋 Tổng quan Kiến trúc

```
Người dùng A (điện thoại/máy tính bất kỳ)
        ↓ HTTPS
Người dùng B ──→ https://xxxxx.trycloudflare.com ──→ [Máy chủ Windows]
        ↑                                                    ↓
Người dùng C                                        EduQuest Pro :8000
                                                          ↓
                                                  data/questions.db (chung)
```

**Cloudflare Tunnel** tạo đường hầm bảo mật từ máy bạn ra Internet — **miễn phí, không cần IP tĩnh, không cần mở router**.

---

## ⚡ Cách Nhanh Nhất (1 file chạy tất cả)

### Bước 1: Chạy file `run_shared.bat`

1. **Chuột phải** vào `run_shared.bat` → **"Run as administrator"**
2. Script tự động:
   - Tải `cloudflared.exe` (nếu chưa có)
   - Mở port 8000 trong Windows Firewall
   - Khởi động EduQuest Pro server
   - Tạo Cloudflare Tunnel

### Bước 2: Lấy URL và chia sẻ

Sau khi chạy, màn hình sẽ hiển thị dạng:
```
Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):
https://abc-def-ghi.trycloudflare.com
```

**Copy URL đó** và gửi cho mọi người — họ mở trình duyệt là dùng được ngay!

> ⚠️ **Lưu ý:** URL thay đổi mỗi lần khởi động lại. Nếu muốn URL cố định → xem mục "URL cố định" bên dưới.

---

## 📖 Hướng dẫn Chi tiết Từng Bước

### Bước 1: Cài đặt Cloudflare Tunnel thủ công (nếu script gặp lỗi)

1. Tải `cloudflared-windows-amd64.exe` tại:
   **https://github.com/cloudflare/cloudflared/releases/latest**

2. Đổi tên thành `cloudflared.exe` và đặt vào thư mục dự án:
   ```
   G:\Mina\Online_Learning\cloudflared.exe
   ```

### Bước 2: Mở Firewall Windows cho port 8000

Mở **PowerShell với quyền Admin** và chạy:
```powershell
netsh advfirewall firewall add rule name="EduQuest Pro" dir=in action=allow protocol=TCP localport=8000
```

### Bước 3: Khởi động Server Chia sẻ

```powershell
python start_server_shared.py
```

Khác với `start_server.py`, script này lắng nghe trên `0.0.0.0` — chấp nhận kết nối từ mọi IP.

### Bước 4: Tạo Cloudflare Tunnel

Mở **cửa sổ PowerShell mới** và chạy:
```powershell
.\cloudflared.exe tunnel --url http://localhost:8000
```

Chờ vài giây, URL sẽ xuất hiện. Copy và chia sẻ!

---

## 🔗 URL Cố định (Nâng cao)

Nếu muốn URL không thay đổi (ví dụ: `https://eduquest.yourdomain.com`):

1. Đăng ký tài khoản Cloudflare miễn phí tại **https://cloudflare.com**
2. Đăng nhập cloudflared: `.\cloudflared.exe tunnel login`
3. Tạo tunnel vĩnh viễn: `.\cloudflared.exe tunnel create eduquest`
4. Tạo subdomain cố định (cần có domain riêng)

---

## 🌐 Kết nối Trong Mạng Nội bộ (LAN — không cần Internet)

Nếu mọi người trong cùng WiFi/mạng công ty, dùng địa chỉ IP LAN:

1. Khởi động `start_server_shared.py`
2. Màn hình hiển thị: `[LAN] Trong mạng nội bộ: http://192.168.x.x:8000`
3. Chia sẻ địa chỉ đó — **không cần Cloudflare**

---

## 🔧 Tự động Khởi động Khi Bật Máy (Windows Task Scheduler)

Để server tự chạy khi Windows khởi động mà không cần đăng nhập:

1. Mở **Task Scheduler** (Tìm kiếm Windows)
2. **Create Basic Task** → Đặt tên: `EduQuest Pro Shared`
3. **Trigger:** When the computer starts
4. **Action:** Start a program
   - Program: `python`
   - Arguments: `start_server_shared.py`
   - Start in: `G:\Mina\Online_Learning`
5. Trong **General tab** → Chọn **"Run whether user is logged on or not"**

---

## 🛡️ Lưu ý Bảo mật

| Vấn đề | Giải pháp |
|--------|-----------|
| Ai cũng có thể sửa/xóa câu hỏi | Thêm xác thực đăng nhập (nhắn để thực hiện) |
| URL Cloudflare thay đổi mỗi lần | Dùng URL cố định (cần domain) hoặc thông báo URL mới |
| Máy tắt = mọi người mất kết nối | Bật **Task Scheduler** hoặc chạy 24/7 |
| Dữ liệu mất nếu ổ cứng hỏng | Thêm backup tự động vào Google Drive |

---

## ❓ Khắc phục Sự cố

**Lỗi "Access denied" khi chạy .bat:**
→ Chuột phải → "Run as administrator"

**Cloudflare không tạo được URL:**
→ Kiểm tra kết nối Internet, thử chạy lại

**Người khác không vào được:**
→ Kiểm tra server đang chạy: mở `http://localhost:8000` trên máy chủ
→ Kiểm tra Firewall đã mở port 8000

**Extension không gửi được dữ liệu về server:**
→ Extension hiện hardcode `localhost:8000` — cần cập nhật để nhập URL động (nhắn để thực hiện)
