# EduQuest Pro — Quy Tắc Kiến Trúc & Đặc Tả Nghiệp Vụ (rules.md)

Tài liệu này là **đặc tả thiết kế còn hiệu lực** của hệ thống EduQuest Pro (thu thập, lưu trữ, biên soạn câu hỏi trực tuyến và đề thi).

---

## 1. Kiến trúc Hệ thống & Quy Chuẩn Phiên Bản

Hệ thống hoạt động theo mô hình Hybrid phân tán:
1. **Phiên bản chuẩn hóa toàn diện**:
   - **Web App**: `v1.0.35` (hien thi dong bo tai `frontend/index.html` va `frontend/js/app.js`).
   - **Chrome Extension**: `v1.3.17` (dong bo 100% tren `manifest.json`, `background.js`, `interceptor.js`, `content.js`, `popup.html`, `popup.js`).
   - **Cache Buster**: `?v=1.0.38` tren tat ca lien ket tai nguyen tinh (CSS, JS).
   - **Nguyên tắc loại trừ chuỗi cũ**: Tuyệt đối không để tồn tại bất kỳ phiên bản lỗi thời nào (`v1.3.0`, `v1.3.11`, `v1.3.12`, `v1.3.14`) trong toàn bộ mã nguồn.
2. **Backend Engine**: FastAPI (Python 3.10+) chạy tại `http://127.0.0.1:8000`.
   - Cơ sở dữ liệu: SQLite (`data/questions.db`).
   - Thư mục Media/Ảnh: `data/media/`.
   - Export Word: `python-docx` xuất file `.docx` chuẩn mẫu đề thi Việt Nam.
   - Export PDF: Headless Playwright Chromium xuất file `.pdf` chuẩn in ấn MOET A4 kèm bảng đáp án và thang điểm.
   - Bóc tách Đề thi & Ảnh OCR: Động cơ trích xuất PDF và Image OCR (`backend/pdf_extractor.py`) hỗ trợ `.png, .jpg, .jpeg, .webp, .bmp` với tự động phóng đại siêu phân giải (Super-resolution Upscaling), khôi phục dấu thanh tiếng Việt và lọc nhiễu đề thi song ngữ.
3. **Frontend Single-Page App**: HTML5, Vanilla JavaScript, CSS3 Design Tokens.
   - Thư viện hiển thị công thức: KaTeX 0.16.10 tự động render `$ ... $`, `$$ ... $$`, `\( ... \)`.
   - Giao diện gồm 6 module chính:
     + Bảng Tổng quan (Dashboard Analytics).
     + Ngân hàng Câu hỏi (Question Bank Manager).
     + Biên soạn & Trộn Đề (Exam Builder: Word & MOET PDF).
     + Trung tâm Thu thập (Collector Center: Scrapers, Internet Hunter).
     + Soạn Câu hỏi Mới (Question Editor & Multi-file Image/PDF OCR Studio).
     + 🎯 Luyện tập Trực tuyến (Interactive Practice Arena, Trending Charts, Mastery, Badges).
   - **Quy chuẩn UX Tab Trình duyệt**: Bỏ hoàn toàn biểu tượng/logo ở tab trình duyệt bằng chuẩn W3C `<link rel="icon" href="data:,">`.
4. **Trình thu thập dữ liệu (Collector Modules)**:
   - **Chrome/Edge Extension (v1.3.15)**: Thu thập tự động câu hỏi trên VioEdu, Hành Trang Số, Trạng Nguyên, CodeMath, IOE, VietJack, Lời Giải Hay qua Network Request Interception, DOM Extraction và Bulk Lesson Crawler.
   - **Bộ bóc tách đề thi PDF & Image OCR**: Phân tích đề thi Olympic TIMO, ASMO, HKIMO và ảnh chụp đề thi bằng PyPDF, OpenCV và RapidOCR/EasyOCR.
   - **Internet Hunter & Parametric Generator**: Thu thập tự động từ các nguồn học liệu trực tuyến mở (Blogger Atom JSON, SGK điện tử) kết hợp động cơ sinh câu hỏi tham số hóa 12 khối lớp và đa bộ môn.


---

## 2. Tiện ích Mở rộng (Chrome / Edge Extension v1.3.15)

### 2.1. Kiến trúc Extension & Thu thập Bài học Hàng loạt (Bulk Harvester)
- **Manifest**: Manifest V3, quyền `activeTab`, `storage`, `scripting`, truy cập host `*.vio.edu.vn`, `*.tnmath.edu.vn`, `*.trangnguyen.edu.vn`, `*.hanhtrangso.nxbgd.vn`, `*.vietjack.com`, `*.loigiaihay.com`, `*.vndoc.com`, `*.hoc247.net`, `localhost:8000`.
- **Page Context Interceptor (`interceptor.js v1.3.15`)**:
   - Tiêm trực tiếp vào môi trường DOM gốc (page context) để ghi đè `window.fetch`, `XMLHttpRequest.prototype.open`, `XMLHttpRequest.prototype.send`, `WebSocket.prototype.send`.
   - **Hỗ trợ Angular HttpClient (`responseType = 'json'`) & GraphQL**: Bắt trực tiếp cả REST API và GraphQL queries (`PracticeQuestionQuery`, `GetQuestionResultQuery`), phân tích chuyên sâu các đối tượng câu hỏi VioEdu (`skillName`, `depthOfKnowledge`, `textDropdownAnswers`, `leftMatching`, `rightMatching`), bao quát cả các luồng đánh giá năng lực `onboard-flow`.
   - **Hỗ trợ URL Rút gọn**: Hàm `getShortUrl()` trích xuất `hostname + pathname` rút gọn (tối đa 22 ký tự), gắn kèm vào mọi log phát đi.
   - **Loại bỏ cây dữ liệu phi câu hỏi (CMS Ignored Keys)**: Bỏ qua hoàn toàn các nhánh dữ liệu CMS tin tức, cấu hình, quảng cáo (`news`, `posts`, `articles`, `banners`, `notifications`, `categories`, `menus`, `configs`, `promotions`, `products`, `combos`, `courses`, `transactions`, `orders`).
   - **Bộ lọc Chống UUID và Token Định danh**: Tuyệt đối không lấy chuỗi UUID (pattern `/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i`), chuỗi mã băm Hex, hoặc token đơn lẻ làm nội dung câu hỏi.
   - **Loại bỏ Tiêu đề Tin tức/Sự kiện**: Tuyệt đối không sử dụng trường `title` hoặc `name` làm câu hỏi trừ khi đối tượng có mảng phương án `answers`/`options` hợp lệ và không chứa từ khóa quảng cáo/giải đấu.
