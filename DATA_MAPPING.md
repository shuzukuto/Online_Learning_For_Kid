# EduQuest Pro — Hợp Đồng Dữ Liệu & Bản Đồ Mapping (DATA_MAPPING.md)

Tài liệu này quy định cấu trúc bảng SQLite, ánh xạ trường giữa Giao diện người dùng (UI), API REST, Cơ sở dữ liệu SQLite và Dữ liệu bóc tách từ Extension/Scraper.

---

## 1. Bảng `questions` (Ngân hàng Câu hỏi)

| SQLite Column | Kiểu dữ liệu | UI Label / Bộ lọc | JSON API Field | Nguồn Extension / Scraper | Ghi chú |
|---|---|---|---|---|---|
| `id` | `TEXT PRIMARY KEY` | Mã UUID câu hỏi (`#dom_...`, `#q_...`) | `id` | Sinh tự động UUID hoặc DOM ID | Khóa chính nội bộ |
| `q_number` | `INTEGER` | Số thứ tự câu hỏi / ID hiển thị (`ID: #1`, `Câu 1`) | `q_number` | Cấp phát tuần tự liên tục từ 1..N trong CSDL | Định danh số vĩnh viễn toàn ngân hàng, tự động đánh số lại không bị đứt đoạn |
| `source_platform` | `TEXT NOT NULL` | Nền tảng (VioEdu, Hành Trang Số, Trạng Nguyên, Internet Hunter, ...) | `source_platform` | Hostname hoặc tên nguồn (`vioedu`, `hanhtrangso`, `tnmath`, `internet_hunter`, ...) | Hiển thị nhãn nền tảng chính (Tag 3) |
| `source_detail` | `TEXT` | Nguồn chi tiết (CodeMath • TIMO, Trạng Nguyên Tiếng Việt, Kho Đề Mở, ...) | `source_detail` | Phân giải thông minh qua `compute_source_detail()` | Hiển thị thẻ nguồn gốc cụ thể (Tag 4: `🌐 ...`), loại trừ hoàn toàn giá trị trùng lặp `INTERNET_HUNTER` |
| `source_url` | `TEXT` | Đường dẫn nguồn | `source_url` | `window.location.href` | Lưu vết nguồn gốc |
| `exam_name` | `TEXT` | Tên đề thi / Vòng thi | `exam_name` | Tiêu đề vòng thi / trang thi đấu | Vd: "Đấu trường trực tiếp", "Vòng 1" |
| `year` | `INTEGER` | Năm học / Năm thi | `year` | Năm trích xuất | Mặc định năm hiện tại |
| `grade` | `INTEGER` | Khối lớp (Lớp 1 -> Lớp 9) | `grade` | Phân tích từ URL hoặc cấu hình | Mặc định 5 |
| `subject` | `TEXT` | Phân loại Bộ môn | `subject` | AI Classifier (`math`, `vietnamese`, `english`, `science`) | Tự động phân loại |
| `topic` | `TEXT` | Chuyên đề kiến thức | `topic` | Thẻ phân loại hoặc "Chung" | |
| `question_type` | `TEXT NOT NULL` | Dạng câu hỏi | `question_type` | `single_choice`, `multiple_choice`, `fill_blank`, `matching`, `essay` | |
| `content_html` | `TEXT NOT NULL` | Nội dung đầy đủ (kèm thẻ HTML/LaTeX) | `content_html` | HTML trích xuất từ thẻ câu hỏi | Đã chuẩn hóa MathJax/KaTeX, đã loại bỏ sạch sẽ thẻ header số câu (`.panel-heading`) và tiền tố thứ tự ("Câu hỏi số X", "Câu X", "Bài X") |
| `content_text` | `TEXT NOT NULL` | Nội dung văn bản thuần | `content_text` | Text trích xuất từ thẻ câu hỏi | Dùng để tìm kiếm toàn văn; đã cắt bỏ triệt để tiền tố số thứ tự câu hỏi |
| `images` | `TEXT (JSON array)` | Danh sách ảnh đính kèm | `images` | Mảng URL hoặc base64 ảnh minh họa | `["url1", "url2"]` |
| `options` | `TEXT (JSON array)` | Các lựa chọn đáp án A, B, C, D | `options` | `[{"id":"A","content":"..."},...]` | Kèm LaTeX trong từng phương án |
| `correct_answer` | `TEXT` | Đáp án đúng | `correct_answer` | Ký tự đáp án (A/B/C/D) hoặc nội dung điền | Bắt từ phản hồi hoặc user chọn |
| `explanation` | `TEXT` | Lời giải chi tiết | `explanation` | Lời giải trích xuất từ trang web | Tùy chọn |
| `difficulty` | `TEXT` | Mức độ khó | `difficulty` | `easy`, `medium`, `hard`, `olympiad` | Mặc định `medium` |
| `created_at` | `TEXT` | Thời gian tạo | `created_at` | ISO 8601 Timestamp | |
| `updated_at` | `TEXT` | Thời gian sửa | `updated_at` | ISO 8601 Timestamp | |

