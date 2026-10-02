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
| `grade` | `INTEGER` | Khối lớp (Lớp 1 -> Lớp 12) | `grade` | Phân tích từ URL hoặc cấu hình | Mặc định 5 (Hỗ trợ toàn bộ Khối 1 đến 12) |
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

## 3. Bảng `practice_history` (Lịch sử Luyện tập Trực tuyến & Đánh giá Năng lực)

Bảng lưu trữ vết toàn bộ các phiên làm bài trực tuyến trong Phân hệ Luyện tập, hỗ trợ phân tích năng lực và biểu đồ xu hướng:

| SQLite Column | Kiểu dữ liệu | UI Label / Bộ lọc | JSON API Field | Nguồn / Tính toán | Ghi chú |
|---|---|---|---|---|---|
| `id` | `TEXT PRIMARY KEY` | Mã phiên luyện tập | `id` | UUID sinh tự động | Khóa chính |
| `exam_id` | `TEXT` | Mã đề thi | `exam_id` | ID đề hoặc ID phiên ngẫu nhiên | Khóa ngoại mềm tới `exams.id` |
| `exam_title` | `TEXT NOT NULL` | Tiêu đề bài luyện tập | `exam_title` | Tiêu đề hiển thị | Vd: "Luyện tập Toán Khối 5 Tự do" |
| `subject` | `TEXT` | Bộ môn | `subject` | `math`, `vietnamese`, `english`, `science` | Phân môn |
| `grade` | `INTEGER` | Khối lớp | `grade` | 1 đến 12 | Khối lớp thi |
| `total_questions` | `INTEGER NOT NULL` | Tổng số câu | `total_questions` | Đếm số lượng câu hỏi trong đề | |
| `correct_count` | `INTEGER` | Số câu đúng | `correct_count` | Đếm câu trả lời đúng | Ký hiệu ✓ xanh lá |
| `wrong_count` | `INTEGER` | Số câu sai | `wrong_count` | Đếm câu trả lời sai | Ký hiệu ✕ đỏ |
| `skipped_count` | `INTEGER` | Số câu bỏ qua | `skipped_count` | Đếm câu chưa trả lời | |
| `score` | `REAL` | Điểm số (Thang 10) | `score` | `(correct / total) * 10.0` | Thang điểm 10 chuẩn MOET |
| `max_score` | `REAL` | Điểm tối đa | `max_score` | 10.0 | Mặc định 10.0 |
| `duration_seconds` | `INTEGER` | Thời gian cho phép | `duration_seconds` | Thời gian quy định (giây) | Mặc định 900s (15 phút) |
| `time_spent_seconds` | `INTEGER` | Thời gian làm bài | `time_spent_seconds` | Thời gian thực tế học sinh làm | Tính bằng giây |
| `ranking` | `TEXT` | Xếp loại học lực | `ranking` | Xuất sắc, Giỏi, Khá, Trung bình, Cần cố gắng | Quy đổi theo chuẩn Bộ GD&ĐT |
| `answers_detail` | `TEXT (JSON)` | Chi tiết bài làm | `answers_detail` | Mảng JSON chi tiết lựa chọn của học sinh | Lưu vết câu hỏi, đáp án chọn, cờ 🚩, thời gian |
| `created_at` | `TEXT NOT NULL` | Thời gian nộp | `created_at` | ISO 8601 UTC Timestamp | Có chỉ mục `idx_practice_created_at` |

**Chỉ mục hiệu năng SQLite**:
- `idx_practice_created_at` on `practice_history(created_at DESC)`
- `idx_practice_subject` on `practice_history(subject)`
- `idx_practice_grade` on `practice_history(grade)`
- `idx_practice_exam_id` on `practice_history(exam_id)`

---

## 4. Bảng `exams` & `exam_questions` (Quản lý Đề thi)

- `exams`: `id`, `title`, `grade`, `duration_minutes`, `header_info`, `notes`, `created_at`.
- `exam_questions`: `id`, `exam_id`, `question_id`, `order_index`, `points`.

---

## 5. Giao thức API Thu thập, Bóc tách Đề thi & Luyện tập