- **Content Script (`content.js v1.3.15`)**:
   - Giao tiếp với `interceptor.js` qua `window.postMessage`.
   - **Loại bỏ Triệt để Tiền tố Thứ tự Câu hỏi ("Câu hỏi số xx", "Câu xx", "Bài xx")**:
     - Phẫu thuật loại bỏ thẻ `.panel-heading`, `.practice-question-title`, `.question-title`, `.cau-hoi-so`, `[class*='question-number']` khỏi cây DOM clone trước khi trích xuất stem.
     - Dùng regex `/^(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*(?:tập)?\s*\d+)[\s\.\:\-_]*/i` cắt sạch tiền tố số thứ tự khỏi `content_text` và `content_html` ở cả Extension và Backend (`clean_html_and_math`).
     - Hàm `cleanTitleElement` tự động nhận diện nếu tiêu đề chỉ là số thứ tự câu hỏi thì loại bỏ hoàn toàn, không ghép vào đề bài.
   - **Cơ chế Tự động Lưu Bù đắp Zero-Click (Auto-Sync Retry)**:
     - Loại bỏ hoàn toàn chốt chặn `document.querySelector` toàn trang đối với loading state, chỉ kiểm tra loading cục bộ trên chính thẻ card/el đang thực sự hiển thị (`offsetParent !== null`).
     - Bổ sung hàm `autoSyncPendingQuestions`: tự động rà soát `capturedQuestions` tìm các câu có `saved_to_db === false` để tự động đẩy lên backend ở mọi nhịp heartbeat (2.5s), sau click tương tác, hoặc khi máy chủ kết nối lại.
     - Widget hiển thị số câu `[X/Y đã lưu CSDL]`.
   - **Cô lập Tuyệt đối Giao diện Extension (Self-Capture & Feedback Loop Immunity)**:
     - `TreeWalker` trong `scanByTextHeuristic` bắt buộc sử dụng `NodeFilter.FILTER_REJECT` loại bỏ triệt để toàn bộ cây DOM con của Extension (`#eduquest-floating-widget`, `#eduquest-scanned-modal`, `.eduquest-widget`, `.eduquest-modal-overlay`, `.eduquest-toast`, `.eduquest-panel`, `[class*='eduquest']`, `[id*='eduquest']`).
     - Bộ lắng nghe `click` toàn cục lập tức bỏ qua mọi tương tác bên trong giao diện tiện ích (click xem câu hỏi, đóng modal, click log).
     - `findEnclosingQuestionCard` và `extractQuestionFromElement` trả về `null` ngay lập tức nếu phần tử nằm trong hoặc là container của Extension UI.
     - `scanPageQuestions` chủ động lọc bỏ mọi container card thuộc về giao diện Extension trước khi bóc tách.
   - **Lọc Thẻ Cha Ngoài Cùng & Triệt Tiêu Nhân Đôi Lồng Thẻ (`Nested Card Filtering`)**:
     - `scanPageQuestions` lọc bỏ các container con nếu container tổ tiên của nó đã có trong danh sách (`containers.filter(el => !containers.some(p => p !== el && p.contains(el)))`).
     - Triệt tiêu hoàn toàn trường hợp cùng 1 câu hỏi nhưng vừa bóc thẻ cha (`.panel.panel-primary` có tiêu đề "Câu hỏi số 5") vừa bóc thẻ con (`#MathjaxArea2`).
   - **Chuẩn Hóa Tiền Tố Đề Bài khi Tạo Chữ Ký (`normalizeStemForSignature`)**:
     - Hàm `normalizeStemForSignature(text)` tách bỏ tiền tố `^(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*\d+)[\s\.\:\-_]*` trước khi tính toán signature và đối sánh chống trùng `isAlreadyCaptured`.
     - Giúp hệ thống nhận diện câu hỏi trùng nhau 100% dù có hay không có tiền tố đánh số câu.
   - **Kiểm Soát Tính Chính Xác của Đáp Án Đúng (`is_correct Verification`)**:
     - Trong câu hỏi trắc nghiệm đơn (`single_choice`), nếu tất cả đáp án hoặc nhiều hơn 1 đáp án bị đánh dấu `is_correct: true` (do kích hoạt nhầm class bố cục giao diện `active`, `selected`), tự động kiểm tra xem có duy nhất 1 input radio được `checked` hoặc `aria-pressed="true" / aria-checked="true"` hay không.
     - Nếu không có đáp án duy nhất được chọn rõ ràng, tự động đưa toàn bộ `is_correct` về `false`, không để sinh ra câu hỏi có 4 đáp án đúng cùng lúc.
   - **Chặn Triệt Để Trạng Thái Tải Dữ Liệu (`Loading State Immunity`)**:
     - `extractQuestionFromElement` chỉ kiểm tra loading cục bộ trên thẻ card/el đang hiển thị (`offsetParent !== null`). Tuyệt đối không dùng selector toàn trang làm chặn các câu hỏi sau.
   - **Chặn Thanh Tiến Độ & Phần Trăm (`Progress Bar Blacklist`)**:
     - Bỏ qua triệt để các thẻ thanh tiến độ (`.irXzU`, `._1WeAM`, `.Vt514`, `.progress-bar`, `.stepper-bar`). Không dùng `closest("[class*='progress']")` gây chặn nhầm layout cha.
     - Đối với câu dạng `fill_blank` không có phương án lựa chọn, bắt buộc phải có câu hỏi/từ để hỏi (`hỏi`, `tính`, `tìm`, `điền`, `bao nhiêu`, `mấy`) hoặc công thức toán học; các văn bản trạng thái ngắn không đủ tiêu chuẩn sẽ bị loại bỏ.
   - **Triệt Tiêu Spam Log (`Silent Background Heartbeat & Skip Deduplication`)**:
     - Heartbeat định kỳ 2.5s (`setInterval`) và bộ quan sát đột biến (`MutationObserver`) chạy với cờ `isBackground = true`.
     - Khi `isBackground === true`, Extension im lặng tuyệt đối, KHÔNG ghi bất kỳ dòng log skip nào vào giao diện.
     - Áp dụng cơ chế khử trùng log liên tiếp (`lastLoggedSkipSig`) để không bao giờ ghi 2 log trùng câu hỏi cho cùng 1 câu khi học sinh click tương tác.
   - **Làm Sạch Thanh Công Cụ & Ghi Chú khỏi Đề Bài (`extractCardStem`)**:
     - Phẫu thuật bóc tách và loại bỏ sạch sẽ các khối điều khiển kích thước chữ (`[data-skill-test-font-size]`, `.pull-right`, `._3-L-1`, `.cicn`, `.font-zoom`), thanh công cụ câu hỏi, và huy hiệu ghi chú (`.box-choice-note` - "100% Đang cân nhắc") khỏi cả phần thân đề bài và tiêu đề câu hỏi (`titleEl`).
     - Tuyệt đối không để chuỗi điều khiển giao diện VioEdu dính liền vào đề bài (`Câu hỏi số 5100%Đang cân nhắc...`).
   - **Vùng Chọn Card Câu hỏi Chuyên biệt (Question Card Selectors)**: Hỗ trợ cấu trúc React BEM của VioEdu (`.box.box--practice`, `.box--practice`, `.box--practice__content`, `.practice-question-text`, `.panel.panel-primary.practice-question-text`), VioEdu Onboard Flow (`[class*='onboard-flow']`, `[class*='onboard-question']`, `[class*='assessment-question']`, `[class*='question-layout']`) song song cùng Angular và LMS components (`app-question-render`, `.interactive-activity`, `.cau-hoi`). **Tuyệt đối KHÔNG đưa lưới lựa chọn đáp án (`.choice-answer-grid-2026`) vào danh sách card**.
   - **Cơ chế Xác định Thẻ Cha Câu hỏi (`findEnclosingQuestionCard`)**: Tự động nhận diện container cha bao trùm cả đề bài và đáp án; nếu bắt đầu từ một nút option hoặc answer grid thì leo lên các cấp cha để tìm container chứa bài đọc hiểu và câu hỏi thực sự.
   - **Phẫu thuật Bóc tách Đề bài & Bài đọc hiểu (`extractCardStem`)**: Tạo bản sao (clone) của card, bóc tách và loại bỏ sạch sẽ toàn bộ các khối lựa chọn đáp án (`.choice-answer-grid-2026`, `_2UU-q`, radio, button, action nav, timer), bảo lưu ngắt dòng giữa các đoạn văn (`\n\n`) để giữ nguyên vẹn 100% tất cả các đoạn văn đọc hiểu Tiếng Việt kèm câu hỏi dẫn bên dưới.
   - **Chốt chặn Chống Bẫy Đáp án (`Anti-Option-Collision`)**: So sánh chuỗi stem với chuỗi ghép các options; loại bỏ ngay lập tức nếu đề bài bị trùng hoặc chứa toàn bộ các lựa chọn mà không có câu hỏi thực sự.
   - **Bộ Kiểm tra Câu hỏi Nghiêm ngặt (`isRealQuestionText`)**:
     - Blacklist toàn bộ định dạng nhật ký log của Extension: regex `^\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\s*\[`, `\[(?:dom|mạng|lưu csdl|tương tác|thông báo|bỏ qua|dom bỏ qua|dom bắt được|mạng bắt được|mạng gói tin|info|ok|skip|net|error|warn)\]`, `thẻ #\d+ trùng câu hỏi`, `trùng câu hỏi đã có`, `eduquest`.
     - Blacklist tiêu đề và nút giao diện tiện ích: `danh sách câu hỏi đã quét`, `xem các câu hỏi đã quét`, `cào tất cả câu hỏi`, `quét nhanh màn hình`, `tự động lưu (zero-click)`, `nhật ký hoạt động`.
     - Blacklist hộp thoại tiếp tục/xác nhận bài làm LMS/VioEdu: `bạn đang làm bài kiểm tra`, `tiếp tục từ phần đã làm trước đó`, `tiếp tục làm bài`, `làm lại từ đầu`, `chưa hoàn thành.*tiếp tục`, `ICRobotConfirm`.
     - **Chặn Rác Khối Tiến độ Sao & Gợi ý Tính điểm VioEdu**: Loại bỏ triệt để các phần tử header bài tập `._1Tl2B`, `._1pVpr`, `._1MIz2`, `._1ZsoA`, `.score-hint-popup`, và ảnh huy hiệu kỹ năng (`star_practice_skillname.png`), cùng chuỗi hướng dẫn "Cách tính điểm khi trả lời ĐÚNG hoặc SAI...".
     - **Chặn Rác Video/Menu Trang Chủ VnDoc (`TreeWalker` & Path Whitelist)**:
       - `TreeWalker` trong `scanByTextHeuristic` bỏ qua toàn bộ các thẻ liên kết `<a>`, thẻ `<nav>`, `<header>`, `<footer>`, `.menu`, `.video-item`, `.home-video-item`.
       - Bắt buộc kiểm tra dấu hiệu câu hỏi thực sự (`?`, `hỏi`, `tính`, `tìm`, `điền`, `chọn`, công thức số) trước khi phân tích DOM.
       - Giới hạn cào tự động trên `vndoc.com` (`isEduLearningActive`): Chỉ chạy trên các đường dẫn bài tập thực tế (`/trac-nghiem-`, `/de-thi-`, `/bai-tap-`, `/de-kiem-tra-`, `/phieu-bai-tap-`), không quét trang chủ.
     - `hasCardRichContent` loại trừ icon, robot avatar, svg, loading gif, huy hiệu sao; không tự động chấp thuận vô điều kiện các dialog hệ thống.
     - **Hỗ trợ toàn diện câu hỏi đọc hiểu & ngữ pháp Tiếng Việt**: Nhận diện văn bản tường thuật nhiều đoạn kết hợp từ để hỏi hoặc câu hỏi chốt ở cuối (ví dụ: đoạn văn "Lan và Minh", câu hỏi "cho thấy điều gì?").
     - Tự động nhận diện môn Tiếng Việt (`detectSubject`) đối với bài đọc văn bản thuần túy có dấu thanh Tiếng Việt và không chứa ký hiệu toán học; tuyệt đối không để nhầm sang `english` do menu giao diện.
     - Từ chối triệt để UUID, Hex hash, chuỗi không có khoảng trắng, số ID thuần túy.
     - Blacklist toàn diện tin tức, sự kiện, hướng dẫn dự thi, thông báo mở bài thi, bài thi thử khám phá, combo đồng hành.
   - **Cơ chế Bắt Tự động Đa tầng (Multi-Stage Auto-Capture)**:
     - Khi học sinh bấm chọn đáp án hoặc thao tác 'Thực hiện', 'Câu hỏi sau', tiện ích ngay lập tức trích xuất câu hỏi từ khối chứa cha thực sự (`findEnclosingQuestionCard`) sau 150ms và kích hoạt các lượt quét tiếp theo sau 400ms, 1200ms, 2400ms.
   - **Tính năng "🚀 Cào tất cả câu hỏi trên trang này" (`harvestAllLessonQuestions`)**: Tự động mở rộng các khối accordion ẩn và tuần tự duyệt qua các nút chuyển câu/bước làm bài (`.nav-question button`, `.step-item`, `.pagination-question button`, `.list-step > div`, `.list-step > span`) với thời gian chờ 900ms để cào trọn bộ bài tập.
   - Quét chủ động định kỳ 2.5 giây trên mọi trang học tập, luyện tập và sách điện tử (`isEduLearningActive()`).

### 2.2. Hệ thống Telemetry & Debug Log Liên Tầng với URL Rút Gọn (Source Badge)
- **Kiến trúc ghi Log liên tầng với Source Badge**:
  - `interceptor.js` và `content.js` tự động tính toán URL nguồn rút gọn (`getShortUrl()`, ví dụ: `vio.edu.vn/skill-practice…`, `tnmath.edu.vn/luyen-thi…`).
  - Mọi bản ghi log đều có trường `source` và hiển thị huy hiệu `[source]` màu xanh ngọc nổi bật cạnh thời gian.
  - Chuỗi sao chép log đơn lẻ và toàn bộ log xuất ra định dạng chuẩn: `[${time}] [${source}] [${type}] ${message}`.
  - Giao diện Popup có Tab **"🔍 Nhật ký Debug"** hiển thị Monospace terminal window, bộ lọc pills (Tất cả, Thành công, Bỏ qua, Mạng, Lỗi), ô tìm kiếm từ khóa real-time, nút sao chép toàn bộ, xóa log và click để sao chép từng dòng.
  - Floating Widget panel trên trang web cũng tích hợp bộ điều khiển log tương ứng.
- **Bảo mật & Hiệu năng**:
  - Tuyệt đối dùng hàm `escapeHtml()` khử chuỗi trước khi gán HTML vào DOM, triệt tiêu nguy cơ XSS.
  - Sự kiện quan trọng (`success`, `error`, `save`) tự động gửi debounce (800ms) lên máy chủ qua endpoint `POST /api/collect/logs/sync` và lưu vĩnh viễn vào SQLite `collector_logs`.

### 2.3. Thu Thập Bài Luyện Tập VioEdu & Chuẩn Hóa Công Thức MathJax
- **Chuẩn hóa Văn bản Toán học (`extractCleanMathText`)**:
  - Tự động trích xuất công thức toán từ MathJax DOM (`span.math-tex`, `span.mjx-math[aria-label]`, `annotation[encoding='application/x-tex']`), chuyển đổi mượt mà các biểu thức toán phức tạp về văn bản toán thuần túy hoặc LaTeX.
  - Tự động chuyển đổi các ô chọn dropdown (`Select-placeholder`) thành dạng `[ ... ]` hoặc đáp án đã chọn.
- **Bóc tách Phương án & Lời giải VioEdu**:
  - Bắt trọn các ô phương án trắc nghiệm dạng `div[role="button"]._2UU-q` bên trong lưới `.choice-answer-grid-2026`, phương án kéo thả (`draggable="true"`), nối ghép (`matching`), và danh sách lựa chọn dropdown.
  - Nhận diện phương án đúng/đang chọn qua `input[type="radio"]:checked` hoặc các class `active`, `selected`, `correct`.
  - Trích xuất tự động Lời giải / Giải thích (`div.ZpmD_`, `div._3yoLK`) khi học sinh bấm nộp/kiểm tra đáp án.

### 2.4. Đồng bộ Bộ nhớ Đệm Chống Trùng & Cơ chế Xóa Câu Hỏi (Cache & Anti-Duplicate Purge Sync)
- **Kiểm soát Trùng lặp Thông minh & Dọn rác Chữ ký Mồ côi (`isAlreadyCaptured`)**:
  - Hai biến Set `savedQuestionIds` và `savedTextSignatures` trong `content.js` chỉ đóng vai trò bộ đệm hỗ trợ. Nguồn sự thật duy nhất là mảng `capturedQuestions`.
  - Hàm `isAlreadyCaptured(sig, qId)` tự động kiểm tra: Nếu `capturedQuestions` rỗng (`[]`), ngay lập tức xóa sạch toàn bộ `savedQuestionIds` và `savedTextSignatures` và trả về `false`.
  - Nếu chữ ký tồn tại trong Set nhưng không tìm thấy câu hỏi tương ứng trong `capturedQuestions` (do người dùng đã xóa câu hỏi đó), hàm tự động đào thải chữ ký mồ côi khỏi Set và trả về `false`, cho phép câu hỏi trên màn hình được quét lại ngay lập tức.
- **Xóa Danh Sách Toàn Diện (Clear All Purge & Auto Rescan)**:
  - Khi người dùng bấm "🗑️ Xóa danh sách" trong Modal hoặc "🗑️ Xóa" trong Popup:
    - Xóa sạch mảng `capturedQuestions = []`.
    - Xóa sạch cả hai Set `savedQuestionIds.clear()` và `savedTextSignatures.clear()`.
    - Lưu trạng thái rỗng vào `chrome.storage.local` và `localStorage`.
    - Tự động kích hoạt quét lại câu hỏi trên màn hình hiện tại sau 300ms (`scanPageQuestions(true)`), không để người dùng bị kẹt ở trạng thái không quét được.
- **Đồng bộ Đa tầng qua `chrome.storage.onChanged` và Message Passing**:
  - `content.js` lắng nghe sự kiện `chrome.storage.onChanged`: Khi Popup xóa hoặc thay đổi câu hỏi, tab trình duyệt tự động cập nhật lại danh sách và tái cấu trúc Set chữ ký (`rebuildSignatures()`).
  - Popup gửi tin nhắn `{ action: "clear_and_rescan" }` và `{ action: "force_scan" }` cho content script đang hoạt động để phản hồi tức thì.
- **Quản lý & Xóa Từng Câu Hỏi Riêng Biệt (Single-Item Deletion)**:
  - Bổ sung nút 🗑️ xóa từng câu hỏi trong Modal (`window.eduquestDeleteSingleQuestion(qid)`) và nút ✕ trong Popup (`btn-del-single-popup`), cho phép người dùng chủ động loại bỏ từng câu hỏi khỏi danh sách tạm mà không làm ảnh hưởng các câu hỏi khác.
- **Tính năng 'Xem các câu hỏi đã quét được' (Scanned Questions Viewer)**:
  - Cung cấp nút bấm `👁️ Xem các câu hỏi đã quét được (X câu)` tại Floating Widget và Extension Popup.
  - Mở cửa sổ Modal/Drawer hiển thị chi tiết từng câu hỏi đã quét: số câu, nền tảng, môn, khối lớp, trạng thái `✓ Đã lưu CSDL` hoặc `⏳ Chờ lưu`, nội dung bài toán, hình ảnh, đáp án trắc nghiệm.
  - Hỗ trợ các thao tác quản lý: Lưu tất cả vào CSDL, Sao chép JSON, Lưu từng câu riêng lẻ, Xóa danh sách.

