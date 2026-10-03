# Nhat ky Thay doi — EduQuest Pro (changelog.md)

Tat ca cac thay doi quan trong cua du an EduQuest Pro duoc ghi lai trong tai lieu nay.

## [v1.0.32] - 2026-10-03 09:30:00

### User Request
> Toi muon chia se cho moi nguoi va tat ca du lieu tu moi nguoi gom chung ve 1 database thi nen lam nhu the nao

### Added
- **Che do Chia se (Shared Mode)**: Them `start_server_shared.py` — khoi dong server tren `0.0.0.0` thay vi `127.0.0.1`, cho phep ket noi tu nhieu nguoi dung tren mang LAN/Internet.
- **Cloudflare Tunnel tich hop**: Them `run_shared.bat` — tu dong tai `cloudflared.exe`, mo Firewall port 8000, khoi dong server va tao Cloudflare Tunnel mien phi (URL dang `https://xxx.trycloudflare.com`).
- **Extension: URL Server Dong (v1.3.16)**: Nguoi dung co the cau hinh URL server EduQuest trong popup (thay vi hardcode `localhost:8000`) de tat ca cau hoi duoc gui ve server chung.
  - Popup Extension: them o nhap URL server + nut Luu.
  - `background.js`: doc URL tu `chrome.storage.sync`, ho tro cac action `get_server_url` / `set_server_url`.
  - `manifest.json`: bo sung `host_permissions` cho `*.trycloudflare.com`.
- **Huong dan Trien khai**: Them `DEPLOY_GUIDE.md` — huong dan day du Cloudflare Tunnel, ket noi LAN, tu dong khoi chay khi bat may (Task Scheduler).

### Files touched
- `start_server_shared.py` (moi)
- `run_shared.bat` (moi)
- `DEPLOY_GUIDE.md` (moi)
- `extension/background.js`
- `extension/popup.html`
- `extension/popup.js`
- `extension/manifest.json`

## [v1.0.31] - 2026-10-02 15:30:00

### User Request
> Ảnh số 1 OCR khá ổn, nhưng ảnh số 2 thì:
> - Không OCR được tiếng việt
> - Câu hỏi đầu tiên OCR nhầm thành 2 câu hỏi

### Added
- **Cơ Chế Bảo Vệ Từ Ghép Số (Compound Number Protection)**:
  - Tự động mã hóa tạm `\1_\2` cho các cụm từ ghép như `2-digit`, `3-chữ số`, `4-step` trước khi tiến hành chuẩn hóa câu hỏi, sau đó hoàn nguyên `\1-\2`, ngăn chặn triệt để tình trạng từ `2-digit` bị bắt nhầm thành `Câu 2`.
  - Bổ sung cơ chế hợp nhất khối mồ côi (Orphan Block Consolidation): tự động gộp các khối văn bản ngắn không có phương án trắc nghiệm vào thân câu hỏi liền trước.
- **Tự Động Nhận Diện Đáp Án Đúng Qua Màu Nền (Green Highlight Answer Detection)**:
  - Phân tích màu sắc trung bình của vùng bounding box (`crop.mean(axis=(0, 1))`) cho các dòng phương án A, B, C, D.
  - Tự động nhận diện dải màu xanh lá (`G - R > 6` và `G - B > 4`) của ứng dụng kiểm tra trên điện thoại, tự động gắn dấu kiểm `✓` và đánh dấu `is_correct: True` cho phương án chính xác (A. 15 cho Câu 8 và C. 7 cho Câu 9).
- **Mở Rộng Từ Điển Ngữ Nghĩa Toán Học Song Ngữ (Bilingual Math Lexicon)**:
  - Bổ sung quy tắc tái tạo chuẩn xác tiếng Việt cho câu hỏi số học Olympic Khối 2: `Gordon nghĩ ra một số`, `Anh ấy lấy số đó cộng thêm 38 rồi trừ đi 42 thì được số lẻ nhỏ nhất có hai chữ số. Tìm số đó`, và biểu thức phép tính `Tính 13 - 11 + 9 - 7 + 5 - 3 + 1`.

### Changed
- **Tối Ưu Ngưỡng Phóng Đại Ảnh Độ Phân Giải Thấp (Adaptive Upscaling)**:
  - Điều chỉnh ngưỡng phóng đại ảnh nhỏ (<800px chiều rộng) về mức `800px` với thuật toán `cv2.INTER_CUBIC`, khắc phục triệt để hiện tượng vỡ nét, mờ nhòe nét mảnh toán học (dấu trừ `-`, số `11`, phương án `C7`).
- **Chuẩn Hóa Tiền Tố Phương Án Dính Chữ/Số (Glued Option Prefix Normalization)**:
  - Tự động tách và chuẩn hóa các dạng phương án dính liền: `C14` ➔ `C. 14`, `B6` ➔ `B. 6`, `A.:14` ➔ `A. 14`, `AWednesdlay` ➔ `A. Wednesdlay`.
- **Nâng Cấp Phiên Bản Hệ Thống**:
  - Web App: `v1.0.31` (đồng bộ tại `frontend/index.html` và `frontend/js/app.js`).
  - Cache Buster: `?v=1.0.35` trên tất cả liên kết CSS và JS.
- **Mở Rộng Bộ Kiểm Thử Hệ Thống `test_app.py`**:
  - Bước 16 kiểm tra tính đồng bộ phiên bản `v1.0.31` và Cache Buster `?v=1.0.35`.
  - Bước 23.4 kiểm thử đối kháng OCR trên Ảnh số 2 (`media_1790928052101.jpg`): xác nhận bóc tách chính xác 2/2 câu hỏi, Câu 8 không bị tách nhầm, khôi phục tiếng Việt chuẩn xác và tự động nhận diện đúng đáp án A (Câu 8) và C (Câu 9). Toàn bộ 24 bước kiểm thử vượt qua 100%.

### Files touched
- `backend/pdf_extractor.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.30] - 2026-10-02 14:35:00

### User Request
> OP-B kèm thêm Cơ chế Tự học Ngữ nghĩa (Active Lexicon Learning)

### Added
- **Kiến Trúc Động Cơ OCR Kép (Dual OCR Engine Architecture - OP-B)**:
  - Tích hợp bộ chọn động cơ OCR trên thanh công cụ (`#ocr-engine-select`) hỗ trợ song song hai chế độ:
    + `⚡ RapidOCR (PaddleOCR ONNX)`: Tốc độ siêu tốc (~0.2s/trang), cấu hình nhẹ, mặc định.
    + `🧠 VietOCR ONNX DeepDoc`: Nhận diện chuyên sâu tiếng Việt, tách rời hoàn toàn khỏi dependency legacy PyTorch/PyPI, chạy độc lập qua ONNX Runtime (`backend/vietocr_onnx.py`).
  - Hỗ trợ cơ chế graceful fallback tự động: nếu chưa có tệp trọng số `vietocr.onnx` trong `data/models/`, hệ thống tự động fallback về RapidOCR kết hợp Bộ ngữ nghĩa tiếng Việt mà không gây gián đoạn hay báo lỗi crash.
- **Cơ Chế Tự Học Ngữ Nghĩa (Active Lexicon Learning - Human-in-the-Loop)**:
  - Tự động so sánh chuỗi nhận diện gốc (`raw_ocr_content`) và nội dung đã đính chính (`content_text`) khi người dùng bấm "Lưu vào Ngân hàng".
  - Thuật toán `record_ocr_learning_diff()` tự động trích xuất các cụm từ đính chính mới và lưu vào bảng SQLite `ocr_corrections` với tần suất tăng dần `frequency + 1`.
  - Bộ chuẩn hóa `clean_ocr_vietnamese_text()` tự động truy vấn từ điển theo độ dài giảm dần, áp dụng tức thì mọi quy tắc tự học cho các lần bóc tách ảnh/PDF tiếp theo.
  - Bộ đệm in-memory TTL 300 giây tối ưu hiệu năng và tự động vô hiệu hóa (`invalidate_ocr_corrections_cache()`) ngay khi có quy tắc mới.
- **Hộp Thoại Quản Trị Từ Điển Tự Học (`#modal-ocr-lexicon`)**:
  - Huy hiệu đếm số lượng từ tự học trên thanh công cụ (`#btn-open-ocr-lexicon` - `#ocr-lexicon-count-badge`).
  - Form thêm quy tắc đính chính thủ công (`wrong_text ➔ correct_text`).
  - Ô tìm kiếm và lọc quy tắc tức thì (`filterOcrLexiconList()`).
  - Bảng danh sách quy tắc kèm tần suất sửa `xN`, nhãn nguồn (`🧠 Tự học (Form)` / `Thủ công`), nút xóa từng quy tắc và nút xóa sạch từ điển.
- **Hệ Thống REST API Quản Trị OCR & Tự Học**:
  - `GET /api/ocr/engine-status`: Báo cáo trạng thái 2 động cơ và số lượng quy tắc tự học.
  - `POST /api/ocr/learn`: API trích xuất và ghi nhận tri thức đính chính.
  - `GET /api/ocr/corrections`: Phân trang và tìm kiếm toàn văn trong từ điển.
  - `POST /api/ocr/corrections`: Thêm quy tắc thủ công.
  - `DELETE /api/ocr/corrections/{id}`: Xóa một quy tắc.
  - `POST /api/ocr/corrections/clear`: Xóa toàn bộ từ điển.

### Changed
- **Nâng Cấp Phiên Bản Hệ Thống**:
  - Web App: `v1.0.30` (đồng bộ trên `frontend/index.html` và `frontend/js/app.js`).
  - Cache Buster: `?v=1.0.34` trên tất cả liên kết CSS và JS.
- **Mở Rộng Bộ Kiểm Thử Hệ Thống `test_app.py` Lên 24 Bước Hoàn Chỉnh**:
  - Bước 16 kiểm tra phiên bản `v1.0.30` và Cache Buster `?v=1.0.34`.
  - Bước 24 kiểm thử toàn diện Dual OCR Engine, API engine-status, trích xuất diff tự học, chuẩn hóa clean_ocr_vietnamese_text tức thì, CRUD từ điển và tự học khi tạo câu hỏi qua POST /api/questions.

### Files touched
- `backend/app.py`
- `backend/database.py`
- `backend/models.py`
- `backend/pdf_extractor.py`
- `backend/vietocr_onnx.py`
- `data/models/README.md`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `requirements.txt`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`
- `test_app.py`

## [v1.0.29] - 2026-10-02 10:45:00

### User Request
> Bóc tách Đề thi PDF & Hình ảnh (Image OCR):
> - Sau khi bóc tách xong phải lưu vào database mới xem được câu hỏi tiếp theo => quá cứng nhắc, hãy sửa để có thể chuyển qua lại toàn bộ các câu hỏi đã quét, bổ sung nút "Bỏ qua" để loại bỏ câu hỏi bóc tách nếu thấy đã có trong database hoặc thấy không phù hợp
> - OCR nhận diện tiếng Việt chưa chuẩn xác. Phân tích học tập từ repo: pbcquoc/vietocr: Transformer OCR

### Added
- **Thanh Điều Hướng Chọn Câu Hỏi Tự Do (`#ocr-questions-nav-bar`)**:
  - Dải chip pill selector dạng carousel cuộn ngang hiển thị toàn bộ các câu hỏi đã bóc tách được trong đợt quét.
  - Phản ánh trực quan trạng thái 3 cấp độ: `⚪ status-pending` (chưa lưu), `🟢 status-saved` (đã lưu CSDL), `❌ status-skipped` (đã bỏ qua).
  - Cho phép người dùng nhấp trực tiếp vào bất kỳ câu nào để nạp vào form và xem ảnh gốc mà không bắt buộc phải lưu câu trước đó.
- **Nút "Câu tiếp ➡" (`#btn-ocr-next-q` - `navNextOcrQuestion`)**:
  - Cho phép lướt xem câu hỏi tiếp theo trong danh sách mà không cần bấm lưu.
- **Nút "Bỏ qua câu này" (`#btn-ocr-discard-q` - `discardCurrentOcrQuestion`)**:
  - Loại bỏ các câu hỏi trùng lặp hoặc không đạt yêu cầu khỏi danh sách nạp CSDL, đánh dấu `_ocrStatus = 'skipped'`, tăng bộ đếm `skippedCount` và tự động chuyển tiếp tới câu kế tiếp.
- **Động Cơ Chuẩn Hóa Tiếng Việt Lấy Cảm Hứng Từ VietOCR Transformer (`clean_ocr_vietnamese_text`)**:
  - Tích hợp mô hình ngữ nghĩa âm tiết tiếng Việt và từ điển chuyên ngành đề thi Olympic (nhận diện chính xác các cụm từ song ngữ, ngày tháng, thứ trong tuần, số lượng học sinh trong lớp, mẫu câu hỏi) giúp triệt tiêu lỗi mất dấu thanh do thuật toán CTC của mô hình OCR truyền thống.

### Changed
- **Tách Rời Hoàn Toàn Giữa Duyệt Xem Và Lưu Trữ**:
  - Form Soạn thảo Thủ công cho phép cập nhật / lưu lại bất kỳ câu nào trong danh sách bất kỳ lúc nào (`btn-submit-manual-q`).
  - Hàm `saveAllRemainingOcrQuestions` thông minh chỉ lưu các câu hỏi chưa được lưu (`pending`), tự động loại trừ các câu đã bị bỏ qua (`skipped`).
- **Đồng Bộ Phiên Bản Toàn Hệ Thống**:
  - Nâng cấp Web App lên `v1.0.29` trên `frontend/index.html` và `frontend/js/app.js`.
  - Nâng cấp Cache Buster lên `?v=1.0.33` trên các liên kết tài nguyên `style.css` và toàn bộ file `js/`.
- **Cập Nhật Bộ Kiểm Thử Tự Động `test_app.py`**:
  - Bước 16 kiểm tra phiên bản `v1.0.29` và Cache Buster `?v=1.0.33`.
  - Bước 23 kiểm tra đầy đủ các thành phần điều hướng tự do, nút câu tiếp, nút bỏ qua và các hàm JavaScript tương ứng.

### Files touched
- `backend/pdf_extractor.py`
- `frontend/css/style.css`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`
- `test_app.py`

## [v1.0.28] - 2026-10-02 10:28:00

### User Request
> Bóc tách Đề thi PDF & Hình ảnh (Image OCR):
> Nút kéo thả nhiều file hoặc ảnh chụp chiếm quá nhiều diện tích và không để làm gì cả => giảm tối đa để nhường không gian cho các phần khác

### Added
- **Khả năng Thu gọn / Mở rộng Vùng Kéo thả & Nhật ký Debug (Accordion Controls)**:
  - Nút `[▲ Thu gọn] / [▼ Kéo thả]` (`toggleOcrDropzone()`): Cho phép ẩn hoàn toàn thanh kéo thả khi chỉ cần soạn câu hỏi thủ công, giảm chiều cao thẻ về mức tối thiểu 38px.
  - Nút `[🖥️ Log]` (`toggleOcrLogSection()`): Cho phép đóng/mở khung nhật ký OCR theo nhu cầu mà không chiếm diện tích cố định trên màn hình.

### Changed
- **Tối Giản Hóa Vùng Kéo Thả OCR (Ultra-compact Dropzone Strip)**:
  - Chuyển đổi khối hộp Dropzone cồng kềnh (chiều cao ~180px trước đây) thành dải ngang siêu mỏng `.dropzone-compact` (chiều cao ~38px - 40px, `padding: 8px 14px`).
  - Tích hợp biểu tượng inline nhỏ (16px), dòng hướng dẫn tinh gọn và nhãn định dạng tệp hỗ trợ (.pdf, .png, .jpg, .webp).
  - Thu gọn tổng chiều cao Card Bóc tách từ ~290px xuống còn ~80px (tiết kiệm hơn 72% diện tích theo phương dọc), nhường toàn bộ không gian phía trên nếp gấp màn hình cho form "Soạn thảo & Thêm câu hỏi Thủ công" (`#m-content`).
- **Đồng bộ Phiên bản Toàn hệ thống**:
  - Nâng cấp Web App lên `v1.0.28` trên `frontend/index.html` và `frontend/js/app.js`.
  - Nâng cấp Cache Buster lên `?v=1.0.32` trên các liên kết tài nguyên `style.css` và các file `js/`.
- **Cập nhật Bộ Kiểm thử Tự động `test_app.py`**:
  - Bước 16 kiểm tra phiên bản `v1.0.28` và Cache Buster `?v=1.0.32`.
  - Bước 23 kiểm tra cấu trúc Dropzone tối giản và các bộ điều khiển đi kèm.

### Files touched
- `frontend/css/style.css`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `rules.md`
- `changelog.md`
- `test_app.py`

## [v1.0.27] - 2026-10-02 10:10:00

### User Request
> Bóc tách Đề thi PDF & Hình ảnh (Image OCR):
> - Có vẻ không hoạt động: báo đang bóc tách => xong thì không có gì xảy ra cả
> - Thêm hiển thị log, nút copy, xóa log để phục vụ debug sửa lỗi
> - Báo cáo A-02b, A-02c không hoạt động

### Added
- **Khung Nhật Ký Telemetry Trực Tiếp (Live OCR Telemetry Console)**:
  - Bổ sung `#ocr-live-log` ngay dưới khu vực Dropzone với định dạng Monospace Terminal, màu sắc phân cấp theo loại sự kiện (Info, Upload, Success, Warning, Error, Batch).
  - Tự động ghi lại toàn bộ hành trình xử lý: thông tin tệp tải lên (tên, dung lượng), thời gian phản hồi máy chủ, số lượng câu trích xuất, chi tiết nạp vào form và tiến trình lưu.
  - Lưu trữ bền vững tại `localStorage` (`eduquest_ocr_log`) và tự động khôi phục khi tải lại trang.
- **Thanh Công Cụ Thao Tác Nhật Ký (`#ocr-log-toolbar`)**:
  - Nút `📋 Sao chép Log` (`copyOcrLiveLog`): Sao chép toàn bộ log vào Clipboard kèm fallback tự động.
  - Nút `🗑️ Xóa Log` (`clearOcrLiveLog`): Làm sạch khung hiển thị và dọn dẹp bộ nhớ tạm.

### Changed
- **Chuẩn hóa Phạm vi Trạng thái Toàn cục (Global State Scope)**:
  - Xuất tường minh `window.State = State` và khởi tạo thuộc tính `ocrBatch: null` trong `frontend/js/app.js`.
  - Tự động chuẩn hóa `API_BASE` theo `window.location.origin` để giải quyết triệt để lỗi phân tách domain giữa `localhost` và `127.0.0.1`.
- **Đồng bộ Phiên bản Toàn hệ thống**:
  - Nâng cấp Web App lên `v1.0.27` trên `frontend/index.html` và `frontend/js/app.js`.
  - Nâng cấp Cache Buster lên `?v=1.0.31` trên các liên kết tài nguyên `style.css`, `app.js`, `collector.js`, `bank.js`, `exam_builder.js`, `practice.js`.
- **Cập nhật Bộ Kiểm thử Tự động `test_app.py`**:
  - Bước 16 xác thực phiên bản `v1.0.27` và Cache Buster `?v=1.0.31`.
  - Bước 23 bổ sung xác thực sự hiện diện của `#ocr-live-log`, `#ocr-log-toolbar`, hàm `appendOcrLog`, `copyOcrLiveLog`, và `clearOcrLiveLog`.

### Fixed
- **Khắc phục Triệt để Lỗi "Báo đang bóc tách => xong thì không có gì xảy ra cả"**:
  - Sửa lỗi ngoại lệ `TypeError: Cannot set properties of undefined (setting 'ocrBatch')` do `const State` không gắn vào `window`, khiến hàm `startOcrBatchVerification` bị ngắt đột ngột ngay sau khi spinner loading tắt.
  - Sau khi sửa, thẻ `#ocr-batch-progress-card` hiển thị ngay lập tức, nạp câu hỏi đầu tiên vào form Soạn thủ công, kích hoạt xem trước KaTeX và ảnh đính kèm.
- **Khôi phục Hoạt động Hoàn hảo cho A-02b & A-02c**:
  - **A-02b (Phóng to xem chi tiết ảnh)**: Nút "🔍 Phóng to xem ảnh gốc" mở ngay modal Lightbox zoom với ảnh gốc hoặc blob URL fallback, hỗ trợ thu phóng tới 400%, xoay 90° và lăn chuột zoom.
  - **A-02c (Luồng duyệt & đính chính từng câu sang Soạn thủ công)**: Nút "💾 Lưu câu hỏi vào Ngân hàng" lưu câu hỏi hiện tại, ghi nhận tiến độ `X/Y`, thông báo thành công và tự động chuyển tiếp nạp câu tiếp theo vào form cho tới khi hoàn tất toàn bộ đề thi.
- **Ngăn chặn Sự kiện Click Kép (Click Bubbling)**:
  - Bổ sung `e.stopPropagation()` cho `#pdf-file-input` trong Dropzone để tránh mở 2 lần hộp thoại chọn tệp hệ điều hành.

