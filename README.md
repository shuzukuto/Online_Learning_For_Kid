# EduQuest Pro — Hệ Thống Thu Thập & Quản Lý Ngân Hàng Câu Hỏi Thi Trực Tuyến

![Version](https://img.shields.io/badge/App-v1.0.43-blue)
![Extension](https://img.shields.io/badge/Extension-v1.3.18-emerald)
![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen)
![FastAPI](https://img.shields.io/badge/FastAPI-Framework-teal)
![KaTeX](https://img.shields.io/badge/Math-KaTeX%20LaTeX-orange)

> **Hệ sinh thái thu thập:** VioEdu (`vio.edu.vn`), Trạng Nguyên (`tnmath.edu.vn`, `trangnguyen.edu.vn`), Hành Trang Số - NXB Giáo Dục (`hanhtrangso.nxbgd.vn`), CodeMath (`codemath.vn`), Olympic IOE Tiếng Anh (`ioe.vn`), cùng các kỳ thi Olympic Toán quốc tế: **TIMO, HKIMO, ASMO, SASMO, Kangaroo, FMO...**

---

## 1. Giới thiệu Tổng quan

**EduQuest Pro** là ứng dụng chuyên biệt dành cho giáo viên, phụ huynh và học sinh nhằm giải quyết bài toán:
- **Tự động thu thập và lưu trữ câu hỏi** từ các nền tảng học & thi trực tuyến hàng đầu Việt Nam và Quốc tế qua Extension và Internet Hunter.
- **Tự động tải và lưu trữ hình ảnh đề thi về máy cục bộ** (không lo link ảnh trên mạng bị xóa hoặc lỗi sau kỳ thi).
- **Chuẩn hóa toàn bộ công thức Toán học** sang định dạng **LaTeX / KaTeX** sắc nét.
- **Tự động làm sạch đề bài**: Phẫu thuật bóc tách và loại bỏ triệt để tiền tố số câu ("Câu hỏi số xx", "Câu xx", "Bài xx") để ngân hàng câu hỏi luôn là câu hỏi độc lập, chuẩn hóa.
- **Cơ chế Tự động lưu Zero-Click (Auto-Sync Retry)**: Extension tự động phát hiện và đồng bộ câu hỏi mới về máy chủ ở chế độ nền mà không cần thao tác click thủ công.
- **Quản lý ngân hàng câu hỏi thông minh**: Tìm kiếm toàn văn FTS5 tức thì, lọc theo Khối lớp (1 đến 12), Bộ môn (Toán, Tiếng Việt, Tiếng Anh, Khoa học, Tin học), Chuyên đề, Dạng câu hỏi (Trắc nghiệm, Điền số, Ghép cặp, Tự luận) và Mức độ.
- **Biên soạn, trộn đề và xuất đề thi ra file Microsoft Word (`.docx`)** chuẩn quy chuẩn in ấn Việt Nam (kèm bảng đáp án và hướng dẫn giải chi tiết ở cuối trang).

---

## 2. Kiến trúc Hệ thống

```
Online_Learning_For_Kid/
├── backend/
│   ├── app.py                 # FastAPI Application (REST APIs & Static Mounts)
│   ├── database.py            # Quản lý SQLite database (questions.db, q_number 1..N)
│   ├── models.py              # Pydantic schemas (Question, Exam, Options)
│   ├── normalizer.py          # Chuẩn hóa LaTeX/MathJax, loại bỏ số câu & tải ảnh offline
│   ├── classifier.py          # Bộ AI phân loại bộ môn tự động (Toán, TV, Anh, Khoa học)
│   ├── docx_exporter.py       # Bộ xuất đề thi Word .docx chuyên nghiệp
│   ├── pdf_extractor.py       # Bộ bóc tách thông minh từ file PDF (TIMO, ASMO...)
│   └── scrapers/
│       ├── internet_hunter.py # Bot cào kho học liệu trực tuyến mở & đề thi online
│       ├── vioedu.py          # Bot kết nối API VioEdu
│       └── tnmath.py          # Bot kết nối API Trạng Nguyên
├── extension/                 # Tiện ích Chrome / Edge Extension (v1.3.15 Manifest V3)
│   ├── manifest.json
│   ├── background.js          # Service worker đồng bộ với máy chủ port 8000
│   ├── interceptor.js         # Tiêm page context bắt gói tin mạng Fetch/XHR/WebSocket
│   ├── content.js             # Bắt câu hỏi DOM, Floating Widget & Zero-Click Auto-Sync
│   ├── popup.html / popup.js  # Giao diện điều khiển popup & Monospace Debug Log
│   └── styles.css
├── frontend/                  # Web Dashboard UI/UX Pro Max (v1.0.43)
│   ├── index.html             # Single Page Application
│   ├── css/style.css          # Design system & KaTeX layout
│   └── js/
│       ├── app.js             # Quản lý Router, State, Live Sync không cần F5
│       ├── bank.js            # Ngân hàng câu hỏi, bộ lọc, xem tất cả, KaTeX
│       ├── exam_builder.js    # Soạn đề, ma trận tạo đề tự động, trộn đề & xuất Word
│       └── collector.js       # Trung tâm thu thập, Auto-Hunter loop & kéo thả PDF
├── data/
│   ├── questions.db           # SQLite Database lưu trữ toàn bộ dữ liệu câu hỏi
│   └── media/                 # Kho ảnh đề thi tải về máy cục bộ
├── start_server.py            # File khởi động máy chủ
├── test_app.py                # Kịch bản kiểm thử tự động
├── runapp.bat                 # Khởi chạy 1-click cho Windows
├── rules.md                   # Đặc tả kiến trúc & nghiệp vụ chi tiết
├── DATA_MAPPING.md            # Hợp đồng dữ liệu UI ↔ API ↔ DB ↔ CSV
├── changelog.md               # Lịch sử các phiên bản
└── requirements.txt           # Danh mục thư viện Python
```

---

## 3. Hướng dẫn Cài đặt & Khởi chạy

### Bước 1: Cài đặt Thư viện Python
```powershell
pip install -r requirements.txt
```

### Bước 2: Khởi động Máy chủ Web
Mở Terminal hoặc PowerShell tại thư mục dự án và chạy:
```powershell
python start_server.py
```
*(hoặc click đúp file `runapp.bat` trên Windows)*.

Máy chủ sẽ khởi chạy tại: **http://localhost:8000** (hoặc `http://127.0.0.1:8000`).

Mở trình duyệt web truy cập `http://localhost:8000` để bắt đầu sử dụng giao diện quản trị!

---

## 4. Hướng dẫn Thu thập Câu hỏi

### Cách 1: Tiện ích mở rộng Chrome / Edge Extension (Khuyên dùng)
Tiện ích Extension cho phép bạn bắt câu hỏi ngay trong phiên duyệt web hợp lệ của mình mà **không sợ bị khóa nick hay dính Captcha**.

1. Mở trình duyệt Chrome hoặc Microsoft Edge.
2. Truy cập vào trang quản lý tiện ích:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
3. Bật công tắc **Developer mode (Chế độ cho nhà phát triển)** ở góc trên bên phải.
4. Bấm nút **Load unpacked (Tải tiện ích đã giải nén)** và chọn thư mục:
   `G:\Mina\Online_Learning\extension`
5. Khi vào làm bài hoặc xem lại bài thi trên `vio.edu.vn`, `tnmath.edu.vn`, `hanhtrangso.nxbgd.vn`...:
   - Một widget nổi **"⚡ EduQuest Pro"** xuất hiện ở góc dưới bên phải màn hình.
   - Bật **"⚡ Tự động lưu (Zero-Click)"**: Mỗi khi bạn làm bài hoặc chuyển sang câu hỏi mới, Extension tự động bắt và lưu thẳng vào CSDL.
   - Bấm **"🚀 Cào tất cả câu hỏi trên trang này"**: Extension tự động duyệt qua các bước/phân trang để cào toàn bộ câu hỏi của bài học.
   - Bấm **"👁️ Xem các câu hỏi đã quét được"**: Xem trước danh sách câu hỏi, hình ảnh, đáp án và trạng thái đã lưu CSDL.
   - Bảng **"📋 Nhật ký Hoạt động (Debug Log)"**: Theo dõi trạng thái quét, bắt gói tin mạng kèm URL nguồn rút gọn.

### Cách 2: Kéo-Thả File PDF Đề thi Olympic (TIMO, HKIMO, ASMO, SASMO...)
1. Trên giao diện Web Dashboard, chọn mục **"⚡ Trung tâm Thu thập"**.
2. Tại khung **"Bóc tách Đề thi PDF"**, kéo thả file PDF đề thi các năm vào ô.
3. Hệ thống tự động quét, nhận diện cấu trúc từng câu hỏi, công thức toán và trích xuất hình vẽ trong đề.
4. Xem trước kết quả bóc tách và nhấn **"✓ Lưu toàn bộ vào Ngân hàng"**.

### Cách 3: Thợ săn Tự động Internet (Auto-Hunter)
1. Tại **"⚡ Trung tâm Thu thập"**, thêm các đường link bài học / đề thi trực tuyến vào danh sách nguồn.
2. Bật công tắc **"Tự động săn sau mỗi 5 phút"** hoặc nhấn **"Săn ngay"**. Hệ thống sẽ tự động bóc tách các câu hỏi mới, lọc trùng và nạp thẳng vào CSDL.

---

## 5. Hướng dẫn Biên soạn & Xuất Đề thi sang Word (.docx)

1. Vào mục **"📚 Ngân hàng Câu hỏi"**.
2. Tìm kiếm và lọc câu hỏi theo Khối lớp, Bộ môn, Chuyên đề hoặc Mức độ mong muốn.
3. Bấm **"+ Thêm vào Đề thi"** ở các câu hỏi bạn muốn đưa vào đề kiểm tra (hoặc dùng tính năng **"Ma trận Tạo Đề Tự Động"** để tạo đề 10 câu, 20 câu, 25 câu trong 1 giây).
4. Chuyển sang mục **"📝 Biên soạn & Trộn Đề"**:
   - Tùy chỉnh: Tiêu đề bài kiểm tra, Tên trường/Sở, Khối lớp, Thời gian làm bài (phút).
   - Nhấn **"🔀 Trộn thứ tự câu hỏi"** nếu muốn tạo các mã đề khác nhau.
   - Nhấn **"📄 Xuất file Word (.docx)"**.
5. File Word tải về đã được căn chỉnh lề chuẩn, phông chữ Times New Roman, chèn hình ảnh đẹp mắt và có sẵn **Bảng đáp án tổng hợp + Hướng dẫn giải chi tiết** ở trang cuối cùng.

---

## 6. Giấy phép

Phát triển bởi đội ngũ EduQuest phục vụ mục đích học tập và ôn luyện phi thương mại cho học sinh tiểu học và trung học cơ sở.