---

## 2. Bảng `collector_logs` (Nhật ký Thu thập & Debug)

| SQLite Column | Kiểu dữ liệu | UI Label | JSON API Field | Mô tả |
|---|---|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | ID | `id` | Mã nhật ký |
| `platform` | `TEXT NOT NULL` | Nền tảng | `platform` | `vioedu`, `tnmath`, `hunter`, `extension`, `pdf` |
| `status` | `TEXT NOT NULL` | Trạng thái | `status` | `success`, `error`, `info`, `warning` |
| `message` | `TEXT NOT NULL` | Thông điệp | `message` | Nội dung log hiển thị |
| `items_count` | `INTEGER` | Số câu hỏi | `items_count` | Số lượng câu hỏi đã thu thập được |
| `created_at` | `TEXT` | Thời gian | `created_at` | Thời điểm ghi nhận |

---

## 3. Bảng `exams` & `exam_questions` (Quản lý Đề thi)

- `exams`: `id`, `title`, `grade`, `duration_minutes`, `header_info`, `notes`, `created_at`.
- `exam_questions`: `id`, `exam_id`, `question_id`, `order_index`, `points`.

---

## 4. Giao thức API Thu thập & Đồng bộ

1. **`POST /api/questions/bulk`**:
   - Nhận mảng câu hỏi từ Chrome Extension (`BulkQuestionCreate`).
   - Thẩm định chất lượng từng câu qua `is_valid_question_payload(q)`: lập tức từ chối và bỏ qua mọi câu hỏi chứa chuỗi debug log Extension, timestamp, giao diện tiện ích, popup tiếp tục bài làm hệ thống (`Bạn đang làm bài kiểm tra này...`), thanh tiến độ hoàn thành bài thi (`Bạn đã hoàn thành...`, `\d+/\d+ câu`, `\d+%$`), hoặc thông báo trạng thái tải dữ liệu (`Đang lấy thông tin câu hỏi`, `viogpt-loading`). Với câu dạng điền khuyết không có options, bắt buộc phải có câu hỏi/từ để hỏi hoặc công thức toán học.
   - Làm sạch tự động: gỡ bỏ toàn bộ thẻ `.panel-heading` và tiền tố "Câu hỏi số X", "Câu X", "Bài X" khỏi `content_text` và `content_html` qua `clean_html_and_math()`.
   - Tự động bỏ qua câu trùng lặp (dựa trên `content_hash` và `id`).
   - Tự động phân loại môn học qua `classify_subject()`.
   - Phản hồi: `{"success": true, "inserted_count": count, "skipped_count": skipped_count}`.
   - Extension tự động cập nhật cờ `saved_to_db = true` và kích hoạt luồng đồng bộ định kỳ `autoSyncPendingQuestions` đảm bảo mọi câu hỏi bóc tách được đều được lưu vĩnh viễn vào CSDL.
   - Trả về `inserted_count` và `skipped_count`.