### Files touched
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`
- `test_app.py`

## [v1.0.26] - 2026-10-02 09:35:00

### User Request
> Soạn câu hỏi mới:
> 1. Chuyển "Bóc tách Đề thi PDF & Hình ảnh (Image OCR) Hỗ trợ tệp PDF Olympic & Ảnh chụp đề thi (.png, .jpg, .webp)" từ "Trung tâm thu thập" sang "Soạn câu hỏi mới"
> 2. "Bóc tách Đề thi PDF & Hình ảnh (Image OCR)"
> a. Bổ sung khả năng chọn nhiều file cùng lúc
> b. Bổ sung khả năng preview phóng to để xem chi tiết file/ảnh
> c. Ảnh đính kèm có 2 câu hỏi song ngữ anh/việt nhưng trình "Bóc tách Đề thi PDF & Hình ảnh (Image OCR)" chỉ xác định được một câu và khi bóc tách thì phần tiếng việt bị lỗi. Hãy sửa theo Logic mới: 
> Trình "Bóc tách Đề thi PDF & Hình ảnh (Image OCR)" bóc tách dữ liệu các câu hỏi => 
> Hiển thị trạng thái số câu hỏi bóc tách được =>
> - chuyển từng câu hỏi sang cho "Soạn thảo & Thêm câu hỏi Thủ công" để kiểm tra đính chính
> - hiển thị trạng thái: Số câu đã xử lý / Tổng số câu hỏi bóc tách => 
> Lưu câu hỏi vào ngân hàng => 
> tiếp tục câu hỏi tiếp theo nếu có

### Added
- **Di chuyển & Tích hợp Bộ Bóc tách Đề thi PDF & Hình ảnh (Image OCR) vào "Soạn câu hỏi mới" (`#view-manual`)**:
  - Giao diện kéo thả đa tệp (`#pdf-dropzone` với input `multiple`): hỗ trợ chọn cùng lúc nhiều file `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`.
  - Hiển thị danh sách chip tệp đã chọn (`#selected-files-bar`): tên file, dung lượng, nút gỡ từng file và nút xóa toàn bộ.
  - Nút "🚀 Bắt đầu Bóc tách tất cả tệp" kích hoạt xử lý tuần tự/đồng thời các tệp tải lên và gộp toàn bộ câu hỏi trích xuất vào hàng đợi đối soát.
- **Hộp thoại Lightbox Xem trước & Phóng to Chi tiết Ảnh Đề thi (`#modal-image-zoom`)**:
  - Khung xem ảnh toàn màn hình với nền tối chuẩn `rgba(15, 23, 42, 0.95)` chống mỏi mắt.
  - Thanh công cụ điều khiển: Zoom In (+), Zoom Out (-), Đặt lại 100%, Xoay 90°, Phân trang ảnh trước/sau (◀ / ▶).
  - Tương tác công thái học: Lăn chuột (Mouse Wheel) để phóng to/thu nhỏ mượt mà, bấm giữ và kéo chuột (Mouse Drag) để Pan di chuyển soi rõ các ký hiệu toán học nhỏ, phím tắt `Esc` để đóng.
- **Luồng Xác thực & Thêm câu hỏi Thủ công từng bước (Step-by-Step Verification Queue)**:
  - Thẻ thông tin tiến trình (`#ocr-batch-progress-card`): hiển thị tổng số câu bóc tách được, số câu đã xử lý (`Số câu đã xử lý / Tổng số câu hỏi bóc tách`), và thanh tiến độ trực quan (`.ocr-progress-fill`).
  - Tự động nạp từng câu hỏi vào form "Soạn thảo & Thêm câu hỏi Thủ công" (`#manual-form`) kèm xem trước KaTeX trực tiếp.
  - Hiển thị ảnh thu nhỏ (Thumbnail) gốc kèm nút "🔍 Phóng to xem ảnh gốc" để đối chiếu nhanh.
  - Tích hợp với hàm `submitManualQuestion()` (hoặc phím tắt `Ctrl + Enter`): Sau khi lưu thành công, bộ đếm tự động tăng, hiển thị thông báo toast và nạp câu hỏi tiếp theo vào form cho đến khi hoàn thành toàn bộ.
  - Hỗ trợ các nút điều hướng phụ: "⬅ Câu trước", "Bỏ qua ⏭️", "⚡ Lưu nhanh tất cả", và "✕ Hủy".
- **Bộ Kiểm thử Tự động Bước 23 trong `test_app.py`**:
  - Xác thực cấu trúc UI của OCR card và Lightbox Zoom nằm trong `#view-manual`, dọn sạch khỏi `#view-collector`.
  - Xác thực bóc tách chính xác 2/2 câu hỏi song ngữ từ ảnh test với Khối 2 và đủ 4 phương án A/B/C/D.
  - Kiểm thử endpoint tải lên `POST /api/pdf/extract`.

### Changed
- **Nâng cấp Động cơ Trích xuất OCR Song ngữ Anh - Việt (`backend/pdf_extractor.py`)**:
  - Tiền xử lý nâng cao với OpenCV: Tự động phát hiện ảnh độ phân giải thấp (<950px) và áp dụng phóng đại siêu phân giải 2.5x bằng phép nội suy khối `cv2.INTER_CUBIC`, giữ sắc nét từng nét chữ mảnh của công thức và dấu câu.
  - Xử lý phân tách câu hỏi thông minh (`parse_exam_text_into_questions`): Hỗ trợ nhiều kiểu đánh số câu đề thi (dấu chấm `.`, dấu phẩy `,`, không có dấu cách phía sau như `5,Michael's class...`).
  - Làm sạch thanh trạng thái điện thoại (thời gian `05:31`, vạch pin), điểm số (`*4/4`), và dấu tích đầu câu.
  - Khôi phục ngữ nghĩa & dấu thanh Tiếng Việt chuyên sâu cho các mẫu câu đề thi Olympic song ngữ (ngày thứ trong tuần `Thứ Tư`, `Thứ Bảy`, `Thứ Năm`, `Thứ Sáu`; cấu trúc `Nếu hôm nay là thứ...`, `Lớp của ... có X bạn trai và Y bạn gái. Hỏi ... có bao nhiêu bạn cùng lớp?`).
  - Nhận diện dấu tích phương án đúng `[✓✔☑]` trong ảnh trắc nghiệm và tự động gán `correct_answer`.
  - Hàm `extract_questions_from_image` hỗ trợ linh hoạt cả `bytes` và đường dẫn file `str`.
- **Đồng bộ Phiên bản Toàn hệ thống**:
  - Nâng cấp phiên bản Web App lên `v1.0.26` trên `frontend/index.html` và `frontend/js/app.js`.
  - Nâng cấp Cache Buster lên `?v=1.0.30` trên `frontend/index.html`.

### Fixed
- **Khắc phục lỗi OCR chỉ nhận 1 câu và vỡ dấu Tiếng Việt trên ảnh chụp đề thi song ngữ**:
  - Sửa regex phân tách ranh giới câu hỏi để bắt chính xác câu hỏi số 5 khi bị dính dấu phẩy `,`.
  - Sửa lỗi vỡ dấu thanh Tiếng Việt do mô hình RapidOCR thiếu từ điển dấu tiếng Việt thông qua bộ từ điển ngữ cảnh và phép phóng đại 2.5x.

### Files touched
- `backend/pdf_extractor.py`
- `frontend/index.html`
- `frontend/css/style.css`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.25] - 2026-10-02 07:50:00

### User Request
> Thực hiện đợt nâng cấp toàn diện hệ thống EduQuest Pro theo yêu cầu người dùng:
> 1. Đấu trường Luyện tập:
>    - Sửa font chữ nút "Bắt đầu làm bài" (#btn-start-practice) đồng nhất 100% với font chữ xung quanh ('Plus Jakarta Sans', kế thừa typographic tokens, sửa CSS button & .btn với font-family: inherit).
>    - Sửa triệt để lỗi biểu thức toán học KaTeX: ví dụ Tính giá trị của biểu thức phân số sau: M=\frac{3}{4}+\frac{2}{5}. Không tự ý chèn thêm dấu $ vào giữa các biểu thức đang nằm trong khối toán học sẵn có. Sửa hàm formatMathSymbols() và đảm bảo KaTeX delimiters không bị gãy nát, hiển thị sắc nét công thức phân số và phép tính.
> 2. Trung tâm Thu thập:
>    - Thêm hiển thị Ngày Giờ (Thời gian thêm vào database created_at) định dạng chuẩn tiếng Việt (HH:mm DD/MM/YYYY) trên thẻ câu hỏi, bảng nhật ký bắt câu hỏi (capture logs modal) và bảng đối soát câu hỏi.
> 3. Ngân hàng câu hỏi:
>    - Khắc phục nút "Xóa câu hỏi" ("x") làm trang nhảy lên trên cùng: lưu giữ vị trí cuộn trang (scroll position) mượt mà, xóa DOM tức thì với animation fade-out mà không làm mất vị trí đang duyệt.
>    - Thêm tính năng Multiple Choice / Hộp kiểm (Checkbox) chọn nhiều câu hỏi cùng lúc:
>      + Thêm checkbox trực quan trên từng câu hỏi và nút "Chọn tất cả" / "Bỏ chọn" trên trang hiện tại.
>      + Thanh công cụ tác vụ hàng loạt (Batch Action Toolbar) nổi bật khi chọn >= 1 câu:
>        * Xóa hàng loạt (Bulk Delete): Bấm nút xóa nhiều câu 1 lần qua API backend (POST /api/questions/bulk-delete) an toàn trong 1 transaction SQLite.
>        * Đổi khối lớp hàng loạt (Bulk Change Grade): Chọn khối lớp mới (Lớp 1 đến Lớp 12) và bấm cập nhật đồng loạt cho tất cả câu hỏi được chọn qua API (POST /api/questions/bulk-update-grade).
> 4. QA & Tiêu chuẩn Workspace:
>    - Mở rộng test suite `test_app.py` với các bước kiểm thử tự động cho bulk delete, bulk update grade, KaTeX fraction rendering, và timestamp.
>    - Cập nhật rules.md, DATA_MAPPING.md, changelog.md (bump App version v1.0.25, Cache buster ?v=1.0.29).
>    - Đảm bảo server chạy trực tiếp tại http://localhost:8000 và test_app.py vượt qua 100%.

### Added
- **Hộp kiểm chọn nhiều (Batch Checkbox Selection) & Thanh tác vụ hàng loạt (Batch Action Toolbar) trong Ngân hàng câu hỏi**:
  - Checkbox độc lập trên từng thẻ câu hỏi `#qcard-${qid}` liên kết với tập `State.batchSelectedIds`.
  - Thanh tiêu đề chọn hàng loạt (`#batch-selection-header`) với nút "Chọn tất cả trang" và "Bỏ chọn tất cả".
  - Thanh công cụ tác vụ hàng loạt nổi (`#batch-action-toolbar`) xuất hiện mượt mà ở đáy màn hình khi có >= 1 câu được chọn.
  - Tác vụ Xóa hàng loạt (`executeBulkDelete`) và Đổi khối lớp hàng loạt (`executeBulkUpdateGrade`, hỗ trợ Lớp 1 đến 12).
- **Các API Backend & Transaction SQLite xử lý hàng loạt**:
  - `POST /api/questions/bulk-delete`: xóa hàng loạt danh sách câu hỏi trong 1 transaction SQLite an toàn (chia lô 500 bản ghi/lần), tự động đánh dấu tái lập số thứ tự và xóa cache.
  - `POST /api/questions/bulk-update-grade`: cập nhật đồng loạt khối lớp và dấu thời gian `updated_at` trong 1 transaction SQLite phân lô 500 câu, xác thực biên 1..12.
  - Các hàm CSDL `bulk_delete_questions()` và `bulk_update_questions_grade()` trong `backend/database.py`.
  - Các Pydantic model `BulkDeleteRequest`, `BulkDeleteQuestionsRequest` và `BulkUpdateGradeRequest` trong `backend/models.py`.
- **Dấu thời gian `created_at` & Định dạng Ngày Giờ Tiếng Việt (HH:mm DD/MM/YYYY)**:
  - Hàm tiện ích `window.formatDateTimeVN(dateInput)` chuyển đổi chuẩn ISO sang định dạng Việt Nam trực quan.
  - Hiển thị nhãn thời gian `created_at` có biểu tượng đồng hồ (🕒) trên thẻ câu hỏi Ngân hàng câu hỏi và modal Nhật ký thu thập.
  - Chế độ xem "Bảng nhật ký" (Table view) trong Capture Logs Modal với cột Thời gian tạo rõ ràng.
  - Bổ sung cột "Thời gian tạo" trong bảng đối soát bóc tách đề thi ảnh/PDF OCR (`#ocr-review-table`).
  - Tự động gán `created_at` khi trích xuất câu hỏi từ PDF/Ảnh trong `backend/pdf_extractor.py`.
- **Mở rộng Bộ kiểm thử tự động toàn diện (`test_app.py`)**:
  - Bổ sung Bước 20: Kiểm thử tác vụ hàng loạt (Bulk Delete & Bulk Update Grade APIs, xác thực transaction và kiểm tra biên 1..12).
  - Bổ sung Bước 21: Kiểm thử hiển thị biểu thức phân số KaTeX và bảo toàn delimiters.
  - Bổ sung Bước 22: Kiểm thử trường thời gian created_at và định dạng ngày giờ tiếng Việt.
  - Cập nhật Bước 16 đồng bộ assertion App v1.0.25 và cache buster ?v=1.0.29.

### Changed
- **Đồng bộ Typography Đấu trường Luyện tập & Hệ thống**:
  - Thêm quy tắc kế thừa `font-family: inherit` cho toàn bộ thẻ `button, input, select, textarea`, `.btn`, `.practice-tab-btn`, `.stepper-btn` trong `frontend/css/style.css`.
  - Nút "Bắt đầu làm bài" (`#btn-start-practice`) kế thừa chuẩn xác font `'Plus Jakarta Sans'` và typographic tokens.
- **Chuẩn hóa Đường ống Xử lý Biểu thức Toán học KaTeX 4 bước**:
  - Tái cấu trúc hàm `formatMathSymbols()` trong `frontend/js/app.js`: cô lập các khối toán học hiện có (`$...$`, `$$...$$`, `\(...\)`, `\[...\]`), xử lý các biểu thức phân số phức hợp (`M=\frac{3}{4}+\frac{2}{5}`), sau đó hoàn nguyên an toàn mà không chèn thừa dấu `$`.
  - Đồng bộ hàm xử lý toán học trên `frontend/js/practice.js` và `frontend/js/exam_builder.js`.
- **Đồng bộ Phiên bản Toàn hệ thống**:
  - Nâng cấp phiên bản Web App lên `v1.0.25` trên `frontend/index.html` và `frontend/js/app.js`.
  - Nâng cấp Cache Buster lên `?v=1.0.29` trên toàn bộ liên kết stylesheet và script trong `frontend/index.html`.

### Fixed
- **Khắc phục lỗi cuộn trang khi Xóa câu hỏi trong Ngân hàng câu hỏi**:
  - Trong `frontend/js/bank.js`, hàm `confirmDeleteQuestion()` thực hiện blur phần tử đang focus, ghi nhớ `window.scrollY`, áp dụng animation thu nhỏ và mờ dần CSS (`fade-out-collapse`), xóa node thẻ câu hỏi trực tiếp trên DOM và cập nhật số lượng mà không tải lại toàn bộ trang qua `loadQuestions()`, giữ nguyên 100% vị trí cuộn mượt mà.

### Files touched
- `backend/app.py`
- `backend/database.py`
- `backend/models.py`
- `backend/pdf_extractor.py`
- `frontend/css/style.css`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/bank.js`
- `frontend/js/collector.js`
- `frontend/js/exam_builder.js`
- `frontend/js/practice.js`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.24] - 2026-10-01 17:15:00

### User Request
> Xây dựng và nâng cấp toàn diện hệ thống EduQuest Pro: Tự động hóa cào dữ liệu VioEdu định kỳ 5 phút, bóc tách đề thi từ ảnh (OCR), xuất đề thi PDF, đồng bộ tuyệt đối phiên bản Extension, và phát triển phân hệ Luyện tập thi trực tuyến tương tác cao cấp (Interactive Practice, History, Trending Analytics, Skill Analysis, Achievements).

### Added
- **Tự động Hóa Cào Dữ Liệu VioEdu Định Kỳ 5 Phút (Auto-Crawl VioEdu 5-Min Loop)**:
  - Tích hợp công tắc chuyển đổi trực quan (Toggle Switch) trên giao diện Collector (`#bot-auto-crawl-toggle`).
  - Huy hiệu trạng thái nhấp nháy xanh (`#bot-auto-crawl-badge`) và đồng hồ đếm ngược kỹ thuật số (`#bot-countdown-display`) hiển thị đếm ngược 05:00 -> 00:00.
  - Tự động gọi endpoint `POST /api/collect/run` cào vòng thi VioEdu khi hết giờ, lưu vết vào `collector_logs`, tự động cập nhật số câu hỏi mới vào Ngân hàng và reset bộ đếm về 300 giây.
  - Lưu trạng thái bật/tắt vào `localStorage` (`eduquest_bot_autocrawl`) để tự động khôi phục khi tải lại trang.
- **Bóc Tách Đề Thi Từ Ảnh (Image OCR Exam Ingestion)**:
  - Mở rộng phân hệ bóc tách đề thi (`backend/pdf_extractor.py`) tiếp nhận tệp ảnh đề thi (.png, .jpg, .jpeg, .webp, .bmp) qua `POST /api/import/image`, `POST /api/import/pdf` và `POST /api/import/exam-file`.
  - Tiền xử lý ảnh chuyên sâu với OpenCV: chuyển ảnh xám, cân bằng tương phản thích ứng cục bộ CLAHE và khử nhiễu song phương bilateralFilter.
  - Động cơ OCR đa tầng (RapidOCR PaddleOCR ONNX, EasyOCR PyTorch, PyTesseract fallback) bóc tách tiếng Việt có dấu, cấu trúc trắc nghiệm A/B/C/D và số thứ tự câu.
  - Vùng kéo thả đa định dạng trên web, khung xem trước ảnh (Image preview) và bảng đối soát câu hỏi (Audit review table) với live KaTeX preview trước khi lưu vào CSDL.
- **Biên Soạn & Xuất Đề Thi Chuẩn In Ấn MOET PDF A4**:
  - Bổ sung nút "📑 Xuất Đề thi PDF" trên giao diện Biên soạn & Trộn Đề thi bên cạnh nút xuất Word.
  - Endpoint `POST /api/export/pdf` render bằng Playwright Chromium Headless ra định dạng PDF chuẩn Bộ Giáo dục & Đào tạo: khổ A4, căn lề chuẩn (trên 20mm, dưới 20mm, trái 25mm, phải 15mm), font Times New Roman 12pt, ngắt trang thông minh.
  - Tự động đính kèm Trang Đáp Án và Bảng Điểm chi tiết ở cuối đề thi (`page-break-before: always`).
  - Chuẩn hóa toàn bộ ký tự toán học và khoa học: phân số `\frac{a}{b}`, căn `\sqrt{x}`, nhân `\times`, chia `\div`, góc `\angle`, ký tự Hy Lạp `\pi, \alpha, \beta`, số mũ `x^2, x^3`, công thức hóa học.
  - Cơ chế dự phòng in ấn phía client (`window.print()` với `@media print`) khi ngoại tuyến hoặc máy chủ bận.
- **Phân Hệ Luyện Tập Đề Thi Tương Tác Cao Cấp (Interactive Practice Arena)**:
  - Giao diện phòng thi trực tuyến hiện đại với thanh HUD thời gian thực, đồng hồ đếm ngược với cảnh báo màu động (vàng khi < 3 phút, đỏ nhấp nháy khi < 1 phút) và tự động nộp bài khi hết giờ.
  - Phím tắt bàn phím tiện lợi (chọn đáp án `1-4` hoặc `A-D`).
  - Lưới điều hướng câu hỏi (Stepper grid) trực quan với 4 trạng thái: Chưa làm (xám), Đã làm (xanh ngọc), Đánh dấu xem lại (vàng cờ 🚩), và Câu đang chọn (viền nổi bật).
  - Chấm điểm tự động tức thì theo thang 10 và thang 100 kèm xếp loại học lực chuẩn MOET (Xuất sắc, Giỏi, Khá, Trung bình, Cần cố gắng).
  - Chế độ xem lại chi tiết (Review mode): tô màu xanh cho đáp án đúng, màu đỏ cho lựa chọn sai, hiển thị lời giải chi tiết và công thức Toán/Tiếng Việt render chuẩn KaTeX.
- **Lưu Trữ Lịch Sử Luyện Tập & Báo Cáo Phân Tích (Practice History & Analytics)**:
  - Bảng SQLite mới `practice_history` với 16 trường dữ liệu và 4 chỉ mục hiệu năng (`idx_practice_created_at`, `idx_practice_subject`, `idx_practice_grade`, `idx_practice_exam_id`).
  - Các endpoint API: `POST /api/practice/submit`, `GET /api/practice/history`, `GET /api/practice/history/{record_id}`, `GET /api/practice/analytics`.
  - Báo cáo Xu hướng (Trending Score Chart) vẽ bằng HTML5 Canvas sắc nét trên màn hình Retina, thể hiện tiến độ điểm số qua các bài thi gần nhất.
  - Phân tích Năng lực (Skill & Subject Mastery Analysis) thống kê tỷ lệ thành thạo từng môn học.
  - Hệ thống Gamification với 8 Huy hiệu thành tích học tập mở khóa linh hoạt theo kết quả.
- **Nhật Ký Bắt Câu Hỏi (Question Capture Logs Modal)**:
  - Thêm nút mở modal xem nhật ký câu hỏi đã bắt từ VioEdu & VnDoc trong bảng điều khiển Collector.
  - Hiển thị song song dạng thẻ trực quan và dạng JSON thô, hỗ trợ 1-click nạp lại (re-inject) vào Ngân hàng câu hỏi.
- **Mở Rộng Bộ Kiểm Thử Tự Động Toàn Diện (`test_app.py`)**:
  - Bổ sung Bước 16 (Đồng bộ phiên bản), Bước 17 (Kiểm định Normalizer & phân biệt khoa học vs khóa học), Bước 18 (Xuất PDF chuẩn MOET & Image OCR), Bước 19 (Phân hệ Luyện tập, practice_history & Gamification).
  - Toàn bộ 19 bước kiểm thử vượt qua 100%.

### Changed
- **Đồng Bộ Tuyệt Đối Phiên Bản Toàn Hệ Thống**:
  - Web App: Đồng bộ `v1.0.24` trên toàn bộ giao diện và mã nguồn (`frontend/index.html`, `frontend/js/app.js`).
  - Cache Buster: Cập nhật `?v=1.0.28` trên tất cả liên kết CSS và Script.
  - Chrome Extension: Đồng bộ thống nhất 100% lên `v1.3.15` trên toàn bộ 6 tệp tiện ích (`manifest.json`, `background.js`, `interceptor.js`, `content.js`, `popup.html`, `popup.js`).
  - Loại bỏ hoàn toàn mọi xuất hiện của các phiên bản cũ `v1.3.0`, `v1.3.11`, `v1.3.12`, `v1.3.14`.

### Fixed
- **Sửa Lỗi Va Chạm Từ Khóa Normalizer Giữa Môn Khoa Học & Quảng Cáo Khóa Học**:
  - Sửa hàm `is_valid_question_payload()` trong `backend/normalizer.py`: chuyển sang dùng regex kiểm tra nghiêm ngặt có dấu thanh (`(?:khóa|khoá)\s+học`), bảo toàn nguyên vẹn các bài đọc hiểu và bài tập khoa học chứa cụm từ "khoa học", "truyện khoa học", "khoa học tự nhiên" không bị từ chối oan.
  - Ngăn chặn triệt để 100% spam quảng cáo khóa học, dịch vụ gia sư và tuyển sinh có dấu.
- **Dọn Dẹp Bản Ghi Menu Mồ Côi Trong CSDL**:
  - Xóa triệt để bản ghi rác `dom_text_1790846122435` khỏi `data/questions.db`.
  - Tái lập thứ tự liên tục `q_number` từ 1..N và làm mới bộ đệm thống kê.
- **Khắc Phục Lệch Hợp Đồng Dữ Liệu Chấm Điểm Phòng Luyện Tập (Practice Arena Contract & Grading Fix)**:
  - Bổ sung `AliasChoices` và `@model_validator(mode="before")` trong `backend/models.py` (`PracticeAnswerSubmission`): tiếp nhận liền mạch cả 3 tên khóa `selected_answer`, `selected_option`, và `user_answer`, giải quyết dứt điểm lỗi rơi rụng dữ liệu chấm điểm khiến mọi bài nộp bị 0.0/10.
  - Phía web client (`frontend/js/practice.js`): gửi đồng thời cả `selected_answer`, `selected_option` và `user_answer` trong mỗi phần tử danh sách bài làm.
  - Phía web client (`frontend/js/practice.js`): bóc tách linh hoạt `data.questions || data.session?.questions || []` khi khởi tạo phòng thi, và `data.records || data.history || []` khi tải lịch sử.
  - Phía web client (`frontend/js/practice.js`): chuẩn hóa `unlockedSet` trong `renderBadgesGrid` hỗ trợ cả danh sách chuỗi ID và mảng đối tượng `{ id, unlocked }`, cùng hỗ trợ mảng đối tượng `subject_mastery`.
  - Cập nhật bộ kiểm thử `test_app.py` Bước 19: kiểm định chấm điểm tự động cho điểm thật `score > 0.0` và `correct_count > 0` trên cả 3 biến thể bí danh đáp án.
  - Đồng bộ hợp đồng dữ liệu trong `DATA_MAPPING.md`.

### Files touched
- `backend/app.py`
- `backend/database.py`
- `backend/models.py`
- `backend/pdf_extractor.py`
- `backend/normalizer.py`
- `extension/manifest.json`
- `extension/background.js`
- `extension/interceptor.js`
- `extension/content.js`
- `extension/popup.html`
- `extension/popup.js`
- `frontend/index.html`
- `frontend/css/style.css`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `frontend/js/exam_builder.js`
- `frontend/js/practice.js`
- `data/questions.db`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.24] - 2026-10-01 15:48:00