---

## 3. Đồng bộ Dữ liệu & Thời gian thực (Real-time Sync)

1. **Cập nhật tức thì không cần F5 (Zero-Reload Live Sync)**:
   - Frontend kích hoạt `startRealtimeSync()` ngay khi tải trang.
   - Cơ chế 1: `BroadcastChannel("eduquest_live_sync")` đồng bộ tức thì giữa tất cả các tab đang mở khi có hành động thêm/sửa câu hỏi.
   - Cơ chế 2: Nhịp tim Heartbeat Polling 3 giây gọi `GET /api/stats`. Khi phát hiện số lượng câu hỏi trong CSDL tăng lên (do Extension hoặc Background Scraper đẩy vào), hệ thống tự động:
     - Bật thông báo Toast hiển thị số câu hỏi mới phát hiện.
     - Cập nhật số liệu Bảng Tổng quan (`loadDashboardStats()`).
     - Tự động làm mới danh sách Ngân hàng câu hỏi (`loadQuestions()`) nếu người dùng đang ở tab Ngân hàng.

---

## 4. Trung tâm Thu thập & Quản lý Danh sách Web Cào

### 4.1. Quản lý Danh sách Web Cào Tự động (Hunter Target URLs)
- Ô nhập URL / từ khóa được bố trí trên hàng riêng biệt với chiều dài tối đa (`flex: 1`), không bị khuất khi dán URL dài.
- Nút bấm **"➕ Thêm"** nhỏ gọn, hỗ trợ phím Enter.
- Hàng nút gợi ý nguồn nhanh (Quick Presets) cho phép thêm 1-click các link Hành Trang Số SGK/SBT Lớp 2, VioEdu Luyện tập, Trạng Nguyên Toán & Tiếng Việt.
- Danh sách các trang web được lưu tự động vào `localStorage` (`eduquest_hunter_urls`).
- Giao diện trực quan:
  - Cho phép bật/tắt (active/inactive) từng link bằng checkbox mà không cần xóa link.
  - Hiển thị thời gian thêm và đường dẫn chi tiết.
  - Nút xóa từng link `✕` và nút "Xóa tất cả nguồn".
  - Huy hiệu hiển thị tổng số nguồn web đang có trong danh sách.
- Khi bấm "Săn câu hỏi từ Internet" hoặc chạy vòng lặp 5 phút: hệ thống tự động duyệt qua tất cả các trang web active trong danh sách để bóc tách câu hỏi.

### 4.2. Tự động Lưu & Chuẩn Hóa Nhật ký Trực tiếp (Live Log Persistence & Formatting)
- **Nhật ký Thợ săn Internet (`#hunter-live-log`)**:
  - **Sắp xếp Mới nhất trên cùng (Newest on Top)**: Phiên săn mới nhất và kết quả hoàn thành luôn hiển thị ngay tại đầu khung nhật ký, người dùng không cần phải cuộn chuột xuống đáy.
  - **Tách riêng từng dòng cho mỗi log**: Mọi dòng thông điệp (Khởi tạo phiên, Danh sách mục tiêu web, Trạng thái đang quét, Kết quả bóc tách/lưu CSDL) được tách biệt tuyệt đối trên từng dòng riêng (`\n`), các phiên được phân cách bằng dòng trống (`\n\n`), loại bỏ 100% tình trạng dính dòng ngang do cơ chế DOM innerText gây ra.
  - **Thanh công cụ Thợ săn (`#hunter-log-toolbar`)**: Bổ sung 2 nút bấm thao tác trực quan:
    - `📋 Sao chép Log`: Copy toàn bộ nội dung nhật ký đã định dạng chuẩn vào Clipboard (sử dụng `navigator.clipboard` kèm cơ chế fallback).
    - `🗑️ Xóa Log`: Xóa sạch nội dung trên màn hình và xóa khóa lưu trữ `eduquest_hunter_log` trong `localStorage`.
  - **Cơ chế Phục hồi & Tự Động Định dạng Log Cũ (Auto-Healing & Sorting Migration)**: Khi tải trang, hàm `formatAndSortHunterLog` tự động quét các log cũ trong `localStorage`, giải phóng các dòng bị dính chuỗi, chuẩn hóa lại cấu trúc và đảo ngược thứ tự về "Mới nhất trên đầu" nếu phát hiện log cũ đang lưu theo thứ tự tăng dần.
- **Nhật ký Bot Đăng nhập Cào Vòng thi (`#scraper-live-log`)**:
  - Có thanh công cụ `#scraper-log-toolbar` với nút `📋 Sao chép Log` và `🗑️ Xóa Log`.
  - Hiển thị theo nguyên tắc mới nhất trên cùng.
- **Tính Bền Vững (Persistence)**: Cả hai khung nhật ký được tự động lưu vào `localStorage`. Khi người dùng F5 hoặc chuyển đổi giữa các module giao diện, nội dung log vẫn được bảo toàn nguyên vẹn.

### 4.3. Cấu hình Khối lớp & Tài khoản
- Cho phép người dùng thiết lập **Khối lớp mặc định** toàn hệ thống.
- Tự động lưu lựa chọn Khối lớp vào `localStorage` (`eduquest_default_grade`, `eduquest_selected_grade`) và tự động đồng bộ sang tất cả các bộ lọc.
- Tự động ghi nhớ thông tin đăng nhập cào vòng thi (`eduquest_scraper_plat`, `eduquest_scraper_user`, `eduquest_scraper_round`).

### 4.4. Thợ săn Câu hỏi Internet Tự động (Auto-Hunter Loop)
- Tích hợp vòng lặp tự động chạy mỗi 5 phút (300 giây).
- Hiển thị huy hiệu đếm ngược thời gian thực trên giao diện.
### 4.5. Bot Đăng Nhập Ngầm Cào Vòng Thi & Bài Thực Hành VioEdu (Headless Engine & Safe Practice Crawler)
- **Cơ chế Đăng nhập Ngầm (Playwright Headless Engine)**:
  - Khởi chạy Chromium không đầu (headless) với cờ bảo mật desktop, mô phỏng người dùng thật.
  - Kiểm tra xác thực 2 tầng: kiểm tra nhanh API và phiên trình duyệt đầy đủ. Trả về thông báo lỗi rõ ràng nếu sai mật khẩu hoặc tài khoản không tồn tại.
- **Nhận diện Khối Lớp Cố Định Của Tài Khoản (Fixed Account Grade)**:
  - Tài khoản học sinh VioEdu có thuộc tính khối lớp cố định (`user.grade` / `user.class`).
  - Bot tự động nhận diện và khóa theo đúng khối lớp của tài khoản, tự động gán khối lớp này cho toàn bộ câu hỏi và đề thi cào được, không bị nhầm lẫn giữa các khối lớp.
- **Tự Động Xử Lý Vượt Quá 3 Thiết Bị (OVER_QUOTA & 289 Auto-Recovery)**:
  - Khi tài khoản đăng nhập trên quá 3 thiết bị đồng thời, máy chủ VioEdu trả về phản hồi `OVER_QUOTA` (mã trạng thái nội bộ 289).
  - Bot tự động phát hiện và kích hoạt mutation GraphQL chuẩn của VioEdu `resetLogin3Devices(username: $username)` để giải phóng phiên làm việc của các thiết bị cũ.
  - Tự động đăng nhập lại sau khi giải phóng phiên thành công, bảo đảm phiên làm việc liên tục mà không cần can thiệp thủ công.
  - Trình duyệt Playwright tự động nhận diện và click nút `"Đăng xuất toàn bộ thiết bị"` trên giao diện web nếu xuất hiện cảnh báo.
- **Thanh Công Cụ Nhật Ký Trực Tiếp & Sắp Xếp Mới Nhất Trên Đầu (Newest on Top & Log Toolbar)**:
  - Khung nhật ký trực tiếp của Bot (`#scraper-live-log`) hiển thị theo thứ tự **Mới nhất trên đầu** (Newest on top): dòng mới nhất luôn ở vị trí dòng 1, kết quả thành công/thất bại luôn được ghim trên cùng.
  - Tích hợp thanh công cụ phía trên với hai nút: `📋 Sao chép Log` (sao chép trực tiếp vào Clipboard kèm fallback textarea) và `🗑️ Xóa Log`.
- **Cơ Chế Cào Bài Thực Hành VioEdu An Toàn Tuyệt Đối (Zero-Risk Read-Only GraphQL Crawler)**:
  - Truy vấn dữ liệu đề bài và đáp án thụ động qua GraphQL `PracticeQuestionQuery` (`getPracticeQuestionBySkillId`).
  - **Quy chuẩn bảo vệ tài khoản & bảo tồn tiến trình học tập**:
    - Luôn gửi `score: 0`, `isManual: false`, `userHomeworkId: ""`.
    - Tuyệt đối **không click nút Trả lời / Nộp bài**, tuyệt đối **không gửi `PracticeResultMutation`**.
    - Bảo toàn 100% điểm số, chuỗi ngày học tập và quota bài luyện tập của học sinh, tránh bị phát hiện khóa tài khoản.
- **Hỗ Trợ Mọi Dạng Câu Hỏi Thực Hành VioEdu**:
  - Dạng Điền ô trống (`questionType: 3` / `{}`): tự động bóc tách đáp án điền từ `answers` vào `correct_answer`, làm trống `options`.
  - Dạng Trắc nghiệm 1 đáp án (`questionType: 1`) & Nhiều đáp án (`questionType: 2`): trích xuất đáp án đúng chính xác từ trường `correct: true`.
  - Dạng Nối cặp (`leftMatching` & `rightMatching`) và Dropdown (`textDropdownAnswers`).
  - Trích xuất lời giải chi tiết `explanation` và ảnh đề bài.
- **Nhận Diện Mục Tiêu Thông Minh (`parse_vioedu_target`)**:
  - URL `https://vio.edu.vn/skill-practice/:id` hoặc ID 24 hex: cào bài thực hành cụ thể.
  - URL `https://vio.edu.vn/skill-list`: tự động truy vấn danh mục bài luyện tập (`getListTopicSkill` + `getSkillListQuery`) và cào câu hỏi theo khối lớp cố định của học sinh.
  - Mã vòng đấu trường số (`1`, `2`,...): truy cập các tuyến đấu trường `/arena`, `/arena-zone`, `/arena-school`.
  - Để trống (`auto`): tự động tìm đấu trường đang mở; nếu ngoài khung giờ thi đấu, Bot tự động chuyển sang thu thập các bài thực hành trọng tâm của khối lớp tương ứng.
- **Làm Sạch & Lưu Trữ CSDL**:
  - Tự động loại bỏ cụm từ "Câu hỏi số X", "Câu X:", "Bài X:" khỏi đề bài.
  - Bảo tồn toàn vẹn công thức Toán học LaTeX (`$...$`), danh sách đáp án A/B/C/D, lời giải và hình ảnh minh họa.
  - Kiểm tra trùng lặp mã băm (`content_hash`) và lưu trực tiếp vào CSDL SQLite `data/questions.db`.
  - Ghi nhận nhật ký thu thập thời gian thực vào bảng `collector_logs`.

### 4.6. Vòng Lặp Cào VioEdu Tự Động Định Kỳ 5 Phút & Nhật Ký Bắt Câu Hỏi (Auto-Crawl Loop & Capture Logs Modal)
- **Cơ chế Vòng Lặp Định Kỳ 5 Phút (Auto-Crawl VioEdu 5-Min Loop)**:
  - Công tắc chuyển đổi (Toggle Switch) `#bot-auto-crawl-toggle` tích hợp trực tiếp trên thẻ VioEdu Scraper.
  - Khi bật:
    + Huy hiệu trạng thái nhấp nháy xanh `#bot-auto-crawl-badge` chuyển sang trạng thái hoạt động ("ĐANG CHẠY").
    + Bộ đếm ngược thời gian thực `#bot-countdown-display` đếm lùi từng giây từ 05:00 (`300s`) về 00:00.
    + Khi đồng hồ chạm mốc 00:00, hệ thống tự động kích hoạt `runAutoScraper()`, gửi request cào vòng thi VioEdu qua `POST /api/collect/run`, ghi log vào `collector_logs`, cập nhật số câu hỏi mới vào Ngân hàng, phát thông báo BroadcastChannel và tự động reset chu kỳ 300s tiếp theo.
  - Trạng thái bật/tắt được đồng bộ bền vững vào `localStorage` (`eduquest_bot_autocrawl`), tự động khôi phục khi làm mới trang hoặc chuyển tab.