2. **`GET /api/stats`**:
   - Nhịp tim Heartbeat Polling 3 giây từ Frontend.
   - Trả về `total_questions`, `by_platform`, `by_subject`.
   - Kích hoạt cơ chế Zero-Reload tự động làm mới Ngân hàng câu hỏi.
3. **`POST /api/hunter/run`**:
   - Chạy Thợ săn câu hỏi Internet tự động kết hợp Động cơ Tham số hóa Động (`generate_parametric_questions`).
   - Nhận `subject`, `grade`, `custom_url` và `custom_urls: List[str]`.
   - Lọc qua chốt chặn thẩm định `is_valid_question_payload(q)` loại bỏ 100% rác HTML/CSS/Doctype, chuỗi mã UUID/Hex, bài viết tin tức/thông báo giải đấu/combo khóa học, thông tin liên hệ/SĐT/quảng cáo học kèm, thanh tiến độ và các tiêu đề trang.
   - Trả về `total_harvested`, `new_saved`, `skipped_duplicates`, `skipped_invalid` và danh sách câu hỏi đã bóc tách.
4. **`POST /api/collect/logs/sync`**:
   - Nhận sự kiện log telemetry từ Extension v1.3.11 (`platform`, `status`, `message`, `count`).
   - Tự động ghi vào SQLite `collector_logs`.
5. **Bộ nhớ tạm Extension (`eduquest_captured_questions` & `eduquest_ext_logs`)**:
   - Lưu trữ danh sách câu hỏi bóc tách được và nhật ký debug trên client (`localStorage` & `chrome.storage.local`) phục vụ tính năng "Xem các câu hỏi đã quét được" và "Nhật ký Debug".
   - **Cơ chế Chống Trùng & Quản lý Bộ đệm (v1.3.11)**:
     - `savedQuestionIds` và `savedTextSignatures` tự động đồng bộ hóa cùng `capturedQuestions` qua `rebuildSignatures()` và `isAlreadyCaptured(sig, qId)`.
     - **Chuẩn hóa Stem**: Tách bỏ tiền tố "Câu hỏi số X", "Câu X", "Bài X" qua `normalizeStemForSignature` trước khi hash signature, đảm bảo câu hỏi có hay không có thẻ tiêu đề đều nhận diện đúng là trùng nhau.
     - **Lọc lồng thẻ**: Tự động loại trừ các thẻ con nếu thẻ cha đã được chọn (`containers.filter(el => !containers.some(p => p !== el && p.contains(el)))`).
     - **Kiểm soát `is_correct`**: Reset về `false` nếu toàn bộ hoặc nhiều hơn 1 đáp án bị đánh dấu `true` trong câu trắc nghiệm đơn.
     - **Chặn Loading & Tiến độ**: Bỏ qua khi trang hoặc phần tử đang tải dữ liệu hoặc là thanh tiến độ làm bài.
     - **Triệt tiêu Spam Log**: Quét định kỳ chạy ngầm (`isBackground = true`) tuyệt đối im lặng, không ghi log skip; khử trùng lặp skip log liên tiếp (`lastLoggedSkipSig`).
     - Chống chữ ký mồ côi (Orphan Signatures): Khi mảng câu hỏi rỗng hoặc câu hỏi bị xóa, các chữ ký tương ứng tự động bị tiêu hủy, cho phép quét lại câu hỏi trên màn hình ngay lập tức.
     - Khi thực hiện "Xóa danh sách" (Clear All): Cả hai Set chữ ký bị clear lập tức, phát sự kiện quét lại sau 300ms (`scanPageQuestions(true)`).
     - Hỗ trợ xóa từng câu (Single Item Deletion) qua nút 🗑️ trên Modal hoặc ✕ trên Popup.
   - Schema đối tượng câu hỏi quét được:
     - `id`: Mã định danh (`net_...`, `dom_...`, `vio_graphql_...`)
     - `source_platform`: Nền tảng (`vioedu`, `hanhtrangso`, `tnmath`, ...)
     - `grade`: Khối lớp (int)
     - `subject`: Bộ môn (`math`, `vietnamese`, `english`, ...)
     - `question_type`: `single_choice`, `fill_blank`, `matching`
     - `content_html` & `content_text`: Thân câu hỏi (gồm chỉ dẫn + nội dung đề toán đã bóc tách công thức MathJax sang text chuẩn, nghiêm cấm chỉ chứa UUID hoặc tiêu đề tin tức)
     - `options`: Mảng phương án `[{ id: 'A', content: '...', is_correct: bool }]` (hỗ trợ lưới `.choice-answer-grid-2026`, `_2UU-q`, radio, kéo ghép và dropdown)
     - `images`: Mảng URL ảnh minh họa
     - `saved_to_db`: Trạng thái đã lưu vào CSDL (`true` / `false`)
   - Schema bản ghi nhật ký hoạt động (`eduquest_ext_logs`):
     - `id`: Mã log ngẫu nhiên (`log_...`)
     - `time`: Giờ hiển thị (`HH:MM:SS`)
     - `timestamp`: Epoch ms
     - `source`: URL rút gọn của tab/nguồn sinh log (vd: `vio.edu.vn/skill-practice…`)
     - `type`: `info`, `success`, `skip`, `net`, `error`
     - `msg`: Nội dung thông điệp
     - `detail`: Dữ liệu kỹ thuật đính kèm