1. **`POST /api/questions/bulk`**:
   - Nhận mảng câu hỏi từ Chrome Extension (`BulkQuestionCreate`).
   - Thẩm định chất lượng từng câu qua `is_valid_question_payload(q)`: lập tức từ chối và bỏ qua mọi câu hỏi chứa chuỗi debug log Extension, timestamp, giao diện tiện ích, popup tiếp tục bài làm hệ thống (`Bạn đang làm bài kiểm tra này...`), thanh tiến độ hoàn thành bài thi (`Bạn đã hoàn thành...`, `\d+/\d+ câu`, `\d+%$`), thông báo trạng thái tải dữ liệu (`Đang lấy thông tin câu hỏi`, `viogpt-loading`), popup tính điểm VioEdu ("cách tính điểm", "tổng điểm <"), và liên kết khóa học/video VnDoc ("video mở đầu", "học online luyện từ", "kh luyện từ"). Với câu dạng điền khuyết không có options, bắt buộc phải có câu hỏi/từ để hỏi hoặc công thức toán học.
   - Tự động sửa bộ môn (`subject`): Nếu câu hỏi được gắn nhãn `english` nhưng nội dung thực tế chứa dấu thanh Tiếng Việt, hệ thống tự động tái phân loại chính xác về `vietnamese`.
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
   - **Giao diện Nhật ký Trực tiếp (`#hunter-live-log` & `#hunter-log-toolbar`)**:
     - Hiển thị theo nguyên tắc mới nhất trên cùng (Newest on Top).
     - Phân định rõ ràng từng dòng cho mỗi thông báo, ngăn cách giữa các phiên săn bằng khoảng trống `\n\n`.
     - Thanh điều khiển `#hunter-log-toolbar` gồm 2 nút: `📋 Sao chép Log` (sao chép toàn bộ nhật ký với định dạng ngắt dòng sạch) và `🗑️ Xóa Log` (xóa sạch khung log và dọn sạch `eduquest_hunter_log` trong `localStorage`).
     - Cơ chế `formatAndSortHunterLog`: Tự động khôi phục, bóc tách dòng dính và đảo chiều sắp xếp cho các dữ liệu log cũ lưu trong `localStorage`.
4. **`POST /api/collect/logs/sync`**:
   - Nhận sự kiện log telemetry từ Extension v1.3.15 (`platform`, `status`, `message`, `count`).
   - Tự động ghi vào SQLite `collector_logs`.
5. **Bộ nhớ tạm Extension (`eduquest_captured_questions` & `eduquest_ext_logs`)**:
   - Lưu trữ danh sách câu hỏi bóc tách được và nhật ký debug trên client (`localStorage` & `chrome.storage.local`) phục vụ tính năng "Xem các câu hỏi đã quét được" và "Nhật ký Debug".
   - **Cơ chế Chống Trùng & Quản lý Bộ đệm (v1.3.15)**:
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
11. **`POST /api/collect/run` (Bot Đăng nhập & Cào Vòng thi / Bài Thực hành Ngầm VioEdu)**:
   - Kích hoạt Bot tự động chạy ngầm (Playwright Chromium) để đăng nhập, tìm kiếm và cào câu hỏi từ VioEdu.
12. **`GET /api/hunter/grade-sources` & `POST /api/hunter/harvest-by-grade` (Săn Dữ Liệu Toán Toàn Diện Khối 1 đến 12)**:
   - `GET /api/hunter/grade-sources?grade={1..12}`: Trả về danh mục các nguồn bài tập Toán chuẩn hóa động theo khối lớp được chọn (hỗ trợ toàn bộ Khối 1 đến Khối 12) theo 3 nhóm:
     - 🇻🇳 **Toán Tiếng Việt (GDPT 2018)**: Hành Trang Số (SGK/SBT Kết nối & Cánh diều `classes={grade}`), VioEdu (FPT), Trạng Nguyên Toán, OLM.vn (ĐH Sư Phạm `toan-lop-{grade}`), VnDoc (Phiếu tuần & Đề thi `toan-lop-{grade}`), VietJack (`toan-lop-{grade}/index.jsp`).
     - 🇬🇧 **Toán Tiếng Anh (Math Grade {grade})**: K5 Learning (Worksheets PDF kèm Answer Key theo khối 1-6), IXL Learning Math (US Common Core skills `grade-{grade}`), Khan Academy (`cc-{grade}th-grade-math` hoặc `algebra`, `geometry`, `algebra2`, `precalculus`), Common Core Math.
     - 🏆 **Toán Olympic & Tư duy Song ngữ**: Kangaroo Math (IKMC phân nhóm Ecolier 1-2 / Ecolier 3-4 / Benjamin 5-6 / Cadet 7-8 / Junior 9-10 / Student 11-12), Olympic TIMO (Primary 1-5 / Secondary 1-4 / Senior), Olympic SASMO & CodeMath.
   - `POST /api/hunter/harvest-by-grade`: Nhận payload `{ "grade": int, "subject": "math" }` (1 <= grade <= 12). Kích hoạt cơ chế 1-click quét và nạp nhanh toàn diện kho câu hỏi Toán cho đúng khối lớp được chọn, tự động phân lập không bị lẫn đề khối khác, chuẩn hóa LaTeX/KaTeX, gán thẻ `source_detail` chuyên biệt, loại trừ trùng lặp và lưu vĩnh viễn vào CSDL SQLite.
   - **Backward compatibility**: Duy trì alias `GET /api/hunter/grade2-sources` và `POST /api/hunter/harvest-grade2` cho các luồng gọi cũ.
