# EduQuest Pro — Hệ Thống Thu Thập & Quản Lý Ngân Hàng Câu Hỏi Thi Trực Tuyến

> **Hỗ trợ thu thập:** VioEdu (`vio.edu.vn`), Trạng Nguyên (`tnmath.edu.vn`), và các kỳ thi Olympic Toán quốc tế: **TIMO, HKIMO, ASMO, SASMO, Kangaroo...**

---

## 1. Giới thiệu Tổng quan

**EduQuest Pro** là ứng dụng chuyên biệt dành cho giáo viên, phụ huynh và học sinh nhằm giải quyết bài toán:
- Tự động thu thập và lưu trữ câu hỏi từ các nền tảng học & thi trực tuyến hàng đầu Việt Nam và Quốc tế.
- Tự động tải và lưu trữ **hình ảnh đề thi về máy cục bộ** (không lo link ảnh trên mạng bị xóa hoặc lỗi sau kỳ thi).
- Chuẩn hóa toàn bộ công thức Toán học sang định dạng **LaTeX / KaTeX** sắc nét.
- Quản lý ngân hàng câu hỏi thông minh: Tìm kiếm tức thì, lọc theo Khối lớp (1 đến 12), Chuyên đề, Dạng câu hỏi (Trắc nghiệm, Điền số, Ghép cặp, Tự luận) và Mức độ.
- **Biên soạn, trộn đề và xuất đề thi ra file Microsoft Word (`.docx`)** chuẩn quy chuẩn in ấn Việt Nam (kèm bảng đáp án và hướng dẫn giải chi tiết ở cuối trang).

---

## 2. Kiến trúc Hệ thống

```
g:\Mina\Online_Learning\
├── backend/
│   ├── app.py                 # FastAPI Application (REST APIs & Static Mounts)
│   ├── database.py            # Quản lý SQLite database (questions.db)
│   ├── models.py              # Pydantic schemas (Question, Exam, Options)
│   ├── normalizer.py          # Chuẩn hóa LaTeX/MathJax & Tải ảnh lưu offline
│   ├── docx_exporter.py       # Bộ xuất đề thi Word .docx chuyên nghiệp
│   ├── pdf_extractor.py       # Bộ bóc tách thông minh từ file PDF (TIMO, ASMO...)
│   └── scrapers/
│       ├── vioedu.py          # Bot kết nối API VioEdu
│       └── tnmath.py          # Bot kết nối API Trạng Nguyên
├── extension/                 # Tiện ích Chrome / Edge Extension (Manifest V3)
│   ├── manifest.json
│   ├── background.js          # Service worker đồng bộ với máy chủ local
│   ├── content.js             # Bắt câu hỏi DOM & Widget nổi 1-click
│   ├── popup.html / popup.js  # Giao diện điều khiển popup
│   └── styles.css
├── frontend/                  # Web Dashboard UI/UX Pro Max (Slate Navy & Cobalt)
│   ├── index.html             # Single Page Application
│   ├── css/style.css          # Design system & KaTeX layout
│   └── js/
│       ├── app.js             # Quản lý Router, State, Notifications
│       ├── bank.js            # Ngân hàng câu hỏi, bộ lọc, hiển thị KaTeX
│       ├── exam_builder.js    # Soạn đề, trộn đề & xuất Word
│       └── collector.js       # Trung tâm thu thập, kéo thả PDF & Scraper
├── data/
│   ├── questions.db           # SQLite Database lưu trữ toàn bộ dữ liệu
│   └── media/                 # Kho ảnh đề thi tải về máy cục bộ
├── start_server.py            # File khởi động máy chủ
├── test_app.py                # Kịch bản kiểm thử tự động
└── requirements.txt           # Danh mục thư viện Python
```

---

## 3. Hướng dẫn Khởi chạy Ứng dụng