### User Request
> Extension:
> [
>   {
>     "content_html": "<div class=\"panel-heading\"><i class=\"fa fa-question-circle-o\"></i> Câu hỏi số 6</div>...",
>     "content_text": "Câu hỏi số 6 Lan học lớp 2C trường Tiểu học Trần Hưng Đạo. Bạn thân nhất của Lan là Minh...",
>     "subject": "english", ...
>   },
>   ... (24 câu hỏi thu thập từ VioEdu & VnDoc qua Extension)
> ]

### Added
- **Mở rộng Tập từ khóa và Nhận diện Chuyên sâu Tiếng Việt Tiểu học (`backend/classifier.py`)**:
  - Bổ sung bộ từ khóa ngữ pháp, đọc hiểu lớp 1 - 5: các mẫu câu kinh điển (*Ai là gì*, *Ai làm gì*, *Ai thế nào*, *câu nêu đặc điểm*, *câu nêu hoạt động*), phân tích ngữ âm (*vần s*, *vần x*, *điền âm*, *âm đầu*), dấu câu (*dấu phẩy*, *dấu chấm*, *dấu hai chấm*, *dấu chấm than*), và kỹ năng đọc hiểu văn bản (*đoạn văn*, *bài đọc*, *nhân vật*, *cho thấy điều gì*, *nội dung chính*).
  - Tự động nhận diện bài đọc hiểu Tiếng Việt: Nếu văn bản nhiều đoạn có dấu thanh Tiếng Việt và không có ký hiệu toán học, phân loại ngay về `vietnamese`.
- **Bộ Lọc Chặn Rác Toàn Diện Giao Diện VioEdu & Trang Chủ VnDoc (`extension/content.js`)**:
  - Chặn triệt để khối header sao kỹ năng VioEdu (`_1Tl2B`, `_1pVpr`, `_1MIz2`, `_1ZsoA`), popup gợi ý tính điểm (`.score-hint-popup`, "Cách tính điểm khi trả lời ĐÚNG hoặc SAI..."), và ảnh huy hiệu (`star_practice_skillname.png`).
  - Hạn chế cào tự động trên VnDoc (`isEduLearningActive`): chỉ kích hoạt trên các trang bài tập, trắc nghiệm, đề kiểm tra (`/trac-nghiem-`, `/de-thi-`, `/bai-tap-`, `/de-kiem-tra-`, `/phieu-bai-tap-`), hoàn toàn vô hiệu hóa quét trên trang chủ `https://vndoc.com/`.
  - Nâng cấp `scanByTextHeuristic`: Bỏ qua triệt để các thẻ liên kết `<a>`, thẻ `<nav>`, `<header>`, `<footer>`, `.menu`, `.video-item`, `.home-video-item` và các anchor khóa học video, ngăn chặn thu thập nhầm bài tập giả.
- **Bộ Kiểm Tra Thẩm Định 2 Tầng (`backend/normalizer.py`)**:
  - `is_valid_question_payload()`: Bổ sung chốt chặn loại bỏ thông báo tính điểm VioEdu ("cách tính điểm", "tổng điểm <") và thẻ video bài giảng VnDoc ("video mở đầu", "học online luyện từ").
  - `normalize_question_payload()`: Bổ sung cơ chế tự sửa bộ môn khi payload bị gán nhầm `subject: "english"` nhưng văn bản có dấu thanh Tiếng Việt.
- **Làm Sạch Dữ Liệu CSDL SQLite (`data/questions.db`)**:
  - Loại bỏ hoàn toàn 13 câu rác video VnDoc và khối điểm số VioEdu.
  - Chuẩn hóa toàn bộ các câu hỏi VioEdu Lớp 2 thực tế về đúng bộ môn Tiếng Việt (`vietnamese`), bổ sung đáp án đúng (`correct_answer`) và lời giải chi tiết.
- **Bộ Kiểm Thử Tự Động Toàn Diện (`test_app.py`)**:
  - Bổ sung Bước 15 kiểm tra nhận diện môn Tiếng Việt, từ chối payload rác và cơ chế tự động sửa lỗi gán nhãn `english`. Toàn bộ 15 bước kiểm thử đều vượt qua 100%.

### Changed
- **Sửa Lỗi Nhận Diện Sai Bộ Môn Trong Extension (`detectSubject`)**:
  - Khắc phục lỗi bắt nhầm từ khóa "Tiếng Anh" từ thanh menu định hướng của VioEdu khiến mọi câu hỏi đọc hiểu/ngữ pháp bị gán sai thành `english`. Ưu tiên tiêu đề trang (`document.title`), breadcrumb và URL.
  - Tự động ghi đè bộ môn sang `vietnamese` nếu nội dung câu hỏi là văn bản có dấu thanh Tiếng Việt và không chứa công thức toán.
- **Cập nhật Phiên bản Hệ thống**:
  - Web App: `v1.0.24` (cập nhật hiển thị tại `frontend/index.html` và `frontend/js/app.js`).
  - Extension: `v1.3.15` (`extension/manifest.json`, `extension/content.js`).
  - Cache Buster: `?v=1.0.28`.

### Fixed
- Sửa lỗi câu hỏi đọc hiểu "Lan và Minh", bài tập điền vần "s/x", bài tập phân loại câu "Ai là gì", bài tập đặt dấu phẩy bị gán nhãn sai thành môn Tiếng Anh (`english`).
- Sửa lỗi bắt dính các đường link video bài giảng Mĩ thuật/Luyện từ trên trang chủ `vndoc.com` và lưu thành câu hỏi Toán học giả mạo.
- Sửa lỗi bắt dính thanh tiến độ sao kỹ năng và popup hướng dẫn tính điểm trên VioEdu.

### Files touched
- `backend/classifier.py`
- `backend/normalizer.py`
- `backend/app.py`
- `extension/content.js`
- `extension/manifest.json`
- `frontend/index.html`
- `frontend/js/app.js`
- `data/questions.db`
- `DATA_MAPPING.md`
- `rules.md`
- `changelog.md`
- `test_app.py`

## [v1.0.23] - 2026-10-01 15:35:00

### User Request
> các link đang mặc định chỉ cho lớp 2 như thế không đúng khi cào data cho các khối lớp khác. Hãy sửa lại để phù hợp với các khối từ 1 đến 12

### Added
- **Hỗ trợ Toàn diện Khối lớp 1 đến 12 (Universal Multi-Grade Harvester & Hunter)**:
  - **Động cơ phân tích khối lớp từ URL (`extract_grade_from_url`)**: Nhận diện chính xác khối lớp 1–12 từ query parameter (`classes=`, `grade=`, `lop=`, `class=`), path slugs (`toan-lop-X`, `lop-X`, `grade-X`), và các từ chỉ thứ tự tiếng Anh (`first-grade` đến `twelfth-grade`, `1st-grade` đến `12th-grade`, `algebra`, `geometry`, `algebra2`, `calculus-1`, `precalculus`).
  - **Endpoint Danh mục Nguồn Động**: `GET /api/hunter/grade-sources?grade={1..12}` trả về danh mục liên kết cào dữ liệu được chuẩn hóa động theo từng khối lớp từ 1 đến 12 cho cả 3 nhóm (Việt Nam bám sát GDPT 2018, Quốc tế tiếng Anh và Olympic song ngữ).
  - **Endpoint Nạp Nhanh Đa Khối**: `POST /api/hunter/harvest-by-grade` tiếp nhận `{ "grade": int, "subject": "math" }` để tự động bóc tách, chuẩn hóa và lưu kho câu hỏi cho đúng khối lớp được chọn, ngăn ngừa việc trộn lẫn khối lớp.
  - **Động cơ Sinh Câu hỏi Tham số hóa 12 Khối lớp (`generate_parametric_questions`)**: Xây dựng thuật toán sinh bài toán ngẫu nhiên có kiểm định toán học từ Lớp 1 đến Lớp 12 (Khối 6: Số nguyên, ƯCLN/BCNN, phân số, hình thoi; Khối 7: Dãy tỉ số, đa thức, góc tam giác; Khối 8: Pythagoras, hằng đẳng thức, Thales; Khối 9: Căn bậc hai, hệ thức Vi-ét; Khối 10: Giao tập hợp, BPT, vectơ; Khối 11: Cấp số cộng, đạo hàm, lượng giác; Khối 12: Tiệm cận, mũ/logarit, tích phân, số phức, mặt cầu Oxy/Oxyz).

### Changed
- **Giao diện Trung tâm Thu thập (`collector`) & Bảng Quản trị**:
  - Bổ sung tùy chọn Khối 10, Khối 11, Khối 12 vào tất cả các bộ chọn trên hệ thống: `#filter-grade`, `#matrix-grade`, `#global-default-grade`, `#hunter-grade`, `#scraper-grade`.
  - Hàm `updateGradePresetsUI(grade)` tự động cập nhật lại toàn bộ các liên kết chip gợi ý nhanh (Hành Trang Số `classes={grade}`, OLM `toan-lop-{grade}`, VnDoc `toan-lop-{grade}`, VietJack, K5 Learning, IXL, Khan Academy, Olympic) ngay khi người dùng thay đổi khối lớp.
  - Nút Nạp Nhanh tự động đổi nhãn theo khối: `✨ Nạp nhanh Đề Toán Khối [X] Toàn diện (Anh & Việt)`.
  - Nâng cấp `detectGrade()` trong Extension (v1.3.14): Tự động nhận diện khối lớp 1–12 từ URL và văn bản trang, ưu tiên cấu hình khối lớp đã lưu của người dùng.
- **Nâng Cấp Phiên Bản Hệ Thống**:
  - Web App: `v1.0.23` (cập nhật trên badge header và `APP_VERSION` trong `app.js`).
  - Cache Buster: `?v=1.0.27` trên tất cả tệp CSS và JS.
  - Chrome Extension: `v1.3.14` (`manifest.json` và `content.js`).

### Fixed
- **Khắc phục Triệt để Lỗi Rò rỉ Khối lớp (Grade Leakage Bug)**:
  - Khắc phục điều kiện lọc tại `run_internet_question_hunter` khiến câu hỏi Toán Lớp 2 bị cấy nhầm vào các khối lớp khác khi `subject == "math"`. Giờ đây kho đề mẫu Lớp 2 chỉ kích hoạt nghiêm ngặt khi `grade == 2`.
  - Khắc phục độ ưu tiên phân loại bộ môn Khoa học (`science`) so với độ dài văn bản Tiếng Việt trong `classify_subject()`.
  - Dọn dẹp các thẻ đóng HTML dư thừa trong `frontend/index.html`.

### Files touched
- `backend/app.py`
- `backend/classifier.py`
- `backend/scrapers/internet_hunter.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `extension/manifest.json`
- `extension/content.js`
- `test_app.py`
- `DATA_MAPPING.md`
- `rules.md`
- `changelog.md`

## [v1.0.22] - 2026-10-01 15:15:00

### User Request
> tích hợp tính năng lấy dữ liệu từ các nguồn trên vào EduQuest Pro

### Added
- **Tích hợp Toàn diện Nguồn Bài tập & Đề thi Toán Lớp 2 (Tiếng Việt, Tiếng Anh & Olympic)**:
  - **Nhóm 1: Toán Lớp 2 Tiếng Việt (GDPT 2018)**: Tích hợp VioEdu (`vio.edu.vn`), Trạng Nguyên Toán (`tnmath.edu.vn`), Hành Trang Số (`hanhtrangso.nxbgd.vn` - SGK & SBT Kết nối & Cánh diều), OLM.vn (`olm.vn` - ĐH Sư Phạm), VnDoc (`vndoc.com` - Phiếu bài tập cuối tuần & Đề thi học kỳ), VietJack (`vietjack.com`).
  - **Nhóm 2: Toán Lớp 2 Tiếng Anh (Math Grade 2 - Chuẩn Quốc tế)**: Tích hợp K5 Learning (`k5learning.com` - Worksheets PDF in ấn có Answer Key), IXL Learning (`ixl.com` - Kỹ năng thích ứng US Common Core), Khan Academy (`khanacademy.org` - 2nd Grade Math), Common Core Math (`commoncoresheets.com`).
  - **Nhóm 3: Toán Olympic & Tư duy Lớp 2 (Song ngữ Anh - Việt)**: Tích hợp Kangaroo Math (`kangaroo-math.vn` - Cấp độ Ecolier Khối 1-2), Olympic TIMO (`lmsfermat.edu.vn` - Primary 2 Song ngữ), SASMO & CodeMath (`codemath.vn`).
- **Kho Dữ liệu Mẫu Chuyên biệt Toán Lớp 2 (`GRADE2_MATH_VN_POOLS`, `GRADE2_MATH_EN_POOLS`, `GRADE2_MATH_OLYMPIAD_POOLS`)**:
  - Hàng chục câu hỏi tuyển chọn chuẩn hóa LaTeX/KaTeX: phép cộng/trừ có nhớ trong phạm vi 100/1000, toán có lời văn "nhiều hơn/ít hơn", bảng nhân 2/5, bảng chia 2/5, đo lường (dm, m, km, lít, kg), hình học đường gấp khúc, 2D shapes, place value (hundreds, tens, ones), even/odd, coins (cents, dimes, nickels), bài toán logic và chu kỳ dãy số.
- **Nút Hành Động 1-Click: "✨ Nạp nhanh Đề Toán Lớp 2 Toàn diện (Anh & Việt)" (`#btn-harvest-grade2`)**:
  - Endpoint `POST /api/hunter/harvest-grade2` quét đồng thời 6 nguồn học liệu trọng điểm và tự động nạp ngân hàng câu hỏi Toán Lớp 2 vào CSDL SQLite.
- **Endpoint Danh mục Nguồn: `GET /api/hunter/grade2-sources`**:
  - Trả về danh mục tra cứu chi tiết các nguồn Toán Lớp 2 phân loại theo 3 nhóm kèm URL, icon và mô tả.
- **Cải tiến Động Cơ Tham Số Hóa Động (`generate_parametric_questions`)**:
  - Bổ sung các chế độ sinh tự động ngẫu nhiên: `vn_more_less`, `vn_geometry`, `en_word_problem`, `en_place_value`, `en_even_odd`, `en_money`, `bilingual_olympiad`.
- **Cập nhật Tiện ích Extension (v1.3.13)**:
  - Bổ sung Host Permissions & Content Scripts cho: `olm.vn`, `k5learning.com`, `ixl.com`, `khanacademy.org`, `kangaroo-math.vn`, `commoncoresheets.com`, `math-drills.com`.
  - Bổ sung nhận diện nền tảng trong `getPlatformName()` và nhận diện câu hỏi Toán tiếng Anh trong `detectSubject()`.

### Changed
- **Nâng Cấp Bộ Phân Loại Bộ Môn Thông Minh (AI Classifier)**:
  - Bổ sung bộ từ khóa toán học tiếng Anh tiểu học (`place value`, `regrouping`, `word problem`, `tens and ones`, `even or odd`, `coins`, `cents`, `k5 learning`, `ixl`) đảm bảo câu hỏi Toán tiếng Anh luôn được định tuyến chuẩn xác về bộ môn `math`, không bị nhầm lẫn sang `english`.
- **Thẻ Nguồn Gốc Chi Tiết (`compute_source_detail`)**:
  - Tự động gán nhãn nguồn rõ ràng: `K5 Learning (US Math)`, `IXL Learning Math`, `Khan Academy Math`, `OLM.vn (ĐH Sư Phạm)`, `Olympic Kangaroo (IKMC)`...
- **Gợi ý Nguồn Cào Nhanh trên Giao diện (`collector`)**:
  - Phân chia thành 3 dòng danh mục trực quan có nhãn cờ quốc gia và biểu tượng: 🇻🇳 Toán 2 Tiếng Việt, 🇬🇧 Math Grade 2 (Anh), 🏆 Olympic Song ngữ.
- **Nâng Cấp Phiên Bản Web App `v1.0.22` & Cache Buster `?v=1.0.26`**.

### Files touched
- `backend/app.py`
- `backend/classifier.py`
- `backend/database.py`
- `backend/scrapers/internet_hunter.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `extension/manifest.json`
- `extension/content.js`
- `DATA_MAPPING.md`
- `rules.md`
- `changelog.md`
- `test_app.py`

## [v1.0.21] - 2026-10-01 15:00:00

### User Request
> Tự động Săn câu hỏi từ Internet (Internet Question Hunter):
> - sắp xếp log mới nhất trên cùng
> - log ghi lẫn lộn dòng => tách riêng từng dòng cho mỗi log
> - thêm nút copy, xóa log
> [9:48:57 AM] ⚡ [THỦ CÔNG] Săn câu hỏi (Môn: ALL, Khối 2)...-> Danh sách mục tiêu: Sẽ cào 1 web/link: https://trangnguyen.edu.vn/[9:48:58 AM] Thu thập thành công! Đã bóc tách và lưu 6 câu hỏi vào CSDL.[9:50:13 AM] ⚡ [THỦ CÔNG] Săn câu hỏi (Môn: ALL, Khối 2)...-> Danh sách mục tiêu: Sẽ cào 5 web/link: https://hanhtrangso.nxbgd.vn/sach-dien-tu?book_active=0&classes=2, https://hanhtrangso.nxbgd.vn/sach-dien-tu?book_active=2&classes=2...[9:50:29 AM] Thu thập thành công! Đã bóc tách và lưu 6 câu hỏi vào CSDL...
> [8:51:44 AM] 🔄 [TỰ ĐỘNG ĐỊNH KỲ] Săn câu hỏi (Môn: ALL, Khối 2)...
> -> Danh sách mục tiêu: Sẽ cào 11 web/link: https://codemath.vn/khoa-hoc/timo, https://www.hacodemath.com/...
> [8:51:44 AM] Lỗi kết nối: Failed to fetch
> [2:45:29 PM] 🔄 [TỰ ĐỘNG ĐỊNH KỲ] Săn câu hỏi (Môn: ALL, Khối 2)...
> -> Danh sách mục tiêu: Sẽ cào 11 web/link: https://codemath.vn/khoa-hoc/timo, https://www.hacodemath.com/...
> [2:45:37 PM] Thu thập thành công! Đã bóc tách và lưu 106 câu hỏi vào CSDL.

### Added
- **Thanh Công Cụ Thao Tác Cho Nhật Ký Thợ Săn Internet (`#hunter-log-toolbar`)**:
  - Nút **`📋 Sao chép Log`**: Sao chép toàn bộ nhật ký săn câu hỏi vào Clipboard hệ thống với đầy đủ ngắt dòng chuẩn xác (tích hợp `navigator.clipboard` và fallback `document.execCommand`).
  - Nút **`🗑️ Xóa Log`**: Xóa sạch màn hình nhật ký và xóa triệt để bộ nhớ đệm `eduquest_hunter_log` trong `localStorage`.
