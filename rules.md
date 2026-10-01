# EduQuest Pro — Quy Tắc Kiến Trúc & Đặc Tả Nghiệp Vụ (rules.md)

Tài liệu này là **đặc tả thiết kế còn hiệu lực** của hệ thống EduQuest Pro (thu thập, lưu trữ, biên soạn câu hỏi trực tuyến và đề thi).

---

## 1. Kiến trúc Hệ thống & Phiên bản

Hệ thống hoạt động theo mô hình Hybrid phân tán:
1. **Phiên bản chuẩn hóa**: **App: `v1.0.17`**, **Extension: `v1.3.12`**.
2. **Backend Engine**: FastAPI (Python 3.10+) chạy tại `http://127.0.0.1:8000`.
   - Cơ sở dữ liệu: SQLite (`data/questions.db`).
   - Thư mục Media/Ảnh: `data/media/`.
   - Export Word: `python-docx` xuất file `.docx` chuẩn mẫu đề thi Việt Nam.
3. **Frontend Single-Page App**: HTML5, Vanilla JavaScript, CSS3.
   - Thư viện hiển thị công thức: KaTeX 0.16.10 tự động render `$ ... $`, `$$ ... $$`, `\( ... \)`.
   - Giao diện gồm 5 module: Bảng Tổng quan, Ngân hàng Câu hỏi, Biên soạn & Trộn Đề, Trung tâm Thu thập, Soạn Câu hỏi Mới.
   - **Quy chuẩn UX Tab Trình duyệt**: Bỏ hoàn toàn biểu tượng/logo ở tab trình duyệt bằng chuẩn W3C `<link rel="icon" href="data:,">`.
4. **Trình thu thập dữ liệu (Collector Modules)**:
   - **Chrome/Edge Extension (v1.3.12)**: Thu thập tự động câu hỏi trên VioEdu, Hành Trang Số, Trạng Nguyên, CodeMath, IOE, VietJack, Lời Giải Hay qua Network Request Interception, DOM Extraction và Bulk Lesson Crawler.
   - **Bộ bóc tách đề thi PDF**: Phân tích đề thi Olympic TIMO, ASMO, HKIMO bằng PyPDF & Regex.
   - **Internet Hunter & Parametric Generator**: Thu thập tự động từ các nguồn học liệu trực tuyến mở (Blogger Atom JSON, SGK điện tử) kết hợp động cơ sinh câu hỏi tham số hóa đa khối lớp và đa bộ môn.

---

## 2. Tiện ích Mở rộng (Chrome / Edge Extension v1.3.12)

### 2.1. Kiến trúc Extension & Thu thập Bài học Hàng loạt (Bulk Harvester)
- **Manifest**: Manifest V3, quyền `activeTab`, `storage`, `scripting`, truy cập host `*.vio.edu.vn`, `*.tnmath.edu.vn`, `*.trangnguyen.edu.vn`, `*.hanhtrangso.nxbgd.vn`, `*.vietjack.com`, `*.loigiaihay.com`, `*.vndoc.com`, `*.hoc247.net`, `localhost:8000`.
- **Page Context Interceptor (`interceptor.js v1.3.12`)**:
   - Tiêm trực tiếp vào môi trường DOM gốc (page context) để ghi đè `window.fetch`, `XMLHttpRequest.prototype.open`, `XMLHttpRequest.prototype.send`, `WebSocket.prototype.send`.
   - **Hỗ trợ Angular HttpClient (`responseType = 'json'`) & GraphQL**: Bắt trực tiếp cả REST API và GraphQL queries (`PracticeQuestionQuery`, `GetQuestionResultQuery`), phân tích chuyên sâu các đối tượng câu hỏi VioEdu (`skillName`, `depthOfKnowledge`, `textDropdownAnswers`, `leftMatching`, `rightMatching`), bao quát cả các luồng đánh giá năng lực `onboard-flow`.
   - **Hỗ trợ URL Rút gọn**: Hàm `getShortUrl()` trích xuất `hostname + pathname` rút gọn (tối đa 22 ký tự), gắn kèm vào mọi log phát đi.
   - **Loại bỏ cây dữ liệu phi câu hỏi (CMS Ignored Keys)**: Bỏ qua hoàn toàn các nhánh dữ liệu CMS tin tức, cấu hình, quảng cáo (`news`, `posts`, `articles`, `banners`, `notifications`, `categories`, `menus`, `configs`, `promotions`, `products`, `combos`, `courses`, `transactions`, `orders`).
   - **Bộ lọc Chống UUID và Token Định danh**: Tuyệt đối không lấy chuỗi UUID (pattern `/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i`), chuỗi mã băm Hex, hoặc token đơn lẻ làm nội dung câu hỏi.
   - **Loại bỏ Tiêu đề Tin tức/Sự kiện**: Tuyệt đối không sử dụng trường `title` hoặc `name` làm câu hỏi trừ khi đối tượng có mảng phương án `answers`/`options` hợp lệ và không chứa từ khóa quảng cáo/giải đấu.
