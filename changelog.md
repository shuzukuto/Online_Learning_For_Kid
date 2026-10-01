# Nhật ký Thay đổi — EduQuest Pro (changelog.md)

Tất cả các thay đổi quan trọng của dự án EduQuest Pro được ghi lại trong tài liệu này.

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