### Bước 1: Khởi động Máy chủ Web
Mở Terminal hoặc PowerShell tại thư mục dự án và chạy:
```powershell
python start_server.py
```
Máy chủ sẽ khởi chạy tại: **http://localhost:8000** (hoặc http://127.0.0.1:8000).

Mở trình duyệt web truy cập `http://localhost:8000` để bắt đầu sử dụng giao diện quản trị!

---

## 4. Hướng dẫn Thu thập Câu hỏi

### Cách 1: Tiện ích mở rộng Chrome / Edge Extension (Khuyên dùng cho VioEdu & Trạng Nguyên)
Tiện ích Extension cho phép bạn bắt câu hỏi ngay trong phiên duyệt web hợp lệ của mình mà **không sợ bị khóa nick hay dính Captcha**.

1. Mở trình duyệt Chrome hoặc Microsoft Edge.
2. Truy cập vào trang quản lý tiện ích:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
3. Bật công tắc **Developer mode (Chế độ cho nhà phát triển)** ở góc trên bên phải.
4. Bấm nút **Load unpacked (Tải tiện ích đã giải nén)** và chọn thư mục:
   `G:\Mina\Online_Learning\extension`
5. Khi vào làm bài hoặc xem lại bài thi trên `vio.edu.vn` hoặc `tnmath.edu.vn`:
   - Một widget nhỏ màu đen **"⚡ EduQuest"** sẽ xuất hiện ở góc dưới bên phải màn hình.
   - Nhấn **"Quét trang hiện tại"** -> Extension sẽ nhận diện câu hỏi và hiển thị số lượng.
   - Nhấn **"Lưu vào Ngân hàng"** -> Toàn bộ câu hỏi được gửi thẳng về phần mềm trên máy bạn!

### Cách 2: Kéo-Thả File PDF Đề thi Olympic (TIMO, HKIMO, ASMO, SASMO...)
1. Trên giao diện Web Dashboard, chọn mục **"⚡ Trung tâm Thu thập"**.
2. Tại khung **"Bóc tách Đề thi PDF"**, kéo thả file PDF đề thi các năm vào ô.
3. Hệ thống sẽ tự động quét, nhận diện cấu trúc từng câu hỏi, công thức toán và trích xuất hình vẽ trong đề.
4. Xem trước kết quả bóc tách và nhấn **"✓ Lưu toàn bộ vào Ngân hàng"**.

### Cách 3: Nạp nhanh 7 Câu hỏi Mẫu có sẵn
Ngay trên thanh Header của ứng dụng, bấm nút **"⚡ Nạp câu hỏi mẫu"**. Hệ thống sẽ ngay lập tức nạp 7 câu hỏi mẫu chuẩn quốc tế & học đường từ VioEdu, Trạng Nguyên, TIMO, HKIMO, ASMO có sẵn công thức LaTeX để bạn trải nghiệm ngay.

---

## 5. Hướng dẫn Biên soạn & Xuất Đề thi sang Word (.docx)

1. Vào mục **"📚 Ngân hàng Câu hỏi"**.
2. Tìm kiếm và lọc câu hỏi theo Khối lớp, Chuyên đề hoặc Mức độ mong muốn.
3. Bấm **"+ Thêm vào Đề thi"** ở các câu hỏi bạn muốn đưa vào đề kiểm tra.
4. Chuyển sang mục **"📝 Biên soạn & Trộn Đề"**:
   - Tùy chỉnh: Tiêu đề bài kiểm tra, Tên trường/Sở, Khối lớp, Thời gian làm bài (phút).
   - Nhấn **"🔀 Trộn thứ tự câu hỏi"** nếu muốn tạo các mã đề khác nhau.
   - Nhấn **"📄 Xuất file Word (.docx)"**.
5. File Word tải về đã được căn chỉnh lề chuẩn, phông chữ Times New Roman, chèn hình ảnh đẹp mắt và có sẵn **Bảng đáp án tổng hợp + Hướng dẫn giải chi tiết** ở trang cuối cùng.