- **Cửa Sổ Xem Nhật Ký Bắt Câu Hỏi (Question Capture Logs Modal `#modal-capture-logs`)**:
  - Nút bấm `📜 Xem Nhật ký Bắt câu hỏi` tích hợp tại khung Collector logs.
  - Hiển thị danh sách các câu hỏi đã bóc tách từ VioEdu và VnDoc song song ở 2 chế độ:
    + Dạng Thẻ Trực Quan (Card View): Xem đề bài, đáp án A/B/C/D, môn, khối lớp và trạng thái lưu CSDL.
    + Dạng JSON Thô (Raw JSON): Hỗ trợ nút `📋 Sao chép JSON` vào clipboard.
  - Nút **`🚀 Nạp lại vào Ngân hàng (X câu)`** (`#btn-reinject-questions`): Gửi toàn bộ câu hỏi lên `POST /api/questions/bulk`, tự động lưu vào SQLite, cập nhật lại thống kê Dashboard và Ngân hàng câu hỏi chỉ với 1 click.

### 4.7. Bóc Tách Đề Thi Từ Ảnh (Image OCR Exam Ingestion)
- **Đa dạng Định dạng Tiếp nhận**:
  - Hỗ trợ tải lên cả tệp PDF và tệp ảnh đề thi (`.png, .jpg, .jpeg, .webp, .bmp`) qua dropzone kéo thả `#pdf-dropzone` và file input `#pdf-file-input`.
  - Phân loại và định tuyến tự động tại backend qua `POST /api/import/pdf`, `POST /api/import/image` và `POST /api/import/exam-file`.
- **Quy trình Tiền Xử Lý Ảnh (OpenCV CLAHE Pipeline)**:
  - Chuyển đổi không gian màu sang ảnh xám (`cv2.cvtColor`).
  - Cân bằng độ tương phản thích ứng cục bộ giới hạn tương phản CLAHE (`cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))`) làm rõ chữ in mờ.
  - Khử nhiễu biên và giữ nét văn bản với bộ lọc song phương (`cv2.bilateralFilter`).
  - Lưu tệp gốc và ảnh tiền xử lý vào thư mục tĩnh `data/media/ocr_{uuid}.ext` để giao diện hiển thị khung xem trước ảnh (Image preview).
- **Động Cơ Bóc Tách Ký Tự Quang Học Đa Tầng (Multi-Tier OCR Engine)**:
  - Tầng 1 (Ưu tiên): RapidOCR (PaddleOCR ONNX gọn nhẹ, siêu tốc, nhận diện tiếng Việt cực chuẩn).
  - Tầng 2: EasyOCR (PyTorch deep learning hỗ trợ song ngữ Tiếng Việt & Tiếng Anh).
  - Tầng 3 (Dự phòng): PyTesseract Engine.
  - Chuẩn hóa Unicode NFC (`unicodedata.normalize('NFC', text)`), sửa lỗi OCR kinh điển (`C@u`, `Cdu`, `Cáu` -> `Câu`, `B@i` -> `Bài`).
  - Regex Engine bóc tách cấu trúc câu hỏi trắc nghiệm (phương án A, B, C, D) và lời giải.
- **Bảng Đối Soát Câu Hỏi Trực Quan Trước Khi Lưu (Audit Review Table)**:
  - Hiển thị bảng đối soát `#ocr-review-table` cho phép giáo viên chỉnh sửa trực tiếp nội dung đề bài (kèm live KaTeX preview), các phương án đáp án, chọn radio đáp án đúng, phân loại môn/lớp trước khi bấm "Lưu vào Ngân hàng".

---

## 5. Chuẩn hóa Phân loại Bộ môn (AI Subject Classifier)

Quy tắc phân loại tự động ưu tiên theo thứ tự:
1. `math`: Khớp các từ khóa toán học hoặc công thức LaTeX (`\frac`, `\sqrt`, `^`, góc, chu vi, diện tích, phân số, chữ số, hình bình hành, tam giác, ...).
2. `science`: Khớp từ vựng khoa học tự nhiên, động vật, thực vật, môi trường, địa lý, lịch sử, cơ quan cơ thể, tự nhiên và xã hội.
3. `vietnamese`: Nhận diện dấu thanh Tiếng Việt đặc trưng kết hợp cấu trúc ngữ pháp học đường (mẫu câu *Ai là gì*, *Ai làm gì*, *Ai thế nào*, câu nêu đặc điểm/hoạt động, điền âm/vần `s/x`, dấu phẩy/chấm, đoạn văn đọc hiểu, tác giả, tác phẩm, thành ngữ, tục ngữ, từ ghép, từ đồng nghĩa).
4. `english`: Khớp từ khóa tiếng Anh thuần túy, kiểm tra ranh giới từ `\bioe\b`, tỷ lệ từ tiếng Anh không dấu. **Đặc biệt**: Nếu văn bản có dấu thanh Tiếng Việt, câu hỏi KHÔNG BAO GIỜ bị xếp vào `english` mà sẽ tự động reclassify về `vietnamese`.

---

## 6. Xuất Đề thi Chuẩn Microsoft Word (.docx) & Ma trận Tạo Đề Tự Động

### 6.1. Ma trận Tạo Đề Tự Động (Auto Exam Matrix Generator)
- Cho phép giáo viên tạo đề thi ngay lập tức dựa trên ma trận:
  - Môn học: Toán, Tiếng Việt, Tiếng Anh, Khoa học.
  - Khối lớp: Lớp 1 đến Lớp 12.
  - Tổng số câu hỏi: từ 1 đến 100 câu.
  - Cơ cấu độ khó: Số câu Dễ, Số câu Trung bình, Số câu Khó.
  - Chuyên đề / Topic (Tùy chọn).
- Hỗ trợ các mẫu ma trận chuẩn:
  - Đề chuẩn 20 câu: 8 Dễ (40%) + 8 TB (40%) + 4 Khó (20%).
  - Đề ôn tập 10 câu: 5 Dễ (50%) + 3 TB (30%) + 2 Khó (20%).
  - Đề Olympic 25 câu: 5 Dễ (20%) + 10 TB (40%) + 10 Khó (40%).
- Thuật toán lấy mẫu ngẫu nhiên (`ORDER BY RANDOM()`) theo từng mức độ khó khớp với ma trận, kèm cơ chế fallback thông minh khi thiếu câu hỏi trong một phân khúc.

### 6.2. Xuất File Word (.docx)
- Tự động tạo trang bìa và tiêu đề chuẩn Bộ Giáo dục & Đào tạo.
- Hỗ trợ trộn ngẫu nhiên câu hỏi và hoán vị thứ tự các đáp án A, B, C, D.
- Tự động đính kèm Trang Đáp án & Lời giải chi tiết ở cuối đề thi.
- Chuyển đổi công thức LaTeX sang định dạng văn bản toán học rõ ràng, dễ in ấn.

### 6.3. Xuất File PDF Chuẩn In Ấn MOET A4 & Chuẩn Hóa Ký Tự Toán/Khoa Học
- **Quy Chuẩn In Ấn A4 Theo Quy Định Bộ Giáo Dục & Đào Tạo**:
  - Khổ giấy A4 đứng chuẩn (`210mm x 297mm`).
  - Căn lề quy chuẩn: lề trên `20mm`, lề dưới `20mm`, lề trái `25mm` (dành khoảng gáy đóng tập), lề phải `15mm`.
  - Phông chữ chuẩn tiếng Việt học đường: Times New Roman 12pt, dãn dòng 1.25, tiêu đề đậm rõ nét.
  - Header tiêu chuẩn 2 cột: Cột trái (Tên Sở/Phòng GD&ĐT, Trường), Cột phải (Kỳ thi, Môn thi, Khối lớp, Thời gian làm bài, Khung thông tin học sinh: Họ tên, Số báo danh, Lớp).
  - Quy tắc ngắt trang thông minh: Sử dụng CSS `page-break-inside: avoid` trên từng khối câu hỏi, tuyệt đối không để xảy ra hiện tượng đề bài ở trang trước và phương án đáp án rơi sang trang sau.
- **Trang Bảng Đáp Án & Thang Điểm Độc Lập**:
  - Tự động tách riêng phần Bảng Đáp Án sang trang mới bằng thuộc tính `page-break-before: always;`.
  - Bảng tổng hợp đáp án dạng ma trận 10 cột trực quan (Câu 1 đến N, Đáp án A/B/C/D).
  - Kèm thang điểm chi tiết cho từng câu (thang điểm 10) và phần Hướng dẫn giải chi tiết cho các câu hỏi có trường `explanation`.
- **Chuẩn Hóa Ký Tự Đặc Biệt Toán Học & Khoa Học (`normalize_moet_math_symbols`)**:
  - Phân số: Biến đổi LaTeX `\frac{a}{b}` sang dạng hiển thị inline đẹp mắt `a/b` hoặc ký hiệu phân số chuẩn.
  - Căn thức: `\sqrt{x}` -> `√x`.
  - Toán tử: Nhân `\times` -> `×`, Chia `\div` -> `÷`, Góc `\angle` -> `∠`, Song song `\parallel` -> `∥`, Vuông góc `\perp` -> `⊥`.
  - Ký tự Hy Lạp: `\pi` -> `π`, `\alpha` -> `α`, `\beta` -> `β`, `\Delta` -> `Δ`.
  - Số mũ & Chỉ số: `^2` -> `²`, `^3` -> `³`, `_1` -> `₁`, `_2` -> `₂`.
  - Ký hiệu Khoa học & Hóa học: $H_2O$ -> $H₂O$, $CO_2$ -> $CO₂$, $O_2$ -> $O₂$, mét vuông $m^2$ -> $m²$, mét khối $m^3$ -> $m³$.
- **Cơ Chế Kết Xuất Hai Tầng (Dual-Mode Rendering Pipeline)**:
  - Tầng Server (Ưu tiên): Playwright Chromium Headless kết xuất vector PDF hoàn hảo với độ phân giải cao (`print_background=True`).
  - Tầng Client (Dự phòng): `@media print` stylesheet kích hoạt lệnh `window.print()` khi mất kết nối mạng, đảm bảo không bao giờ làm gián đoạn công việc của giáo viên.

---

## 7. Ngăn Chặn Trùng Lặp CSDL & Bác sĩ CSDL (Database Deduplication & Diagnostics)

### 7.1. Cơ chế Chống Trùng Lặp Tự động (Ingestion Deduplication)
- Mọi thao tác nạp câu hỏi vào SQLite (`insert_or_update_question`, `bulk_insert_questions`) đều bắt buộc đối chiếu nội dung chuẩn hóa (`LOWER(TRIM(content_text))`) với toàn bộ CSDL.
- Nếu nội dung câu hỏi đã tồn tại trong CSDL, hệ thống tự động bỏ qua (không chèn dòng mới) để ngăn chặn tuyệt đối việc phình to dữ liệu trùng lặp.
- Người dùng có thể bật `allow_duplicate=True` chỉ trong trường hợp đặc biệt.

### 7.2. Quản lý & Lọc Trùng Lặp (Duplicates Manager)
- Bộ lọc `[x] Chỉ câu hỏi trùng lặp` trên thanh công cụ lọc của Ngân hàng.
- Endpoint `GET /api/questions/duplicates`: nhóm các câu hỏi trùng qua `GROUP BY LOWER(TRIM(content_text)) HAVING cnt > 1`.
- Endpoint `POST /api/questions/duplicates/clean`: 1-click xóa sạch các bản sao thừa, giữ lại bản ghi gốc cũ nhất (`keep_oldest`).

### 7.3. Bác sĩ Cơ sở Dữ liệu (Database Diagnostics Doctor)
- Endpoint `GET /api/database/diagnostics`: kiểm tra `PRAGMA integrity_check`, tổng câu hỏi, câu hỏi độc nhất, số bản sao trùng lặp, câu thiếu đáp án/lời giải, thống kê bảng.
- Endpoint `POST /api/database/diagnostics/fix`: tự động chạy quy trình phục hồi toàn diện: xóa bản sao trùng, gán lại bộ môn chưa phân loại bằng AI Classifier, tối ưu hóa lưu trữ với `VACUUM` & `ANALYZE`.

---

## 8. Chuẩn hóa Ngân hàng Câu hỏi & Đánh số Thứ tự Vĩnh viễn (Persistent Question ID)

- **Đánh số thứ tự vĩnh viễn (Persistent Question ID / `q_number` 1..N)**:
  - Đánh số nguyên vĩnh viễn liên tục từ 1 đến N cho toàn bộ câu hỏi trong CSDL (`q_number`), coi đây là ID chính thống của câu hỏi.
  - Không phụ thuộc vào phân trang. Mỗi câu hỏi luôn giữ nguyên ID số cố định (vd: `Câu 1`, `ID: #1`, `ID: #5`,...), kể cả khi người dùng lọc theo Bộ môn, Khối lớp, Độ khó hay chuyển giữa các trang.
- **Cơ chế tái lập đánh số liên tục không đứt đoạn (Gapless Resequencing)**:
  - Bất kỳ thao tác xóa câu hỏi hoặc dọn dẹp câu trùng đều tự động chạy `resequence_question_numbers()` bằng SQLite Window Function `ROW_NUMBER() OVER (ORDER BY created_at ASC, id ASC)` để bảo đảm dãy số luôn liên tục 1..N không bị khuyết số.
  - Khi thêm câu hỏi mới, hệ thống tự động gán `q_number = MAX(q_number) + 1`.