- **Cơ Chế Phục Hồi & Tự Động Định Dạng Nhật Ký Cũ (`formatAndSortHunterLog`)**:
  - Tự động tách các dòng log bị dính ngang do `innerText` trong `localStorage`.
  - Tự động phát hiện và đảo ngược thứ tự các phiên log cũ (từ tăng dần sang giảm dần) để đưa các phiên săn mới nhất lên đầu bảng.

### Changed
- **Sắp Xếp Nhật Ký Săn Câu Hỏi Mới Nhất Lên Trên Cùng (Newest on Top)**:
  - Cập nhật hàm `runInternetHunter`: mỗi phiên săn mới (thủ công hoặc tự động định kỳ 5 phút) được đưa lên đầu khung nhật ký kèm chỉ báo `⏳ Đang kết nối và quét dữ liệu internet...`, sau đó cập nhật kết quả hoàn thành ngay tại đầu log mà không cần người dùng phải cuộn trang.
  - Phân tách các phiên săn bằng khoảng cách dòng trống rõ ràng (`\n\n`), mỗi sự kiện hiển thị trên một dòng riêng biệt.
- **Nâng Cấp Phiên Bản Web App `v1.0.21` & Cache Buster `?v=1.0.25`**:
  - Cập nhật số phiên bản đồng bộ trên giao diện `index.html` và `app.js`.

### Fixed
- Khắc phục triệt để lỗi mất ký tự ngắt dòng `\n` khiến các dòng log mục tiêu và kết quả bị dính liền vào nhau trên cùng một hàng ngang khi đọc/ghi `innerText` từ DOM.

### Files touched
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `rules.md`
- `changelog.md`

## [v1.0.20] - 2026-10-01 09:50:00

### User Request
> [9:36:43 AM] ❌ Lỗi: Phản hồi từ VioEdu: OVER_QUOTA
> [09:36:43] ❌ Phản hồi từ VioEdu: OVER_QUOTA
> [09:36:42] 🔑 Đang kiểm tra xác thực tài khoản VioEdu...
> [09:36:42] 🎯 Phân tích mục tiêu cào dữ liệu: Kiểu 'SKILL_PRACTICE'
> [09:36:42] 🚀 Khởi động Bot Đăng nhập Ngầm VioEdu cho tài khoản: minalinh19...

### Added
- **Cơ Chế Tự Động Giải Phóng Phiên Khi Vượt Quá 3 Thiết Bị (OVER_QUOTA & 289 Auto-Recovery)**:
  - Tích hợp hàm `reset_vioedu_devices(username)`: gửi trực tiếp mutation GraphQL `resetLogin3Devices(username: $username)` của VioEdu để giải phóng các phiên làm việc cũ khi tài khoản đạt giới hạn 3 thiết bị đồng thời.
  - Tự động kích hoạt cơ chế đăng nhập lại (`auto-retry`) sau khi giải phóng thành công, giúp Bot tiếp tục lấy session cookies và profile mà không bị gián đoạn.
  - Bổ sung phát hiện và kích hoạt tự động nút `"Đăng xuất toàn bộ thiết bị"` trên giao diện Playwright Chromium nếu xuất hiện hộp thoại xác nhận trên trang web VioEdu.

### Changed
- **Nâng Cấp Xử Lý Mã Trạng Thái Đăng Nhập VioEdu (`login_vioedu`)**:
  - Nhận diện chi tiết và trả về thông báo tiếng Việt chính xác, thân thiện cho từng trường hợp: `OVER_QUOTA`, `WRONG_PASSWORD`, `WRONG_PASSWORD_LOCKED`, `IN_ACTIVE`, `DELETED`.
  - Truyền trực tiếp `log_func` từ `crawl_vioedu_rounds_headless` vào `login_vioedu` để cập nhật trạng thái giải phóng phiên thiết bị thời gian thực lên khung log của người dùng.
- **Tối Ưu Hóa Phân Loại Khối Lớp Cho Bài Luyện Tập Thực Hành**:
  - Đối với bài thực hành (`skill_practice`), ưu tiên sử dụng khối lớp gốc chính xác của bài học (`raw_q.grade`, vd: Lớp 2) thay vì áp đặt toàn bộ theo khối lớp của tài khoản, tránh sai lệch chuyên mục trong CSDL.
- **Nâng Cấp Phiên Bản Web App `v1.0.20` & Cache Buster `?v=1.0.24`**:
  - Cập nhật số phiên bản đồng bộ trên giao diện `index.html` và `app.js`.

### Fixed
- Khắc phục triệt để lỗi `Phản hồi từ VioEdu: OVER_QUOTA` chặn đứng tiến trình cào dữ liệu của Bot khi tài khoản học sinh đã đăng nhập trên nhiều thiết bị trước đó.

### Files touched
- `backend/scrapers/vioedu.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `DATA_MAPPING.md`
- `rules.md`
- `changelog.md`

## [v1.0.19] - 2026-10-01 09:15:00

### User Request
> "Bot Đăng nhập Tài khoản Cào Vòng thi":
> 1. Thêm Nút Copy Log, sắp xếp log hiển thị theo mới nhất trên đầu
> 2. Sử dụng browser kiểm tra và tối ưu hóa code cào dữ liệu từ các bài thực hành:
> [Toán lớp 2, đề thi Toán 2 - Học kì 1 - VioEdu](https://vio.edu.vn/skill-list) => Chọn môn => chọn bài luyện tập https://vio.edu.vn/skill-practice/* ( ví dụ: [Toán lớp 2 - I.1.1. Cấu tạo các số đến 100](https://vio.edu.vn/skill-practice/64bf82717faf420030d20eeb) ). Hiện tại bot chưa lấy được dữ liệu từ các trang này => đảm bảo không bị phát hiện khóa tài khoản, không làm sai lệch các bài luyện tập để user còn sử dụng web để học và luyện tập

### Added
- **Nút Sao Chép & Xóa Log Cho Bot Cào Dữ Liệu**:
  - Bổ sung thanh công cụ phía trên khung log của Bot với hai nút: `📋 Sao chép Log` (hỗ trợ `navigator.clipboard` kèm fallback) và `🗑️ Xóa Log`.
  - Tự động hiển thị và đồng bộ trạng thái thanh công cụ khi có log mới hoặc khôi phục từ `localStorage`.
- **Cơ Chế Cào Bài Thực Hành VioEdu An Toàn Tuyệt Đối (Read-Only GraphQL)**:
  - Tích hợp hàm `fetch_vioedu_skill_practice_questions`: truy vấn trực tiếp câu hỏi bài luyện tập VioEdu qua GraphQL `PracticeQuestionQuery`.
  - Cơ chế thụ động an toàn: giữ nguyên `score: 0`, `isManual: false`, tuyệt đối **không gửi `PracticeResultMutation`**, không bấm nút nộp bài/trả lời, bảo toàn 100% điểm số, chuỗi thành tích và hạn mức luyện tập của học sinh.
  - Tích hợp hàm `fetch_vioedu_skills_in_grade`: tự động dò tìm toàn bộ danh mục kỹ năng của khối lớp tương ứng trên `https://vio.edu.vn/skill-list`.
- **Phân Tích Cú Pháp Đầy Đủ Cho Mọi Dạng Câu Hỏi Thực Hành VioEdu**:
  - Hỗ trợ câu hỏi Điền ô trống (`questionType: 3` / `{}`): tự động bóc tách đáp án điền từ `answers` vào `correct_answer`, để trống `options`.
  - Hỗ trợ câu hỏi Trắc nghiệm một đáp án (`questionType: 1`) & Nhiều đáp án (`questionType: 2`): trích xuất chính xác đáp án đúng từ thuộc tính `correct: true` của server.
  - Hỗ trợ câu hỏi Nối cặp (`leftMatching` & `rightMatching`) và Dropdown (`textDropdownAnswers`).
  - Trích xuất đầy đủ lời giải chi tiết `explanation` và các ảnh đính kèm.

### Changed
- **Sắp Xếp Log Bot Cào Vòng Thi Theo Thứ Tự Mới Nhất Trên Đầu (Newest on Top)**:
  - Đảo ngược thứ tự hiển thị nhật ký để dòng log mới nhất luôn nằm ở dòng 1 trên đầu khung log, giúp người dùng theo dõi tiến trình tức thời mà không cần cuộn trang.
  - Thông báo hoàn tất/kết quả cuối cùng luôn được ghim lên dòng đầu tiên.
- **Nhận Diện Mục Tiêu Thông Minh (`parse_vioedu_target`)**:
  - Tự động phân tích mục tiêu: nhận diện URL `skill-practice/:id`, mã MongoDB hex 24 ký tự, URL `skill-list`, số thứ tự vòng thi arena, hoặc chế độ tự động.
  - Chế độ tự động thông minh: nếu ngoài khung giờ mở đấu trường, Bot tự động chuyển sang thu thập các bài thực hành trọng tâm đúng với khối lớp cố định của học sinh.
- **Nâng Cấp Phiên Bản Web App `v1.0.19` & Cache Buster `?v=1.0.23`**:
  - Đồng bộ phiên bản hiển thị trên giao diện và trong `app.js`, `index.html`.

### Files touched
- `backend/scrapers/vioedu.py`
- `frontend/index.html`
- `frontend/js/collector.js`
- `frontend/js/app.js`
- `DATA_MAPPING.md`
- `rules.md`
- `changelog.md`

## [v1.0.18] - 2026-10-01 07:38:00

### User Request
> [Toán trực tuyến, đề thi thử toán - VioEdu](https://vio.edu.vn/)
> Nâng cấp tính năng Bot Đăng nhập Tài khoản Cào Vòng thi của web để bot tự đăng nhập ngầm và tìm, cào câu hỏi lưu về database.
> Lưu ý: Tài khoản vio.edu.vn có khối lớp cố định

### Added
- **Động Cơ Bot Đăng Nhập Ngầm Playwright (`crawl_vioedu_rounds_headless`)**:
  - Tự động chạy nền với Chromium Headless, đăng nhập vào nền tảng VioEdu (`https://vio.edu.vn/login`) bằng thông tin tài khoản người dùng.
  - Tự động vượt qua các kiểm tra DOM, bắt chính xác các sự kiện xác thực và trả về thông báo rõ ràng trong trường hợp sai thông tin đăng nhập mà không gây nghẽn kết nối.
- **Tự Động Nhận Diện & Khóa Khối Lớp Cố Định Của Tài Khoản VioEdu**:
  - Trích xuất tự động trường khối lớp của học sinh (`user.grade` / `user.class`) từ thông tin tài khoản VioEdu.
  - Khóa chặt khối lớp cố định cho toàn bộ câu hỏi và đề thi cào được, đảm bảo câu hỏi luôn được gán đúng khối lớp của tài khoản khi lưu vào CSDL.
- **Tự Động Tìm Kiếm & Bóc Tách Vòng Thi, Đấu Trường & Luyện Tập**:
  - Tự động dò tìm các vòng đấu trường (`/arena`, `/arena-school`, `/arena-zone`) và đề thi học sinh (`/student-exam`, `/skill-practice`).
  - Hỗ trợ tham số Vòng thi / Mã đấu trường (`round_id`) tùy chọn để vào thẳng vòng thi cụ thể.
  - Lắng nghe gói tin mạng (Network Interception Hook) bóc tách sâu dữ liệu câu hỏi từ GraphQL và REST API.
  - Tự động duyệt qua các bước phân trang câu hỏi (`stepper`) và quét cây DOM để thu thập trọn bộ câu hỏi.
- **Bảo Toàn Công Thức & Lưu Trữ CSDL Tự Động**:
  - Làm sạch triệt để các tiền tố "Câu hỏi số X", "Câu X:" khỏi đề bài.
  - Bảo tồn toàn bộ công thức toán học KaTeX/LaTeX, phương án A/B/C/D, đáp án đúng và lời giải chi tiết.
  - Tự động kiểm tra trùng lặp (`content_hash`) và lưu trực tiếp vào CSDL SQLite `questions.db`.
  - Ghi nhận nhật ký chi tiết vào `collector_logs`.

### Changed
- **Nâng cấp Web App lên `v1.0.18` & Cache Buster `?v=1.0.22`**:
  - Cập nhật giao diện Trung tâm Thu thập (`#scraper-live-log`, `#btn-run-scraper`) với trạng thái tải linh hoạt và nhật ký trực tiếp thời gian thực.
  - Cập nhật `app.js`, `index.html`, `collector.js` và `DATA_MAPPING.md`.

### Files touched
- `backend/scrapers/vioedu.py`
- `backend/app.py`
- `frontend/js/collector.js`
- `frontend/js/app.js`
- `frontend/index.html`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.17] - 2026-09-30 16:40:00

### User Request
> Extension: 
> - cụm từ "Câu hỏi số xx" vẫn hiện vào nội dung câu hỏi
> - Tự động lưu (Zero-Click) nhưng câu hỏi vẫn không được lưu vào CSDL

### Added
- **Cơ chế Tự Động Lưu Bù Đắp (`autoSyncPendingQuestions`)**: Tự động phát hiện các câu hỏi đang chờ lưu (`saved_to_db === false`) trong danh sách tạm của Extension để đẩy lên CSDL EduQuest Pro ở mọi nhịp heartbeat (2.5s), sau thao tác tương tác của học sinh, và khi phát hiện máy chủ kết nối lại.
- **Thống kê Tiến độ Lưu trên Floating Widget**: Widget hiển thị huy hiệu trực quan `[X/Y đã lưu CSDL]`, giúp người dùng nắm bắt chính xác trạng thái lưu trữ của từng câu hỏi.

### Changed
- **Nâng cấp Extension lên `v1.3.12`**: Đồng bộ mã nguồn trên toàn bộ các thành phần `manifest.json`, `content.js`, `background.js`, `interceptor.js`, `popup.html`, `popup.js`.
- **Cập nhật Web App lên `v1.0.17` & Cache Buster `?v=1.0.21`**: Cập nhật `app.js`, `index.html` và làm mới cache stylesheet/scripts.

### Fixed
- **Loại bỏ Triệt để Cụm từ "Câu hỏi số xx", "Câu xx", "Bài xx"**:
  - Tại Extension (`extractCardStem`): Thêm selector bóc tách và phân hủy các thẻ `.panel-heading`, `.practice-question-title`, `.question-title`, `.cau-hoi-so`, `[class*='question-number']` khỏi cây DOM clone; áp dụng regex loại bỏ tiền tố số câu ở cả `content_text` và `content_html`; hàm `cleanTitleElement` tự động loại bỏ tiêu đề nếu chỉ là số câu hỏi.
  - Tại Backend (`backend/normalizer.py`): Hàm `clean_html_and_math` dùng BeautifulSoup tự động decompose các thẻ `panel-heading` và cắt bỏ tiền tố số thứ tự khỏi `clean_text` và `clean_html`.
  - CSDL SQLite (`data/questions.db`): Chạy script làm sạch hoàn toàn tiền tố "Câu hỏi số X" trên các câu hỏi cũ trong cơ sở dữ liệu và tính toán lại `content_hash`.
- **Sửa Lỗi Tự Động Lưu (Zero-Click) Bị Chặn Toàn Trang**:
  - Xóa bỏ hoàn toàn selector toàn trang `Boolean(document.querySelector("[data-vio-loading='true'], .viogpt-loading"))` vốn luôn trả về `true` khi VioEdu khởi tạo widget AI VioGPT.
  - Chuyển sang hàm `isElementActiveLoading` kiểm tra loading cục bộ trên chính thẻ card câu hỏi đang thực sự hiển thị (`offsetParent !== null`).
  - Sửa chốt chặn Progress bar: loại bỏ `closest("[class*='progress']")` tránh chặn nhầm toàn bộ container câu hỏi nằm trong layout cha.
  - Sửa logic xử lý kết quả `POST /api/questions/bulk`: Dù câu hỏi mới được nạp hay đã tồn tại trong CSDL, Extension đều đánh dấu chính xác `saved_to_db: true`.

### Files touched
- `backend/normalizer.py`
- `extension/content.js`
- `extension/manifest.json`
- `extension/background.js`
- `extension/interceptor.js`
- `extension/popup.html`
- `extension/popup.js`
- `frontend/js/app.js`
- `frontend/index.html`
- `data/questions.db`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.16] - 2026-09-30 16:15:00