13. **Mapping Nguồn Nền tảng & Chi tiết Mới (`source_platform` & `source_detail`)**:
   - `k5learning` ↔ `K5 Learning (US Math)`
   - `ixl` ↔ `IXL Learning Math`
   - `khanacademy` ↔ `Khan Academy Math`
   - `olm` ↔ `OLM.vn (ĐH Sư Phạm)`
   - `kangaroo` ↔ `Olympic Kangaroo (IKMC)`
   - `commoncore` ↔ `Common Core Math`
   - **Tham số đầu vào (`ScrapeRequest`)**:
     - `platform`: `vioedu`
     - `action`: `bot_crawl`, `crawl`, `login`
     - `username`: Tên đăng nhập tài khoản học sinh VioEdu
     - `password`: Mật khẩu
     - `round_id`: (Tùy chọn) Mã vòng thi arena (`1`, `2`), URL bài luyện tập (`https://vio.edu.vn/skill-practice/:id`), mã MongoDB hex 24 ký tự, hoặc `https://vio.edu.vn/skill-list`.
     - `grade`: Khối lớp (ưu tiên nhận diện tự động từ tài khoản).
   - **Nhận diện Khối lớp cố định**: Tự động trích xuất `user.grade` từ hồ sơ VioEdu của học sinh. Khóa cứng `account_grade` cho toàn bộ câu hỏi và vòng thi bóc tách.
   - **Tự Động Xử Lý Vượt Quá 3 Thiết Bị (OVER_QUOTA & 289 Auto-Recovery)**:
     - Tự động phát hiện phản hồi `OVER_QUOTA` (mã trạng thái 289) khi tài khoản học sinh vượt quá giới hạn 3 thiết bị đăng nhập đồng thời.
     - Tự động gửi mutation GraphQL chuẩn VioEdu `resetLogin3Devices(username: $username)` để giải phóng phiên làm việc của các thiết bị cũ.
     - Tự động thử lại đăng nhập ngay sau khi giải phóng thành công, tránh đứt đoạn tiến trình.
     - Trình duyệt Playwright tự động nhận diện và click nút `"Đăng xuất toàn bộ thiết bị"` trên giao diện web nếu xuất hiện cảnh báo.
   - **Cơ chế Cào Bài Thực Hành An Toàn Tuyệt Đối (Read-Only GraphQL)**:
     - Sử dụng truy vấn GraphQL `PracticeQuestionQuery` không đột biến dữ liệu (`score: 0`, `isManual: false`).
     - Tuyệt đối không gọi `PracticeResultMutation`, không nộp bài làm sai lệch điểm số hay quota luyện tập của học sinh.
     - Hỗ trợ đầy đủ các dạng: Điền ô trống (`questionType: 3`), trắc nghiệm (`questionType: 1/2`), nối cặp và dropdown.
   - **Giao diện Nhật ký Trực tiếp**:
     - Sắp xếp dòng mới nhất trên đầu (Newest on top).
     - Tích hợp thanh công cụ với nút `📋 Sao chép Log` và `🗑️ Xóa Log`.
   - **Phản hồi**:
     - `success`: `true` / `false`
     - `student_name`: Tên học sinh
     - `account_grade`: Khối lớp cố định của tài khoản
     - `total_found`: Tổng số câu hỏi tìm thấy
     - `inserted_count`: Số câu hỏi mới đã lưu vào SQLite
     - `exam_name`: Tên vòng thi / bài thực hành
     - `logs`: Mảng nhật ký chi tiết từng bước xử lý.