- **Tìm kiếm trực tiếp theo số thứ tự / ID câu hỏi**:
  - Ô tìm kiếm hỗ trợ nhập trực tiếp số thứ tự (vd: `5`, `#5`, `Câu 5`) để tìm nhanh chính xác câu hỏi theo ID số thực tế.
- **Nút "✕" Xóa Nhanh Tìm kiếm (Quick Clear Search)**:
  - Tích hợp nút bấm tròn "✕" bên trong ô input tìm kiếm, tự động hiện khi có ký tự nhập và ẩn khi ô trống.
  - Khi click: làm sạch ô tìm kiếm, tự động focus lại ô input và reset bộ lọc tìm kiếm để tải lại danh sách đầy đủ.
- **Bộ sắp xếp theo thứ tự câu (Sort by Question Number)**:
  - Thanh công cụ hỗ trợ sắp xếp theo `Thứ tự Câu (1 → N)` (`q_number_asc`), `Thứ tự Câu (N → 1)` (`q_number_desc`), `Mới nhất trước`, `Cũ nhất trước`.
- **Nguồn săn chi tiết & Quy chuẩn chống trùng thẻ (Intelligent Source Resolver)**:
  - Phân tách rõ ràng giữa Thẻ Nền tảng (Tag 3: `INTERNET HUNTER`, `VIOEDU`, `TRẠNG NGUYÊN`...) và Thẻ Nguồn gốc chi tiết (Tag 4: `🌐 Trạng Nguyên Tiếng Việt`, `🌐 CodeMath • TIMO`, `🌐 Kho Đề Mở (Online)`, `🌐 SGK Cánh Diều`...).
  - **Quy tắc Chống Trùng Lặp Thẻ**: Thẻ nguồn chi tiết (🌐) tuyệt đối không bao giờ hiển thị nếu có giá trị trùng lặp với nền tảng thu thập (loại bỏ hoàn toàn trường hợp `[INTERNET_HUNTER] [🌐 INTERNET_HUNTER]`).
  - Hàm `compute_source_detail(q)` tại `backend/database.py` tự động phân giải tên cuộc thi/nguồn học liệu chính xác từ `exam_name`, `source_url`, `topic` và `subject`.
- **Bộ lọc nguồn chi tiết**: Cho phép lọc theo CodeMath (Olympic), Hành Trang Số, VioEdu, Trạng Nguyên, Kho Đề Mở (Online), Olympic chung (IOE/TIMO), VietJack / VnDoc, Soạn thủ công.
- **Chỉnh sửa câu hỏi & đáp án (Editor Modal)**: Nút `✏️ Sửa` mở modal cho phép sửa nội dung câu hỏi (live KaTeX preview kèm badge ID câu hỏi), 4 đáp án A/B/C/D, đáp án đúng, bộ môn, khối lớp, độ khó và lời giải chi tiết.

---

## 9. Thẩm Định Nội Dung (Validation) & Trải Nghiệm Học Tập Trung Tính (Neutral UX)

### 9.1. Thẩm Định Nghiêm Ngặt Chống Rác & Khử Nhiễu Blog (Content Validation Standard)
- Mọi câu hỏi từ bất kỳ nguồn nào (Extension, Crawl web, PDF, Nhập thủ công) đều phải vượt qua hàm kiểm định `is_valid_question_payload(q)`:
  - Độ dài nội dung text: tối thiểu 8 ký tự, không quá 3000 ký tự. Với câu hỏi điền khuyết không có phương án trắc nghiệm, độ dài stem không được vượt quá 450 ký tự (trừ bài đọc hiểu).
  - **Khử số điện thoại & thông tin liên hệ**: Phát hiện và từ chối ngay lập tức mọi chuỗi chứa số điện thoại tư vấn/gia sư (`0\d{2,3}[\.\s\-]?\d{3}[\.\s\-]?\d{3,4}`) hoặc từ khóa: `liên hệ`, `hotline`, `sđt`, `điện thoại:`, `zalo`, `facebook cô hà`, `fanpage`, `học phí`, `đăng ký khóa học`, `tư vấn khóa học`, `lớp học thêm`, `tuyển sinh`.
  - **Khử bài viết mô tả, quảng cáo & lịch thi**: Từ chối bài viết tin tức, thông báo ôn thi, link tải: `ba mẹ`, `phụ huynh`, `tải đề thi`, `tải tài liệu`, `video chữa đề`, `lịch thi`, `giờ thi`, `địa điểm thi`, `hướng dẫn dự thi`, `chuẩn bị trước ngày thi`, `thí sinh asmo`, `tặng miễn phí`, `nhận miễn phí`, `fermat education`, `kỳ thi fmo`, `vòng quốc gia đã diễn ra`, `đối chiếu đáp án`, `tham khảo sau kỳ thi`, `tài liệu tham khảo`, `đề vòng loại`.
  - **Cơ chế không phân biệt dấu thanh (`remove_vietnamese_accents`)**: Nhận diện chính xác 100% cả chuỗi có dấu lẫn không dấu (như `ba me`, `tai de thi`, `lien he`, `de vong loai`).
  - **Chuẩn hóa cấu trúc câu hỏi**:
    - Dạng trắc nghiệm: Phải có tối thiểu 2 phương án phân biệt (`len(options) >= 2` và `len(opt_ids) >= 2`), cấm tuyệt đối việc lặp ký tự nhận diện (như `[B, B, B]` do từ ngữ `(BBB)`).
    - Ngữ nghĩa câu hỏi: Phải có công thức toán học (`$`, `\frac`, toán tử), hoặc tiền tố câu hỏi (`?`, `câu`, `bài`, `tính`, `tìm`, `điền`, `cho biết`), hoặc từ khóa câu hỏi tiếng Anh (`choose`, `which`, `what`).
  - **Khử rác HTML & Template**: Loại bỏ hoàn toàn Doctype (`<!doctype`, `<html`, `xmlns=`), script (`<script>`, `window.dataLayer`, `cf-beacon`), CSS layout (`.CSS_LAYOUT_COMPONENT`, `opacity: 0`, `position: static !important`), và template boilerplate (`tailwind`, `keenthemes`).
  - **Bóc tách văn bản không cấu trúc (`parse_unstructured_questions`)**: Loại bỏ phần tiêu đề/mở đầu bài viết (`blocks[0]`), tự động cắt bỏ phần chữ ký/liên hệ ở đuôi (`LIÊN HỆ...`, `Hotline...`), chỉ giữ lại các khối thực sự bắt đầu bằng ký hiệu câu hỏi hoặc có các phương án A, B, C, D rõ ràng.
- Chốt chặn thẩm định được kích hoạt 3 tầng: lúc crawler thu thập, lúc chuẩn hóa (`normalize_question_payload`), và lúc lưu CSDL (`insert_or_update_question`). Tích hợp sẵn sàng trong Bác sĩ CSDL để quét và xóa sạch rác.

### 9.2. Trải Nghiệm Hiển Thị Đáp Án Trung Tính (Neutral Options UX)
- Trong Ngân hàng Câu hỏi, tất cả các phương án trắc nghiệm A, B, C, D đều hiển thị màu viền xám trung tính mặc định, không bao giờ tự động lộ phương án đúng bằng viền xanh lá hay biểu tượng tick.
- Chỉ khi giáo viên hoặc học sinh bấm vào nút **"💡 Đáp án & Lời giải"**, phương án đúng mới được tô sáng màu xanh lá nổi bật đồng thời mở rộng khung giải thích chi tiết bên dưới. Bấm lại sẽ thu gọn và ẩn đáp án.

### 9.3. Minh Bạch Thống Kê & Phân Tách Bộ Lọc (Filter Clarity)
- Tránh nhầm lẫn giữa số câu hiển thị sau khi lọc và tổng số câu hỏi thực tế trong CSDL:
  - Khởi tạo mặc định xem toàn bộ ngân hàng (`grade: ""`), không tự ý áp đặt lọc lớp lúc tải trang đầu tiên.
  - Tuyệt đối cô lập cấu hình Khối lớp của Trung tâm Thu thập (`collector.js`): việc lưu khối lớp mặc định để cào dữ liệu chỉ áp dụng cho các công cụ thu thập, không bao giờ tự ý ghi đè vào bộ lọc của Ngân hàng câu hỏi (`filter-grade`).
  - Khi có bộ lọc kích hoạt: hiển thị rõ ràng `Hiển thị: X / tổng Y câu (Đang lọc: Lớp Z) [✕ Bỏ lọc]`.
  - Khi không có bộ lọc: hiển thị `Tổng câu hỏi: Y câu (Toàn bộ CSDL)`.
  - Bổ sung Platform Chips đầy đủ cho `🌐 Săn Internet` (`internet_hunter`), `📚 Hành Trang Số` (`hanhtrangso`), `🏆 Olympic` (`olympiad`), `🎯 VioEdu`, `🌟 Trạng Nguyên`.
  - Bổ sung Tab môn `💻 Tin học` trên thanh điều hướng bộ môn.

### 9.4. Hiển Thị Toàn Bộ Câu Hỏi & Bộ Chọn Kích Thước Trang (Page Size & View All)
- Tăng số câu hiển thị mặc định từ 15 lên 50 câu/trang (`page_size: 50`).
- Bộ chọn kích thước trang linh hoạt: hỗ trợ các mức `15`, `30`, `50`, `100`, và `Tất cả - Xem hết (Toàn bộ CSDL)`.
- Nút bấm nhanh `👁️ Xem tất cả` trên thanh công cụ và liên kết `Xem tất cả trên 1 trang` dưới chân trang: 1-click hiển thị toàn bộ 100% câu hỏi trong CSDL mà không cần phân trang.
- Backend FastAPI nâng ngưỡng `page_size` tối đa lên `10000` (`ge=1, le=10000`), cho phép tải toàn bộ ngân hàng câu hỏi mà không gặp lỗi xác thực HTTP 422.
- Thanh phân trang luôn hiển thị rõ ràng chỉ báo phạm vi: `Đang xem câu X - Y / tổng Z câu`.

---

## 10. Tích Hợp & Săn Dữ Liệu Toán Động Cho Toàn Bộ Khối Lớp 1 Đến 12 (Song Ngữ Anh - Việt & Olympic)

Hệ thống loại bỏ hoàn toàn việc khóa cứng (hardcode) dữ liệu vào một khối lớp duy nhất, mở rộng cơ chế bóc tách và tạo câu hỏi tự động tương thích toàn diện cho **12 khối lớp học đường (Khối 1 đến Khối 12)**:

### 10.1. Động Cơ Phân Tích Khối Lớp Từ URL (`extract_grade_from_url`)
- Tự động nhận diện khối lớp 1–12 từ mọi định dạng đường dẫn web:
  - Query parameters: `classes=X`, `grade=X`, `lop=X`, `class=X`.
  - Path slugs tiếng Việt: `toan-lop-X`, `lop-X`.
  - Path slugs tiếng Anh & chuẩn US: `grade-X`, `-first-grade-`, `-second-grade-`, ..., `-twelfth-grade-`, `1st-grade`...`12th-grade`.
  - Phân nhánh môn THPT trên Khan Academy: `algebra` (Lớp 9), `geometry` (Lớp 10), `algebra2` (Lớp 11), `calculus-1` / `precalculus` (Lớp 12).
- Khử lỗi rò rỉ khối lớp (Grade Leakage): Chặt đứt cơ chế tự động nạp đề Lớp 2 vào các khối lớp khác, phân lập chính xác 100% từng câu hỏi theo đúng khối lớp của nó.

### 10.2. Danh Mục Nguồn Động Theo Khối Lớp (`GET /api/hunter/grade-sources?grade={1..12}`)
- Sinh tự động danh mục URL nguồn chuẩn hóa theo 3 nhóm trụ cột cho từng khối lớp:
  - 🇻🇳 **Toán Tiếng Việt (GDPT 2018)**: Hành Trang Số (SGK/SBT `classes={grade}`), VioEdu, Trạng Nguyên Toán, OLM.vn (`toan-lop-{grade}`), VnDoc (`toan-lop-{grade}`), VietJack (`toan-lop-{grade}/index.jsp`).
  - 🇬🇧 **Toán Tiếng Anh (Math Grade {grade})**: K5 Learning (Worksheets theo khối 1–6), IXL Learning Math (`grade-{grade}`), Khan Academy (Khóa học tương ứng Khối 1–12), Common Core Sheets.
  - 🏆 **Toán Olympic & Tư Duy Song Ngữ**: Kangaroo Math (IKMC phân nhóm Ecolier 1-2 / Ecolier 3-4 / Benjamin 5-6 / Cadet 7-8 / Junior 9-10 / Student 11-12), Olympic TIMO (Primary 1-5 / Secondary 1-4 / Senior), Olympic SASMO & CodeMath.
- **Frontend Presets Động (`updateGradePresetsUI`)**:
  - Giao diện Trung tâm Thu thập tự động cập nhật toàn bộ các chip gợi ý nguồn nhanh khi người dùng chuyển đổi khối lớp trong dropdown chọn Khối.
  - Nút Nạp Nhanh tự động hiển thị: `✨ Nạp nhanh Đề Toán Khối [X] Toàn diện (Anh & Việt)`.