6. **Bóc tách Câu hỏi VioEdu (VioEdu GraphQL, React BEM Spec & Onboard Flow)**:
   - **GraphQL Endpoint**: `POST https://vio.edu.vn/graphql`
     - Truy vấn câu hỏi: `PracticeQuestionQuery` -> `data.getPracticeQuestionBySkillId` (`_id`, `skillName`, `content`, `questionType`, `answers`, `textDropdownAnswers`, `leftMatching`, `rightMatching`).
     - Truy vấn kết quả & giải thích: `GetQuestionResultQuery` -> `data.getQuestionResultQuery` (`explainPractice`, `correctAnswers`).
   - **DOM React BEM & Onboard Flow Architecture**:
     - Khung câu hỏi / bài khảo sát: `.box.box--practice`, `.box--practice__content`, `.practice-question-text`, `[class*='onboard-flow']`, `[class*='onboard-question']`, `[class*='assessment-question']`, `[class*='question-layout']`.
     - Lưới đáp án: `.choice-answer-grid-2026`, từng lựa chọn là `div[role="button"]._2UU-q` bên trong `div._27IHb`. **Tuyệt đối không coi lưới đáp án là question card**.
     - Bóc tách Bài đọc hiểu & Thân đề bài (`extractCardStem`): Clone container câu hỏi, phẫu thuật bóc tách và xóa sạch 100% các khối đáp án (`.choice-answer-grid-2026`, `_2UU-q`, button, action nav, timer), loại bỏ toàn bộ các khối điều khiển cỡ chữ (`[data-skill-test-font-size]`, `.pull-right`, `._3-L-1`, `.cicn`) và ghi chú (`.box-choice-note` - "100% Đang cân nhắc") khỏi cả đề bài và tiêu đề, bảo lưu ngắt dòng đoạn văn (`\n\n`) để giữ nguyên vẹn trọn vẹn toàn bộ các đoạn văn đọc hiểu Tiếng Việt kèm câu hỏi dẫn bên dưới.
     - Chốt chặn chống bẫy đáp án (`Anti-Option-Collision`): Kiểm tra chuỗi stem với chuỗi ghép các options; loại bỏ ngay nếu đề bài bị trùng hoặc chứa toàn bộ các lựa chọn mà không có câu hỏi thực sự.
     - Thân bài & Công thức: Trích xuất aria-label công thức toán từ `span.math-tex > span.mjpage > span.mjx-math[aria-label]`.
     - Ô điền số / Dropdown: Chuyển placeholder dropdown thành `[ ... ]`.
     - Lời giải bài toán: Bóc tách tự động từ `div.ZpmD_`, `div._3yoLK` ("Giải thích: ...").