14. **Bóc Tách Đề Thi Từ Ảnh (Image OCR) & File PDF (`POST /api/import/image`, `POST /api/import/pdf`, `POST /api/import/exam-file`)**:
    - **Đầu vào**: Tệp đa định dạng (PDF hoặc Ảnh: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`), cờ `save_to_bank` (boolean).
    - **Tiền xử lý ảnh**: OpenCV CLAHE (`clipLimit=2.5`, `tileGridSize=(8,8)`), lọc song phương (`bilateralFilter`), lưu ảnh xem trước vào `data/media/ocr_{uuid}.ext`.
    - **Động cơ OCR**: RapidOCR (PaddleOCR ONNX) / EasyOCR / PyTesseract.
    - **Phản hồi**:
      - `success`: `true` / `false`
      - `filename`: Tên tệp
      - `file_type`: `"image"` hoặc `"pdf"`
      - `total_extracted`: Số câu trích xuất thành công
      - `saved_to_bank`: Cờ lưu CSDL
      - `saved_count`: Số câu đã lưu
      - `preview_questions`: Mảng đối tượng câu hỏi kèm URL ảnh `images: ["/media/ocr_..."]`, phương án trắc nghiệm, đáp án và lời giải.
    - **Giao diện đối soát**: Bảng đối soát câu hỏi (Audit review table) cho phép giáo viên kiểm tra, sửa nội dung KaTeX, chọn đáp án đúng trước khi commit vào CSDL.
15. **Biên Soạn & Xuất Đề Thi Chuẩn In Ấn MOET PDF A4 (`POST /api/export/pdf`)**:
    - **Đầu vào (`ExamCreate`)**:
      - `title`: Tiêu đề đề thi
      - `grade`: Khối lớp (1 đến 12)
      - `duration_minutes`: Thời gian làm bài
      - `question_ids`: Danh sách ID câu hỏi chọn lọc
    - **Xử lý Backend**:
      - `normalize_moet_math_symbols`: Chuẩn hóa công thức Toán (`\frac`, `\sqrt`, `\times`, `\div`, `\angle`, `\pi`, `x^2`, `x^3`).
      - `build_moet_exam_html`: Tạo HTML chuẩn Bộ GD&ĐT: khổ A4, căn lề 20/20/25/15mm, font Times New Roman 12pt, ngắt trang thông minh `page-break-inside: avoid`.
      - Tách riêng Bảng Đáp Án & Thang Điểm ở cuối đề thi (`page-break-before: always;`).
    - **Động cơ kết xuất**: Headless Playwright Chromium (`page.pdf()`).
    - **Phản hồi**: Nhị phân `application/pdf` (`b'%PDF-'`, 100-150KB), Content-Disposition attachment.
    - **Fallback**: `@media print` CSS kích hoạt `window.print()` khi ngoại tuyến.
16. **Phân Hệ Luyện Tập Trực Tuyến & Báo Cáo Phân Tích (Interactive Practice Arena APIs)**:
    - **`POST /api/practice/generate`**:
      - Tham số: `{ "exam_id": str, "subject": str, "grade": int, "count": int, "difficulty": str }`.
      - Phản hồi: `{ "success": true, "exam_id": str|null, "exam_title": str, "duration_minutes": int, "duration_seconds": int, "grade": int, "subject": str, "total_questions": int, "questions": [...] }`.
      - **Tương thích Frontend**: Hỗ trợ bóc tách linh hoạt cả `data.questions` và cấu trúc bọc `data.session?.questions` (`data.questions || data.session?.questions || []`).
    - **`POST /api/practice/submit`**:
      - Tham số (`PracticeSubmitRequest`):
        + `exam_id`: Mã bài thi
        + `exam_title`: Tên bài thi
        + `subject`: Bộ môn
        + `grade`: Khối lớp
        + `duration_seconds`: Thời gian quy định
        + `time_spent_seconds`: Thời gian thực tế làm bài
        + `answers`: Danh sách câu trả lời `[{ question_id, selected_answer, time_spent_seconds, is_flagged }]`
          * **Hỗ trợ Bí danh Khóa (Payload Aliases)**: Pydantic model `PracticeAnswerSubmission` hỗ trợ đồng thời cả 3 khóa qua `AliasChoices` và `@model_validator(mode="before")`:
            - `selected_answer`: Khóa chuẩn backend Pydantic model.
            - `selected_option`: Khóa client web SPA `practice.js`.
            - `user_answer`: Khóa tài liệu & bộ kiểm thử `test_app.py`.
          * Phía Frontend (`practice.js`) tự động truyền cả `selected_answer`, `selected_option` và `user_answer` trong mỗi phần tử để bảo đảm tương thích hai chiều tuyệt đối.
      - Xử lý: So khớp đáp án đúng trong CSDL, tính điểm thang 10.0 và thang 100.0, xếp loại học lực Bộ GD&ĐT, lưu bản ghi vào bảng SQLite `practice_history`.
      - Phản hồi: `{ "success": true, "id": str, "score": float, "score_100": float, "ranking": str, "correct_count": int, "wrong_count": int, "skipped_count": int, "answers_detail": [...] }`.
    - **`GET /api/practice/history`**:
      - Tham số: `limit` (mặc định 50), `subject`, `grade`.
      - Phản hồi: `{ "success": true, "count": int, "records": [...] }`.
      - **Tương thích Frontend**: Phía client hỗ trợ tiếp nhận cả `data.records` và `data.history` (`data.records || data.history || []`).
    - **`GET /api/practice/history/{record_id}`**:
      - Phản hồi: `{ "success": true, "record": { "id", "exam_title", "score", "answers_detail", ... } }`.
    - **`GET /api/practice/analytics`**:
      - Tham số: `subject`, `grade`.
      - Phản hồi:
        + `total_attempts`: Tổng số lượt luyện tập
        + `overall_accuracy`: Tỷ lệ chính xác tổng thể (%)
        + `average_score`: Điểm trung bình
        + `highest_score`: Điểm cao nhất
        + `trending_scores`: Mảng điểm số theo thời gian phục vụ vẽ biểu đồ Canvas
        + `subject_mastery`: Mảng tỷ lệ thành thạo từng môn (`[ { subject, subject_label, attempts, accuracy_rate, average_score, ... } ]`). Client hỗ trợ cả định dạng mảng đối tượng và từ điển tra cứu theo subject key.
        + `badges`: Danh sách 8 huy hiệu thành tích kèm trạng thái mở khóa `unlocked: true/false`. Client `renderBadgesGrid` hỗ trợ cả mảng đối tượng `{ id, unlocked }` và mảng chuỗi mã huy hiệu `[ "badge_first_step", ... ]`.

---

## 6. Ánh xạ Lưu trữ Cục bộ (Local Storage Mapping)

| Khóa LocalStorage | Kiểu | Thành phần sử dụng | Mục đích |
|---|---|---|---|
| `eduquest_default_grade` | String (`"1"`-`"12"`) | Hệ thống | Khối lớp mặc định toàn hệ thống |
| `eduquest_selected_grade` | String (`"1"`-`"12"`) | Tất cả bộ lọc | Khối lớp được chọn gần nhất |
| `eduquest_scraper_plat` | String | Bot cào | Nền tảng cào đã chọn (`vioedu`/`tnmath`) |
| `eduquest_scraper_user` | String | Bot cào | Tên đăng nhập cào |
| `eduquest_scraper_round` | String | Bot cào | Mã vòng thi cào |
| `eduquest_bot_autocrawl` | String (`"true"`/`"false"`) | Bot VioEdu | Trạng thái bật/tắt chu kỳ tự động cào 5 phút |
| `eduquest_autohunter` | String (`"true"`/`"false"`) | Hunter | Trạng thái vòng lặp 5 phút của Thợ săn |
| `eduquest_hunter_urls` | JSON Array | Hunter | Danh sách link web tùy chọn cào tự động |
| `eduquest_hunter_log` | String | Hunter | Nhật ký trực tiếp của Thợ săn internet |
| `eduquest_scraper_log` | String | Bot cào | Nhật ký trực tiếp của Bot cào tài khoản |
| `eduquest_practice_history` | JSON Array | Practice Arena | Bộ đệm lịch sử các phiên thi gần nhất trên client |
| `eduquest_ext_logs` | JSON Array | Extension | Toàn bộ log debug hoạt động của Extension |