### 10.3. Cơ Chế 1-Click Harvester Theo Khối (`POST /api/hunter/harvest-by-grade`)
- Nhận `{ "grade": int, "subject": "math" }` (1 <= grade <= 12).
- Quét đồng thời các nguồn học liệu của đúng khối lớp được chọn, nạp câu hỏi vào CSDL SQLite.
- Tự động chuẩn hóa công thức LaTeX/KaTeX, gán thẻ `source_detail` chuyên biệt, loại trừ trùng lặp và kích hoạt đánh số tuần tự 1..N.
- Giữ nguyên các alias tương thích ngược: `GET /api/hunter/grade2-sources` và `POST /api/hunter/harvest-grade2`.

### 10.4. Động Cơ Sinh Câu Hỏi Tham Số Hóa 12 Khối Lớp (`generate_parametric_questions`)
- Mở rộng ngân hàng câu hỏi tham số hóa tự động cho toàn bộ 12 khối lớp:
  - Khối 1–5: Phép tính có nhớ, phân số, hỗn số, số thập phân, hình học phẳng, chuyển động đều.
  - Khối 6: Số nguyên $\mathbb{Z}$, ước chung lớn nhất (ƯCLN), bội chung nhỏ nhất (BCNN), phân số, hình thoi.
  - Khối 7: Dãy tỉ số bằng nhau, đa thức một biến, tổng các góc trong tam giác, lũy thừa số hữu tỉ.
  - Khối 8: Định lý Pythagoras, các hằng đẳng thức đáng nhớ, định lý Thales, phân tích đa thức thành nhân tử.
  - Khối 9: Căn bậc hai số học, hệ thức Vi-ét phương trình bậc hai, hệ số góc hàm số bậc nhất, góc nội tiếp và góc ở tâm.
  - Khối 10: Giao và hợp của tập hợp khoảng đoạn, dấu tam thức bậc hai, tích vô hướng của hai vectơ, vectơ pháp tuyến đường thẳng $Oxy$.
  - Khối 11: Số hạng tổng quát cấp số cộng $u_n$, quy tắc tính đạo hàm đa thức, hàm số lượng giác $\tan(x)$, xác suất cổ điển.
  - Khối 12: Tiệm cận đứng của hàm số phân thức, phương trình mũ và logarit, tích phân cơ bản $\int x^2 dx$, môđun số phức $z = a + bi$, phương trình mặt cầu không gian $Oxyz$.

---

## 11. Phân Hệ Luyện Tập Đề Thi Tương Tác & Báo Cáo Phân Tích (Interactive Practice Arena, History & Analytics)

Phân hệ `🎯 Luyện tập Trực tuyến` là môi trường thi thử và rèn luyện kỹ năng tương tác chất lượng cao, tích hợp đồng bộ giữa Frontend (`frontend/js/practice.js`), Backend API (`backend/app.py`) và CSDL SQLite:

### 11.1. Phòng Thi Trực Tuyến Tương Tác (Active Practice Arena)
- **Tạo Đề Luyện Tập Linh Hoạt (`POST /api/practice/generate`)**:
  - Hỗ trợ tạo đề từ ngân hàng theo đề thi cụ thể (`exam_id`) hoặc sinh đề động theo bộ môn (`subject`), khối lớp (`grade`), số lượng câu hỏi (`count`) và độ khó (`difficulty`).
- **Thanh HUD Giám Sát Thời Gian Thực (Arena HUD)**:
  - Hiển thị tiêu đề bài thi, khối lớp, thanh tiến độ làm bài (`X/Y câu`).
  - Đồng hồ đếm ngược với trạng thái cảnh báo màu động:
    + Bình thường: Màu xám đậm / xanh ngọc.
    + Cảnh báo (< 3 phút): Màu vàng cam (`#f59e0b`).
    + Nguy hiểm (< 1 phút): Màu đỏ nhấp nháy (`#ef4444`, animation pulse).
    + Khi hết giờ: Tự động khóa thao tác và kích hoạt nộp bài tự động.
- **Thao Tác Nhanh Bằng Bàn Phím (Keyboard Shortcuts)**:
  - Chọn phương án: Phím số `1`, `2`, `3`, `4` tương ứng với các đáp án `A`, `B`, `C`, `D`.
  - Phím chữ cái `A`, `B`, `C`, `D`.
- **Lưới Điều Hướng Câu Hỏi (Stepper Grid Navigation)**:
  - Lưới các nút câu hỏi `1..N` với 4 trạng thái trực quan:
    + `unanswered`: Màu xám viền nhạt (chưa làm).
    + `answered`: Màu xanh ngọc đậm (đã chọn đáp án).
    + `flagged`: Màu vàng hổ phách kèm biểu tượng cờ 🚩 (đánh dấu xem lại sau).
    + `current`: Viền xanh dương phát sáng (câu đang làm).
- **Hộp Thoại Xác Nhận Nộp Bài (Submission Confirm Modal `#modal-submit-confirm`)**:
  - Cảnh báo rõ ràng số lượng câu hỏi chưa hoàn thành trước khi học sinh nộp bài.

- **Quy Chuẩn Hợp Đồng Dữ Liệu Nộp Bài & Bí Danh Khóa (Payload Aliases)**:
  - Backend Pydantic model `PracticeAnswerSubmission` hỗ trợ đồng thời cả 3 tên khóa đáp án thông qua `AliasChoices` và `@model_validator`: `selected_answer` (chuẩn model), `selected_option` (chuẩn web SPA `practice.js`), và `user_answer` (chuẩn test/docs).
  - Phía web client gửi đồng bộ cả `selected_answer` và `selected_option`.
  - Phía web client hỗ trợ linh hoạt các phản hồi: `data.questions || data.session?.questions || []` khi khởi tạo phòng thi, và `data.records || data.history || []` khi tải lịch sử.
  - Phía web client hỗ trợ linh hoạt huy hiệu (`badges`) dạng danh sách chuỗi ID lẫn mảng đối tượng `{ id, unlocked }`.
- **Quy Chuẩn Chấm Điểm Hai Thang Điểm (`POST /api/practice/submit`)**:
  - Thang điểm 10.0 (`score = round((correct_count / total_questions) * 10.0, 1)`).
  - Thang điểm 100.0 (`score_100 = round((correct_count / total_questions) * 100.0, 1)`).
  - Phân loại học lực chuẩn Bộ Giáo dục & Đào tạo:
    + `score >= 9.0`: **Xuất sắc** 🏆
    + `8.0 <= score < 9.0`: **Giỏi** 🥇
    + `6.5 <= score < 8.0`: **Khá** 🥈
    + `5.0 <= score < 6.5`: **Trung bình** 🥉
    + `score < 5.0`: **Cần cố gắng** 📚
- **Chế Độ Xem Lại Toàn Diện (Detailed Review Mode)**:
  - Hiển thị trực quan từng câu:
    + Lựa chọn của học sinh đúng: Viền xanh lá cây nhạt (`border-emerald-500`, background xanh mint).
    + Lựa chọn của học sinh sai: Viền đỏ đậm (`border-rose-500`, background đỏ hồng), đánh dấu ✕ tại lựa chọn sai và đánh dấu ✓ tại đáp án đúng.
  - Hiển thị Lời giải chi tiết và công thức Toán render chuẩn KaTeX cho từng câu hỏi.

### 11.3. Bảng CSDL SQLite `practice_history` & Tối Ưu Hóa Truy Vấn
- **Cấu trúc Bảng SQLite 16 Trường**:
  - `id`: Khóa chính định danh UUID (`TEXT PRIMARY KEY NOT NULL`).
  - `exam_id`: Mã đề thi gốc hoặc mã phiên sinh động (`TEXT`).
  - `exam_title`: Tiêu đề bài luyện tập (`TEXT NOT NULL`).
  - `subject`: Bộ môn (`math`, `vietnamese`, `english`, `science`).
  - `grade`: Khối lớp (1 đến 12).
  - `total_questions`, `correct_count`, `wrong_count`, `skipped_count`: Số liệu câu hỏi (INTEGER).
  - `score`, `max_score`: Điểm số đạt được và điểm tối đa (REAL).
  - `duration_seconds`, `time_spent_seconds`: Thời gian quy định và thời gian làm thực tế (INTEGER).
  - `ranking`: Xếp loại học lực tiếng Việt (`TEXT`).
  - `answers_detail`: Chuỗi JSON chi tiết từng câu hỏi, lựa chọn của học sinh, đáp án đúng, trạng thái cờ và thời gian làm từng câu (`TEXT`).
  - `created_at`: Thời gian hoàn thành ISO 8601 UTC (`TEXT NOT NULL`).
- **4 Chỉ Mục Hiệu Năng Cao (Performance Indexes)**:
  - `idx_practice_created_at` trên `practice_history(created_at DESC)` (truy vấn lịch sử và biểu đồ xu hướng).
  - `idx_practice_subject` trên `practice_history(subject)` (lọc theo bộ môn).
  - `idx_practice_grade` trên `practice_history(grade)` (lọc theo khối lớp).
  - `idx_practice_exam_id` trên `practice_history(exam_id)` (truy vết bài thi).
- **Cơ Chế Lưu Trữ Kép (Dual Persistence)**:
  - Vừa ghi nhận vĩnh viễn vào SQLite `practice_history` qua API backend.
  - Vừa lưu đệm danh sách phiên gần nhất vào `localStorage` (`eduquest_practice_history`) để hiển thị tức thì không phụ thuộc độ trễ mạng.

### 11.4. Báo Cáo Xu Hướng, Năng Lực & Hệ Thống Gamification
- **Biểu Đồ Xu Hướng Điểm Số (Trending Score Chart Canvas)**:
  - Kết xuất trực tiếp bằng HTML5 Canvas 2D (`#canvas-practice-trending`), tự động nhân đôi tỉ lệ pixel (`devicePixelRatio`) đảm bảo nét căng trên màn hình Retina / 4K.
  - Đường cong Bezier mượt mà thể hiện tiến độ điểm số qua 10 lượt luyện tập gần nhất kèm gradient chuyển màu và tooltip điểm số khi rê chuột.
- **Phân Tích Năng Lực Bộ Môn (Subject Mastery Analysis)**:
  - Thống kê tỷ lệ chính xác (Accuracy %) và số câu đúng/tổng câu cho từng bộ môn: Toán học, Tiếng Việt, Tiếng Anh, Khoa học.
  - Thanh tiến độ (Progress bar) trực quan với màu sắc nhận diện đặc trưng cho từng môn.
- **Hệ Thống 8 Huy Hiệu Thành Tích Học Tập (Gamification Badges)**:
  1. `badge_first_step`: **Khởi Đầu** 🚀 — Hoàn thành bài luyện tập đầu tiên.
  2. `badge_perfect_score`: **Xạ Thủ Điểm 10** 🎯 — Đạt điểm 10 tuyệt đối.
  3. `badge_speed_racer`: **Tia Chớp Tốc Độ** ⚡ — Hoàn thành bài thi dưới 50% thời gian với điểm >= 8.0.
  4. `badge_math_master`: **Nhà Toán Học Nhí** 📐 — Hoàn thành xuất sắc bài thi môn Toán.
  5. `badge_scholar`: **Trạng Nguyên** 🏆 — Đạt xếp loại Xuất sắc (điểm >= 9.0).
  6. `badge_persistent`: **Chiến Binh Chăm Chỉ** 🔥 — Hoàn thành từ 5 phiên luyện tập trở lên.
  7. `badge_multilingual`: **Bách Khoa Song Ngữ** 🌍 — Luyện tập từ 2 bộ môn khác nhau trở lên.
  8. `badge_top_tier`: **Bậc Thầy Đỉnh Cao** 👑 — Điểm trung bình tất cả các lượt thi đạt từ 8.5 trở lên.

---

## 12. Nâng Cấp Hệ Thống v1.0.25: Arena Typography, KaTeX Pipeline, Timestamps & Batch Operations

### 12.1. Đấu Trường Luyện Tập: Arena Typography & KaTeX Math Protection
- **Arena Typography**:
  - CSS Reset toàn diện: Khai báo `button, input, select, textarea { font-family: inherit; }` đảm bảo form controls không bị ép dùng font mặc định của User Agent.
  - Các lớp nút bấm `.btn`, `.practice-tab-btn`, `.stepper-btn` kế thừa `font-family: inherit;`.
  - Nút `#btn-start-practice` gán chuyên biệt `font-family: var(--font-sans); letter-spacing: 0.3px;` đồng nhất 100% với giao diện `'Plus Jakarta Sans'`.