- **Content Script (`content.js v1.3.12`)**:
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
     - `hasCardRichContent` loại trừ icon, robot avatar, svg, loading gif; không tự động chấp thuận vô điều kiện các dialog hệ thống.
     - Hỗ trợ câu hỏi đọc hiểu Tiếng Việt: Nhận diện văn bản tường thuật nhiều đoạn kết hợp từ để hỏi hoặc câu hỏi chốt ở cuối.
     - Tự động nhận diện môn Tiếng Việt (`detectSubject`) đối với bài đọc văn bản thuần túy không chứa ký hiệu toán học.
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

### 4.2. Tự động Lưu Nhật ký Trực tiếp (Live Log Persistence)
- Nhật ký trực tiếp của Thợ săn Internet (`#hunter-live-log`) và Bot cào (`#scraper-live-log`) được tự động lưu vào `localStorage`. Khi người dùng F5 hoặc chuyển view, nội dung log vẫn được giữ nguyên vẹn.

### 4.3. Cấu hình Khối lớp & Tài khoản
- Cho phép người dùng thiết lập **Khối lớp mặc định** toàn hệ thống.
- Tự động lưu lựa chọn Khối lớp vào `localStorage` (`eduquest_default_grade`, `eduquest_selected_grade`) và tự động đồng bộ sang tất cả các bộ lọc.
- Tự động ghi nhớ thông tin đăng nhập cào vòng thi (`eduquest_scraper_plat`, `eduquest_scraper_user`, `eduquest_scraper_round`).

### 4.4. Thợ săn Câu hỏi Internet Tự động (Auto-Hunter Loop)
- Tích hợp vòng lặp tự động chạy mỗi 5 phút (300 giây).
- Hiển thị huy hiệu đếm ngược thời gian thực trên giao diện.
- Trạng thái bật/tắt được ghi nhớ qua `localStorage` (`eduquest_autohunter`).

---

## 5. Chuẩn hóa Phân loại Bộ môn (AI Subject Classifier)

Quy tắc phân loại tự động ưu tiên theo thứ tự:
1. `math`: Khớp các từ khóa toán học hoặc công thức LaTeX (`\frac`, `\sqrt`, `^`, góc, chu vi, diện tích, phân số, chữ số, hình bình hành, tam giác, ...).
2. `english`: Khớp từ khóa tiếng Anh thuần túy, kiểm tra ranh giới từ `\bioe\b`, kiểm tra tỷ lệ từ tiếng Anh không dấu.
3. `vietnamese`: Nhận diện dấu thanh Tiếng Việt đặc trưng kết hợp từ vựng văn học, tiếng Việt (từ ghép, biện pháp tu từ, trạng ngữ, chủ ngữ, vị ngữ, chính tả, thành ngữ, tục ngữ, ...).
4. `science`: Khớp từ vựng khoa học tự nhiên, động vật, thực vật, môi trường, địa lý, lịch sử.

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


