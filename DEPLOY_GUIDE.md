# 🚀 Hướng dẫn Chia sẻ EduQuest Pro cho Nhiều Người Dùng

> **Mục tiêu:** Mọi người truy cập cùng 1 ngân hàng câu hỏi qua Internet, không cần cài đặt gì trên máy người dùng.

---

## 📋 Tổng quan Kiến trúc

### Sơ đồ luồng dữ liệu đầy đủ

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INTERNET (HTTPS / TLS)                           │
└─────────────────────────────────────────────────────────────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
  👩 Người dùng A          👨 Người dùng B          👦 Người dùng C
  (Trình duyệt Web)        (Extension Chrome)       (Điện thoại)
  xem / tìm câu hỏi        bắt + gửi câu hỏi        xem đề thi
         │                        │                        │
         └──────────────┬─────────┘────────────────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │   Cloudflare Network (CDN)   │  ← HTTPS miễn phí, che giấu IP thật
         │  https://abc.trycloudflare.  │     của máy chủ, chống DDoS cơ bản
         │           com               │
         └──────────────────────────────┘
                        │ Tunnel (mã hóa TLS)
                        ▼
         ┌──────────────────────────────┐
         │     cloudflared.exe          │  ← Chạy trên máy chủ Windows,
         │   (Cloudflare Tunnel agent)  │     tạo kết nối ra ngoài (outbound),
         └──────────────────────────────┘     KHÔNG cần mở port router
                        │ HTTP nội bộ (localhost)
                        ▼
         ┌──────────────────────────────┐
         │   EduQuest Pro (FastAPI)     │  ← start_server_shared.py
         │   host: 0.0.0.0  port: 8000 │     Python + Uvicorn
         │                              │
         │  /api/questions  (REST API)  │
         │  /               (Web UI)    │
         └──────────────────────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │   data/questions.db          │  ← SQLite — 1 file duy nhất,
         │   (SQLite Database)          │     tất cả người dùng đọc/ghi chung
         │                              │
         │   data/media/                │  ← Ảnh đề thi lưu cục bộ
         └──────────────────────────────┘