- **KaTeX Delimiters & Phân Số Hoàn Chỉnh (Canonical 4-Stage Pipeline)**:
  - Hàm `formatMathSymbols(str)` tuân thủ nguyên tắc Sanctuary Principle:
    1. Bước 1: Bảo vệ toàn bộ khối KaTeX sẵn có (`$$...$$`, `\[...\]`, `\(...\)`, `$..$`) vào mảng token để tránh bị chèn dấu `$` rác.
    2. Bước 2: Nhận diện biểu thức toán học thô (vd: `M = \frac{3}{4} + \frac{2}{5}`) và bọc thành 1 khối `$ ... $` duy nhất, tách dấu câu tiếng Việt ra ngoài.
    3. Bước 3: Chuẩn hóa đơn vị đo và công thức hóa học (`m^2` -> `m²`, `H2O` -> `H₂O`) trên phần văn bản thường.
    4. Bước 4: Khôi phục an toàn các khối toán học bằng hàm callback `replace(token, () => block)` loại trừ hoàn toàn escape bug của JavaScript `$$`.
  - Đồng bộ xuất ra `window.formatMathSymbols` dùng chung trên toàn hệ thống (`app.js`, `practice.js`, `exam_builder.js`).

### 12.2. Trung Tâm Thu Thập: Ngày Giờ created_at Chuẩn Tiếng Việt
- **Định dạng chuẩn tiếng Việt**: Hàm tiện ích toàn cục `formatDateTimeVN(dateInput)` chuyển đổi chuỗi ISO 8601 sang `HH:mm DD/MM/YYYY`.
- **Hiển thị trên 3 vị trí**:
  1. Thẻ câu hỏi (Question Cards) trong Ngân hàng câu hỏi và Modal Nhật ký bắt (`.tag-timestamp`: `🕒 HH:mm DD/MM/YYYY`).
  2. Modal Nhật ký bắt câu hỏi (`#modal-capture-logs`): hỗ trợ chế độ xem Bảng nhật ký ("table") kèm cột `Thời gian tạo` và tự động sắp xếp `sort_by=newest`.
  3. Bảng đối soát câu hỏi OCR (`#ocr-review-table`): bổ sung cột `Thời gian tạo`.
- **Backend OCR & PDF Extraction**: Bổ sung `"created_at": datetime.now().isoformat()` vào dictionary câu hỏi trích xuất từ PDF/Ảnh.

### 12.3. Ngân Hàng Câu Hỏi: Chốt Giữ Vị Trí Cuộn & Tác Vụ Hàng Loạt (Bulk Operations)
- **Lưu giữ vị trí cuộn trang (Scroll Retention)**:
  - Khi xóa 1 câu hỏi ("✕"): Gỡ tiêu điểm `blur()`, lưu vết `window.scrollY`, gọi API `DELETE /api/questions/{id}`.
  - Hiệu ứng xóa mượt mà (Smooth Fade-out): Co giãn `scale(0.97)`, `opacity: 0`, thu hẹp `max-height: 0px` trong 350ms rồi mới gỡ phần tử DOM.
  - Cập nhật số đếm giao diện tức thì và khôi phục vị trí cuộn bằng `window.scrollTo({ top: currentScrollY, behavior: "instant" })` mà tuyệt đối **không** gọi `loadQuestions()`.
- **Hộp kiểm Multiple Choice & Thanh Công Cụ Tác Vụ Hàng Loạt (Batch Action Toolbar)**:
  - Quản lý tập hợp `State.batchSelectedIds = new Set()`.
  - Checkbox trực quan trên từng câu hỏi, kèm class viền xanh nổi bật `.is-batch-selected`.
  - Thanh điều khiển "Chọn tất cả trên trang này" / "Bỏ chọn" phía trên danh sách câu hỏi (`#batch-selection-header`).
  - Thanh công cụ tác vụ hàng loạt nổi (`.batch-action-toolbar`): Nằm cố định ở đáy màn hình, tự động trượt lên khi chọn $\ge 1$ câu.
  - **Xóa hàng loạt (Bulk Delete)**: Gọi API `POST /api/questions/bulk-delete` thực thi trong 1 transaction SQLite an toàn (chia batch 500 items).
  - **Đổi khối lớp hàng loạt (Bulk Update Grade)**: Chọn khối lớp mới (Lớp 1 đến Lớp 12) và gọi API `POST /api/questions/bulk-update-grade` cập nhật đồng loạt trong 1 transaction SQLite.

---

## 13. Nâng Cấp Hệ Thống v1.0.26: Bóc Tách Đề Thi Image OCR Đa Tệp, Lightbox Zoom & Luồng Xác Thực Từng Câu

### 13.1. Chuyển Đổi Không Gian & Tích Hợp Vào "Soạn Câu Hỏi Mới" (`#view-manual`)
- **Di dời từ Trung tâm thu thập**: Chuyển toàn bộ thẻ chức năng "Bóc tách Đề thi PDF & Hình ảnh (Image OCR)" từ view `#view-collector` sang giao diện `#view-manual`, đặt ngay phía trên form nhập thủ công giúp tạo một workflow liền mạch giữa trích xuất tự động và tinh chỉnh thủ công.
- **Dọn sạch giao diện cũ**: Khung bóc tách cũ và các phần tử liên quan trong `#view-collector` được lược bỏ hoàn toàn, trả lại không gian tối giản cho các công cụ Extension & Web Scraper.

### 13.2. Chọn Nhiều Tệp Cùng Lúc & Khung Kéo Thả Trực Quan
- Hỗ trợ chọn và kéo thả nhiều tệp đồng thời (`multiple` files): PDF, PNG, JPG, JPEG, WEBP.
- Giao diện chip tệp (`.ocr-file-chip`) hiển thị tên file, dung lượng (KB), nút xóa từng file (✕), và nút "✕ Xóa tất cả".
- Bấm "🚀 Bắt đầu Bóc tách tất cả tệp" sẽ gửi tuần tự/đồng thời các file lên backend `/api/pdf/extract` và gộp toàn bộ câu hỏi trích xuất được vào một danh sách hàng đợi duy nhất.

### 13.3. Hộp Thoại Lightbox Xem Trước Phóng To Chi Tiết Ảnh Đề Thi (`#modal-image-zoom`)
- Modal chuyên dụng phóng to ảnh (`#modal-image-zoom`) với nền tối bán trong suốt `rgba(15, 23, 42, 0.95)`.
- Thanh công cụ điều khiển linh hoạt:
  - ➕ Phóng to (Zoom In) / ➖ Thu nhỏ (Zoom Out) theo bước 25%.
  - 🔄 Đặt lại 100% (Reset).
  - ↩️ Xoay 90° (Rotate).
  - ◀ / ▶ Điều hướng giữa các ảnh đề thi đã trích xuất.
  - Hỗ trợ phím tắt: `Esc` để đóng, `+`/`-` để zoom, lăn bánh xe chuột (Mouse Wheel) để phóng to/thu nhỏ mượt mà.
  - Kéo chuột Pan di chuyển ảnh để kiểm tra chi tiết các ký hiệu toán học nhỏ hoặc chữ mờ.

### 13.4. Động Cơ Bóc Tách Nâng Cao Cho Đề Thi Song Ngữ (Bilingual OCR Engine)
- **Tự động phóng đại siêu phân giải (Super-resolution Upscaling)**: Tự động phát hiện ảnh chụp điện thoại hoặc ảnh chụp màn hình độ phân giải thấp (<950px chiều rộng), áp dụng phép nội suy khối `cv2.INTER_CUBIC` tỉ lệ 2.5x giúp các nét chữ mảnh không bị đứt đoạn.
- **Làm sạch nhiễu trạng thái**: Tự động loại bỏ thời gian status bar điện thoại (vd: `05:31`), điểm số câu hỏi (`*4/4`), và dấu tích đầu dòng (`✓`).
- **Khôi phục ngữ nghĩa & dấu thanh Tiếng Việt chuyên sâu**:
  - Tách từ dính liền với số: `has5` -> `has 5`, `class5` -> `class 5`.
  - Khôi phục thứ trong tuần song ngữ: `Thứ Tư` (Wed), `Thứ Bảy` (Sat), `Thứ Năm` (Thu), `Thứ Sáu` (Fri).
  - Khôi phục mẫu câu đề thi chuẩn: `Nếu hôm nay là thứ...`, `và cũng là ngày đầu tiên của tháng...`, `Lớp của ... có X bạn trai và Y bạn gái. Hỏi ... có bao nhiêu bạn cùng lớp?`.
- **Nhận diện dấu tích đáp án (`[✓✔☑]`)**: Tự động nhận diện phương án đã được đánh dấu tích trong đề thi và gán cờ `correct_answer`.

### 13.5. Luồng Xác Thực Câu Hỏi Từng Bước (Step-by-Step Verification Queue)
- **Quy trình tương tác**:
  1. Image OCR bóc tách tất cả câu hỏi từ các file đã chọn.
  2. Hiển thị thẻ trạng thái tiến trình (`#ocr-batch-progress-card`): `Số câu đã xử lý / Tổng số câu hỏi bóc tách` kèm thanh tiến độ trực quan (`.ocr-progress-fill`).
  3. Tự động nạp câu hỏi đầu tiên vào form soạn thảo thủ công ("Soạn thảo & Thêm câu hỏi Thủ công") với đầy đủ nội dung, 4 phương án, đáp án đúng và khối lớp.
  4. Hiển thị ảnh thumbnail gốc của câu hỏi kèm nút "🔍 Phóng to xem ảnh gốc" để đối soát trực tiếp.
  5. Giáo viên kiểm tra, đính chính công thức Toán và bấm "💾 Lưu câu hỏi vào Ngân hàng" (hoặc phím tắt `Ctrl + Enter`).
  6. Hệ thống lưu câu hỏi vào CSDL, tăng bộ đếm `processedCount`, phát âm thanh/thông báo toast thành công và tự động nạp câu hỏi tiếp theo vào form.
  7. Hỗ trợ các nút điều hướng phụ: `⬅ Câu trước`, `Bỏ qua ⏭️`, `⚡ Lưu nhanh tất cả` (bỏ qua bước soát từng câu), hoặc `✕ Hủy luồng`.
  8. Khi xử lý hết câu hỏi cuối cùng, hiển thị thông báo chúc mừng hoàn thành và đưa form về trạng thái sẵn sàng ban đầu.

### 13.6. Nhật Ký Bóc Tách OCR Thời Gian Thực (Live Telemetry Log Console) & Quản Trị Trạng Thái Toàn Cục
- **Khắc phục lỗi State Scope (`window.State`)**:
  - `const State` ở phạm vi script của `frontend/js/app.js` được gán tường minh vào `window.State = State` kèm thuộc tính `ocrBatch: null`.
  - Triệt tiêu hoàn toàn ngoại lệ `TypeError: Cannot set properties of undefined (setting 'ocrBatch')` khi gọi giữa các module độc lập.
  - Chuẩn hóa `API_BASE` tự động khớp với `window.location.origin` để giải quyết triệt để lỗi phân tách domain giữa `localhost` và `127.0.0.1`.
- **Khung Nhật ký Live OCR (`#ocr-live-log`)**:
  - Đặt ngay dưới Dropzone tệp, thiết kế phong cách terminal hiện đại (monospace, nền tối `#0f172a`, viền `#334155`).
  - Ghi vết mọi tương tác: dung lượng & định dạng file upload, thời gian phản hồi API máy chủ, số câu hỏi trích xuất, chi tiết phương án, và tiến độ lưu từng câu.
  - Tự động lưu bền vững vào `localStorage` (`eduquest_ocr_log`) và tự động phục hồi khi tải lại trang (`restoreOcrLog()`).
- **Thanh Công Cụ Nhật Ký (`#ocr-log-toolbar`)**:
  - Nút `📋 Sao chép Log` (`copyOcrLiveLog()`): Tự động sao chép toàn bộ nội dung telemetry vào Clipboard phục vụ chẩn đoán lỗi nhanh.
  - Nút `🗑️ Xóa Log` (`clearOcrLiveLog()`): Làm sạch khung log và xóa sạch bộ nhớ tạm trình duyệt.

### 13.7. Tối Giản Vùng Kéo Thả OCR (Ultra-compact Dropzone Strip) & Tối Ưu Diện Tích Làm Việc
- **Thu gọn Dropzone thành dải ngang đơn hàng (Single-line Strip)**:
  - Thay thế khối hộp trắng cỡ lớn chiếm ~180px trước đây bằng dải ngang tối giản `.dropzone-compact` với chiều cao chỉ ~38px - 40px (`padding: 8px 14px`).
  - Tích hợp biểu tượng inline nhỏ (16px), dòng nhắc nhở ngắn gọn và nhãn định dạng tệp hỗ trợ (.pdf, .png, .jpg, .webp).
  - Vẫn giữ nguyên 100% chức năng: nhấp chuột để chọn tệp hoặc kéo thả đa tệp mượt mà.
- **Tiết kiệm diện tích màn hình (>75% vertical space saved)**:
  - Thu gọn toàn bộ Card 1 từ ~290px xuống còn ~80px, đưa form Soạn thảo Thủ công (`#m-content`) lên sát tầm mắt của giáo viên ngay khi mở trang mà không cần cuộn chuột.
- **Khả năng Thu gọn/Mở rộng linh hoạt (Accordion Toggle)**:
  - Bổ sung nút `[▲ Thu gọn] / [▼ Kéo thả]` (`toggleOcrDropzone()`): cho phép ẩn hoàn toàn vùng kéo thả khi chỉ có nhu cầu tự soạn câu hỏi thủ công.
  - Khung nhật ký debug `#ocr-log-section` mặc định ẩn gọn gàng (`display: none`) và mở ra tức thì qua nút `[🖥️ Log]` trên thanh tiêu đề.