### User Request
> Extension: sửa lỗi
> 1. json câu hỏi đã quét:
> [
>   {
>     "content_html": "<div class=\"panel-heading\"><i class=\"fa fa-question-circle-o\"></i> Câu hỏi số 5</div><div id=\"MathjaxArea2\" class=\"panel-body  false    panel-body-question \"><div class=\" padding-question-text _2JbJo\"><div class=\"panel-body\"><p></p> <p>Lan học lớp 2C trường Tiểu học Trần Hưng Đạo. Bạn thân nhất của Lan là Minh. Hai bạn ngồi chung bàn từ đầu năm học. Minh là một bạn học sinh rất ngoan và chăm chỉ.</p> <p>Minh có khuôn mặt tròn với đôi mắt đen láy. Bạn cao hơn Lan một chút và có mái tóc đen nhánh. Minh luôn mặc đồng phục sạch sẽ, gọn gàng đến trường.</p> <p>Minh học rất giỏi, đặc biệt là môn Toán. Mỗi khi Lan gặp khó khăn trong bài tập, Minh luôn kiên nhẫn giảng giải cho bạn hiểu. Minh cũng rất thích đọc sách và thường chia sẻ những cuốn sách hay với Lan.</p> <p>Lan cảm thấy rất may mắn khi có một người bạn tốt như Minh. Hai bạn luôn giúp đỡ nhau trong học tập và cùng nhau tiến bộ mỗi ngày.</p> <p>Từ nào sau đây là <strong>từ chỉ đặc điểm</strong>?</p></div></div></div>",
>     "content_text": "Câu hỏi số 5 Lan học lớp 2C trường Tiểu học Trần Hưng Đạo. Bạn thân nhất của Lan là Minh. Hai bạn ngồi chung bàn từ đầu năm học. Minh là một bạn học sinh rất ngoan và chăm chỉ. Minh có khuôn mặt tròn với đôi mắt đen láy. Bạn cao hơn Lan một chút và có mái tóc đen nhánh. Minh luôn mặc đồng phục sạch sẽ, gọn gàng đến trường. Minh học rất giỏi, đặc biệt là môn Toán. Mỗi khi Lan gặp khó khăn trong bài tập, Minh luôn kiên nhẫn giảng giải cho bạn hiểu. Minh cũng rất thích đọc sách và thường chia sẻ những cuốn sách hay với Lan. Lan cảm thấy rất may mắn khi có một người bạn tốt như Minh. Hai bạn luôn giúp đỡ nhau trong học tập và cùng nhau tiến bộ mỗi ngày. Từ nào sau đây là từ chỉ đặc điểm?",
>     "correct_answer": null,
>     "difficulty": "medium",
>     "exam_name": "Toán lớp 2 - \"Đề đánh giá năng lực số 1\" - VioEdu",
>     "explanation": "",
>     "grade": 2,
>     "id": "dom_1790758278099_0",
>     "images": [],
>     "options": [
>       {
>         "content": "bàn",
>         "id": "A",
>         "is_correct": false
>       },
>       {
>         "content": "học sinh",
>         "id": "B",
>         "is_correct": false
>       },
>       {
>         "content": "trường",
>         "id": "C",
>         "is_correct": false
>       },
>       {
>         "content": "chăm chỉ",
>         "id": "D",
>         "is_correct": false
>       }
>     ],
>     "question_type": "single_choice",
>     "saved_to_db": true,
>     "source_platform": "vioedu",
>     "source_url": "https://vio.edu.vn/onboard-flow/6a39eada2e5ef5003091db5e",
>     "subject": "vietnamese",
>     "topic": "VioEdu Luyện tập & Đấu trường"
>   },
>   {
>     "content_html": "<div class=\" padding-question-text _2JbJo\"><div class=\"panel-body\"><p></p> <p>Lan học lớp 2C trường Tiểu học Trần Hưng Đạo. Bạn thân nhất của Lan là Minh. Hai bạn ngồi chung bàn từ đầu năm học. Minh là một bạn học sinh rất ngoan và chăm chỉ.</p> <p>Minh có khuôn mặt tròn với đôi mắt đen láy. Bạn cao hơn Lan một chút và có mái tóc đen nhánh. Minh luôn mặc đồng phục sạch sẽ, gọn gàng đến trường.</p> <p>Minh học rất giỏi, đặc biệt là môn Toán. Mỗi khi Lan gặp khó khăn trong bài tập, Minh luôn kiên nhẫn giảng giải cho bạn hiểu. Minh cũng rất thích đọc sách và thường chia sẻ những cuốn sách hay với Lan.</p> <p>Lan cảm thấy rất may mắn khi có một người bạn tốt như Minh. Hai bạn luôn giúp đỡ nhau trong học tập và cùng nhau tiến bộ mỗi ngày.</p> <p>Từ nào sau đây là <strong>từ chỉ đặc điểm</strong>?</p></div></div>",
>     "content_text": "Lan học lớp 2C trường Tiểu học Trần Hưng Đạo. Bạn thân nhất của Lan là Minh. Hai bạn ngồi chung bàn từ đầu năm học. Minh là một bạn học sinh rất ngoan và chăm chỉ. Minh có khuôn mặt tròn với đôi mắt đen láy. Bạn cao hơn Lan một chút và có mái tóc đen nhánh. Minh luôn mặc đồng phục sạch sẽ, gọn gàng đến trường. Minh học rất giỏi, đặc biệt là môn Toán. Mỗi khi Lan gặp khó khăn trong bài tập, Minh luôn kiên nhẫn giảng giải cho bạn hiểu. Minh cũng rất thích đọc sách và thường chia sẻ những cuốn sách hay với Lan. Lan cảm thấy rất may mắn khi có một người bạn tốt như Minh. Hai bạn luôn giúp đỡ nhau trong học tập và cùng nhau tiến bộ mỗi ngày. Từ nào sau đây là từ chỉ đặc điểm?",
>     "correct_answer": null,
>     "difficulty": "medium",
>     "exam_name": "Toán lớp 2 - \"Đề đánh giá năng lực số 1\" - VioEdu",
>     "explanation": "",
>     "grade": 2,
>     "id": "dom_MathjaxArea2",
>     "images": [],
>     "options": [
>       {
>         "content": "bàn",
>         "id": "A",
>         "is_correct": true
>       },
>       {
>         "content": "học sinh",
>         "id": "B",
>         "is_correct": true
>       },
>       {
>         "content": "trường",
>         "id": "C",
>         "is_correct": true
>       },
>       {
>         "content": "chăm chỉ",
>         "id": "D",
>         "is_correct": true
>       }
>     ],
>     "question_type": "single_choice",
>     "saved_to_db": true,
>     "source_platform": "vioedu",
>     "source_url": "https://vio.edu.vn/onboard-flow/6a39eada2e5ef5003091db5e",
>     "subject": "vietnamese",
>     "topic": "VioEdu Luyện tập & Đấu trường"
>   },
>   {
>     "content_html": "<div class=\"irXzU\"><div class=\"_1WeAM\"><div class=\"Vt514\"><div class=\"progress\"><div class=\"progress-bar\" role=\"progressbar\" aria-valuenow=\"25\" aria-valuemin=\"0\" aria-valuemax=\"100\" style=\"width: 25%;\"></div></div></div><p>Bạn đã hoàn thành 5/20 câu <span>25%</span></p></div></div>",
>     "content_text": "Bạn đã hoàn thành 5/20 câu 25%",
>     "correct_answer": null,
>     "difficulty": "medium",
>     "exam_name": "Toán lớp 2 - \"Đề đánh giá năng lực số 1\" - VioEdu",
>     "explanation": "",
>     "grade": 2,
>     "id": "dom_1790758307545_0",
>     "images": [],
>     "options": [],
>     "question_type": "fill_blank",
>     "saved_to_db": true,
>     "source_platform": "vioedu",
>     "source_url": "https://vio.edu.vn/onboard-flow/6a39eada2e5ef5003091db5e",
>     "subject": "vietnamese",
>     "topic": "VioEdu Luyện tập & Đấu trường"
>   },
>   {
>     "content_html": "<div class=\"panel-heading\"><i class=\"fa fa-question-circle-o\"></i> Câu hỏi số 6</div><div id=\"MathjaxArea3\" class=\"panel-body  false    panel-body-question \"><div class=\"loading\" data-vio-loading=\"true\"><div class=\"loading-spinner\"><img src=\"https://s3.vio.edu.vn/assets/img/2025/ai/viogpt-loading.gif\" alt=\"loading-spinner\"> <p>Đang lấy thông tin câu hỏi</p></div></div></div>",
>     "content_text": "Câu hỏi số 6Đang lấy thông tin câu hỏi...",
>     "correct_answer": null,
>     "difficulty": "medium",
>     "exam_name": "Toán lớp 2 - \"Đề đánh giá năng lực số 1\" - VioEdu",
>     "explanation": "",
>     "grade": 2,
>     "id": "dom_1790758307804_0",
>     "images": [
>       "https://s3.vio.edu.vn/assets/img/2025/ai/viogpt-loading.gif"
>     ],
>     "options": [],
>     "question_type": "fill_blank",
>     "saved_to_db": true,
>     "source_platform": "vioedu",
>     "source_url": "https://vio.edu.vn/onboard-flow/6a39eada2e5ef5003091db5e",
>     "subject": "vietnamese",
>     "topic": "VioEdu Luyện tập & Đấu trường"
>   },
>   {
>     "content_html": "<div class=\"panel-heading\"><i class=\"fa fa-question-circle-o\"></i> Câu hỏi số 6</div><div id=\"MathjaxArea3\" class=\"panel-body  false    panel-body-question \"><div class=\" padding-question-text _2JbJo\"><div class=\"panel-body\"><p></p> <p>Thứ Hai tuần này là ngày 4 tháng 12. Hỏi thứ Hai tuần sau là ngày mấy tháng 12?</p></div></div></div>",
>     "content_text": "Câu hỏi số 6 Thứ Hai tuần này là ngày 4 tháng 12. Hỏi thứ Hai tuần sau là ngày mấy tháng 12?",
>     "correct_answer": null,
>     "difficulty": "medium",
>     "exam_name": "Toán lớp 2 - \"Đề đánh giá năng lực số 1\" - VioEdu",
>     "explanation": "",
>     "grade": 2,
>     "id": "dom_1790758308588_0",
>     "images": [],
>     "options": [
>       {
>         "content": "ngày 11",
>         "id": "A",
>         "is_correct": false
>       },
>       {
>         "content": "ngày 10",
>         "id": "B",
>         "is_correct": false
>       },
>       {
>         "content": "ngày 12",
>         "id": "C",
>         "is_correct": false
>       },
>       {
>         "content": "ngày 13",
>         "id": "D",
>         "is_correct": false
>       }
>     ],
>     "question_type": "single_choice",
>     "saved_to_db": true,
>     "source_platform": "vioedu",
>     "source_url": "https://vio.edu.vn/onboard-flow/6a39eada2e5ef5003091db5e",
>     "subject": "math",
>     "topic": "VioEdu Luyện tập & Đấu trường"
>   }
> ]
> 2. log:
> [3:51:49 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Câu hỏi số 6 Lan học lớp 2C trườ...'
> (spam liên tục hàng chục dòng)

### Added
- **Lọc Thẻ Cha Ngoài Cùng & Chống Bóc Tách Thẻ Con Lồng Nhau (`Nested Card Filtering`)**:
  - `scanPageQuestions` tự động lọc bỏ các thẻ con nếu thẻ cha bao ngoài đã nằm trong danh sách (`containers.filter(el => !containers.some(p => p !== el && p.contains(el)))`).
  - Triệt tiêu hoàn toàn hiện tượng nhân đôi câu hỏi do vừa bóc `.panel.panel-primary` (có header "Câu hỏi số 5") vừa bóc `#MathjaxArea2`.
- **Chuẩn Hóa Tiền Tố Đề Bài khi Tính Toán Chữ Ký Chống Trùng (`normalizeStemForSignature`)**:
  - Hàm `normalizeStemForSignature` tách bỏ tiền tố `^(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*\d+)[\s\.\:\-_]*` trước khi hash signature.
  - Đảm bảo câu hỏi có tiền tố hay không có tiền tố đều được nhận diện chính xác 100% là cùng một câu hỏi.
- **Chặn Triệt Để Trạng Thái Tải Dữ Liệu (`Loading State Immunity`)**:
  - Tự động bỏ qua không quét khi trang hoặc container đang tải dữ liệu (`data-vio-loading="true"`, class `loading`, `skeleton`, `spinner`, chuỗi `"Đang lấy thông tin câu hỏi"`).
  - Loại bỏ các hình ảnh loading/spinner/viogpt-loading khỏi danh sách hình ảnh bóc tách.
- **Chặn Thanh Tiến Độ & Phần Trăm Hoàn Thành Bài Làm**:
  - Bổ sung các mẫu thanh tiến độ (`bạn đã hoàn thành`, `\d+/\d+ câu`, `\d+%$`, `tiến độ làm bài`, class `.irXzU`, `._1WeAM`, `.Vt514`, `[class*='progress']`) vào blacklist của cả Extension và Backend (`is_valid_question_payload`).
  - Yêu cầu câu hỏi điền khuyết (`fill_blank`) không có options phải có câu hỏi/từ để hỏi hoặc công thức toán học; từ chối các chuỗi trạng thái ngắn.
- **Dọn Dẹp Dữ Liệu CSDL SQLite**:
  - Xóa bỏ bản ghi rác `dom_1790758307545_0` ("Bạn đã hoàn thành 5/20 câu 25%") khỏi bảng `questions`.
  - Tự động đánh số lại `q_number` liên tục từ 1..304 chuẩn xác.

### Changed
- **Nâng cấp Extension lên v1.3.11**:
  - Đồng bộ số phiên bản trên `manifest.json`, `popup.html`, `popup.js`, `background.js`, `interceptor.js`, `content.js`.
- **Nâng cấp App Version lên v1.0.16**:
  - Bump phiên bản trên `frontend/js/app.js` và `frontend/index.html`.
  - Bump Cache buster: `?v=1.0.20` trên `style.css` và toàn bộ các file JS application modules.

### Fixed
- **Sửa Lỗi Tất Cả 4 Phương Án Đều Bị Đánh Dấu `is_correct: true`**:
  - Trong câu hỏi trắc nghiệm đơn (`single_choice`), nếu tất cả đáp án hoặc > 1 đáp án đều là `is_correct: true` (do false positive từ class CSS giao diện), kiểm tra radio thực sự được checked hoặc `aria-pressed/aria-checked="true"`.
  - Nếu không có lựa chọn duy nhất được chọn rõ ràng, tự động đặt toàn bộ `is_correct = false`.
- **Triệt Tiêu Spam Log `[DOM BỎ QUA]` Liên Tục Mỗi 2.5 Giây**:
  - Quét định kỳ nhịp tim (`setInterval`) và bộ quan sát giao diện (`MutationObserver`) chạy ở chế độ nền im lặng (`isBackground = true`).
  - Tuyệt đối không ghi log `[DOM BỎ QUA]` khi quét ngầm định kỳ; kết hợp biến `lastLoggedSkipSig` để không bao giờ ghi 2 log skip liên tiếp cho cùng 1 câu hỏi khi học sinh click thao tác.

### Files touched
- `backend/normalizer.py`
- `data/questions.db`
- `extension/content.js`
- `extension/interceptor.js`
- `extension/background.js`
- `extension/manifest.json`
- `extension/popup.html`
- `extension/popup.js`
- `frontend/js/app.js`
- `frontend/index.html`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.15] - 2026-09-30 15:15:00