7. **`DELETE /api/collect/logs`**:
   - Xóa toàn bộ nhật ký thu thập trong CSDL để làm sạch giao diện.
7. **`GET /api/questions/duplicates` & `POST /api/questions/duplicates/clean`**:
   - `GET`: Quét và gom nhóm toàn bộ các câu hỏi trùng lặp trong CSDL (`GROUP BY LOWER(TRIM(content_text)) HAVING count > 1`).
   - `POST`: 1-click xóa sạch các bản sao dư thừa, giữ lại bản ghi gốc cũ nhất (`action: "keep_oldest"`).
8. **`GET /api/database/diagnostics` & `POST /api/database/diagnostics/fix`**:
   - `GET`: Bác sĩ CSDL chuẩn đoán toàn vẹn SQLite (`PRAGMA integrity_check`), phát hiện câu hỏi độc nhất/trùng lặp, và quét các câu hỏi rác/blog/liên hệ qua `is_valid_question_payload`.
   - `POST`: Tự động sửa chữa: xóa sạch các câu rác blog / quảng cáo, xóa bản sao trùng, bổ sung môn học bị thiếu qua AI Classifier, tự động đánh số lại dãy 1..N và tối ưu hóa file DB với `VACUUM` & `ANALYZE`.
9. **`POST /api/exams/auto-generate`**:
   - Tự động tạo đề thi theo ma trận: `subject`, `grade`, `total_questions`, `easy_count`, `medium_count`, `hard_count`, `topic`.
   - Lấy mẫu ngẫu nhiên khớp cơ cấu ma trận và trả về danh sách `question_ids`.
10. **`GET /api/questions`**:
   - Phân trang và tìm kiếm câu hỏi trong CSDL.
   - Hỗ trợ tham số: `platform`, `grade`, `subject`, `topic`, `question_type`, `difficulty`, `search`, `source_detail`, `only_duplicates`, `sort_by`, `page`, `page_size` (hỗ trợ từ `1` đến `10000` để lấy toàn bộ CSDL một lần).
   - Trả về: `items` (danh sách câu hỏi), `total` (tổng số câu thỏa mãn bộ lọc), `page`, `page_size`, `total_pages`.

---

## 5. Ánh xạ Lưu trữ Cục bộ (Local Storage Mapping)

| Khóa LocalStorage | Kiểu | Thành phần sử dụng | Mục đích |
|---|---|---|---|
| `eduquest_default_grade` | String (`"1"`-`"9"`) | Hệ thống | Khối lớp mặc định toàn hệ thống |
| `eduquest_selected_grade` | String (`"1"`-`"9"`) | Tất cả bộ lọc | Khối lớp được chọn gần nhất |
| `eduquest_scraper_plat` | String | Bot cào | Nền tảng cào đã chọn (`vioedu`/`tnmath`) |
| `eduquest_scraper_user` | String | Bot cào | Tên đăng nhập cào |
| `eduquest_scraper_round` | String | Bot cào | Mã vòng thi cào |
| `eduquest_autohunter` | String (`"true"`/`"false"`) | Hunter | Trạng thái vòng lặp 5 phút |
| `eduquest_hunter_urls` | JSON Array | Hunter | Danh sách link web tùy chọn cào tự động |
| `eduquest_hunter_log` | String | Hunter | Nhật ký trực tiếp của Thợ săn internet |
| `eduquest_scraper_log` | String | Bot cào | Nhật ký trực tiếp của Bot cào tài khoản |
| `eduquest_ext_logs` | JSON Array | Extension | Toàn bộ log debug hoạt động của Extension |