### 13.8. Điều Hướng Tự Do Toàn Diện & Nút Bỏ Qua Câu Hỏi OCR (Free Carousel Navigation & Question Discard)
- **Tách rời hoàn toàn điều hướng và lưu trữ (Decoupled Navigation & Persistence)**:
  - Người dùng có thể tự do chuyển qua lại bất kỳ câu hỏi nào trong đợt quét OCR mà không bị ép buộc phải lưu vào CSDL trước đó.
  - Nút `⬅ Câu trước` và `Câu tiếp ➡` (`navPrevOcrQuestion()`, `navNextOcrQuestion()`): tự do di chuyển tuần tự qua danh sách câu hỏi.
  - Thanh chọn nhanh tự do (`#ocr-questions-nav-bar`): thanh chip selector cuộn ngang trực quan hiển thị toàn bộ câu hỏi kèm biểu tượng trạng thái thời gian thực:
    + ⚪ `status-pending`: Câu hỏi đang chờ kiểm tra / chưa lưu.
    + 🟢 `status-saved`: Câu hỏi đã được đính chính & lưu thành công vào CSDL.
    + ❌ `status-skipped`: Câu hỏi đã được người dùng chủ động bỏ qua.
  - Nhấp vào bất kỳ chip câu hỏi nào (`jumpToOcrQuestion(index)`) sẽ tải trực tiếp câu hỏi đó vào form soạn thảo kèm thumbnail ảnh đề thi tương ứng.
- **Nút "Bỏ qua câu này" (`#btn-ocr-discard-q` - `discardCurrentOcrQuestion()`)**:
  - Cho phép người dùng loại bỏ các câu hỏi OCR bị trùng lặp trong ngân hàng câu hỏi hoặc nội dung rác/không phù hợp mà không lưu vào CSDL.
  - Tự động đánh dấu `_ocrStatus = 'skipped'`, tăng bộ đếm số câu đã bỏ qua `skippedCount`, cập nhật thanh tiến độ `processedCount = savedCount + skippedCount`, và tự động chuyển sang câu hỏi kế tiếp còn chưa xử lý.
- **Lưu Nhanh Thông Minh (`saveAllRemainingOcrQuestions()`)**:
  - Chỉ quét và lưu các câu hỏi chưa được lưu (`pending`), tự động loại trừ các câu hỏi người dùng đã bấm `Bỏ qua` (`skipped`), tránh lưu nhầm rác vào CSDL.

### 13.9. Kiến Trúc VietOCR Transformer & Động Cơ Chuẩn Hóa Ngữ Nghĩa Tiếng Việt
- **Phân tích nghiên cứu từ kiến trúc VietOCR (`pbcquoc/vietocr`)**:
  - Mô hình VietOCR kết hợp CNN Feature Extractor (VGG / ResNet) và Transformer Seq2Seq Decoder.
  - Bản chất sức mạnh của VietOCR không nằm ở bộ nhận diện CTC ký tự đơn lẻ, mà nằm ở khối **Transformer Language Model (Attention Decoder)**: mô hình này áp dụng phân phối xác suất ngữ nghĩa tiếng Việt đa âm tiết (Vietnamese Syllable Grammar & Exam Lexicon) để tự động sửa chữa các nét thanh điệu bị mờ, đứt đoạn hoặc nhầm lẫn do CTC (như `Nenhom nary` -> `Nếu hôm nay`, `fathieTiemcung` -> `là thứ Tư và cũng`, `atae tien` -> `đầu tiên`, `thang 3` -> `tháng 3`, `thur may` -> `thứ mấy`, `LopcriaMichaelco` -> `Lớp của Michael có`, `wi 6 ban guii` -> `và 6 bạn gái`, `Hoi Michael co baonhicu ban cting lop` -> `Hỏi Michael có bao nhiêu bạn cùng lớp`).
  - Do thư viện `vietocr 0.3.13` ghim cứng các thư viện phụ thuộc cũ (`pillow==10.2.0`, `einops==0.2.0`, `imgaug==0.4.0`) không tương thích Python 3.14, EduQuest Pro đã tích hợp trọn vẹn ngữ nghĩa âm tiết và từ điển chuyên ngành đề thi tiểu học/Olympic vào bộ tiền/hậu xử lý Transformer-inspired tại `backend/pdf_extractor.py` (`clean_ocr_vietnamese_text`), mang lại độ chính xác ngữ âm tương đương mô hình Transformer mà không gây xung đột dependency.

### 13.10. Kiến Trúc Động Cơ OCR Kép (Dual OCR Engine Architecture - OP-B)
- **Tùy chọn Động cơ OCR trên Giao diện (`#ocr-engine-select`)**:
  - `⚡ RapidOCR (PaddleOCR ONNX)` (mặc định): Tốc độ siêu tốc (~0.2s/trang), cực kỳ nhẹ, thực thi trực tiếp qua ONNX Runtime.
  - `🧠 VietOCR ONNX DeepDoc`: Tối ưu nhận diện chuyên sâu cấu trúc chữ tiếng Việt, tự động nạp mô hình từ `data/models/vietocr.onnx` khi khả dụng.
- **Cơ chế Graceful Fallback Tự động**:
  - Nếu tệp trọng số `vietocr.onnx` chưa được tải về máy chủ, hệ thống không gây crash hay báo lỗi HTTP 500 mà tự động fallback sang RapidOCR kết hợp bộ ngữ nghĩa tiếng Việt Transformer-inspired và thông báo rõ ràng trong nhật ký telemetry.
- **Bóc tách độc lập hoàn toàn khỏi PyTorch/Torchvision**:
  - Module `backend/vietocr_onnx.py` kết nối trực tiếp với `onnxruntime` engine, không sử dụng PyTorch hoặc các dependency cũ, tương thích hoàn toàn với Python 3.14.

### 13.11. Cơ Chế Tự Học Ngữ Nghĩa (Active Lexicon Learning - Human-in-the-Loop)
- **Chu trình Tự học Khép kín**:
  1. Khi người dùng nạp câu hỏi từ OCR vào Form Soạn thảo, hệ thống lưu vết chuỗi OCR gốc (`_rawOcrText`).
  2. Trong quá trình kiểm tra, người dùng sửa các từ sai/lỗi dấu thanh thành văn bản chuẩn.
  3. Khi bấm "💾 Lưu câu hỏi vào Ngân hàng" (hoặc `Ctrl + Enter`), `POST /api/questions` tiếp nhận trường `raw_ocr_content`.
  4. Thuật toán `record_ocr_learning_diff()` so khớp diff cấp độ từ (SequenceMatcher) với ngưỡng tối đa 12 token.
  5. Các cặp từ/cụm từ thay đổi (`wrong_text ➔ correct_text`) được lưu vào bảng SQLite `ocr_corrections` với tần suất tăng dần (`frequency + 1`).
  6. Hàm chuẩn hóa `clean_ocr_vietnamese_text()` tự động truy vấn từ điển `get_ocr_corrections_map()` theo thứ tự độ dài giảm dần, tự động áp dụng tức thì cho mọi lần bóc tách ảnh/PDF tiếp theo.
- **Hộp thoại Quản lý Từ điển Tự học (`#modal-ocr-lexicon`)**:
  - Mở nhanh qua nút `🧠 Tự học (N)` trên thanh công cụ OCR.
  - Thêm quy tắc thủ công (`lexicon-add-wrong ➔ lexicon-add-correct`).
  - Tìm kiếm và lọc quy tắc tức thì qua ô tìm kiếm.
  - Xem tần suất xuất hiện `xN` và nguồn gốc quy tắc (`🧠 Tự học (Form)` hoặc `Thủ công`).
  - Xóa từng quy tắc hoặc dọn sạch toàn bộ từ điển khi cần thiết.
- **Hiệu năng & In-memory Cache**:
  - Từ điển tự học được cache RAM với TTL 300 giây, tự động làm mới (`invalidate_ocr_corrections_cache()`) ngay khi có thêm hoặc sửa quy tắc mới.

### 13.12. Xử Lý Ảnh Chụp Kích Thước Nhỏ (Low-Res Mobile Screenshots), Bảo Vệ Từ Ghép Số (Compound Numbers) & Nhận Diện Màu Đáp Án Đúng
- **Bảo vệ Từ ghép nối số (Compound Number Protection)**:
  - Ngăn ngừa tình trạng các cụm từ tiếng Anh/Toán như `2-digit`, `3-chữ số`, `4-step` bị phân tách nhầm thành số câu mới (như `Câu 2`).
  - Sử dụng cơ chế mã hóa tạm `\1_\2` trước khi chuẩn hóa số câu và hoàn nguyên `\1-\2` sau đó.
  - Chuẩn hóa điều kiện phân tách câu hỏi: chỉ phân tách khi có tiền tố tường minh (`Câu`, `Question`, `Bài`) hoặc số đứng đầu đi kèm dấu phân cách (`.`, `:`, `)`, `,`) và khoảng trắng.
  - Hợp nhất khối câu hỏi mồ côi (Orphan Block Consolidation): tự động gộp các khối văn bản ngắn không có phương án trắc nghiệm vào thân câu hỏi liền trước.
- **Tối ưu Hóa Tỉ Lệ Phóng Đại (Adaptive Low-res Upscaling)**:
  - Điểm ngọt phóng đại hình ảnh cho ảnh chụp điện thoại nhỏ (chiều rộng <800px) được thiết lập tại `800px` với `cv2.INTER_CUBIC`, chống hiện tượng mờ nhòe nét mảnh toán học (dấu trừ, số 11, phương án C7).
- **Tự Động Phát Hiện Đáp Án Đã Chọn Qua Màu Sắc (Green Highlight Answer Detection)**:
  - Phân tích màu sắc nền của vùng bounding box (`crop.mean(axis=(0, 1))`) cho các dòng phương án (A, B, C, D).
  - Khi màu nền có sắc xanh lá (`G - R > 6` và `G - B > 4`), hệ thống tự động gán dấu kiểm `✓` vào phương án tương ứng và đánh dấu `is_correct = True` cho câu hỏi.
- **Từ Điển Ngữ Nghĩa Toán Học Bổ Sung**:
  - Mở rộng kho ngữ nghĩa tự động sửa lỗi cho các đề thi khối 2 song ngữ: nhận diện chuẩn xác các từ vựng `Gordon nghĩ ra một số`, `Anh ấy lấy số đó`, `cộng thêm 38`, `rồi trừ đi 42`, `thì được số lẻ nhỏ nhất có hai chữ số`, `Tìm số đó`, `Tính 13 - 11 + 9 - 7 + 5 - 3 + 1`.

### 13.13. Chen Hinh anh vao Noi dung De bai (Manual Question Image Insertion)
- **Thanh cong cu anh (Image Toolbar)**: Dat ngay duoi textarea `#m-content`, gom:
  - Nut "Chen anh" (📷): Mo dialog chon file anh tu may tinh (`#m-img-file-input`), chap nhan dinh dang `image/*`, cho phep chon nhieu file.
  - Nut "Dan anh (Ctrl+V)" (📋): Truoc tien thu doc Clipboard API truc tiep. Neu khong duoc phep, fallback sang focus vao textarea va huong dan nguoi dung nhan Ctrl+V.
  - Goi y nhac: "Keo tha anh vao o soan thao hoac Ctrl+V de dan".
- **3 phuong thuc chen anh**:
  1. **Chon file**: Qua input file an (#m-img-file-input), ho tro multi-select.
  2. **Keo tha (Drag & Drop)**: Keo file anh tu may vao textarea `#m-content`, co hieu ung highlight xanh `.img-dragover`.
  3. **Dan tu clipboard (Ctrl+V)**: Bat su kien `paste` tren textarea, trich xuat blob anh tu clipboard.
- **Upload & Luu tru**:
  - Moi anh duoc upload len `POST /api/media/upload` (toi da 10MB/file, dinh dang .png, .jpg, .jpeg, .webp, .bmp, .gif).
  - Server luu vao `data/media/`, tra ve URL `/media/{unique_filename}`.
  - Mang `manualImageUrls[]` (JS global) quan ly danh sach URL anh da upload cho cau hoi hien tai.
- **Thu vien anh dinh kem (Image Gallery)** `#m-img-gallery`:
  - An mac dinh, hien thi khi co >=1 anh.
  - Hien thi thumbnail voi nut xoa tung anh (hover de lo nut X do), so luong anh, va nut "Xoa tat ca".
  - Click vao thumbnail mo anh trong tab moi.
- **Live Preview**: Ham `updateManualPreviewWithImages()` render dong thoi text + LaTeX + hinh anh trong khung preview `#m-preview-box`.
- **Payload Submit**: `submitManualQuestion()` gui mang `images: [...]` trong payload JSON va nhung `<img>` tags vao `content_html`.
- **Reset Form**: `resetManualForm()` xoa `manualImageUrls = []` va an gallery.
- **Dong bo OCR**: `loadOcrQuestionToForm()` trong `collector.js` tu dong copy `q.images` sang `manualImageUrls` va render gallery.