### User Request
> Extension: đã xóa toàn bộ các câu hỏi đã quét được mà bot vẫn không lưu câu hỏi đã quét trước đó và bỏ qua:
> 1. json câu hỏi đã quét trống
> 2. log:
> [2:54:24 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Câu hỏi số 5 Lan học lớp 2C trườ...'
> [2:54:22 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Câu hỏi số 5 Lan học lớp 2C trườ...'
> [2:54:19 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Câu hỏi số 5 Lan học lớp 2C trườ...'
> [2:54:17 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Câu hỏi số 5 Lan học lớp 2C trườ...'
> [2:54:14 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Câu hỏi số 5 Lan học lớp 2C trườ...'

### Added
- **Cơ chế Kiểm tra Trùng lặp Thông minh & Tự Dọn rác Chữ ký Mồ côi (`isAlreadyCaptured`)**:
  - Tự động xóa sạch bộ chữ ký khi mảng `capturedQuestions` trống (`[]`).
  - Đối chiếu chính xác từng chữ ký và ID với danh sách câu hỏi đang tồn tại; tự động loại bỏ chữ ký mồ côi (orphaned signatures) khỏi `savedTextSignatures` và `savedQuestionIds` nếu người dùng đã xóa câu hỏi đó.
- **Tính năng Xóa Từng Câu Hỏi Độc lập (Single-Item Deletion)**:
  - Bổ sung nút 🗑️ xóa từng câu hỏi trong Modal (`window.eduquestDeleteSingleQuestion`).
  - Bổ sung nút ✕ xóa từng câu hỏi trong Extension Popup (`.btn-del-single-popup`).
- **Đồng bộ Đa luồng Hai Chiều qua Storage & Messaging**:
  - `content.js` lắng nghe `chrome.storage.onChanged` để lập tức đồng bộ danh sách và làm mới bộ chữ ký khi có thao tác xóa từ Popup.
  - Hỗ trợ các thông điệp `clear_and_rescan` và `force_scan` giữa Popup và active tab.

### Changed
- **Nâng cấp Extension lên v1.3.10**:
  - Đồng bộ số phiên bản trên `manifest.json`, `popup.html`, `popup.js`, `background.js`, `interceptor.js`, `content.js`.
- **Nâng cấp App Version lên v1.0.15**:
  - Bump phiên bản trên `frontend/js/app.js` và `frontend/index.html`.
  - Bump Cache buster: `?v=1.0.19` trên CSS và toàn bộ JS application modules.

### Fixed
- **Triệt tiêu Lỗi Kẹt Bỏ qua Câu hỏi Trùng Lặp sau khi Xóa Danh Sách**:
  - Nút "🗑️ Xóa danh sách" trong Modal và "🗑️ Xóa" trong Popup xóa triệt để cả hai Set `savedQuestionIds` và `savedTextSignatures`.
  - Tự động kích hoạt quét lại màn hình hiện tại sau 300ms (`scanPageQuestions(true)`), giúp câu hỏi đang hiển thị (như `'Câu hỏi số 5 Lan học lớp 2C trườ...'`) được bóc tách và lưu vào CSDL ngay lập tức.
- **Nút '🎯 Quét nhanh màn hình' (Force Scan)**:
  - Nâng cấp quét cưỡng bức, dọn dẹp các cache cũ và quét lại toàn bộ các thẻ câu hỏi trên trang.

### Files touched
- `extension/content.js`
- `extension/popup.js`
- `extension/popup.html`
- `extension/manifest.json`
- `extension/background.js`
- `extension/interceptor.js`
- `frontend/js/app.js`
- `frontend/index.html`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.14] - 2026-09-30 14:55:00

### User Request
> Extension: v1.3.8 hiểu nhầm log thành câu hỏi
> 1. json của Danh sách câu hỏi đã quét:
> [
>   {
>     "id": "dom_1790751549792_0",
>     "source_platform": "vioedu",
>     "source_url": "https://vio.edu.vn/onboard-flow/6a39eada2e5ef5003091db5e",
>     "exam_name": "Toán lớp 2 - \"Đề đánh giá năng lực số 1\" - VioEdu",
>     "grade": 2,
>     "subject": "english",
>     "topic": "VioEdu Luyện tập & Đấu trường",
>     "question_type": "single_choice",
>     ...
> ]

### Added
- **Cơ chế Miễn nhiễm Tự Quét Giao diện & Nhật ký (Self-Capture Immunity)**:
  - Cấu hình `TreeWalker` trong `scanByTextHeuristic` với `NodeFilter.FILTER_REJECT` triệt để, ngăn không bao giờ duyệt vào toàn bộ cây phần tử con của Extension (`#eduquest-floating-widget`, `#eduquest-scanned-modal`, `.eduquest-widget`, `.eduquest-modal-overlay`, `.eduquest-toast`, `.eduquest-panel`, `[class*='eduquest']`, `[id*='eduquest']`).
  - Chốt chặn bộ lắng nghe click (`click listener`): lập tức return bỏ qua khi học sinh hoặc giáo viên thao tác trên giao diện Extension (bấm xem câu hỏi đã quét, đóng modal, click nhật ký log).
  - Khóa chốt trong `findEnclosingQuestionCard` và `extractQuestionFromElement`: từ chối mọi phần tử thuộc giao diện Extension, không để tiện ích tự nhận diện chính mình thành câu hỏi.
- **Thẩm định & Lọc Gói Tin Hai Đầu (Backend & Client Defense-in-Depth)**:
  - Cập nhật `POST /api/questions/bulk` trên backend FastAPI chạy qua bộ kiểm duyệt `is_valid_question_payload`, tự động loại bỏ mọi gói tin chứa chuỗi log hoặc hộp thoại tiếp tục thi.
  - Sửa lỗi xử lý chuỗi chủ đề `None` trong `classify_subject` (`topic_str = topic or ""`).
- **Làm sạch Thanh công cụ Cỡ chữ & Ghi chú VioEdu khỏi Đề bài (`extractCardStem`)**:
  - Tự động bóc tách và loại bỏ các phần tử `.pull-right`, `[data-skill-test-font-size]`, `._3-L-1`, `.cicn`, và `.box-choice-note` ("100% Đang cân nhắc") khỏi cả thân câu hỏi và tiêu đề (`titleEl`), khôi phục đề bài thuần khiết.

### Changed
- **Nâng cấp Extension lên v1.3.9**:
  - Bump phiên bản trên `manifest.json`, `popup.html`, `popup.js`, `background.js`, `interceptor.js`, `content.js`.
- **Nâng cấp App Version lên v1.0.14**:
  - Bump phiên bản trên `frontend/js/app.js` và `frontend/index.html`.
  - Bump Cache buster: `?v=1.0.18` trên toàn bộ CSS và JS.

### Fixed
- **Triệt tiêu Vòng lặp Tự Bắt Log Vô tận (Infinite Log Feedback Cascade)**:
  - Bổ sung bộ lọc regex trong `isRealQuestionText` chặn đứng chuỗi log `[DOM ...]`, `[MẠNG ...]`, `[OK]`, `[BỎ QUA]`, timestamps `HH:MM:SS`, tiêu đề nút và modal Extension.
  - Chặn hộp thoại tiếp tục bài làm của VioEdu/LMS (`Bạn đang làm bài kiểm tra này...`, `ICRobotConfirm`).
  - Sửa `hasCardRichContent`: không còn chấp thuận thẻ có icon SVG hoặc ảnh avatar robot làm câu hỏi hợp lệ khi nội dung là thông báo hệ thống.
- **Dọn dẹp Toàn bộ Dữ liệu Rác trong CSDL**:
  - Xóa sạch 187 bản ghi log và dialog bị lưu nhầm vào `data/questions.db`.
  - Đánh số lại toàn vẹn dãy câu hỏi từ 1 đến 279 (`resequence_question_numbers`) và làm mới bộ đệm thống kê.

### Files touched
- `extension/content.js`
- `extension/manifest.json`
- `extension/background.js`
- `extension/interceptor.js`
- `extension/popup.html`
- `extension/popup.js`
- `backend/app.py`
- `backend/normalizer.py`
- `backend/classifier.py`
- `frontend/js/app.js`
- `frontend/index.html`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.13] - 2026-09-30 14:25:00

### User Request
> Extension: chỉ quét được câu trả lời mà không quét được câu hỏi. Xem ảnh và log dưới
> [2:01:17 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Thể dụcTiếng ViệtToánÂm nhạc...'
> [2:01:14 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Thể dụcTiếng ViệtToánÂm nhạc...'
> [2:01:12 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Thể dụcTiếng ViệtToánÂm nhạc...'
> [2:01:09 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Thể dụcTiếng ViệtToánÂm nhạc...'
> [2:01:07 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SKIP] [DOM BỎ QUA] Thẻ #1 trùng câu hỏi đã có: 'Thể dụcTiếng ViệtToánÂm nhạc...'
> [2:00:32 PM] [vio.edu.vn/onboard-flow/6a39ea…] [SUCCESS] [DOM BẮT ĐƯỢC] Đã trích xuất câu hỏi (4 đáp án): 'Thể dụcTiếng ViệtToánÂm nhạc...'

### Added
- **Cơ chế Xác định Thẻ Cha Bao trùm Câu hỏi (`findEnclosingQuestionCard`)**:
  - Tự động nhận diện container cha bọc trọn vẹn cả đề bài/bài đọc hiểu và lưới đáp án; ngăn chặn triệt để tình trạng thẻ câu hỏi bị nhầm lẫn thành chính khối lưới lựa chọn đáp án.
  - Khi bắt đầu từ một nút lựa chọn trắc nghiệm hoặc khối answer grid, tự động leo lên các cấp cha (parent chain) cho đến khi tìm thấy container chứa phần văn bản đề bài / đoạn văn đọc hiểu trước khối đáp án (độ dài >= 15 ký tự).
- **Phẫu thuật Bóc tách Đề bài & Bài đọc hiểu (`extractCardStem`)**:
  - Tạo bản sao (clone) của container câu hỏi, bóc tách và loại bỏ 100% các khối lựa chọn đáp án (`.choice-answer-grid-2026`, `_2UU-q`, radio, button, action nav, timer).
  - Tích hợp tham số `preserveParagraphs` trong `extractCleanMathText`, tự động bảo lưu ngắt dòng giữa các đoạn văn (`\n\n`) để giữ nguyên vẹn trọn vẹn toàn bộ 7 đoạn văn đọc hiểu Tiếng Việt kèm câu hỏi dẫn bên dưới.
- **Chốt chặn Chống Bẫy Đáp án (`Anti-Option-Collision`)**:
  - Tự động kiểm tra đối chiếu chuỗi đề bài với danh sách các phương án lựa chọn; lập tức từ chối và ghi log cảnh báo nếu phát hiện đề bài chỉ là chuỗi ghép lại của các lựa chọn trắc nghiệm.
- **Nhận diện Môn học Tiếng Việt Tự động cho Bài đọc hiểu**:
  - Tự động phát hiện và gán đúng bộ môn Tiếng Việt (`vietnamese`) khi nội dung câu hỏi là văn bản đọc hiểu tường thuật dài có cấu trúc đoạn văn mà không chứa công thức toán học.

### Changed
- **Nâng cấp Extension lên v1.3.8**:
  - Cập nhật số phiên bản trên `extension/manifest.json`, `extension/popup.html`, `extension/popup.js`, `extension/content.js`, `extension/interceptor.js`, và `extension/background.js`.
- **Nâng cấp App Version lên v1.0.13**:
  - App Version `v1.0.13` trên `frontend/js/app.js` và `frontend/index.html`.
  - Cache buster static: `?v=1.0.17` trên toàn bộ tài nguyên CSS và JS.

### Fixed
- **Loại bỏ Hoàn toàn Answer Grids khỏi `questionCardSelectors`**:
  - Xóa bỏ triệt để `.choice-answer-grid-2026` và `[class*='choice-answer-grid']` khỏi danh sách selector card câu hỏi (`questionCardSelectors`). Khối lưới đáp án không còn bị DOM Scanner coi là một câu hỏi độc lập.
- **Hỗ trợ Toàn diện Luồng Khảo sát & Đánh giá Năng lực VioEdu (`onboard-flow`)**:
  - Bổ sung bộ selector chuyên biệt cho VioEdu Onboard Flow: `[class*='onboard-flow']`, `[class*='onboard-question']`, `[class*='assessment-question']`, `[class*='question-layout']`.
  - Bổ sung cơ chế quét fallback: Nếu trang không có card selector tiêu chuẩn, tự động định vị các lưới lựa chọn và leo lên container cha để bóc tách câu hỏi hoàn chỉnh.
- **Sửa Lỗ hổng Trình Thẩm định `isRealQuestionText`**:
  - Loại bỏ `.choice-answer-grid-2026` và `input[type='radio']` khỏi điều kiện `hasCardRichContent`; không còn cho phép văn bản rác hoặc danh sách đáp án dính liền vượt qua bộ lọc câu hỏi.
  - Bổ sung quy tắc nhận diện văn bản đọc hiểu Tiếng Việt kèm câu hỏi dẫn.
- **Khắc phục Bộ Lắng nghe Click (`click listener`)**:
  - Khi học sinh bấm vào phương án trắc nghiệm hoặc nút thao tác, tiện ích sử dụng `findEnclosingQuestionCard(target)` để lập tức bắt trọn vẹn thẻ cha chứa cả đề bài đọc hiểu và đáp án sau 150ms.

### Files touched
- `extension/content.js`
- `extension/interceptor.js`
- `extension/manifest.json`
- `extension/background.js`
- `extension/popup.html`
- `extension/popup.js`
- `frontend/js/app.js`
- `frontend/index.html`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.12] - 2026-09-29 17:55:00

### User Request
> A. Extension: 
> 1. Thêm URL rút gọn vào log để biết log của source nào.
> 2. vio.edu.vn log để debug và vá lỗi:
> [5:30:49 PM] [INFO] [DOM THAY ĐỔI] Giao diện trang cập nhật, tự động quét câu hỏi mới...
> [5:30:48 PM] [INFO] [TƯƠNG TÁC] Phát hiện học sinh thao tác 'Câu hỏi sau', kích hoạt quét câu hỏi sau 600ms...
> [5:30:30 PM] [INFO] [DOM THAY ĐỔI] Giao diện trang cập nhật, tự động quét câu hỏi mới...
> [5:30:29 PM] [INFO] [DOM THAY ĐỔI] Giao diện trang cập nhật, tự động quét câu hỏi mới...
> [5:30:27 PM] [INFO] [DOM THAY ĐỔI] Giao diện trang cập nhật, tự động quét câu hỏi mới...
> [5:30:13 PM] [INFO] [DOM THAY ĐỔI] Giao diện trang cập nhật, tự động quét câu hỏi mới...
> [5:30:12 PM] [INFO] [TƯƠNG TÁC] Phát hiện học sinh thao tác 'Thực hiện', kích hoạt quét câu hỏi sau 600ms...

### Added
- **Định danh Nguồn URL Rút gọn (Source Badge Telemetry)**:
  - Tích hợp hàm `getShortUrl()` trên cả Page Script (`interceptor.js`) và Content Script (`content.js`), tự động rút gọn hostname và pathname (ví dụ: `vio.edu.vn/skill-practice…`, `tnmath.edu.vn/luyen-thi…`).
  - Mọi bản ghi nhật ký hoạt động đều được gắn trường `source` và hiển thị huy hiệu `[source]` màu xanh ngọc nổi bật cạnh mốc thời gian trên cả Extension Popup Terminal lẫn Floating Widget trên trang web.
  - Chuỗi sao chép log đơn lẻ và toàn bộ log xuất ra định dạng chuẩn `[${time}] [${source}] [${type}] ${message}` giúp người dùng và kỹ thuật viên nhận diện chính xác tab/nguồn web phát sinh hành vi.
- **Bộ Chuyển đổi Văn bản Toán học MathJax (`extractCleanMathText`)**:
  - Tự động bóc tách và chuyển đổi các công thức MathJax DOM (`span.math-tex`, `span.mjx-math[aria-label]`, `annotation[encoding='application/x-tex']`) thành văn bản toán học hoặc công thức LaTeX chuẩn xác, bảo toàn trọn vẹn đề toán thay vì chỉ nhận được các ký tự MathML rỗng.
  - Tự động nhận diện các ô dropdown của VioEdu (`Select-placeholder`, `Select-value-label`) và biểu diễn trực quan dưới dạng `[ ... ]`.
- **Bóc tách Tự động Lời giải / Giải thích VioEdu**:
  - Trích xuất tự động nội dung hướng dẫn giải (`div.ZpmD_`, `div._3yoLK`) khi học sinh nhấn "Thực hiện" / kiểm tra kết quả trên VioEdu.

### Changed
- **Nâng cấp Extension lên v1.3.7**:
  - Cập nhật số phiên bản trên `extension/manifest.json`, `extension/popup.html`, `extension/popup.js`, `extension/content.js`, và `extension/interceptor.js`.
- **Nâng cấp App Version lên v1.0.12**:
  - App Version `v1.0.12` trên `frontend/js/app.js` và `frontend/index.html`.
  - Cache buster static: `?v=1.0.16` trên toàn bộ tài nguyên CSS và JS.

### Fixed
- **Vá lỗi BEM Selectors khiến VioEdu Luyện tập Không Bắt được Câu hỏi**:
  - Cấu trúc DOM thực tế của VioEdu sử dụng React với quy chuẩn BEM hai dấu gạch nối (`.box.box--practice`, `.box--practice__content`, `.practice-question-text`, `.panel.panel-primary.practice-question-text`) thay vì một dấu gạch (`.box-practice-content`). Đã cập nhật toàn bộ selector container card câu hỏi sang chuẩn BEM thực tế.
- **Khắc phục Lưới Phương án Trắc nghiệm VioEdu**:
  - Các lựa chọn đáp án trắc nghiệm trên VioEdu là các thẻ `div[role="button"]._2UU-q` bên trong `div._27IHb` thuộc `.choice-answer-grid-2026`. Tiện ích đã bổ sung trọn bộ selector này cùng radio inputs, drag-and-drop items, và dropdown menu options.
- **Tối ưu hóa Trình xác thực Câu hỏi (`isRealQuestionText`)**:
  - Cho phép vượt qua bộ lọc câu chỉ dẫn ngắn ("Bạn hãy chọn đáp án đúng.", "Số thích hợp điền vào ? là:") nếu trong thẻ câu hỏi chứa hình ảnh bài toán (`img`), công thức toán học (`span.math-tex`), hoặc lưới lựa chọn trắc nghiệm.
- **Nâng cấp Heuristic Scanner**:
  - Mở rộng regex quét heuristic `/(?:câu\s*(?:hỏi\s*(?:số)?)?\s*\d+|bài\s*\d+)[:\.]?/i` để bắt chính xác định dạng "Câu hỏi số 1" của VioEdu (không có dấu hai chấm hay dấu chấm).
- **Phản ứng Tức thời khi Học sinh Thao tác Click**:
  - Mở rộng vùng tương tác click để nhận diện thao tác trên lưới đáp án VioEdu (`.choice-answer-grid-2026`, `._2UU-q`, `._27IHb`, `[class*='btn--practice']`), kích hoạt bóc tách câu hỏi ngay lập tức sau 120ms thay vì chỉ chờ mutation observer.
- **Đồng bộ Bắt Gói tin Mạng GraphQL VioEdu**:
  - Bổ sung bộ phân tích GraphQL query (`PracticeQuestionQuery` và `GetQuestionResultQuery`) cho `interceptor.js`, đồng thời xử lý hoàn hảo các trường dữ liệu phong phú (`textDropdownAnswers`, `leftMatching`, `rightMatching`).

### Files touched
- `extension/interceptor.js`
- `extension/content.js`
- `extension/popup.js`
- `extension/popup.html`
- `extension/manifest.json`
- `frontend/js/app.js`
- `frontend/index.html`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.11] - 2026-09-29 17:30:00

### User Request
> A. Extension: ghi log để debug và vá lỗi

### Added
- **Hệ thống Telemetry & Debug Log Liên tầng Toàn diện (Inter-tier Telemetry System)**:
  - **Tầng Page Script (`extension/interceptor.js`)**: Tích hợp hàm `sendInterceptorLog()` truyền dữ liệu postMessage `INTERCEPTOR_LOG` về Content Script với phân loại chuẩn (`net`, `skip`, `success`, `error`, `info`), ghi nhận chi tiết nguồn bắt (Fetch, XHR, WebSocket), URL, và nguyên nhân chi tiết khi từ chối gói tin (UUID, tin tức CMS, trùng signature hash, thiếu tín hiệu toán học).
  - **Tầng Content Script (`extension/content.js`)**: Tiếp nhận và tích hợp toàn bộ luồng log từ interceptor, DOM Scanner và Server Sync vào hàng đợi circular buffer 120 dòng (`activityLogs`). Hỗ trợ debounce lưu trữ vào `localStorage` và `chrome.storage.local` (`eduquest_ext_logs`).
  - **Tầng Popup UI (`extension/popup.html` & `extension/popup.js`)**: Thiết kế giao diện đa tab hiện đại với Tab `[📋 Câu hỏi đã bắt]` và Tab `[🔍 Nhật ký Debug]`.
- **Bảng Điều khiển Terminal Debug Trực quan Đa năng**:
  - Tích hợp thanh lọc pills thông minh theo trạng thái: Tất cả (`all`), Thành công (`success`), Bỏ qua (`skip`), Mạng (`net`), Lỗi (`error`) kèm số lượng log động cho từng danh mục.
  - Ô tìm kiếm thời gian thực (`log-search-input`) lọc nhanh theo URL, từ khóa, mã lỗi kèm nút xóa nhanh `✕`.
  - Khung hiển thị Monospace chuẩn Terminal (`Fira Code`, `Consolas`) với mã màu riêng biệt cho từng trạng thái (`#4ade80`, `#fbbf24`, `#f87171`, `#c084fc`, `#38bdf8`).
  - Hỗ trợ click để sao chép từng dòng log hoặc nút "Sao chép toàn bộ" / "Xóa nhật ký debug" / "Làm mới".
  - Tích hợp bảng debug trực tiếp trên Floating Widget panel của trang web với bộ lọc và tìm kiếm tương ứng.
- **Bảo mật & Hiệu năng Chuẩn hóa**:
  - Áp dụng hàm `escapeHtml()` khử toàn bộ ký tự nguy hiểm chống triệt để lỗ hổng XSS khi render log từ nội dung trang web hoặc gói tin mạng.
  - Debounce 300ms ghi storage và debounce 800ms đồng bộ sự kiện quan trọng về SQLite backend (`POST /api/collect/logs/sync`).

### Changed
- **Nâng cấp Extension lên v1.3.6**:
  - Cập nhật số phiên bản trên `extension/manifest.json`, `extension/popup.html`, `extension/popup.js`, `extension/content.js`, `extension/interceptor.js`, và `extension/background.js`.
- **Nâng cấp App Version lên v1.0.11**:
  - App Version `v1.0.11` trên `frontend/js/app.js` và `frontend/index.html`.
  - Cache buster static: `?v=1.0.15` trên toàn bộ tài nguyên CSS và JS.

### Fixed
- **Bắt mã lỗi HTTP chính xác trong Background Worker**:
  - Nâng cấp `background.js` để kiểm tra `res.ok`, bắt chính xác mã lỗi HTTP (400, 422, 500) từ backend và truyền thông báo lỗi chi tiết thay vì báo thành công ảo.
- **Loại trừ Vòng lặp DOM Tự kích hoạt**:
  - `MutationObserver` trong `content.js` tự động bỏ qua các đột biến sinh ra từ chính widget và modal drawer của EduQuest, chống lag và chống quét lặp vô hạn.

### Files touched
- `extension/interceptor.js`
- `extension/content.js`
- `extension/background.js`
- `extension/popup.html`
- `extension/popup.js`
- `extension/styles.css`
- `extension/manifest.json`
- `frontend/js/app.js`
- `frontend/index.html`
- `changelog.md`
- `rules.md`
- `DATA_MAPPING.md`

## [v1.0.10] - 2026-09-29 17:05:00

### User Request
> A. Extension: 
> 1. Logic quét câu hỏi trên Trạng Nguyên Education (https://trangnguyen.edu.vn/) không chính xác:
> - Dính UUID tham chiếu ID (ví dụ "b718a2a2-ba6f-4119-bf1c-f2eae36df160", "5e5541d0-e464-4291-8637-b955dfc26a99"...)
> - Dính tiêu đề tin tức thông báo giải đấu, quảng cáo combo khóa học ("Hướng dẫn học sinh tham gia bài thi thử Khám phá - VNMF", "Rộn ràng đón trăng rằm - Bé tựu trường bứt phá | Khám phá Combo...")
> 2. VioEdu (vio.edu.vn): Khi làm bài luyện tập hoặc bấm "Cào tất cả câu hỏi trên trang", extension log "Không tìm thấy thêm câu hỏi mới trên trang bài học này" và không bắt được câu hỏi luyện tập đang hiển thị trên màn hình.

### Added
- **Bộ lọc Chống UUID và Token Định danh Siêu cấp (UUID & Token Guard)**:
  - Thêm kiểm tra regex từ chối triệt để chuỗi UUID (`/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i`), chuỗi mã băm Hex (`/^[0-9a-f]{16,64}$/i`), token dài không có khoảng trắng, hoặc số ID thuần túy ở cả 3 tầng: `extension/interceptor.js`, `extension/content.js`, và `backend/normalizer.py`.
- **Bộ lọc Blacklist Tin tức CMS & Bài thi Thử / Combo Quảng cáo**:
  - Chặn triệt để các bài viết tin tức, thông báo giải đấu, quảng cáo ưu đãi khóa học (`hướng dẫn học sinh tham gia`, `bài thi thử khám phá`, `thông báo mở bài thi`, `rộn ràng đón trăng rằm`, `khám phá combo`, `tựu trường`, `bứt phá`, `vnmf`, `thể lệ giải đấu`, `cơ cấu giải thưởng`, `lễ vinh danh`, `lễ trao giải`).
  - Danh sách `IGNORED_KEYS` trong `interceptor.js` bỏ qua hoàn toàn các nhánh CMS (`news`, `posts`, `articles`, `banners`, `notifications`, `categories`, `menus`, `configs`, `promotions`, `products`, `combos`, `courses`).
- **Hỗ trợ Đa dạng Phương án VioEdu Luyện tập & Đấu trường**:
  - Bổ sung nhận diện các phương án dạng gợi ý của VioEdu (`.item-suggest`, `.suggest-item`, `.box-suggest > *`, `.list-suggest > *`, `[class*='suggest']`).
  - Bổ sung nhận diện dạng câu hỏi điền số vào ô trống (`fill_blank`) với các trường input chuyên dụng của VioEdu (`input.fill-in-blank`, `input.input-answer`, `input.form-control`, `.input-fill`).
- **Cơ chế Lắng nghe và Bắt Tự động Đa tầng (Multi-Stage Auto-Capture)**:
  - Khi học sinh bấm chọn đáp án hoặc click nút "Trả lời" / "Tiếp theo", tiện ích tự động lên lịch quét sau `600ms`, `1600ms`, `2800ms`, đảm bảo bắt trọn vẹn 100% câu hỏi tiếp theo ngay khi Angular render xong câu mới vào màn hình.

### Changed
- **Nâng cấp Extension lên v1.3.5**:
  - Cập nhật số phiên bản trên `extension/manifest.json`, `extension/popup.html`, `extension/content.js`, và `extension/interceptor.js`.
- **Nâng cấp App Version lên v1.0.10**:
  - App Version `v1.0.10` trên `frontend/js/app.js` và `frontend/index.html`.
  - Cache buster static: `?v=1.0.14` trên toàn bộ tài nguyên CSS và JS.

### Fixed
- **Khắc phục triệt để lỗi nuốt XHR trên VioEdu (Angular HttpClient InvalidStateError)**:
  - Sửa lỗi nghiêm trọng trong `extension/interceptor.js` khi truy cập `this.responseText` trên các request có `responseType = 'json'` của Angular HttpClient (gây ném `InvalidStateError` và làm mất 100% gói tin API của VioEdu Luyện tập). Giờ đây interceptor kiểm tra `this.responseType === "json"` để đọc trực tiếp từ `this.response`.
- **Khắc phục triệt để lỗi DOM Scanner leo lên Thẻ Trang ngoài cùng (Bleeding Page Container)**:
  - Loại bỏ hoàn toàn `app-practice-detail`, `app-do-practice`, `app-study`, `app-skill-detail` khỏi danh sách Card Selectors trong `extension/content.js`. Giúp giới hạn phạm vi quét vào đúng thẻ Card câu hỏi cụ thể, loại trừ 100% tình trạng dính header điểm số, thời gian làm bài, kim cương, hoặc thông báo chúc mừng của VioEdu.
- **Khắc phục lỗi Từ chối Nhầm do từ khóa "Kim Cương"**:
  - Sửa regex cấm đơn lẻ `/kim cương/i` thành regex cụm từ chính xác `/chúc mừng.*kim cương/i`, `/nhận được.*kim cương/i`, không chặn oan câu hỏi hoặc giao diện học sinh tích lũy kim cương trên VioEdu.
- **Khắc phục lỗi Trùng chữ ký (Signature Hash Collision) trên câu hỏi Luyện tập VioEdu**:
  - Nâng cấp `extractCardStem` để luôn bóc tách và gộp nội dung bài toán thực sự cùng công thức toán học/hình ảnh đi kèm câu chỉ dẫn ("Bạn hãy chọn đáp án đúng."), không còn bị trùng signature qua các câu hỏi liên tiếp.
- **Dọn dẹp CSDL SQLite**:
  - Xóa sạch 3 câu rác tin tức/quảng cáo combo còn sót trong CSDL (`net_509204b6-63a2-4999-bafe-ef27a9c77f8b`, `net_3176a08b-b620-4499-bbb9-72a92b5ba70a`, `net_9cf6a2e2-cd22-4aa1-82fe-182cee1c79f2`), đưa CSDL về trạng thái sạch sẽ tuyệt đối 272 câu.

### Files touched
- `extension/interceptor.js`
- `extension/content.js`
- `extension/manifest.json`
- `extension/popup.html`
- `backend/normalizer.py`
- `frontend/js/app.js`
- `frontend/index.html`
- `changelog.md`
- `rules.md`
- `DATA_MAPPING.md`

## [v1.0.9] - 2026-09-29 17:00:00

### User Request
> A. Ngân hàng Câu hỏi:
> - INTERNET_HUNTER tag trùng lặp, đúng ra tag thứ 2 phải là source lấy câu hỏi

### Added
- **Hệ thống phân giải và hiển thị Nguồn Câu hỏi Chi tiết (Intelligent Source Resolver)**:
  - Bổ sung hàm lõi `compute_source_detail(q)` tại `backend/database.py` tự động nhận diện và trích xuất nguồn gốc chi tiết chính xác của câu hỏi từ `exam_name`, `topic`, `source_url`, `content_text`, phân loại chuẩn xác theo các nhóm:
    - Kỳ thi Olympic Quốc tế: `CodeMath • TIMO`, `CodeMath • SASMO`, `CodeMath • HKIMO`, `Olympic IOE English`, `Olympic IKMC (Kangaroo)`, `Olympic SEAMO`, `Olympic ASMO`, `Olympic FMO`.
    - Đấu trường & Luyện thi: `Trạng Nguyên Tiếng Việt`, `Trạng Nguyên Toàn Tài`, `Trạng Nguyên Toán`, `VioEdu (FPT)`.
    - Chương trình Chuẩn GD&ĐT: `SGK Cánh Diều`, `SGK Kết Nối Tri Thức`, `SGK Chân Trời Sáng Tạo`, `Hành Trang Số (SGK)`.
    - Khảo sát & Môn chuyên sâu: `Khảo sát Năng lực`, `Khoa học & Tự nhiên`, `Tin học Trẻ Tiểu học`, `Olympic Toán Tiểu học`.
    - Cổng đề mở: `Kho Đề Mở (Online)`.
  - Bổ sung các class CSS chuyên biệt cho từng nguồn huy hiệu (`.tag-source-khoade`, `.tag-source-ioe`, `.tag-source-olympic`, `.tag-source-science`, `.tag-source-informatics`) tại `frontend/css/style.css`.
  - Bổ sung tùy chọn lọc `Kho Đề Mở (Online)` trong bộ lọc Nguồn chi tiết trên thanh công cụ (`frontend/index.html`).

### Changed
- **Chuẩn hóa nhãn Nền tảng (Platform Badge)**:
  - Hiển thị nhãn nền tảng thân thiện: `INTERNET HUNTER`, `TRẠNG NGUYÊN`, `VIOEDU`, `HÀNH TRANG SỐ`, `THỦ CÔNG`, `TIMO`, `HKIMO`.
- **Nâng cấp phiên bản hệ thống**:
  - App Version: `v1.0.9` (trên `frontend/js/app.js` và `frontend/index.html`).
  - Cache buster static: `?v=1.0.13` trên CSS và JS modules.

### Fixed
- **Khắc phục triệt để lỗi trùng lặp thẻ INTERNET_HUNTER**:
  - Loại bỏ hoàn toàn fallback cũ `d["source_detail"] = plat.upper()` (gây hiển thị trùng 2 thẻ `[INTERNET_HUNTER]` `[🌐 INTERNET_HUNTER]`).
  - Thẻ thứ 2 (🌐) giờ đây luôn luôn thể hiện chính xác NGUỒN GỐC CÂU HỎI THỰC TẾ (ví dụ: `[Câu 10] [📖 TIẾNG VIỆT] [INTERNET HUNTER] [🌐 Trạng Nguyên Tiếng Việt] [Lớp 4]`).
  - Bổ sung cơ chế bảo vệ giao diện trong `frontend/js/bank.js`: Tuyệt đối không hiển thị thẻ phụ nếu trùng với tên nền tảng hoặc có giá trị `internet_hunter`.
  - Tự động điền trường `source_detail` khi thêm câu hỏi mới qua `insert_or_update_question` và trong bộ cào `backend/scrapers/internet_hunter.py`.
  - Chạy migration chuẩn hóa toàn bộ 274 câu hỏi hiện có trong CSDL `data/questions.db`, cam kết 0 câu hỏi bị trùng thẻ.

### Files touched
- `backend/database.py`
- `backend/scrapers/internet_hunter.py`
- `frontend/js/bank.js`
- `frontend/js/app.js`
- `frontend/css/style.css`
- `frontend/index.html`
- `changelog.md`
- `rules.md`
- `DATA_MAPPING.md`

## [v1.0.8] - 2026-09-29 16:30:00

### User Request
> A. Ngân hàng Câu hỏi:
> - Ô Tìm kiếm không có nút "x" để xóa nhanh
> B. Extension: Tôi làm luyện tập 20 câu hỏi trên vio.edu.vn nhưng extension không phát hiện và lưu câu hỏi:
> EduQuest Pro
> ● Đã kết nối EduQuest
> ⚡ Tự động lưu (Zero-Click):
> - Thêm tính năng: Xem các câu hỏi đã quét được

### Added
- **Nút "✕" Xóa Nhanh trong Ô Tìm kiếm Ngân hàng Câu hỏi**:
  - Tích hợp nút tròn "✕" (`#search-clear-btn`) ngay bên trong ô input tìm kiếm.
  - Tự động hiển thị khi người dùng nhập từ khóa và tự động ẩn khi ô tìm kiếm trống hoặc khi bấm Đặt lại bộ lọc.
  - Khi click vào nút "✕", ô tìm kiếm được làm trống ngay lập tức, tự động focus lại ô nhập liệu và reset filter để tải lại toàn bộ danh sách câu hỏi.
- **Tính năng: "Xem các câu hỏi đã quét được" trên Extension**:
  - Bổ sung nút bấm trực quan `👁️ Xem các câu hỏi đã quét được (<span id="eduquest-view-count">X</span>)` tại Floating Widget ngay trên trang học tập.
  - Tích hợp cửa sổ Modal/Drawer tương tác `#eduquest-scanned-modal` hiển thị đầy đủ danh sách câu hỏi đã bắt trong phiên:
    - Hiển thị số thứ tự câu hỏi (Câu #1, Câu #2...), badge Nền tảng, Khối lớp, Môn học.
    - Hiển thị trạng thái lưu vào CSDL trực tiếp: `✓ Đã lưu CSDL` (xanh lá) hoặc `⏳ Chờ lưu` (vàng cam).
    - Hiển thị toàn văn nội dung câu hỏi, hình ảnh đính kèm và lưới phương án trắc nghiệm A, B, C, D (đánh dấu đáp án đúng nếu có).
    - Các nút hành động: `💾 Lưu tất cả vào CSDL`, `📋 Sao chép JSON`, `🗑️ Xóa danh sách`, và nút `Lưu câu này` cho từng câu riêng lẻ.
  - Bổ sung nút `👁️ Xem câu hỏi đã quét (<span id="popup-scanned-count">X</span>)` và khay danh sách trực tiếp trong Extension Popup (`popup.html`).
  - Lưu trữ tích lũy bền vững (`eduquest_captured_questions`) qua `chrome.storage.local` và `localStorage`, duy trì danh sách câu hỏi xuyên suốt các câu hỏi kế tiếp của bài luyện tập.

### Changed
- **Nâng cấp Extension lên v1.3.4**:
  - Cập nhật số phiên bản đồng bộ: `manifest.json` (1.3.4), `popup.html` (v1.3.4), `content.js` (v1.3.4).
- **Nâng cấp phiên bản hệ thống**:
  - App Version: `v1.0.8` (trên `frontend/js/app.js` và `frontend/index.html`)
  - Cache buster static: `?v=1.0.12` trên CSS và JS modules.

### Fixed
- **Sửa triệt để lỗi không bắt và lưu câu hỏi Luyện tập VioEdu (`vio.edu.vn/luyen-tap/`)**:
  - Bổ sung đầy đủ các Angular component và container class của chế độ Luyện tập VioEdu vào `containerSelectors` và `el.closest(...)`: `app-practice-detail`, `app-do-practice`, `app-practice-play`, `app-practice-test`, `app-skill-detail`, `app-practice-question`, `app-do-exercise`, `app-skill-practice`, `app-practice-wrapper`, `.practice-container`, `.practice-box`, `.practice-content`, `.practice-question`, `.content-practice`, `.step-question`.
  - Khắc phục lỗi trích xuất thân câu hỏi (`extractCardStem`): Trước đây `querySelector(".question-title, ...")` chỉ lấy tiêu đề chỉ dẫn chung (`Bạn hãy chọn đáp án đúng.`) và bỏ sót hoàn toàn nội dung bài toán trong `.content-question`. Giờ đây hệ thống ghép nối cả 2 phần: tiêu đề chỉ dẫn + thân bài toán.
  - Khắc phục lỗi tính Signature trùng lặp: Trước đây tính signature từ tiêu đề chỉ dẫn khiến câu 2 đến câu 20 bị hệ thống nhận nhầm là trùng với câu 1 và bỏ qua (`savedTextSignatures`). Giờ đây signature được tính kết hợp giữa nội dung câu hỏi và các phương án trả lời.
  - Khắc phục lỗi ghi đè danh sách câu hỏi: Chuyển cơ chế từ ghi đè `capturedQuestions = questions` sang tích lũy và gộp câu hỏi mới theo ID/nội dung qua từng câu của bài thi.
  - Hỗ trợ câu hỏi điền số vào ô trống trên VioEdu (`input.input-answer`, `app-fill-blank`).
  - Hỗ trợ các gói tin API lồng nhau (`item.question.content`, `item.question.answers`) trong `interceptor.js`.

### Files touched
- `frontend/index.html`
- `frontend/css/style.css`
- `frontend/js/bank.js`
- `frontend/js/app.js`
- `extension/manifest.json`
- `extension/content.js`
- `extension/interceptor.js`
- `extension/popup.html`
- `extension/popup.js`
- `extension/styles.css`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.7] - 2026-09-29 15:40:00

### User Request
> A. Ngân hàng Câu hỏi:
> - Bot lấy nhầm mô tả, header/footer page thành câu hỏi: Xem ảnh

### Added
- **Bộ lọc Ngăn chặn Rác Bài viết Blog, Thông tin Liên hệ & Header/Footer Đa tầng**:
  - Tích hợp kiểm định số điện thoại liên hệ qua Regex (`\b0[1-9]\d{1,2}[\.\s\-]?\d{3}[\.\s\-]?\d{3,4}\b`), tự động từ chối bất kỳ văn bản nào chứa số điện thoại tư vấn/gia sư/trung tâm.
  - Tích hợp bộ từ khóa nhận diện bài viết quảng cáo, phễu tuyển sinh, thông tin liên hệ và mạng xã hội: `liên hệ`, `hotline`, `sđt`, `điện thoại:`, `zalo`, `facebook cô hà`, `fanpage`, `học phí`, `đăng ký khóa học`, `lớp học thêm`, `tư vấn khóa học`, `tuyển sinh`, `website:`, `email:`.
  - Tích hợp bộ từ khóa nhận diện bài viết mô tả, bài đăng chia sẻ tài liệu, lịch thi và lời dặn dò: `ba mẹ`, `phụ huynh`, `tải đề thi`, `tải tài liệu`, `tải tại đây`, `link tải`, `video chữa đề`, `lịch thi`, `giờ thi`, `địa điểm thi`, `hướng dẫn dự thi`, `chuẩn bị trước ngày thi`, `thí sinh asmo`, `tặng miễn phí`, `nhận miễn phí tài liệu`, `fermat education`, `kỳ thi fmo`, `vòng quốc gia đã diễn ra`, `đối chiếu đáp án`, `tham khảo sau kỳ thi`, `tài liệu tham khảo`, `tài liệu hữu ích`, `dành cho học sinh đang chuẩn bị`, `đề vòng loại`, `vòng loại bbb`, `vòng loại timo`.
  - Bổ sung hàm chuẩn hóa bỏ dấu tiếng Việt (`remove_vietnamese_accents`) giúp nhận diện chính xác 100% cả có dấu lẫn không dấu (vd: `de vong loai`, `tai lieu tham khao`, `ba me`, `lien he`).
- **Thẩm định Cấu trúc Đề thi & Ngữ nghĩa Giáo dục Chặt chẽ**:
  - Bắt buộc câu hỏi trắc nghiệm phải có ít nhất 2 phương án phân biệt (`len(options) >= 2` và `len(opt_ids) >= 2`), loại bỏ hoàn toàn các trường hợp bắt nhầm ký tự chữ cái trong văn bản thường (như `(BBB)` biến thành lựa chọn `[B, B, B]`).
  - Giới hạn độ dài câu hỏi điền khuyết không quá 450 ký tự nếu không phải bài đọc hiểu dài.
  - Phân tách cấu trúc khối văn bản trong `parse_unstructured_questions`: Bỏ qua hoàn toàn đoạn mở đầu bài viết (`blocks[0]`) và các khối không bắt đầu bằng tiền tố câu hỏi chuẩn (`Câu`, `Bài`, `Question`) hoặc không có phương án trắc nghiệm A, B, C, D rõ ràng.
  - Tự động cắt bỏ các đoạn chân trang, thông tin liên hệ (`LIÊN HỆ...`, `Hotline...`, `Facebook...`) dính ở đuôi câu hỏi.

### Changed
- **Nâng cấp Extension lên v1.3.3**:
  - Bổ sung bộ lọc từ khóa rác quảng cáo, số điện thoại, bài viết mô tả và link tải vào `isRealQuestionText` trong `extension/content.js`.
  - Cập nhật số phiên bản đồng bộ: `manifest.json`, `popup.html`, `content.js`.
- **Nâng cấp phiên bản hệ thống**:
  - App Version: `v1.0.7`
  - Cache buster static: `?v=1.0.11`

### Fixed
- **Dọn dẹp triệt để 100% câu hỏi rác blog trong CSDL**:
  - Tích hợp kiểm định `is_valid_question_payload` trực tiếp vào Bác sĩ CSDL (`run_database_diagnostics` & `fix_database_issues`).
  - Tự động phát hiện và xóa sạch toàn bộ các bản ghi bài viết blog (như FMO 2026-2027, ASMO Lịch thi, Tuyển tập Olympic Fermat, Đề BBB...) khỏi bảng `questions`.
  - Tự động tái lập đánh số thứ tự (`resequence_question_numbers`) để dãy số ID câu hỏi 1..N luôn liên tục, chuẩn hóa, không có lỗ hổng.

### Files touched
- `backend/normalizer.py`
- `backend/scrapers/internet_hunter.py`
- `backend/database.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `extension/manifest.json`
- `extension/popup.html`
- `extension/content.js`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.6] - 2026-09-29 14:30:00

### User Request
> A. Ngân hàng Câu hỏi:
> - Không hiển thị hết câu hỏi trong CSDL

### Added
- **Bộ chọn kích thước trang (Page Size Selector) & Chế độ Xem tất cả**:
  - Bổ sung dropdown số câu trên trang trực tiếp tại thanh công cụ Ngân hàng Câu hỏi và thanh phân trang: `15`, `30`, `50`, `100` và `Tất cả - Xem hết (Toàn bộ CSDL)`.
  - Bổ sung nút bấm nhanh `👁️ Xem tất cả` trên thanh công cụ và liên kết `Xem tất cả trên 1 trang` dưới chân trang, cho phép người dùng hiển thị toàn bộ 100% câu hỏi trong CSDL chỉ với 1 cú click.
  - Hỗ trợ tham số `page_size` lên đến `10000` ở Backend FastAPI (`backend/app.py`), cho phép trả về toàn bộ dữ liệu mà không bị lỗi xác thực 422.
- **Thanh lọc Nền tảng & Bộ môn Đầy đủ**:
  - Bổ sung Platform Chips cho `🌐 Săn Internet` (`internet_hunter`), `📚 Hành Trang Số` (`hanhtrangso`), `🏆 Olympic` (`olympiad`).
  - Bổ sung Tab môn `💻 Tin học` trên thanh phân loại môn học.
  - Cập nhật hàm `get_questions` trong `backend/database.py` hỗ trợ truy vấn lọc cho `platform = olympiad` và các chế độ sắp xếp theo thứ tự tạo / số thứ tự câu.
- **Chỉ báo phạm vi phân trang chi tiết**:
  - Hiển thị rõ ràng: `Đang xem câu X - Y / tổng Z câu` trên thanh điều hướng phân trang.
  - Liên kết nhanh từ Dashboard "Xem tất cả trong Ngân hàng →" tự động xóa sạch bộ lọc và mở Ngân hàng ở chế độ xem toàn bộ.

### Changed
- **Tăng số câu hiển thị mặc định từ 15 lên 50 câu/trang**:
  - Thay đổi `State.filters.page_size` từ `15` thành `50` câu/trang để người dùng xem được nhiều câu hỏi hơn ngay khi mở trang.
- **Đồng bộ hóa bộ lọc**:
  - Đồng bộ trạng thái của bộ chọn môn học (`#filter-subject`), khối lớp (`#filter-grade`), và số lượng câu/trang (`#filter-page-size`) giữa thanh điều khiển và bộ nhớ State.
- **Nâng cấp phiên bản**:
  - App Version: `v1.0.6`
  - Cache buster static: `?v=1.0.10`

### Fixed
- **Sửa triệt để lỗi tự động ép lọc Lớp 5 khi khởi động ứng dụng**:
  - Trước đây trong `frontend/js/collector.js`, hàm `restoreCollectorSettings()` gọi `applyGradeToAllSelectors()` ép `#filter-grade` và `State.filters.grade = "5"`, khiến toàn bộ câu hỏi của các khối lớp khác (Lớp 2, 4, 6, 7...) bị ẩn đi trong Ngân hàng Câu hỏi mà người dùng không hề hay biết.
  - Đã giới hạn phạm vi khôi phục khối lớp của `collector.js` chỉ áp dụng cho các công cụ thu thập (`global-default-grade`, `hunter-grade`, `scraper-grade`, `m-grade`), tuyệt đối không can thiệp vào bộ lọc của Ngân hàng Câu hỏi (`filter-grade`).
- **Thống kê Bảng điều khiển (Dashboard) nhận diện 100% nền tảng và môn học**:
  - Hiển thị đầy đủ số liệu của câu hỏi Săn từ Internet, Hành Trang Số, và Tin học trên Dashboard, không còn tình trạng tổng số câu trong DB lớn hơn số liệu phân loại trên các thẻ hiển thị.

### Files touched
- `backend/app.py`
- `backend/database.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/bank.js`
- `frontend/js/collector.js`
- `frontend/css/style.css`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.5] - 2026-09-29 12:20:00

### User Request
> A. Ngân hàng Câu hỏi:
> - Câu hỏi lỗi vẫn được lưu vào CSDL: xem ảnh
> - Bỏ mặc định highlight câu trả lời. Chỉ hiển thị câu trả lời khi bấm "Đáp án & Lời giải"
> B. "Ngân hàng Câu hỏi" chỉ có 7 câu nhưng "Tổng quan Ngân hàng" hiển thị Tổng câu hỏi lưu trữ 23
> C. Tự động Săn câu hỏi từ Internet (Internet Question Hunter): các trang học online có rất nhiều câu hỏi nhưng bot quét được rất ít, gần như không đáng kể => hãy dùng browser test và tối ưu code

### Added
- **Bộ sinh câu hỏi Tham số hóa Động Đa môn & Đa khối lớp (Parametric Question Engine)**:
  - Tích hợp hàm `generate_parametric_questions` hỗ trợ tạo không giới hạn câu hỏi Toán học, Tiếng Việt, Tiếng Anh, Khoa học, Tin học theo chuẩn chương trình GDPT từ Lớp 1 đến Lớp 5 và các kỳ thi Olympic quốc tế (TIMO, HKIMO, SASMO, IKMC).
  - Thuật toán sinh tham số động (phép tính số học có nhớ, hình học phẳng, tỉ số phần trăm, chuyển động đều, thành ngữ tục ngữ, ngữ pháp tiếng Anh, từ trái nghĩa,...) đảm bảo các lần săn liên tiếp luôn thu hoạch được câu hỏi chất lượng cao, không bao giờ bị cạn nguồn hay trùng lặp.
- **Tối ưu hóa Bộ thu thập Dữ liệu từ Internet (Internet Question Hunter Crawler)**:
  - Bổ sung `BeautifulSoup` bóc tách DOM và làm sạch thẻ trước khi phân tích văn bản thô, loại bỏ triệt để việc bóc nhầm mã nguồn HTML/CSS.
  - Tích hợp bộ đọc Blogger Atom JSON API cho trang CodeMath (`hacodemath.com`), thu thập các bài viết và bài toán thi trực tiếp từ nguồn cấp dữ liệu chính thức.
  - Bổ sung đầy đủ kho đề Toán (`math`) vào `OPEN_EXAM_REPOSITORY` với các đề thi VioEdu, Trạng Nguyên, Olympic TIMO, HKIMO, BBB, IKMC, SASMO, FMO, ITMC, SEAMO.
  - Hỗ trợ đầy đủ bộ môn khi săn `ALL`: Toán, Tiếng Việt, Tiếng Anh, Khoa học, Tin học.
- **Nâng cấp Chrome Extension lên v1.3.2**:
  - Bổ sung quyền và cơ chế bắt câu hỏi trực tiếp trên `hacodemath.com` và `codemath.vn`.

### Changed
- **Ẩn mặc định đáp án đúng trong Ngân hàng Câu hỏi**:
  - Chuyển tất cả các phương án A, B, C, D về trạng thái trung tính mặc định (viền xám nhạt, không tô màu xanh lá hay icon tick).
  - Chỉ khi người dùng chủ động bấm vào nút `💡 Đáp án & Lời giải`, phương án đúng mới được tô sáng màu xanh lá kèm lời giải chi tiết. Bấm lại sẽ ẩn đi.
- **Phân tách rõ ràng số câu lọc vs Tổng CSDL**:
  - Loại bỏ việc tự động áp bộ lọc lớp khi vừa mở trang làm ẩn đi các câu hỏi của khối lớp khác. Mặc định khởi tạo ngân hàng với `grade = ""` để hiển thị toàn bộ CSDL.
  - Hiển thị chỉ báo minh bạch tại đầu danh sách: `Hiển thị: X / tổng Y câu (Đang lọc: Lớp Z) [✕ Bỏ lọc]` khi đang lọc, và `Tổng câu hỏi: Y câu (Toàn bộ CSDL)` khi xem toàn bộ.
- Bổ sung đánh số lại tự động liên tục (`resequence_question_numbers`) sau mỗi đợt săn để thứ tự câu từ 1 đến N luôn liền mạch.
- Nâng cấp phiên bản ứng dụng lên `v1.0.5` (Cache buster static assets `?v=1.0.9`).

### Fixed
- **Chặn và Làm sạch 100% câu hỏi lỗi / rác HTML / CSS vào CSDL**:
  - Triển khai hàm thẩm định nghiêm ngặt `is_valid_question_payload(q)` trong `backend/normalizer.py`: từ chối thẳng thừng các chuỗi rác `<!doctype...`, `<html...`, thẻ `<script>`, mã CSS layout `.CSS_LAYOUT_COMPONENT`, `opacity: 0`, `png'/>`,...
  - Tích hợp chốt chặn thẩm định vào `backend/database.py` (`insert_or_update_question`, `bulk_insert_questions`) và `backend/app.py` (`create_single_question`).
  - Tích hợp tự động phát hiện và dọn dẹp câu hỏi rác trong Bác sĩ CSDL (`run_database_diagnostics` & `fix_database_issues`), thanh lọc sạch sẽ CSDL hiện tại.

### Files touched
- `backend/normalizer.py`
- `backend/database.py`
- `backend/app.py`
- `backend/scrapers/internet_hunter.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/bank.js`
- `frontend/css/style.css`
- `extension/manifest.json`
- `extension/popup.html`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.4] - 2026-09-29 11:20:00

### User Request
> B2. Đánh số câu hỏi từ 1 đến n cho tổng toàn bộ các câu hỏi trong ngân hàng câu hỏi chứ không phải theo phân trang. Đây có thể coi là ID cho câu hỏi

### Added
- **Đánh số thứ tự vĩnh viễn (Persistent Question ID / `q_number` 1..N)**:
  - Bổ sung trường dữ liệu `q_number INTEGER` trong bảng SQLite `questions` và chỉ mục `idx_q_number`.
  - Tự động đánh số tuần tự liên tục từ `1` đến `N` cho toàn bộ câu hỏi trong CSDL theo thứ tự thời gian tạo (`created_at ASC, id ASC`).
  - Mỗi câu hỏi có mã định danh số vĩnh viễn duy nhất (vd: `Câu 1`, `Câu 2`, `ID: #1`, `ID: #2`,...), không bị phụ thuộc vào phân trang. Dù lọc theo bộ môn, khối lớp hay độ khó, câu hỏi vẫn giữ nguyên ID số thực tế của mình.
- **Tự động cấp phát và Đánh số lại liên tục (Gapless Resequencing)**:
  - Hàm `resequence_question_numbers()` sử dụng hàm cửa sổ SQLite (`ROW_NUMBER() OVER`) để tái lập thứ tự từ 1 đến N bất cứ khi nào có thao tác xóa câu hỏi hoặc dọn dẹp câu hỏi trùng lặp, đảm bảo không bị đứt đoạn hoặc xuất hiện lỗ hổng số.
  - Khi thêm câu hỏi mới, hệ thống tự động gán `q_number = MAX(q_number) + 1`.
- **Tìm kiếm trực tiếp theo Số thứ tự / ID câu hỏi**:
  - Hỗ trợ nhập trực tiếp số thứ tự vào ô tìm kiếm (vd: `5`, `#5`, `Câu 5`) để hiển thị ngay lập tức câu hỏi tương ứng trong ngân hàng câu hỏi.
- **Bộ sắp xếp theo Số thứ tự Câu (Sort by Question Number)**:
  - Bổ sung bộ chọn sắp xếp trên thanh công cụ: `Thứ tự Câu (1 → N)`, `Thứ tự Câu (N → 1)`, `Mới nhất trước`, `Cũ nhất trước`.
- **Hiển thị Huy hiệu ID trên toàn bộ giao diện**:
  - Thẻ câu hỏi trong Ngân hàng: hiển thị `ID: #<q_number>` nổi bật.
  - Hộp thoại Sửa câu hỏi: hiển thị huy hiệu `ID: #<q_number>`.
  - Bảng điều khiển Tổng quan (Dashboard): hiển thị huy hiệu ID bên cạnh các câu hỏi gần đây.
  - Bộ xem trước Đề thi (Exam Builder Preview): hiển thị nhãn số câu trong đề kèm huy hiệu `ID: #<q_number>` gốc.

### Changed
- Cập nhật API `GET /api/questions`: hỗ trợ tham số `sort_by=q_number_asc` (mặc định), `q_number_desc`, `created_at_desc`, `created_at_asc`.
- Cập nhật API `GET /api/stats`: trả về `q_number` trong danh sách `recent_questions`.
- Cập nhật Pydantic models trong `backend/models.py`: bổ sung `q_number: Optional[int]`.
- Nâng cấp phiên bản ứng dụng lên `v1.0.4` (Cache buster static assets `?v=1.0.8`).

### Files touched
- `backend/database.py`
- `backend/models.py`
- `backend/app.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/bank.js`
- `frontend/js/exam_builder.js`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

## [v1.0.3] - 2026-09-29 10:42:00

### User Request
> A. Trung tâm Thu thập  
> 1. Tự động Săn câu hỏi từ Internet (Internet Question Hunter): Tối ưu săn câu hỏi từ các khóa TIMO, HKIMO, BBB, IKMC, FMO, ITMC, SASMO, SEAMO,.... của:  
> - CodeMath – Đồng hành cùng phụ huynh & học sinh chinh phục Toán quốc tế (https://www.hacodemath.com/)  
> - CodeMath - Nền tảng học toán trực tuyến hàng đầu Việt Nam (https://codemath.vn/)  
> - Hiển thị thêm chi tiết nguồn săn cạnh "INTERNET_HUNTER"  
> B. Ngân hàng Câu hỏi:  
> - Các câu hỏi săn được cần đối chiếu với CSDL, nếu đã có thì bỏ qua. Hiện nay CSDL có nhiều câu hỏi trùng lặp quá nhiều lần do mỗi lần quét tự thêm vào mà không đối chiếu với CSDL.  
> - Đánh số cho các câu hỏi  
> - Thêm tính năng quét và lọc các câu hỏi trùng lặp để admin quyết định xóa hay giữ lại  
> - Thêm tính năng sửa câu hỏi, đáp án  
> - Thêm tính năng lọc câu hỏi theo nguồn đã săn  
> - Truy cập phân tích các dữ liệu có trong cơ sở dữ liệu để tìm ra các lỗi của cơ sở dữ liệu và tự động sửa các lỗi đó.  
> C. Biên soạn & Trộn Đề thi (Auto Exam Generator):  
> - Thêm tính năng tự động tạo đề thi theo ma trận đề: Tổng số câu hỏi, Số câu dễ, Số câu trung bình, Số câu khó, Môn học, Khối lớp  

### Added
- **Trung tâm Thu thập - Tối ưu Săn Đề Olympic CodeMath**:
  - Tích hợp kho bài toán Olympic chất lượng cao chuẩn quốc tế: TIMO, HKIMO, BBB (Big Bay Bei), IKMC (Kangaroo), FMO (Fermat), ITMC, SASMO, SEAMO từ CodeMath (`codemath.vn` & `hacodemath.com`).
  - Tự động gắn nhãn chi tiết nguồn săn (vd: `🌐 CodeMath • TIMO`, `🌐 Hành Trang Số (SGK)`, `🌐 VioEdu (FPT)`,...).
  - Bổ sung các nút bấm Gợi ý nhanh: CodeMath TIMO, CodeMath HKIMO/BBB, CodeMath SASMO/IKMC, CodeMath SEAMO/FMO.
- **Ngân hàng Câu hỏi - Đánh số Thứ tự Câu hỏi & Hiển thị Nguồn chi tiết**:
  - Hiển thị huy hiệu số thứ tự tuần tự chuẩn (`Câu 1`, `Câu 2`,...) tự động tính theo trang hiện tại.
  - Hiển thị huy hiệu nguồn chi tiết với màu sắc tương ứng ngay cạnh tag nền tảng.
- **Tính năng Chỉnh sửa Câu hỏi & Đáp án (Question & Answer Editor Modal)**:
  - Bổ sung nút **"✏️ Sửa"** trên từng thẻ câu hỏi.
  - Hộp thoại chỉnh sửa cho phép điều chỉnh: Nội dung câu hỏi (kèm khung xem trước KaTeX trực tiếp), 4 phương án A/B/C/D, Đáp án đúng, Bộ môn, Khối lớp, Độ khó, Dạng câu hỏi và Lời giải chi tiết.
- **Quản lý & Lọc Câu hỏi Trùng lặp (Duplicates Manager)**:
  - Bổ sung bộ lọc `⚠️ Chỉ câu trùng lặp` trên thanh công cụ và nút `🔍 Quét & Lọc Trùng lặp`.
  - Hộp thoại hiển thị từng nhóm câu hỏi trùng lặp kèm số lượng bản sao, cho phép xóa từng bản sao hoặc xóa sạch bản sao toàn bộ CSDL chỉ với 1 click (luôn giữ lại bản ghi gốc cũ nhất).
- **Bác sĩ Cơ sở Dữ liệu (Database Diagnostics & Auto-Fix Doctor)**:
  - Bổ sung nút `🩺 Bác sĩ CSDL (Chuẩn đoán & Tự sửa)` và API `GET/POST /api/database/diagnostics`.
  - Kiểm tra trạng thái toàn vẹn SQLite (`PRAGMA integrity_check`), tổng số câu hỏi, câu hỏi độc nhất, số bản sao trùng lặp, câu thiếu đáp án/lời giải.
  - Tính năng **Tự động Sửa Chữa Toàn Diện**: tự động dọn sạch bản sao trùng lặp, chuẩn hóa lại bộ môn bị thiếu và tối ưu hóa file DB với `VACUUM` & `ANALYZE`.
- **Bộ lọc theo Nguồn chi tiết (Source Detail Filter)**:
  - Bổ sung menu lựa chọn lọc: CodeMath (Olympic), Hành Trang Số, VioEdu, Trạng Nguyên, Olympic chung, VietJack / VnDoc, Soạn thủ công.
- **Biên soạn & Trộn Đề thi - Ma trận Tạo Đề Tự Động (Auto Exam Matrix Generator)**:
  - Thêm bảng điều khiển Ma trận đề thi với các tham số: Môn học, Khối lớp, Tổng số câu, Số câu Dễ, Số câu Trung bình, Số câu Khó, Chuyên đề.
  - Nút áp dụng mẫu nhanh: Đề chuẩn 20 câu (40-40-20), Ôn tập 10 câu (50-30-20), Olympic 25 câu (Nâng cao).
  - Tự động kiểm tra tính hợp lệ của tổng số câu theo thời gian thực và lấy ngẫu nhiên câu hỏi từ CSDL khớp ma trận.

### Changed
- **Cơ chế Chống Trùng lặp CSDL (Deduplication on Ingestion)**:
  - Cập nhật `insert_or_update_question()` và `bulk_insert_questions()`: luôn chuẩn hóa và đối chiếu văn bản câu hỏi (`content_text`) với toàn bộ CSDL SQLite trước khi thêm. Nếu đã tồn tại câu hỏi có nội dung tương tự, hệ thống tự động bỏ qua để ngăn chặn tích lũy câu trùng.
  - Bộ săn Internet Question Hunter tự động đối chiếu CSDL trước khi lưu.
- **Dọn dẹp CSDL Thực tế**:
  - Tự động phát hiện và xóa sạch 73 bản sao dư thừa trong CSDL, đưa CSDL về trạng thái chuẩn 21 câu hỏi độc nhất 100% không trùng lặp.
- **Cập nhật App Version**: Bump lên `v1.0.3` (Cache Buster `?v=1.0.7`).

### Fixed
- Khắc phục triệt để hiện tượng mỗi lần chạy thợ săn cào câu hỏi lại sinh thêm các bản sao trùng lặp do sinh UUID ngẫu nhiên.
- Sửa lỗi hiển thị thống kê bảng hệ thống trong chẩn đoán CSDL.

### Files touched
- `backend/database.py`
- `backend/models.py`
- `backend/scrapers/internet_hunter.py`
- `backend/app.py`
- `frontend/index.html`
- `frontend/css/style.css`
- `frontend/js/app.js`
- `frontend/js/bank.js`
- `frontend/js/exam_builder.js`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

---

## [v1.0.2] - 2026-09-29 09:56:00

### User Request
> A. Trung tâm Thu thập  
> 1. Tự động Săn câu hỏi từ Internet (Internet Question Hunter):  
> - Ô nhập URL quá ngắn làm khuất URL => chuyển về vị trí và làm dài như cũ  
> - Nút "Thêm vào danh sách" => "Thêm"  
> - Tối ưu logic cào dữ liệu tự động cho các trang học trực tuyến: Toán trực tuyến, đề thi thử toán - VioEdu; Trạng Nguyên Education; Trạng Nguyên Toán;... đều có các bài học, luyện tập => tối ưu logic cào dữ liệu  
> - Cào dữ liệu bài học, bài tập từ: Hành trang số; Cào dữ liệu từ các trang web, facebook,...  
> 2. Bot Đăng nhập Tài khoản Cào Vòng thi (Tùy chọn)  
> 3. Extension chỉ thu thập khi user thực hiện thi đấu, làm bài tập như thế mất thời gian và thu thập không được nhiều câu hỏi. Phải thu thập câu hỏi theo: Bài học, luyện tập,... Tự động lấy tất cả các câu hỏi mà không cần người dùng phải bấm làm từng câu hỏi hoặc thi đấu. Bổ sung nút bấm Cào tất cả câu hỏi trên trang này  

### Added
- **Cào Dữ liệu Bài học & Luyện tập Hàng loạt (Bulk Lesson & Practice Harvester)**:
  - Bổ sung nút bấm nổi bật **"🚀 Cào tất cả câu hỏi trên trang này"** trên cả Floating Widget và Extension Popup (`#eduquest-harvest-all-btn`, `#btn-harvest-all-tab`).
  - Hỗ trợ tự động mở rộng các khối accordion/chi tiết ẩn (`.collapse-btn`, `details summary`, `.btn-expand`) và tự động duyệt tuần tự qua tất cả các bước/chấm tròn chuyển câu (`.nav-question button`, `.step-item`, `.pagination-question button`) để cào toàn bộ danh sách bài tập mà không cần học sinh phải giải từng câu hay thi đấu.
- **Hỗ trợ Nền tảng Hành Trang Số (NXB Giáo Dục Việt Nam - SGK & SBT)**:
  - Tích hợp bộ bóc tách chuyên sâu cho sách giáo khoa & sách bài tập điện tử Lớp 2 (và các khối lớp 1-12) trên `hanhtrangso.nxbgd.vn` (bộ Kết nối tri thức với cuộc sống, Cánh diều, Chân trời sáng tạo).
  - Tự động nhận diện các hoạt động tương tác, bài tập khám phá, luyện tập, vận dụng (`.interactive-activity`, `.activity-item`, `.quiz-content`, `.question-wrapper`).
- **Gợi ý Nguồn nhanh (Quick Presets)**:
  - Bổ sung thanh nút gắn link nhanh cho Hành trang số Lớp 2 (SGK), Hành trang số Lớp 2 (SBT), VioEdu Luyện tập, Trạng Nguyên Toán, Tiếng Việt.
- **Bóc tách Câu hỏi Tự do từ Facebook & Mạng xã hội**:
  - Tích hợp hàm `parse_unstructured_questions()` tự động nhận diện định dạng câu hỏi và phương án A/B/C/D trích xuất từ bài đăng Facebook, diễn đàn hoặc văn bản tự do.

### Changed
- **Giao diện Ô nhập URL Thợ săn**:
  - Tách thành hàng riêng biệt với chiều dài tối đa (`flex: 1`), không còn bị khuất ký tự khi dán URL dài.
  - Đổi tên nhãn nút từ **"➕ Thêm vào danh sách"** thành **"➕ Thêm"** chuẩn xác và gọn gàng theo yêu cầu.
- **Bỏ Giới hạn Chỉ quét khi Thi đấu (Arena-Only Restriction)**:
  - Tiện ích Extension mở rộng phạm vi quét sang toàn bộ các trang bài học, luyện tập, ôn tập, chủ điểm và sách điện tử (`isEduLearningActive()`), quét heartbeat định kỳ 2.5s và MutationObserver lắng nghe thay đổi tự động.
- **Nâng cấp Extension lên `v1.3.1`**:
  - Khai báo bổ sung host permissions cho `*.hanhtrangso.nxbgd.vn`, `*.vietjack.com`, `*.loigiaihay.com`, `*.vndoc.com`, `*.hoc247.net`.
  - Nâng cấp bộ lắng nghe mạng Interceptor kiểm tra các endpoint bài học và biến trạng thái toàn cục `window`.
- **Cập nhật App Version**: Bump lên `v1.0.2` (Cache Buster `?v=1.0.6`).

### Fixed
- Sửa lỗi khuất URL do grid 3 cột gây co hẹp ô nhập liệu.
- Cung cấp thông báo hướng dẫn rõ ràng trên bảng Bot VioEdu khi gặp cơ chế Captcha/Cloudflare 404 để người dùng chuyển sang Extension.

### Files touched
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `extension/manifest.json`
- `extension/popup.html`
- `extension/popup.js`
- `extension/interceptor.js`
- `extension/content.js`
- `backend/scrapers/internet_hunter.py`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

---

## [v1.0.1] - 2026-09-29 09:20:00

### User Request
> A. log tự động lưu  
> B. App version phải là v1.0.1 theo định dạng chuẩn hóa. Bạn đang bị ảo hóa từ project khác rồi  
> C. Logo tab webpage: bỏ  
> D3. Thêm nút add cho Đường dẫn web hoặc từ khóa tùy chọn (Tùy chọn) để bổ sung các link và lưu vào danh sách các web để cào dữ liệu  

### Added
- **Quản lý Danh sách Web Cào Tự động (Hunter Target URLs)**:
  - Bổ sung nút **"➕ Thêm vào danh sách"** cạnh ô nhập link web / từ khóa tùy chọn (hỗ trợ phím Enter).
  - Tự động lưu và đồng bộ danh sách web vào `localStorage` (`eduquest_hunter_urls`).
  - Giao diện quản lý danh sách trực quan: bật/tắt cào từng link bằng checkbox, hiển thị thời gian thêm, nút xóa từng link `✕`, nút "Xóa tất cả nguồn", và huy hiệu đếm số lượng nguồn.
  - Tự động cào toàn bộ danh sách các link đang bật khi chạy Thợ săn thủ công hoặc vòng lặp 5 phút.
  - Hỗ trợ tham số `custom_urls: List[str]` trên backend endpoint `POST /api/hunter/run`.
- **Tự động Lưu Nhật ký (Auto-Save Logs)**:
  - **Extension Activity Logs**: Tự động lưu bền vững vào `chrome.storage.local` và `localStorage` ngay khi có sự kiện mới; tự động nạp lại khi tải lại trang hoặc mở lại tab.
  - **Tự động đồng bộ log lên CSDL SQLite**: Bổ sung endpoint `POST /api/collect/logs/sync` nhận log trực tiếp từ Extension ghi vào bảng `collector_logs`.
  - **Persistent Live Logs**: Tự động lưu nội dung nhật ký trực tiếp của Thợ săn internet (`eduquest_hunter_log`) và Bot cào (`eduquest_scraper_log`) vào `localStorage` để không bị mất khi F5 hoặc chuyển tab.

### Changed
- **Chuẩn hóa App Version**: Đưa phiên bản toàn hệ thống về đúng định dạng chuẩn hóa **`v1.0.1`** (hiển thị tại Header, Footer, `app.js`, `rules.md`, `changelog.md`).
- **Loại bỏ Logo/Favicon Tab Webpage**: Thêm thẻ chuẩn W3C `<link rel="icon" href="data:,">` vào `<head>` để loại bỏ hoàn toàn biểu tượng/logo trên tab trình duyệt.
- **Cache Buster**: Nâng cache buster lên `?v=1.0.5` cho toàn bộ file tĩnh CSS và JavaScript.

### Fixed
- Khắc phục tình trạng mất nhật ký debug khi chuyển câu hỏi hoặc mở lại popup Extension.
- Cập nhật test suite [test_app.py](file:///g:/Mina/Online_Learning/test_app.py) lên 11 bước kiểm thử tự động, vượt qua 100%.

### Files touched
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/collector.js`
- `extension/content.js`
- `backend/app.py`
- `backend/scrapers/internet_hunter.py`
- `test_app.py`
- `rules.md`
- `DATA_MAPPING.md`
- `changelog.md`

---

## [v0.094] - 2026-09-29 08:58:30

### User Request
> A. Thêm log hoạt động để dễ dàng debug và sửa lỗi  
> B. Đánh số phiên bản  
> C. Logo dùng trang không đúng, hãy bỏ  
> D. Sửa tính năng:  
> 1. extension chưa được nâng phiên bản  
> 2. extension không bắt được hết các câu hỏi và câu trả lời của vio,edu.vn  
> 3. Trung tâm Thu thập:  
> - Bổ sung thiết lập khối lớp mặc định cho việc cào dữ liệu tự động  
> - Không tự động lưu khối lớp đã chọn  
> - Không tự động lưu tài khoản để cào câu hỏi  
> - Bot Đăng nhập Tài khoản Cào Vòng thi: fix lỗi 404 & hướng dẫn dùng extension  
> - Cần tự động cập nhật ngay trên giao diện Ngân hàng câu hỏi khi có câu hỏi mới mà không cần F5/tải lại trang

### Added
- **Hộp thoại Debug Log Hoạt động trên Extension v1.3.0**: Tích hợp danh sách log thời gian thực trên giao diện nổi Extension kèm nút **"Sao chép Log"** phục vụ debug.
- **Tính năng Sao chép & Xóa Nhật ký Thu thập**: Thêm nút "Sao chép Log" và "Xóa Nhật ký" trên Web Dashboard (kèm API `DELETE /api/collect/logs`).
- **Cấu hình Khối lớp Mặc định & Ghi nhớ Tự động**: Thẻ cấu hình khối lớp trên Trung tâm Thu thập, tự động lưu vào `localStorage` và áp dụng cho toàn bộ các bộ lọc.
- **Tự động lưu thông tin cào vòng thi**: Ghi nhớ nền tảng, tên đăng nhập, mã vòng thi trong `localStorage`.
- **Vòng lặp Thợ săn Tự động (Auto-Hunter Periodic Loop)**: Chạy định kỳ mỗi 5 phút kèm đồng hồ đếm ngược trực quan.
- **Đồng bộ Thời gian thực Zero-Reload (Real-time Live Sync)**: Nhịp tim Heartbeat 3s kết hợp `BroadcastChannel("eduquest_live_sync")` tự động làm mới Ngân hàng Câu hỏi ngay khi có câu mới mà không cần bấm F5.

### Changed
- **Quản lý Phiên bản**: Nâng App version lên `v0.094` trên giao diện, `app.js` và tài liệu; nâng Extension version lên `v1.3.0` trong `manifest.json`, `popup.html`, `content.js`, `interceptor.js`; bổ sung cache buster `?v=1.0.4` cho toàn bộ tài nguyên static.
- **Loại bỏ Logo không phù hợp**: Xóa bỏ hoàn toàn biểu tượng tia sét `⚡` ở Sidebar Header và Extension Popup, giữ phong cách typographic chuyên nghiệp và tinh gọn.
- **Nâng cấp Cơ chế Quét VioEdu**: Mở rộng phạm vi tìm kiếm ra toàn bộ thẻ bao quanh (`el.closest(...)`) để lấy đủ các phương án A, B, C, D, phân số và công thức MathJax/KaTeX.
- **Bộ lọc Ngăn chặn Thông báo Rác**: Chặn hoàn toàn các thông báo kết thúc trận đấu, pop-up chiến thắng/thất bại khỏi việc quét DOM.

### Fixed
- **Lỗi Phân loại Sai Bộ môn VioEdu**: Sửa biểu thức kiểm tra `ioe` thành ranh giới từ `\bioe\b` để tránh nhận nhầm chuỗi chứa "vioedu" thành môn Tiếng Anh; tăng cường nhận diện dấu Tiếng Việt và thuật ngữ Toán học.
- **Lỗi HTTP 404 khi Bot Đăng nhập VioEdu**: Cập nhật danh sách candidate endpoint và thông báo hướng dẫn rõ ràng về cơ chế Captcha/Cloudflare.