```

---

### Vai trò từng thành phần

| Thành phần | File | Vai trò |
|------------|------|---------|
| **Web Dashboard** | `frontend/` | Giao diện quản lý câu hỏi — chạy trên trình duyệt người dùng |
| **FastAPI Server** | `backend/app.py` | Xử lý API, phục vụ giao diện web, đọc/ghi database |
| **SQLite Database** | `data/questions.db` | Lưu trữ **toàn bộ** câu hỏi — 1 file chung cho mọi người |
| **Shared Mode Script** | `start_server_shared.py` | Khởi động server lắng nghe `0.0.0.0` (thay vì `127.0.0.1`) |
| **Cloudflare Tunnel** | `cloudflared.exe` | Tạo đường hầm HTTPS từ máy cục bộ ra Internet |
| **Chrome Extension** | `extension/` | Bắt câu hỏi từ web và gửi về server qua URL đã cấu hình |

---

### So sánh các phương án kết nối

| Phương án | Phạm vi | Yêu cầu | Độ phức tạp | Chi phí |
|-----------|---------|---------|-------------|---------|
| **Localhost** (mặc định) | Chỉ 1 máy | Không có | ⭐ Đơn giản nhất | Miễn phí |
| **LAN / WiFi nội bộ** | Cùng mạng nhà/trường | Chạy `start_server_shared.py` | ⭐⭐ | Miễn phí |
| **Cloudflare Tunnel** | Toàn Internet | `cloudflared.exe` + Internet | ⭐⭐⭐ | **Miễn phí** |
| **VPS / Cloud Server** | Toàn Internet, 24/7 | Thuê server riêng | ⭐⭐⭐⭐ | ~\$5–10/tháng |

> 💡 **Hướng dẫn này tập trung vào Cloudflare Tunnel** — phương án tốt nhất cho nhóm nhỏ đến vừa (10–100 người) vì miễn phí, dễ dùng và bảo mật tốt.

---

### Luồng dữ liệu khi Extension gửi câu hỏi

```
Người dùng làm bài trên VioEdu / Trạng Nguyên...
         │
         ▼
  [Extension Content Script]
  Bắt câu hỏi từ DOM / Network Request
         │
         ▼
  [Extension Background Script]
  Đọc server URL từ chrome.storage.sync
  (mặc định: http://localhost:8000)
  (shared:    https://abc.trycloudflare.com)
         │ POST /api/questions/bulk
         ▼
  [EduQuest Pro API]  ←── tất cả người dùng cùng ghi vào đây
         │
         ▼
  [data/questions.db]  ←── câu hỏi được lưu, dedup, FTS5 index
```

**Cloudflare Tunnel** tạo đường hầm bảo mật từ máy bạn ra Internet — **miễn phí, không cần IP tĩnh, không cần cấu hình router**.

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

## 🆓 URL Cố định MIỄN PHÍ — Không Cần Domain (ngrok)

> **Dành cho:** Người không có domain riêng nhưng muốn URL không đổi.  
> **Kết quả:** URL cố định dạng `https://xxxxx.ngrok-free.app` — **miễn phí vĩnh viễn, không bao giờ thay đổi**.

---

### So sánh nhanh: Cloudflare Tunnel vs ngrok Free

| | Cloudflare Tunnel (URL ngẫu nhiên) | **ngrok Free Static** | Cloudflare Tunnel (URL cố định) |
|--|--|--|--|
| **Chi phí** | Miễn phí | **Miễn phí** | Miễn phí |
| **Cần domain?** | Không | **Không** | ✅ Cần domain |
| **URL cố định?** | ❌ Thay đổi mỗi lần | **✅ Cố định mãi mãi** | ✅ Cố định |
| **Tốc độ setup** | 1 phút | **5 phút** | 30+ phút |
| **Giới hạn** | Không | 1 tunnel, 1 static URL | Không |

→ **Nếu không có domain: dùng ngrok Free là lựa chọn tốt nhất.**

---

### Bước 1 — Đăng ký tài khoản ngrok (miễn phí)

1. Truy cập **https://ngrok.com** → nhấn **Sign up for free**
2. Đăng ký bằng Google / GitHub / email
3. Sau khi đăng nhập, vào **Dashboard → Getting Started → Your Authtoken**
4. Copy **Authtoken** — dạng: `2abc123XYZ_xxxxxxxxxxxxxxxxxxxxxxxx`

---

### Bước 2 — Tải và cài ngrok

1. Tại **Dashboard → Getting Started → Download**, tải file `ngrok-v3-stable-windows-amd64.zip`  
   Hoặc tải trực tiếp: **https://ngrok.com/download**

2. Giải nén → lấy file `ngrok.exe` → đặt vào thư mục dự án:
   ```
   G:\Mina\Online_Learning\ngrok.exe
   ```

3. Mở PowerShell tại thư mục dự án, chạy lệnh cài Authtoken:
   ```powershell
   .\ngrok.exe config add-authtoken <AUTHTOKEN-CUA-BAN>
   ```
   Ví dụ:
   ```powershell
   .\ngrok.exe config add-authtoken 2abc123XYZ_xxxxxxxxxxxxxxxxxxxxxxxx
   ```
   Màn hình hiện `Authtoken saved to configuration file` → thành công ✅

---

### Bước 3 — Lấy URL cố định miễn phí

1. Đăng nhập ngrok Dashboard tại **https://dashboard.ngrok.com**
2. Vào menu **Cloud Edge → Domains** (hoặc **Static Domains**)
3. Nhấn **New Domain** → ngrok tự tạo cho bạn 1 domain cố định miễn phí, ví dụ:
   ```
   flying-octopus-clearly.ngrok-free.app
   ```
4. **Copy domain đó** — đây là URL cố định của bạn mãi mãi

---

### Bước 4 — Tạo `run_ngrok_fixed.bat` để chạy 1-click

Tạo file `run_ngrok_fixed.bat` trong thư mục dự án:

```batch
@echo off
chcp 65001 > nul
title EduQuest Pro - ngrok Fixed URL

echo [1] Khoi dong EduQuest Server...
start "EduQuest Server" python start_server_shared.py

echo [2] Doi server san sang (4 giay)...
timeout /t 4 /nobreak > nul

echo [3] Ket noi ngrok Static Domain...
echo Thay "flying-octopus-clearly.ngrok-free.app" bang domain cua ban!
.\ngrok.exe http --domain=flying-octopus-clearly.ngrok-free.app 8000
pause
```

> ⚠️ **Thay `flying-octopus-clearly.ngrok-free.app`** bằng domain thật bạn lấy ở Bước 3.

---

### Bước 5 — Chạy và lấy URL

1. **Chuột phải** vào `run_ngrok_fixed.bat` → **Run as administrator**
2. Chờ vài giây, cửa sổ ngrok hiện:
   ```
   Session Status     online
   Account            your@email.com (Plan: Free)
   Forwarding         https://flying-octopus-clearly.ngrok-free.app -> http://localhost:8000
   ```
3. URL `https://flying-octopus-clearly.ngrok-free.app` đã sẵn sàng — **chia sẻ cho mọi người!**

---

### Cập nhật Extension để dùng URL ngrok

Mở popup Extension → nhập URL ngrok vào ô **Server URL**:
```
https://flying-octopus-clearly.ngrok-free.app
```
→ Nhấn **💾 Lưu** → Extension sẽ gửi câu hỏi về server chung.

---

### Kiểm tra hoạt động

Mở trình duyệt, truy cập URL ngrok của bạn:

| Kết quả | Nguyên nhân & Xử lý |
|---------|---------------------|
| ✅ Giao diện EduQuest hiện ra | Thành công — chia sẻ URL cho mọi người! |
| ❌ `ERR_NGROK_3200` | Authtoken chưa đăng nhập — chạy lại Bước 2 |
| ❌ `Tunnel not found` | Sai tên domain — kiểm tra lại Bước 4 |
| ❌ `ERR_CONNECTION_REFUSED` | Server chưa chạy — kiểm tra cửa sổ EduQuest Server |
| ⚠️ Trang cảnh báo ngrok | Nhấn **Visit Site** — ngrok hiện cảnh báo lần đầu với người dùng mới |

> 💡 **Lưu ý trang cảnh báo ngrok:** Người dùng truy cập lần đầu sẽ thấy trang "You are about to visit..." của ngrok. Nhấn **Visit Site** để tiếp tục. Cảnh báo này chỉ xuất hiện 1 lần trên mỗi trình duyệt.  
> Nếu muốn bỏ cảnh báo: cần ngrok trả phí ($10/tháng) hoặc dùng Cloudflare Tunnel có domain.

---

## 🔗 URL Cố định (Nâng cao)

> **Kết quả:** Mọi người dùng URL cố định không đổi như `https://eduquest.ten-ban.com` mà không cần thông báo lại mỗi lần khởi động máy.
>
> **Yêu cầu bắt buộc:** Có 1 tên miền (domain) riêng. Bạn có thể mua domain `.com` giá rẻ tại [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/) (~$10/năm) hoặc dùng domain đã có.

---

### Bước 1 — Đăng ký tài khoản Cloudflare (miễn phí)

1. Truy cập **https://cloudflare.com** → nhấn **Sign Up**
2. Điền email + mật khẩu → xác nhận email
3. Nếu đã có domain: nhấn **Add a Site** → nhập tên domain → chọn gói **Free**
4. Cloudflare sẽ cấp cho bạn **2 nameserver** (dạng `xxx.ns.cloudflare.com`)  
   → Đăng nhập vào nơi mua domain (GoDaddy, Namecheap, VNPT...) → tìm mục **Nameservers** → thay bằng 2 nameserver của Cloudflare

> ⏱️ Chờ 5–30 phút để DNS propagate. Cloudflare sẽ gửi email thông báo khi xong.

---

### Bước 2 — Đăng nhập `cloudflared` vào tài khoản Cloudflare

Mở PowerShell tại thư mục dự án:

```powershell
.\cloudflared.exe tunnel login
```

- Lệnh này tự động mở trình duyệt → đăng nhập Cloudflare → **chọn domain** muốn dùng
- Sau khi chọn xong, file chứng chỉ được lưu tự động tại:
  ```
  C:\Users\<ten-may>\.cloudflared\cert.pem
  ```
- Màn hình hiện `You have successfully logged in.` → thành công ✅

---

### Bước 3 — Tạo Tunnel vĩnh viễn

```powershell
.\cloudflared.exe tunnel create eduquest
```

Kết quả trả về dạng:
```
Tunnel credentials written to C:\Users\<ten-may>\.cloudflared\<tunnel-id>.json
Created tunnel eduquest with id a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

> 📋 **Ghi lại Tunnel ID** (`a1b2c3d4-xxxx-...`) — cần dùng ở bước tiếp theo.

---

### Bước 4 — Tạo file cấu hình `cloudflared-config.yml`

Tạo file `cloudflared-config.yml` ngay trong thư mục dự án:

```yaml
# cloudflared-config.yml
# ⚠️  Thay <TUNNEL-ID> bằng ID ở Bước 3
# ⚠️  Thay <ten-may> bằng tên Windows user của bạn (vd: ptlua)
# ⚠️  Thay <ten-ban.com> bằng domain thật của bạn (vd: myschool.com)

tunnel: <TUNNEL-ID>
credentials-file: C:\Users\<ten-may>\.cloudflared\<TUNNEL-ID>.json

ingress:
  - hostname: eduquest.<ten-ban.com>
    service: http://localhost:8000
  - service: http_status:404
```

**Ví dụ thực tế** (domain `myschool.com`, Windows user `ptlua`, Tunnel ID `a1b2c3d4-...`):

```yaml
tunnel: a1b2c3d4-5e6f-7890-abcd-ef1234567890
credentials-file: C:\Users\ptlua\.cloudflared\a1b2c3d4-5e6f-7890-abcd-ef1234567890.json

ingress:
  - hostname: eduquest.myschool.com
    service: http://localhost:8000
  - service: http_status:404
```

---

### Bước 5 — Trỏ DNS subdomain vào Tunnel

```powershell
.\cloudflared.exe tunnel route dns eduquest eduquest.<ten-ban.com>
```

Lệnh này tự động tạo **CNAME record** trên Cloudflare DNS:

```
eduquest.ten-ban.com  →  CNAME  →  <tunnel-id>.cfargotunnel.com
```

Kiểm tra tại: **Cloudflare Dashboard → Chọn domain → DNS → Records**  
→ Phải thấy record `eduquest` vừa được tạo.

---

### Bước 6 — Tạo `run_fixed.bat` để chạy 1-click

Tạo file `run_fixed.bat` trong thư mục dự án:

```batch
@echo off
chcp 65001 > nul
title EduQuest Pro - Fixed URL Mode

echo [1] Khoi dong EduQuest Server...
start "EduQuest Server" python start_server_shared.py

echo [2] Doi server san sang (4 giay)...
timeout /t 4 /nobreak > nul

echo [3] Ket noi Cloudflare Tunnel co dinh...
echo URL co dinh: https://eduquest.<ten-ban.com>
.\cloudflared.exe tunnel --config cloudflared-config.yml run
pause
```

> ✅ Từ giờ chỉ cần **double-click `run_fixed.bat`** (Run as administrator) mỗi lần bật máy.  
> URL `https://eduquest.ten-ban.com` sẽ **không bao giờ thay đổi**.

---

### Kiểm tra hoạt động

Sau khi chạy, mở trình duyệt và vào địa chỉ:
```
https://eduquest.<ten-ban.com>
```

| Kết quả | Nguyên nhân & Xử lý |
|---------|---------------------|
| ✅ Giao diện EduQuest hiện ra | Thành công — chia sẻ URL cho mọi người! |
| ❌ `522 Connection timed out` | Server chưa chạy — kiểm tra cửa sổ EduQuest Server |
| ❌ `SSL` / `ERR_CERT` | Chờ thêm 1–2 phút để Cloudflare cấp SSL tự động |
| ❌ `1033 Tunnel not found` | Sai Tunnel ID trong `cloudflared-config.yml` |
| ❌ `DNS_PROBE_FINISHED_NXDOMAIN` | DNS chưa propagate — chờ thêm hoặc kiểm tra CNAME record |


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
