// EduQuest Collector v1.3.15 - Bulk Lesson & Practice Scraper, Deep Network Telemetry & Debug Logger
(function () {
  console.log("%c[EduQuest Collector v1.3.15] Active on: " + window.location.hostname, "color: #38bdf8; font-weight: bold; font-size: 13px;");

  let capturedQuestions = [];
  let autoSaveEnabled = localStorage.getItem("eduquest_autosave") !== "false"; // Default ON (True)
  let savedQuestionIds = new Set();
  let savedTextSignatures = new Set();
  let lastLoggedSkipSig = ""; // Prevent duplicate skip log spam
  let activityLogs = [];
  let currentLogFilter = "all"; // 'all' | 'success' | 'skip' | 'net' | 'error'
  let logSearchQuery = "";
  let logStorageDebounceTimer = null;
  let backendSyncDebounceTimer = null;
  let pendingBackendLogs = [];

  // Helper: Strip "Câu hỏi số X", "Câu X", "Bài X" prefix for unified stem signature matching
  function normalizeStemForSignature(text) {
    if (!text || typeof text !== "string") return "";
    return text
      .replace(/^(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*\d+)[\s\.\:\-_]*/i, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  // Helper: Rebuild lookup signatures strictly matching current capturedQuestions state
  function rebuildSignatures() {
    savedQuestionIds.clear();
    savedTextSignatures.clear();
    if (Array.isArray(capturedQuestions)) {
      capturedQuestions.forEach(q => {
        if (q.id) savedQuestionIds.add(String(q.id));
        const optSig = (q.options || []).map(o => (typeof o === "object" ? o.content : o)).join(" ");
        const normStem = normalizeStemForSignature(q.content_text || "");
        const sig = (normStem + " " + optSig).toLowerCase().replace(/\s+/g, " ").trim();
        if (sig) savedTextSignatures.add(sig);
      });
    }
  }

  // Smart Anti-Duplicate Check: Verifies existence against active capturedQuestions, purging orphaned signatures
  function isAlreadyCaptured(sig, qId) {
    if (!capturedQuestions || capturedQuestions.length === 0) {
      if (savedQuestionIds.size > 0 || savedTextSignatures.size > 0) {
        savedQuestionIds.clear();
        savedTextSignatures.clear();
      }
      return false;
    }

    const cleanSig = (sig || "").toLowerCase().replace(/\s+/g, " ").trim();
    const strQId = qId ? String(qId).trim() : "";

    const exists = capturedQuestions.some(q => {
      if (strQId && String(q.id) === strQId) return true;
      if (cleanSig) {
        const optSig = (q.options || []).map(o => (typeof o === "object" ? o.content : o)).join(" ");
        const existingStemNorm = normalizeStemForSignature(q.content_text || "").toLowerCase().replace(/\s+/g, " ").trim();
        const existingSig = (existingStemNorm + " " + optSig).toLowerCase().replace(/\s+/g, " ").trim();
        if (existingSig && existingSig === cleanSig) return true;

        const incomingStemNorm = normalizeStemForSignature(cleanSig.split(" ").slice(0, 15).join(" "));
        const existingStemHead = existingStemNorm.split(" ").slice(0, 15).join(" ");
        if (existingStemHead && incomingStemNorm && existingStemHead.length >= 20 && incomingStemNorm.length >= 20) {
          if (existingStemHead.startsWith(incomingStemNorm) || incomingStemNorm.startsWith(existingStemHead)) {
            return true;
          }
        }
      }
      return false;
    });

    if (exists) {
      if (cleanSig) savedTextSignatures.add(cleanSig);
      if (strQId) savedQuestionIds.add(strQId);
      return true;
    } else {
      if (cleanSig) savedTextSignatures.delete(cleanSig);
      if (strQId) savedQuestionIds.delete(strQId);
      return false;
    }
  }

  function getShortUrl() {
    try {
      const host = window.location.hostname.replace(/^www\./, "");
      const path = window.location.pathname;
      if (!path || path === "/") return host;
      const cleanPath = path.replace(/\/$/, "");
      return host + (cleanPath.length > 22 ? cleanPath.substring(0, 20) + "…" : cleanPath);
    } catch (e) {
      return "online";
    }
  }

  function escapeHtml(str) {
    if (typeof str !== "string") str = String(str || "");
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Auto-restore persisted captured questions across session/page transitions
  try {
    const rawQuestions = localStorage.getItem("eduquest_captured_questions");
    if (rawQuestions) {
      capturedQuestions = JSON.parse(rawQuestions);
      if (!Array.isArray(capturedQuestions)) capturedQuestions = [];
      rebuildSignatures();
    }
  } catch (e) {
    capturedQuestions = [];
    rebuildSignatures();
  }

  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    try {
      chrome.storage.local.get(["eduquest_captured_questions", "eduquest_ext_logs"], (res) => {
        if (res && res.eduquest_captured_questions && Array.isArray(res.eduquest_captured_questions)) {
          res.eduquest_captured_questions.forEach(q => {
            if (!capturedQuestions.some(existing => existing.id === q.id || existing.content_text === q.content_text)) {
              capturedQuestions.push(q);
            }
          });
          rebuildSignatures();
          updateWidgetUI();
          renderScannedModalQuestions();
        }
        if (res && res.eduquest_ext_logs && Array.isArray(res.eduquest_ext_logs)) {
          activityLogs = res.eduquest_ext_logs;
          renderActivityLogs();
        }
      });
    } catch (e) {}
  }

  function persistCapturedQuestions() {
    try {
      localStorage.setItem("eduquest_captured_questions", JSON.stringify(capturedQuestions));
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ eduquest_captured_questions: capturedQuestions });
      }
    } catch (e) {}
  }

  // Auto-restore persisted activity logs
  try {
    const rawLogs = localStorage.getItem("eduquest_ext_logs");
    if (rawLogs) {
      activityLogs = JSON.parse(rawLogs);
    }
  } catch (e) {}

  function addLog(msg, type = "info", detail = null, source = null) {
    const now = new Date();
    const time = now.toLocaleTimeString();
    const src = source || getShortUrl();
    const entry = {
      id: "log_" + Date.now() + "_" + Math.random().toString(36).substr(2, 4),
      time,
      timestamp: Date.now(),
      msg: String(msg || ""),
      type: type || "info",
      source: src,
      detail: detail
    };

    activityLogs.unshift(entry);
    if (activityLogs.length > 150) activityLogs.pop();

    const consoleStyle =
      type === "error" ? "color: #ef4444; font-weight: bold;" :
      type === "success" ? "color: #10b981; font-weight: bold;" :
      type === "skip" ? "color: #f59e0b;" :
      type === "net" ? "color: #a855f7; font-weight: bold;" :
      "color: #0284c7;";
    console.log(`%c[EduQuest ${time}] [${src}] [${(type).toUpperCase()}] ${msg}`, consoleStyle);

    renderActivityLogs();

    // 1. Debounced storage sync (300ms)
    clearTimeout(logStorageDebounceTimer);
    logStorageDebounceTimer = setTimeout(() => {
      try {
        localStorage.setItem("eduquest_ext_logs", JSON.stringify(activityLogs));
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          chrome.storage.local.set({ eduquest_ext_logs: activityLogs });
        }
      } catch (e) {}
    }, 300);

    // 2. Debounced backend sync for key diagnostic events
    if (type === "success" || type === "error" || (type === "skip" && activityLogs.length % 5 === 0) || msg.includes("Lưu") || msg.includes("Bắt được")) {
      pendingBackendLogs.push({ platform: "extension", status: type, message: msg });
      clearTimeout(backendSyncDebounceTimer);
      backendSyncDebounceTimer = setTimeout(() => {
        const toSend = pendingBackendLogs.slice(-1)[0];
        pendingBackendLogs = [];
        if (toSend) {
          fetch("http://localhost:8000/api/collect/logs/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(toSend)
          }).catch(() => {});
        }
      }, 800);
    }
  }

  function renderActivityLogs() {
    const listEl = document.getElementById("eduquest-activity-list");
    if (!listEl) return;

    let filtered = activityLogs;
    if (currentLogFilter !== "all") {
      filtered = filtered.filter(l => {
        if (currentLogFilter === "skip") return l.type === "skip" || l.type === "warn";
        return l.type === currentLogFilter;
      });
    }
    if (logSearchQuery) {
      const q = logSearchQuery.toLowerCase();
      filtered = filtered.filter(l => (l.msg && l.msg.toLowerCase().includes(q)) || (l.time && l.time.includes(q)));
    }

    if (filtered.length === 0) {
      listEl.innerHTML = `<div style="color: #64748b; font-size: 11px; text-align: center; padding: 12px;">Không có log nào phù hợp bộ lọc.</div>`;
      return;
    }

    listEl.innerHTML = filtered.map(l => {
      let badgeBg = "#1e293b";
      let badgeColor = "#38bdf8";
      let tagText = "INFO";
      if (l.type === "error") {
        badgeBg = "#450a0a";
        badgeColor = "#f87171";
        tagText = "LỖI";
      } else if (l.type === "success") {
        badgeBg = "#052e16";
        badgeColor = "#4ade80";
        tagText = "OK";
      } else if (l.type === "skip" || l.type === "warn") {
        badgeBg = "#451a03";
        badgeColor = "#fbbf24";
        tagText = "BỎ QUA";
      } else if (l.type === "net") {
        badgeBg = "#3b0764";
        badgeColor = "#c084fc";
        tagText = "MẠNG";
      }

      return `
        <div style="font-size: 11px; margin-bottom: 5px; line-height: 1.4; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 3px;">
          <span style="color: #64748b;">${escapeHtml(l.time)}</span>
          <span style="background: rgba(14, 165, 233, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 0 4px; border-radius: 3px; font-size: 9px; margin: 0 3px;">[${escapeHtml(l.source || getShortUrl())}]</span>
          <span style="background: ${badgeBg}; color: ${badgeColor}; padding: 1px 5px; border-radius: 3px; font-weight: 700; font-size: 9.5px; margin: 0 4px;">[${tagText}]</span>
          <span style="color: ${badgeColor}; word-break: break-word;">${escapeHtml(l.msg)}</span>
        </div>
      `;
    }).join("");
  }

  // 1. Inject Network & WebSocket Interceptor into Page Context
  try {
    const script = document.createElement("script");
    script.src = chrome.runtime.getURL("interceptor.js");
    script.onload = function () {
      this.remove();
    };
    (document.head || document.documentElement).appendChild(script);
    addLog("Đã tiêm Network & WebSocket Interceptor v1.3.15 vào trang", "info");
  } catch (e) {
    addLog("Lỗi tiêm Interceptor: " + e.message, "error");
  }

  // 2. Listen for Network & WebSocket Captures and Telemetry Logs from Interceptor
  window.addEventListener("message", function (event) {
    if (event.source !== window || !event.data || event.data.source !== "EDUQUEST_INTERCEPTOR") {
      return;
    }

    if (event.data.type === "INTERCEPTOR_LOG" && event.data.log) {
      const l = event.data.log;
      addLog(l.msg, l.type || "net", l.detail, l.source || getShortUrl());
      return;
    }

    if (event.data.type === "NETWORK_QUESTION_CAPTURED") {
      addLog(`[MẠNG GÓI TIN] Bắt được gói tin từ ${event.data.url} (${(event.data.payload || []).length} mục)`, "net");
      processNetworkPayload(event.data.payload);
    }
  });

  // Strict Question Validator to reject junk, logs, UUIDs, game dialogs, and news/promos
  function isRealQuestionText(text, card = null) {
    if (!text || typeof text !== "string") return false;
    const clean = text.trim();
    if (clean.length < 5) return false;

    // 1. Reject UUID strings, hex hashes, or single-word token IDs
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(clean)) return false;
    if (/^[0-9a-f]{16,64}$/i.test(clean)) return false;
    if (!/\s/.test(clean) && clean.length > 20) return false;
    if (/^\d+$/.test(clean)) return false;

    // Check if card has an educational image, formula, or canvas (Never count icons, robot avatars, choice containers, stars or badges as rich content)
    const hasCardRichContent = card && Boolean(
      card.querySelector("img:not([class*='icon']):not([class*='avatar']):not([class*='logo']):not([src*='Robot']):not([src*='robot']):not([src*='star_practice']):not([src*='diamondComing']):not([src*='practiceCup']):not([src*='Practice']):not([class*='_1Z8DV']):not([class*='vjy-S']):not([class*='_3JKzW']), span.math-tex, mjx-container, [data-latex], canvas")
    );

    // 2. Reject boilerplate-only text WITHOUT rich media
    if (!hasCardRichContent && /^(bạn hãy|hãy|chọn|điền số|kéo thả|quan sát|hãy chọn|chọn đáp án|khoanh vào|nối|ghép)\s*(đáp án|đúng|thích hợp|vào ô trống|vào chỗ trống)?[\.\:\?]?$/i.test(clean)) {
      return false;
    }

    // 3. Blacklist EduQuest debug logs, timestamps, extension UI strings, system dialogs, non-question / game dialog phrases / contact info / blog descriptions
    const junkPatterns = [
      // EduQuest Debug Log entries & Timestamps
      /^\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\s*\[/i,
      /\[(?:dom|mạng|lưu csdl|tương tác|thông báo|bỏ qua|dom bỏ qua|dom bắt được|mạng bắt được|mạng gói tin|info|ok|skip|net|error|warn)\]/i,
      /\b(?:thẻ #\d+ trùng câu hỏi|trùng câu hỏi đã có|\[vio\.edu\.vn|eduquest)\b/i,
      // EduQuest Extension UI strings & buttons & modal titles
      /danh sách câu hỏi đã quét/i,
      /xem các câu hỏi đã quét/i,
      /cào tất cả câu hỏi/i,
      /quét nhanh màn hình/i,
      /tự động lưu \(zero-click\)/i,
      /nhật ký hoạt động/i,
      /debug log/i,
      // LMS / VioEdu Resume & Confirmation Dialogs, Progress Bars & Loading
      /cách tính điểm/i,
      /tổng điểm\s*</i,
      /đúng cộng \d+ điểm/i,
      /sai trừ \d+ điểm/i,
      /\b\d+\s*\/\s*100\b/,
      // VnDoc Video items, online courses, and category navigation
      /video mở đầu/i,
      /video bài đọc/i,
      /khóa học lớp \d/i,
      /học online toán/i,
      /học online tiếng việt/i,
      /học online luyện từ/i,
      /kh luyện từ/i,
      /tìm bài trong mục này/i,
      /tất cả chân trời kết nối cánh diều/i,
      /\bbạn đã hoàn thành\b/i,
      /\bhoàn thành\s*\d+\s*(?:\/\s*\d+)?\s*(?:câu|%)?/i,
      /\b\d+\s*\/\s*\d+\s*câu\b/i,
      /\b\d+%\s*$/i,
      /\bhoàn thành\s*\d+%/i,
      /tiến độ làm bài/i,
      /đang lấy thông tin câu hỏi/i,
      /đang lấy thông tin/i,
      /đang tải/i,
      /vui lòng chờ/i,
      /loading\.\.\./i,
      /viogpt-loading/i,
      /bạn đang làm bài kiểm tra/i,
      /tiếp tục từ phần đã làm trước đó/i,
      /tiếp tục làm bài/i,
      /làm lại từ đầu/i,
      /bạn có muốn tiếp tục/i,
      /chưa hoàn thành.*tiếp tục/i,
      /xác nhận nộp bài/i,
      /rời khỏi bài thi/i,
      /icrobotconfirm/i,
      // Game victory / defeat dialogs
      /chúc mừng.*chiến thắng/i,
      /bạn vừa chiến thắng/i,
      /thất bại/i,
      /cố gắng rồi/i,
      /trận đấu khốc liệt/i,
      /tiếp tục ở trận sau/i,
      /kết quả trận đấu/i,
      /bảng xếp hạng trận đấu/i,
      /chúc mừng bạn đã hoàn thành/i,
      /thời gian làm bài\s*:/i,
      /kết nối lại/i,
      /bắt đầu thi/i,
      /chuẩn bị bắt đầu/i,
      /lễ vinh danh/i,
      /chúc mừng bạn nhận được.*kim cương/i,
      /nhận được.*kim cương/i,
      /bảng xếp hạng đấu sĩ/i,
      /thông tin đấu sĩ/i,
      /nhận được huân chương/i,
      /điểm số của bạn\s*:/i,
      /rời khỏi phòng thi/i,
      /giành được cúp vàng/i,
      /lịch sử đấu/i,
      // Contact info, phone numbers, tutoring centers
      /\b0[1-9]\d{1,2}[\.\s\-]?\d{3}[\.\s\-]?\d{3,4}\b/,
      /liên hệ/i, /hotline/i, /sđt/i, /điện thoại\s*:/i, /zalo/i, /fanpage/i,
      /học phí/i, /đăng ký khóa học/i, /lớp học thêm/i, /tư vấn khóa học/i,
      // Blog posts, announcements, download links
      /ba mẹ/i, /phụ huynh/i, /tải đề thi/i, /tải tài liệu/i, /video chữa đề/i,
      /tặng miễn phí/i, /hướng dẫn dự thi/i, /lịch thi/i, /giờ thi/i, /địa điểm thi/i,
      /chuẩn bị trước ngày thi/i, /thí sinh asmo/i, /vòng quốc gia đã diễn ra/i,
      /đối chiếu đáp án/i, /tham khảo sau kỳ thi/i, /bài viết liên quan/i, /tin liên quan/i,
      /bản quyền thuộc về/i, /all rights reserved/i,
      // Contest announcements, promo combos, news titles
      /hướng dẫn học sinh tham gia/i, /hướng dẫn tham gia/i, /bài thi thử khám phá/i, /thi thử khám phá/i,
      /thông báo mở bài thi/i, /thông báo mở/i, /thông báo v\/v/i, /thông báo số/i, /thông báo kết quả/i, /thông báo tổ chức/i,
      /rộn ràng đón/i, /trăng rằm/i, /tựu trường/i, /bứt phá/i, /khám phá combo/i, /combo đồng hành/i,
      /khóa học combo/i, /ưu đãi/i, /khuyến mại/i, /thể lệ giải đấu/i, /cơ cấu giải thưởng/i,
      /danh sách nhận thưởng/i, /chúc mừng các thí sinh/i, /lễ trao giải/i,
      /tin tức & sự kiện/i, /tin nổi bật/i, /bài viết mới nhất/i, /hướng dẫn phụ huynh/i,
      /điều khoản sử dụng/i, /chính sách bảo mật/i, /quy định thi/i, /thể lệ cuộc thi/i, /vnmf/i
    ];

    for (const p of junkPatterns) {
      if (p.test(clean)) return false;
    }

    if (clean.length > 3000) return false;

    // If card has rich educational media (diagrams, math formulas, canvas), allow it only if it has educational length
    if (hasCardRichContent && clean.length >= 8) return true;

    // Must look like an educational question
    const hasMath = clean.includes("math-tex") || clean.includes("mjx-") || 
                    /[\$\\=><%]/.test(clean) ||
                    /\d+\s*[\+\-\*\/×÷=]\s*\d+/.test(clean) ||
                    /\b(hình vuông|hình tròn|hình tam giác|hình chữ nhật|hình tứ giác|hình thang|đoạn thẳng|đường thẳng|tính nhẩm|phép tính|số liền trước|số liền sau|chữ số hàng|chục|đơn vị|trăm|nghìn|mét|centimet|dm|cm|mm|kg|lít|giờ|phút|ngày|tháng|tuần|phân số|thập phân|tổng|hiệu|tích|thương|thừa số|số bị trừ|số trừ|số bị chia|số chia)\b/i.test(clean);

    const hasQuestionPrompt = /\?|câu\s*\d+|bài\s*\d+|\bbài tập khám phá\b|\bkhám phá\s*:|hoạt động|luyện tập|vận dụng|hãy chọn|chọn đáp án|\btính\b|\btìm\b|\bđiền\b|\bcho\b|\bhỏi\b|sau đây|biết rằng|hình vẽ|khoanh|đặt tính|ghép|nối|đúng ghi|sai ghi|kết quả|giá trị|số nào|đáp án|đúng|sai|có mấy|trong hình/i.test(clean);

    // Vietnamese Reading Passages & Comprehension Questions
    const hasVietnameseReadingOrEdu = clean.length >= 25 && (
      /[\?\!]\s*$/.test(clean) ||
      /\b(ai|gì|nào|đâu|sao|thế nào|tại sao|vì sao|bao nhiêu|mấy|là gì|làm gì|để làm gì|khi nào)\b/i.test(clean) ||
      /\b(đoạn văn|bài đọc|câu chuyện|nhân vật|tác giả|bài thơ|khổ thơ|từ ngữ|câu văn|tiếng việt|tập đọc|chính tả|môn|giỏi|thích|bạn bè|học sinh|trường|lớp)\b/i.test(clean)
    );

    const hasEnglishQuiz = /\b(choose|which|what|where|when|who|why|how|correct|fill|opposite|meaning|sentence|solve|calculate|find)\b/i.test(clean);

    return hasMath || hasQuestionPrompt || hasVietnameseReadingOrEdu || hasEnglishQuiz;
  }

  function processNetworkPayload(payload) {
    if (!payload) return;
    const rawItems = Array.isArray(payload) ? payload : (payload.data || payload.questions || payload.items || [payload]);
    const parsed = [];

    rawItems.forEach((item, idx) => {
      if (!item || typeof item !== "object") return;
      const rawContent = (typeof item.content === "string" ? item.content : "") ||
                         (typeof item.content_html === "string" ? item.content_html : "") ||
                         (typeof item.content_text === "string" ? item.content_text : "") ||
                         (typeof item.question_content === "string" ? item.question_content : "") ||
                         (typeof item.question_text === "string" ? item.question_text : "") ||
                         (typeof item.question_body === "string" ? item.question_body : "") ||
                         (typeof item.question_html === "string" ? item.question_html : "") ||
                         (typeof item.body === "string" ? item.body : "") ||
                         (typeof item.stem === "string" ? item.stem : "") ||
                         (typeof item.text === "string" ? item.text : "") ||
                         (typeof item.question === "string" && !/^[0-9a-f\-]{20,}$/i.test(item.question) ? item.question : "") ||
                         (item.question && typeof item.question === "object" ? (item.question.content || item.question.text || item.question.body || "") : "") ||
                         "";
      if (!rawContent || rawContent.length < 5) return;

      const cleanText = item.content_text && typeof item.content_text === "string" ? item.content_text : cleanHtmlToText(rawContent);
      const isPreValidated = Boolean(item.skillName || item.questionType || (Array.isArray(item.options) && item.options.length >= 2));
      if (!isPreValidated && !isRealQuestionText(cleanText)) {
        addLog(`[MẠNG BỎ QUA] Không đủ tiêu chuẩn câu hỏi: '${cleanText.substring(0, 32)}...'`, "skip");
        return;
      }

      // Extract options / answers first to include in signature
      const rawOptions = item.options || item.answers || item.list_answer || item.list_answers ||
                         item.choices || item.suggests || item.selects || item.options_list || item.list_suggests ||
                         (item.question && typeof item.question === "object" ? (item.question.answers || item.question.options) : []) || [];
      const options = [];
      let correctAns = item.correct_answer || item.right_answer || (item.question && (item.question.right_answer || item.question.correct_answer)) || null;

      if (Array.isArray(rawOptions)) {
        rawOptions.forEach((opt, oIdx) => {
          const optLetter = (typeof opt === "object" && opt.id && typeof opt.id === "string") ? opt.id : String.fromCharCode(65 + oIdx);
          const optText = typeof opt === "string" ? opt : (opt.content || opt.text || opt.title || opt.name || opt.value || "");
          const isCorrect = (typeof opt === "object" && (opt.is_correct || opt.correct || opt.is_right)) || optLetter === correctAns;
          if (isCorrect && !correctAns) correctAns = optLetter;
          options.push({
            id: optLetter,
            content: cleanOptionContent(optText),
            is_correct: isCorrect
          });
        });
      }

      let qId = item.id;
      if (!qId || (!String(qId).startsWith("net_") && !String(qId).startsWith("vio_"))) {
        qId = "net_" + (item.question_id || (item.question && item.question.id) || Date.now() + "_" + idx);
      }

      const optSig = options.map(o => o.content).join(" ");
      const sig = (cleanText + " " + optSig).toLowerCase().replace(/\s+/g, " ");
      if (isAlreadyCaptured(sig, qId)) {
        addLog(`[MẠNG BỎ QUA] Trùng câu hỏi trong phiên (Signature Hash): '${cleanText.substring(0, 32)}...'`, "skip");
        return;
      }

      savedTextSignatures.add(sig);
      savedQuestionIds.add(qId);

      parsed.push({
        id: qId,
        source_platform: item.source_platform || getPlatformName(),
        source_url: item.source_url || window.location.href,
        exam_name: item.exam_name || document.title || "Đề thi trực tuyến",
        grade: item.grade || detectGrade(),
        subject: item.subject || "math",
        topic: item.topic || item.skillName || item.skill_name || item.unit || "Luyện tập & Đấu trường",
        question_type: item.question_type || (options.length > 0 ? "single_choice" : "fill_blank"),
        content_html: item.content_html || rawContent || cleanText,
        content_text: cleanText,
        images: Array.isArray(item.images) && item.images.length > 0 ? item.images : extractImagesFromHtml(rawContent),
        options: options,
        correct_answer: correctAns,
        explanation: item.explanation || item.guide || item.solution || "",
        difficulty: item.difficulty || item.level || "medium"
      });
    });

    if (parsed.length > 0) {
      addLog(`[MẠNG BẮT ĐƯỢC] Bắt thành công ${parsed.length} câu hỏi từ API mạng`, "success");
      handleNewQuestions(parsed, "Network/WebSocket API");
    }
  }

  function cleanOptionContent(htmlOrText) {
    if (!htmlOrText) return "";
    let str = String(htmlOrText).trim();
    // Remove leading A., B., C., D.
    str = str.replace(/^[A-D]\s*[\.\:\)]\s*/i, "").trim();
    return str;
  }

  function getPlatformName() {
    const host = window.location.hostname.toLowerCase();
    if (host.includes("vio.edu.vn")) return "vioedu";
    if (host.includes("tnmath.edu.vn") || host.includes("trangnguyen.edu.vn")) return "tnmath";
    if (host.includes("hanhtrangso.nxbgd.vn")) return "hanhtrangso";
    if (host.includes("vietjack.com")) return "vietjack";
    if (host.includes("loigiaihay.com")) return "loigiaihay";
    if (host.includes("vndoc.com")) return "vndoc";
    if (host.includes("hoc247.net")) return "hoc247";
    if (host.includes("olm.vn")) return "olm";
    if (host.includes("k5learning.com")) return "k5learning";
    if (host.includes("ixl.com")) return "ixl";
    if (host.includes("khanacademy.org")) return "khanacademy";
    if (host.includes("kangaroo")) return "kangaroo";
    if (host.includes("timo")) return "timo";
    if (host.includes("hkimo")) return "hkimo";
    if (host.includes("asmo")) return "asmo";
    if (host.includes("ioe.vn")) return "ioe";
    return "online_learning";
  }

  function detectGrade() {
    const url = window.location.href.toLowerCase();
    const title = (document.title || "").toLowerCase();
    const bodyHead = (document.body ? document.body.innerText.substring(0, 3000) : "").toLowerCase();
    const fullText = title + " " + bodyHead + " " + url;

    // 1. Check English ordinals in URL
    const ordinalMap = {
      "first-grade": 1, "1st-grade": 1,
      "second-grade": 2, "2nd-grade": 2,
      "third-grade": 3, "3rd-grade": 3,
      "fourth-grade": 4, "4th-grade": 4,
      "fifth-grade": 5, "5th-grade": 5,
      "sixth-grade": 6, "6th-grade": 6,
      "seventh-grade": 7, "7th-grade": 7,
      "eighth-grade": 8, "8th-grade": 8,
      "ninth-grade": 9, "9th-grade": 9,
      "tenth-grade": 10, "10th-grade": 10,
      "eleventh-grade": 11, "11th-grade": 11,
      "twelfth-grade": 12, "12th-grade": 12
    };
    for (const [key, val] of Object.entries(ordinalMap)) {
      if (url.includes(key)) return val;
    }

    // 2. Check standard regex patterns across query params, path, title, and body
    const m = url.match(/classes=([1-9]|1[0-2])\b/) ||
              url.match(/(?:toan-lop|lop|grade)-([1-9]|1[0-2])\b/) ||
              fullText.match(/lớp\s*([1-9]|1[0-2])\b/) ||
              fullText.match(/khối\s*([1-9]|1[0-2])\b/) ||
              fullText.match(/grade\s*([1-9]|1[0-2])\b/);
    if (m) return parseInt(m[1]);

    // 3. Fallback to user-selected grade in local storage if present
    try {
      const saved = localStorage.getItem("eduquest_selected_grade") || localStorage.getItem("eduquest_default_grade");
      if (saved) {
        const parsed = parseInt(saved);
        if (parsed >= 1 && parsed <= 12) return parsed;
      }
    } catch (e) {}

    return 5;
  }

  function detectSubject() {
    const host = window.location.hostname.toLowerCase();
    const title = (document.title || "").toLowerCase();
    const url = window.location.href.toLowerCase();

    // 1. Strict Priority 1: Check document title and URL explicitly
    if (title.includes("toán") || title.includes("math") || url.includes("/toan-") || url.includes("/math-") || url.includes("tnmath")) return "math";
    if (title.includes("tiếng việt") || title.includes("tieng-viet") || title.includes("tieng viet") || title.includes("ngữ văn") || title.includes("luyện từ và câu") || title.includes("tập đọc") || title.includes("chính tả")) return "vietnamese";
    if (title.includes("tiếng anh") || title.includes("tieng-anh") || title.includes("english") || url.includes("/tieng-anh") || url.includes("ioe.vn")) return "english";
    if (title.includes("khoa học") || title.includes("science")) return "science";
    if (title.includes("lịch sử") || title.includes("địa lí")) return "history";

    // 2. Check breadcrumbs or specific subject headers in DOM
    const subjectEl = document.querySelector(".subject-name, .breadcrumb, .exam-subject, [class*='subject']");
    if (subjectEl) {
      const sTxt = subjectEl.innerText.toLowerCase();
      if (sTxt.includes("toán") || sTxt.includes("math")) return "math";
      if (sTxt.includes("tiếng việt") || sTxt.includes("ngữ văn")) return "vietnamese";
      if (sTxt.includes("tiếng anh") || sTxt.includes("english")) return "english";
    }

    if (host.includes("k5learning") || host.includes("ixl") || host.includes("khanacademy")) {
      return "math";
    }

    return "math";
  }

  function isEduLearningActive() {
    const host = window.location.hostname.toLowerCase();
    if (host.includes("vndoc.com")) {
      const p = window.location.pathname.toLowerCase();
      // On VnDoc, only active on actual quiz/test/exercise pages, never on root homepage or video indices
      if (p.includes("/trac-nghiem-") || p.includes("/de-thi-") || p.includes("/bai-tap-") || p.includes("/de-kiem-tra-") || p.includes("/phieu-bai-tap-")) return true;
      return Boolean(document.querySelector(".cau-hoi, .bai-tap, .question-item, .item-quiz, .content-question, [class*='question-item']"));
    }
    if (host.includes("vio.edu.vn") || host.includes("trangnguyen.edu.vn") ||
        host.includes("tnmath.edu.vn") || host.includes("hanhtrangso.nxbgd.vn") ||
        host.includes("vietjack.com") || host.includes("loigiaihay.com") ||
        host.includes("hoc247.net") ||
        host.includes("olm.vn") || host.includes("k5learning.com") ||
        host.includes("ixl.com") || host.includes("khanacademy.org") ||
        host.includes("kangaroo-math.vn") || host.includes("commoncoresheets.com") ||
        host.includes("math-drills.com") || host.includes("lmsfermat.edu.vn") ||
        host.includes("asmo.vn") || host.includes("violympic.vn") || host.includes("ioe.vn")) {
      return true;
    }
    return Boolean(document.querySelector(
      "app-question-render, app-render-question, app-practice-question, app-question-item, " +
      ".box.box--practice, .box--practice, .box--practice__content, .practice-question-text, " +
      ".choice-answer-grid-2026, .box-practice-content, .practice-exercise, .practice-item-content, .content-question-box, " +
      ".interactive-activity, .activity-item, .cau-hoi, .bai-tap"
    ));
  }

  function cleanHtmlToText(html) {
    if (!html) return "";
    const div = document.createElement("div");
    div.innerHTML = html;
    return div.innerText.replace(/\s+/g, " ").trim();
  }

  function extractCleanMathText(container, preserveParagraphs = false) {
    if (!container) return "";
    try {
      const clone = container.cloneNode(true);
      // Replace MathJax / MathTeX spans with their aria-label, data-latex, or annotation text
      clone.querySelectorAll(".math-tex, mjx-container, .mjpage, .mjx-math, [data-latex]").forEach(mathEl => {
        const tex = mathEl.getAttribute("data-latex") || 
                    mathEl.getAttribute("aria-label") || 
                    (mathEl.querySelector("[aria-label]") ? mathEl.querySelector("[aria-label]").getAttribute("aria-label") : "") ||
                    (mathEl.querySelector("annotation[encoding='application/x-tex']") ? mathEl.querySelector("annotation[encoding='application/x-tex']").textContent : "");
        if (tex) {
          mathEl.replaceWith(document.createTextNode(" " + tex.trim() + " "));
        }
      });
      // Replace select dropdown placeholders with [ ... ]
      clone.querySelectorAll(".Select-placeholder, .display-inlineblock-select, .Select-value-label").forEach(selEl => {
        const val = (selEl.innerText || "").trim();
        selEl.replaceWith(document.createTextNode(" [ " + (val && val !== "Chọn" ? val : "...") + " ] "));
      });

      if (preserveParagraphs) {
        // Collect paragraphs or lines with preserved line breaks for reading passages
        const text = clone.innerText || "";
        return text.split("\n").map(l => l.trim()).filter(Boolean).join("\n\n");
      }
      return clone.innerText.replace(/\s+/g, " ").trim();
    } catch (e) {
      return (container.innerText || "").replace(/\s+/g, " ").trim();
    }
  }

  // Helper: Find the genuine Question Card enclosing a clicked or scanned element (Never stops at answer grids or extension UI)
  function findEnclosingQuestionCard(el) {
    if (!el || (el.closest && el.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest'], ._1Tl2B, ._1pVpr, ._1MIz2, ._1ZsoA, .score-hint-popup, ._52PcN, ._1Z8DV, [class*='score-hint'], .home-video-item, .video-item, nav, header, footer"))) {
      return null;
    }

    // 1. Direct match with standard known card containers
    const directCard = el.closest(
      ".box.box--practice, .box--practice, .box--practice__content, " +
      ".practice-question-text, .panel.panel-primary.practice-question-text, " +
      "[class*='box--practice'], [class*='practice-question'], " +
      "[class*='onboard-flow__question'], [class*='onboard-question'], [class*='onboard__question'], " +
      "[class*='onboard-flow'], [class*='onboard_flow'], [class*='onboard-container'], " +
      "[class*='assessment-question'], [class*='assessment-item'], [class*='assessment_content'], " +
      "[class*='question-layout'], [class*='question-wrapper'], [class*='question-content-wrap'], " +
      "app-question-render, app-render-question, app-practice-question, app-question-item, " +
      ".box-practice-content, .practice-exercise, .practice-item-content, .content-question-box, " +
      ".question-render, .question-view-area, .exercise-content, .box-practice, .question-panel, " +
      ".step-question, .question-step, .practice-question, .content-practice, " +
      ".interactive-activity, .activity-item, .quiz-content, .cau-hoi, .bai-tap, " +
      ".question-container, .question-box, .question-item, .box-question, .detail-question, .exam-item"
    );

    // If directCard is inside extension UI or VioEdu score/header or nav/video, reject
    if (directCard && directCard.closest && directCard.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest'], ._1Tl2B, ._1pVpr, ._1MIz2, ._1ZsoA, .score-hint-popup, ._52PcN, ._1Z8DV, [class*='score-hint'], .home-video-item, .video-item, nav, header, footer")) {
      return null;
    }

    // If directCard is NOT just an answer grid, return it
    if (directCard && !directCard.matches(".choice-answer-grid-2026, [class*='choice-answer-grid'], .list-answer, .box-answer, .answers")) {
      return directCard;
    }

    // 2. Ascend parent chain to find the container holding both stem/reading text and answer choices
    let curr = el;
    while (curr && curr !== document.body && curr !== document.documentElement) {
      const parent = curr.parentElement;
      if (!parent) break;
      if (parent.closest && parent.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest']")) {
        break;
      }

      try {
        const pClone = parent.cloneNode(true);
        pClone.querySelectorAll(
          ".choice-answer-grid-2026, [class*='choice-answer'], .list-answer, .box-answer, " +
          ".item-answer, button, nav, .eduquest-widget, #eduquest-floating-widget, #eduquest-scanned-modal, [class*='eduquest'], header, footer"
        ).forEach(n => n.remove());

        const remainingText = (pClone.innerText || "").trim();
        // If remaining text has meaningful educational reading or question (>= 15 chars)
        if (remainingText.length >= 15 && remainingText.length < 3500 && !/^(đăng nhập|trang chủ|menu|chọn lớp)/i.test(remainingText)) {
          return parent;
        }
      } catch (e) {}

      curr = parent;
    }

    return directCard || el;
  }

  function extractCardStem(card, el) {
    if (!card) return { rawText: "", rawHtml: "" };

    const QUESTION_PREFIX_REGEX = /^(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*(?:tập)?\s*\d+)[\s\.\:\-_]*/i;

    // Helper to strip toolbar/control junk and question numbers from title elements
    function cleanTitleElement(targetEl) {
      if (!targetEl) return "";
      try {
        const tClone = targetEl.cloneNode(true);
        tClone.querySelectorAll(".pull-right, .pull-left, .box-choice-note, [data-skill-test-font-size], ._3-L-1, ._1jXLW, ._3xuCG, .cicn, [class*='font-size'], [class*='note'], button, input, i.fa").forEach(n => n.remove());
        const tText = extractCleanMathText(tClone).trim();
        // If title element is only a question index/number, return empty string so it is not appended
        if (!tText || (QUESTION_PREFIX_REGEX.test(tText) && tText.length <= 30)) {
          return "";
        }
        return tText.replace(QUESTION_PREFIX_REGEX, "").trim();
      } catch (e) {
        const tText = extractCleanMathText(targetEl).trim();
        if (!tText || (QUESTION_PREFIX_REGEX.test(tText) && tText.length <= 30)) return "";
        return tText.replace(QUESTION_PREFIX_REGEX, "").trim();
      }
    }

    // Gold Standard: Clone the card and surgically strip out ALL answer choices, option buttons, action buttons, toolbars, and note controls
    try {
      const clone = card.cloneNode(true);
      
      // Strip answer containers, choices, widgets, action buttons, timer, font controls, note badges, question number headings
      const junkAndAnswerSelectors = [
        // Question number / index headings
        ".panel-heading", ".practice-question-title", ".question-title", ".title-question", ".box-question-title",
        ".cau-hoi-so", ".question-number", ".question-index", ".stt-cau-hoi", "[class*='question-number']",
        "[class*='question-index']", "[class*='cau-hoi-so']",
        // VioEdu Note, Font Controls, Status Bars, Audio controls
        ".box-choice-note", "[class*='box-choice-note']", "[class*='choice-note']", ".note-choice", ".badge-note",
        "[data-skill-test-font-size]", "[class*='font-size']", ".font-resizer", ".font-controls", ".font-zoom",
        ".pull-right", ".pull-left",
        ".sound-speaker", ".btn-sound", ".audio-player", ".audio-control",
        ".action-toolbar", ".question-toolbar", ".tools-bar", ".question-tools",
        ".box-status", ".status-box", ".status-question",
        "._3-L-1", "._1jXLW", "._3xuCG", ".cicn", "._76BfG",
        "input[type='checkbox']",
        // EduQuest UI Elements
        ".eduquest-widget", ".eduquest-toast", "#eduquest-floating-widget", "#eduquest-scanned-modal",
        ".eduquest-panel", ".eduquest-modal-overlay", ".eduquest-modal-window", "#eduquest-activity-list", ".eduquest-log-item",
        // Choices and Answers
        ".choice-answer-grid-2026", "[class*='choice-answer-grid']", "[class*='choice-answer']",
        ".list-answer", ".box-answer", ".item-answer", ".answer-item", ".answer-box", ".btn-answer",
        ".list-suggest", ".suggest-item", ".item-suggest", ".box-suggest", "[class*='suggest']",
        ".Select-menu-outer", "[role='listbox']",
        "button", "nav", "footer", ".header", ".timer", ".clock", ".countdown",
        ".btn--practice", ".btn-submit", ".btn-next", ".btn-tiep",
        ".explain-box", ".loi-giai", ".practice-explain", ".ZpmD_", "._3yoLK"
      ];
      clone.querySelectorAll(junkAndAnswerSelectors.join(", ")).forEach(n => n.remove());

      // Surgical sweep: also remove any children whose text is strictly a question number
      clone.querySelectorAll("div, span, h3, h4, h5, p, strong, b").forEach(n => {
        const txt = (n.innerText || n.textContent || "").trim();
        if (txt && QUESTION_PREFIX_REGEX.test(txt) && txt.length <= 30 && !n.querySelector("div, p, img")) {
          n.remove();
        }
      });

      let cleanStem = extractCleanMathText(clone, true);
      cleanStem = cleanStem.replace(QUESTION_PREFIX_REGEX, "").trim();

      // Clean HTML from clone
      let cleanStemHtml = clone.innerHTML.trim();
      // Remove any lingering panel-heading tags
      cleanStemHtml = cleanStemHtml.replace(/<div[^>]*class="[^"]*panel-heading[^"]*"[^>]*>.*?<\/div>/gis, "").trim();
      cleanStemHtml = cleanStemHtml.replace(/^(?:<[^>]+>)*\s*(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*(?:tập)?\s*\d+)[\s\.\:\-_]*/i, "").trim();

      // If stripped clone yields substantive reading passage or question text (>= 8 chars)
      if (cleanStem && cleanStem.length >= 8) {
        return { rawText: cleanStem, rawHtml: cleanStemHtml };
      }
    } catch (err) {}

    // Fallback: If stripped clone was empty, inspect structured title & body elements
    const titleEl = card.querySelector(".panel-heading, .practice-question-title, .question-title, .title-question, .box-question-title, .activity-title, .quiz-title, .instruct, .question-instruct, .title, .prompt");
    const bodyEl = card.querySelector(".practice-question-text .panel-body, .practice-question-text, .box--practice__content .panel-body, .box--practice .panel-body, .reading-passage, .reading-text, .passage, .paragraph-content, .content-question, .question-content, .question-text, .detail-content, .math-content, .arena-text, .activity-text, .stem, .question-body, .body-question, .content-practice, .exercise-content, .box-practice-content, .problem-content, .math-tex-container, .question-main, .question-render, .render-question");

    let rawText = "";
    let rawHtml = "";

    if (titleEl && bodyEl && titleEl !== bodyEl) {
      const tText = cleanTitleElement(titleEl);
      let bText = extractCleanMathText(bodyEl, true);
      bText = bText.replace(QUESTION_PREFIX_REGEX, "").trim();
      rawText = [tText, bText].filter(Boolean).join("\n\n");
      rawHtml = (tText ? titleEl.outerHTML + "\n" : "") + bodyEl.outerHTML;
    } else if (bodyEl) {
      rawText = extractCleanMathText(bodyEl, true).replace(QUESTION_PREFIX_REGEX, "").trim();
      rawHtml = bodyEl.outerHTML;
    } else if (titleEl) {
      const tText = cleanTitleElement(titleEl);
      rawText = tText;
      rawHtml = tText ? titleEl.outerHTML : "";
    } else {
      const contentEl = card.querySelector("h3, h4, p strong, .cau-hoi, .stem, .content-question, .question-body") || el || card;
      rawText = extractCleanMathText(contentEl, true).replace(QUESTION_PREFIX_REGEX, "").trim();
      rawHtml = contentEl.innerHTML || "";
    }
    return { rawText, rawHtml };
  }

  // 3. Precise DOM Scanner: Target specific Question Cards (No whole-page bleeding)
  function scanPageQuestions(force = false, isBackground = false) {
    if (force) {
      rebuildSignatures();
      if (!capturedQuestions || capturedQuestions.length === 0) {
        savedQuestionIds.clear();
        savedTextSignatures.clear();
      }
    }
    let questions = [];

    // Distinct question card selectors across VioEdu, Hành Trang Số, Trạng Nguyên
    const questionCardSelectors = [
      // VioEdu Question Components, Cards & Onboard Assessment Flows
      ".box.box--practice", ".box--practice", ".box--practice__content",
      ".practice-question-text", ".panel.panel-primary.practice-question-text",
      "[class*='box--practice']", "[class*='practice-question']",
      "[class*='onboard-flow__question']", "[class*='onboard-question']", "[class*='onboard__question']",
      "[class*='onboard-flow']", "[class*='onboard_flow']", "[class*='onboard-container']",
      "[class*='assessment-question']", "[class*='assessment-item']", "[class*='assessment_content']",
      "[class*='question-layout']", "[class*='question-wrapper']", "[class*='question-content-wrap']",
      "app-question-render", "app-render-question", "app-practice-question", "app-question-item",
      "app-question-view", "app-quiz-question", "app-exercise-question", "app-arena-question",
      ".box-practice-content", ".practice-exercise", ".practice-item-content", ".content-question-box",
      ".question-render", ".question-view-area", ".exercise-content", ".box-practice", ".question-panel",
      ".step-question", ".question-step", ".practice-question", ".content-practice", ".item-cau-hoi",
      // Hành Trang Số (NXBGD) Interactive Activities & E-Books
      ".interactive-activity", ".activity-item", ".quiz-content", ".question-wrapper",
      ".activity-box", ".exercise-box", ".content-quiz", ".activity-question", ".question-view",
      // Trạng Nguyên, VietJack, Lời Giải Hay, VnDoc, Hoc247
      ".cau-hoi", ".bai-tap", ".quiz-item", ".item-quiz", ".question-wrap",
      // Generic LMS Question Containers
      ".question-container", ".question-box", ".question-item", ".detail-question",
      ".content-question", ".box-question", ".box-cau-hoi", ".exam-content", ".exam-item"
    ];

    let containers = Array.from(document.querySelectorAll(questionCardSelectors.join(", ")))
      .filter(el => !el.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest'], ._1Tl2B, ._1pVpr, ._1MIz2, ._1ZsoA, .score-hint-popup, ._52PcN, ._1Z8DV, [class*='score-hint'], .home-video-item, .video-item, nav, header, footer, .menu, .sidebar"));

    // CRITICAL: Filter out nested child containers if ancestor card is already selected
    containers = containers.filter(el => !containers.some(p => p !== el && p.contains(el)));

    if (containers.length > 0) {
      containers.forEach((el, idx) => {
        const q = extractQuestionFromElement(el, idx, isBackground);
        if (q) questions.push(q);
      });
    }

    // Fallback: If no structured question cards found, locate choice grids and ascend to their parent cards
    if (questions.length === 0) {
      const choiceGrids = Array.from(document.querySelectorAll(".choice-answer-grid-2026, [class*='choice-answer-grid']"))
        .filter(cg => !cg.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest'], ._1Tl2B, ._1pVpr, ._1MIz2, ._1ZsoA, .score-hint-popup, ._52PcN, ._1Z8DV, [class*='score-hint'], .home-video-item, .video-item, nav, header, footer, .menu, .sidebar"));
      if (choiceGrids.length > 0) {
        choiceGrids.forEach((cg, idx) => {
          const card = findEnclosingQuestionCard(cg);
          if (card && card !== cg) {
            const q = extractQuestionFromElement(card, idx, isBackground);
            if (q) questions.push(q);
          }
        });
      }
    }

    // Fallback 2: If still no questions found, search for text containing "Câu"
    if (questions.length === 0) {
      questions = scanByTextHeuristic();
    }

    if (questions.length > 0) {
      addLog(`DOM Scanner: Bắt được ${questions.length} câu hỏi mới kèm đáp án`, "success");
      handleNewQuestions(questions, "Deep DOM Scanner");
    }
    return questions;
  }

  function extractQuestionFromElement(el, idx, isBackground = false) {
    if (!el || (el.closest && el.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest'], ._1Tl2B, ._1pVpr, ._1MIz2, ._1ZsoA, .score-hint-popup, ._52PcN, ._1Z8DV, [class*='score-hint'], .home-video-item, .video-item, nav, header, footer, .menu, .sidebar"))) {
      return null;
    }

    // Helper: Verify if an element is actively displaying a loading spinner/state
    function isElementActiveLoading(targetNode) {
      if (!targetNode || targetNode.offsetParent === null) return false;
      if (targetNode.matches && targetNode.matches("[data-vio-loading='true'], .loading-spinner")) return true;
      const sp = targetNode.querySelector && targetNode.querySelector("[data-vio-loading='true'], .loading-spinner");
      if (sp && sp.offsetParent !== null) return true;
      const txt = (targetNode.innerText || "").trim();
      if (/đang\s+(?:lấy\s+thông\s+tin|tải)\s+câu\s+hỏi/i.test(txt)) return true;
      return false;
    }

    // 1. Loading check: Skip ONLY when CURRENT question element is actively loading
    if (isElementActiveLoading(el)) {
      return null;
    }

    // 2. Progress bar check: Skip if element itself is a progress bar component
    if (el.matches && el.matches(".irXzU, ._1WeAM, .Vt514, .progress-bar, .stepper-bar, .progress-circle, [class*='stepper-item'], ._1Tl2B, ._1pVpr, ._1MIz2, ._1ZsoA, .score-hint-popup, ._52PcN, ._1Z8DV")) {
      return null;
    }

    // Expand to genuine enclosing card (Do NOT stop at choice grids)
    const card = findEnclosingQuestionCard(el) || el;

    if (isElementActiveLoading(card)) {
      return null;
    }

    // 2. Question stem with multi-part support (Title instruction + Reading body + Problem prompt)
    const { rawText, rawHtml } = extractCardStem(card, el);

    // 3. Reject non-question junk & battle popups
    if (!isRealQuestionText(rawText, card)) {
      if (!isBackground && rawText && rawText.length >= 8) {
        addLog(`[DOM BỎ QUA] Thẻ #${idx + 1} không đủ chuẩn câu hỏi giáo dục: '${rawText.substring(0, 32)}...'`, "skip");
      }
      return null;
    }

    // 4. Extract options from enclosing card
    const optEls = card.querySelectorAll(
      // VioEdu Choice Grid & Interactive Buttons
      ".choice-answer-grid-2026 ._2UU-q, .choice-answer-grid-2026 ._27IHb, [class*='choice-answer'] [role='button'], " +
      "[class*='choice-answer'] ._2UU-q, [role='button']._2UU-q, [class*='choice-answer'] label, " +
      "[class*='choice-answer-grid'] > div, [class*='choice-answer'] input[type='radio'], " +
      // Drag and Drop & Matching
      "[draggable='true'], [class*='draggable'], [class*='matching-item'], [class*='match-box'], " +
      // Select dropdowns
      ".Select-option, [role='option'], .Select-menu-outer div, " +
      // Standard LMS option selectors
      ".item-answer, .answer-item, .item-ans, .ans-item, .option-item, .choice-item, " +
      ".item-suggest, .suggest-item, .box-suggest > *, .list-suggest > *, [class*='suggest'], " +
      ".arena-answer, .box-answer, [class*='item-answer'], [class*='answer-content'], " +
      "button[class*='answer'], .list-answer > div, .list-answer > button, .answer-box, " +
      ".btn-answer, app-answer-item, .answer-text, label[class*='answer'], label[class*='item'], " +
      ".activity-option, .choice, .opt, [class*='radio-item'], [class*='checkbox-item'], " +
      ".dap-an, .answer-label"
    );

    const options = [];
    const seenOptTexts = new Set();

    optEls.forEach((optEl) => {
      let optContent = extractCleanMathText(optEl);
      if (!optContent) {
        const img = optEl.querySelector("img");
        if (img && img.src) optContent = img.src;
      }

      if (!optContent || optContent.length > 300) return;
      if (/^(nộp bài|bỏ qua|tiếp tục|xem kết quả|hoàn thành|quay lại|trả lời|thực hiện|câu hỏi sau)$/i.test(optContent)) return;
      if (optContent === rawText) return; // Don't include whole question text as option

      let cleanOptText = cleanOptionContent(optContent);
      if (!cleanOptText) cleanOptText = optContent;

      const optKey = cleanOptText.toLowerCase();
      if (seenOptTexts.has(optKey)) return;
      seenOptTexts.add(optKey);

      const isCorrect = optEl.classList.contains("active") || 
                        optEl.classList.contains("selected") || 
                        optEl.classList.contains("correct") || 
                        Boolean(optEl.querySelector("input:checked, [class*='checked']")) || 
                        (optEl.parentElement && Boolean(optEl.parentElement.querySelector("input:checked")));

      const oIdx = options.length;
      options.push({
        id: String.fromCharCode(65 + oIdx),
        content: cleanOptText,
        is_correct: isCorrect
      });
    });

    // Strict Anti-Collision Check: stem must NEVER be just a concatenation of option choices!
    if (options.length >= 2) {
      const optClean = options.map(o => (o.content || "").toLowerCase().replace(/\s+/g, ""));
      const joinedOpts = optClean.join("");
      const stemClean = (rawText || "").toLowerCase().replace(/\s+/g, "");

      if (joinedOpts && (stemClean === joinedOpts || (stemClean.length <= joinedOpts.length + 6 && optClean.every(c => stemClean.includes(c))))) {
        if (!isBackground) addLog(`[DOM BỎ QUA] Thẻ #${idx + 1} bóc tách nhầm lưới đáp án làm đề bài: '${rawText.substring(0, 30)}...'`, "skip");
        return null;
      }
    }

    // Strict check on is_correct: If all options or multiple options are marked correct in a standard single-choice question, reset all to false (false positive from layout classes)
    const correctOpts = options.filter(o => o.is_correct);
    if (options.length > 1 && (correctOpts.length > 1 || correctOpts.length === options.length)) {
      const genuinelyChecked = [];
      optEls.forEach((optEl, oIdx) => {
        const hasCheckedInput = Boolean(optEl.querySelector("input[type='radio']:checked, input[type='checkbox']:checked"));
        const hasAriaChecked = optEl.getAttribute("aria-checked") === "true" || optEl.getAttribute("aria-pressed") === "true";
        if (hasCheckedInput || hasAriaChecked) {
          genuinelyChecked.push(oIdx);
        }
      });

      if (genuinelyChecked.length === 1) {
        options.forEach((o, oIdx) => {
          o.is_correct = (oIdx === genuinelyChecked[0]);
        });
      } else {
        options.forEach(o => {
          o.is_correct = false;
        });
      }
    }

    // Fill blank extra check: If 0 options, ensure it has genuine question prompt or math formula
    if (options.length === 0) {
      const hasDirectPrompt = /\?|\b(?:hỏi|tính|tìm|điền|bao nhiêu|mấy|kết quả|giá trị|đúng ghi|sai ghi|cho biết)\b/i.test(rawText);
      const hasMathFormula = /[\$\\=><%]|\d+\s*[\+\-\*\/×÷=]\s*\d+/.test(rawText);
      if (rawText.length < 70 && !hasDirectPrompt && !hasMathFormula) {
        return null;
      }
    }

    // Compute distinct signature incorporating normalized question stem and options
    const normStem = normalizeStemForSignature(rawText);
    const optSigStr = options.map(o => o.content).join(" ");
    const sig = (normStem + " " + optSigStr).toLowerCase().replace(/\s+/g, " ");
    const qId = "dom_" + (card.id || (Date.now() + "_" + idx));

    if (isAlreadyCaptured(sig, qId)) {
      if (!isBackground && lastLoggedSkipSig !== sig) {
        lastLoggedSkipSig = sig;
        addLog(`[DOM BỎ QUA] Thẻ #${idx + 1} trùng câu hỏi đã có: '${rawText.substring(0, 32)}...'`, "skip");
      }
      return null;
    }

    // Check for fill_blank inputs
    const hasInput = Boolean(card.querySelector("input[type='text'], input[type='number'], textarea, .input-answer, app-fill-blank, .input-fill, input.fill-in-blank, input.form-control"));
    const questionType = options.length > 1 ? "single_choice" : (hasInput ? "fill_blank" : (options.length === 1 ? "single_choice" : "fill_blank"));

    savedTextSignatures.add(sig);
    savedQuestionIds.add(qId);

    const platform = getPlatformName();
    let topicName = "Bài học & Luyện tập";
    if (platform === "vioedu") topicName = "VioEdu Luyện tập & Đấu trường";
    else if (platform === "hanhtrangso") topicName = "Hành Trang Số - Sách Giáo Khoa";
    else if (platform === "tnmath") topicName = "Trạng Nguyên Luyện thi";

    let detectedSubj = detectSubject();
    const hasVnDiacritics = /[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]/i.test(rawText);
    const hasMathSigns = /[\$\\=><%]|\d+\s*[\+\-\*\/×÷=]\s*\d+|\b(hình|phép tính|số liền|đoạn thẳng|dm|cm|mm|kg|lít|giờ|phút|cộng|trừ|nhân|chia|tổng|hiệu|tích|thương)\b/i.test(rawText);
    const hasVnLangSignals = /\b(ai là gì|ai làm gì|ai thế nào|đặc điểm|dấu phẩy|dấu chấm|vần|âm đầu|chính tả|từ ngữ|từ chỉ|đoạn văn|bài đọc|câu chuyện|nhân vật|cho thấy điều gì|ý nghĩa|tập làm văn|sắp xếp|tiếng bắt đầu|điền âm|vần s|âm s|âm x)\b/i.test(rawText);

    if (hasVnDiacritics && !hasMathSigns) {
      if (hasVnLangSignals || rawText.length >= 45) {
        detectedSubj = "vietnamese";
      }
    } else if (hasMathSigns) {
      detectedSubj = "math";
    }

    const explainEl = card.querySelector(".ZpmD_, ._3yoLK, .explanation, .explain-box, .loi-giai, .practice-explain, [class*='explanation']");
    const explanationText = explainEl ? extractCleanMathText(explainEl) : "";

    addLog(`[DOM BẮT ĐƯỢC] Đã trích xuất câu hỏi (${options.length} đáp án): '${rawText.substring(0, 35).replace(/\s+/g, ' ')}...'`, "success");

    return {
      id: qId,
      source_platform: platform,
      source_url: window.location.href,
      exam_name: document.title || "Bài học & Luyện tập",
      grade: detectGrade(),
      subject: detectedSubj,
      topic: topicName,
      question_type: questionType,
      content_html: rawHtml || rawText,
      content_text: rawText,
      images: extractImagesFromElement(card),
      options: options,
      correct_answer: null,
      explanation: explanationText,
      difficulty: "medium"
    };
  }

  function scanByTextHeuristic() {
    const list = [];
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_ELEMENT,
      {
        acceptNode(node) {
          // STRICT: Reject all EduQuest extension UI nodes & descendants
          if (node.closest && node.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest']")) {
            return NodeFilter.FILTER_REJECT;
          }
          if (node.tagName === "SCRIPT" || node.tagName === "STYLE" || node.tagName === "BUTTON" || node.tagName === "A" || node.tagName === "NAV" || node.tagName === "HEADER" || node.tagName === "FOOTER") {
            return NodeFilter.FILTER_REJECT;
          }
          if (node.closest && node.closest("a, nav, header, footer, .menu, .sidebar, .video-item, .home-video-item, .ul-one, .breadcrumb, [class*='nav'], [class*='menu']")) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );
    let node;
    while ((node = walker.nextNode())) {
      if (node.closest && node.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest'], ._1Tl2B, ._1pVpr, ._1MIz2, ._1ZsoA, .score-hint-popup, ._52PcN, ._1Z8DV, [class*='score-hint'], .home-video-item, .video-item, nav, header, footer, .menu, .sidebar")) continue;

      const text = (node.innerText || "").trim();
      // Block video titles, online courses, category navigation
      if (/^video\b|khóa học|học online|kh luyện từ/i.test(text)) continue;

      if (/(?:câu\s*(?:hỏi\s*(?:số)?)?\s*\d+|bài\s*(?:tập)?\s*\d+)[:\.]?/i.test(text) && text.length > 20 && text.length < 800) {
        // Must contain question indicator (?, hỏi, tính, tìm, điền, chọn, đáp án) or formula
        const hasQuizIndicator = /\?|\b(?:hỏi|tính|tìm|điền|chọn|đáp án|kết quả|giá trị|bao nhiêu|mấy|số nào|đúng|sai)\b/i.test(text) || /[\$\\=><%]|\d+\s*[\+\-\*\/×÷=]\s*\d+/.test(text);
        if (!hasQuizIndicator) continue;

        if (!isRealQuestionText(text)) continue;
        if (text.includes("EduQuest") || /\[(?:dom|mạng|lưu|bỏ qua|ok|skip|net|error)/i.test(text)) continue;

        const sig = text.toLowerCase().replace(/\s+/g, " ");
        if (isAlreadyCaptured(sig, null)) continue;

        if (!node.querySelector("div, section, article")) {
          // Must have genuine context (enclosing question card or form/quiz wrapper)
          const parentCard = findEnclosingQuestionCard(node);
          const hasRealContext = parentCard || node.closest("form, .exam, .test, .quiz, [class*='question'], [class*='exam'], [class*='practice'], .cau-hoi, .bai-tap");
          if (!hasRealContext) continue;

          let heurSubj = detectSubject();
          const hasVn = /[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]/i.test(text);
          const hasMath = /[\$\\=><%]|\d+\s*[\+\-\*\/×÷=]\s*\d+|\b(hình|phép tính|số liền|cm|dm|m|kg|lít)\b/i.test(text);
          if (hasVn && !hasMath) {
            heurSubj = "vietnamese";
          }

          const qId = "dom_text_" + Date.now();
          if (!isAlreadyCaptured(sig, qId)) {
            savedTextSignatures.add(sig);
            savedQuestionIds.add(qId);
            list.push({
              id: qId,
              source_platform: getPlatformName(),
              source_url: window.location.href,
              exam_name: document.title,
              grade: detectGrade(),
              subject: heurSubj,
              topic: heurSubj === "vietnamese" ? "Tiếng Việt Luyện tập" : "Toán Luyện tập & Đấu trường",
              question_type: "single_choice",
              content_html: (node.innerHTML || "").replace(/^(?:<[^>]+>)*\s*(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*(?:tập)?\s*\d+)[\s\.\:\-_]*/i, "").trim(),
              content_text: text.replace(/^(?:câu\s*(?:hỏi)?\s*(?:số)?\s*\d+|bài\s*(?:tập)?\s*\d+)[\s\.\:\-_]*/i, "").trim(),
              images: extractImagesFromElement(node),
              options: [],
              correct_answer: null,
              difficulty: "medium"
            });
            break;
          }
        }
      }
    }
    return list;
  }

  let isSavingInProgress = false;

  function autoSyncPendingQuestions() {
    if (!autoSaveEnabled || isSavingInProgress) return;
    const unsaved = capturedQuestions.filter(q => !q.saved_to_db);
    if (unsaved.length > 0) {
      autoSaveToEduQuest(unsaved);
    }
  }

  function handleNewQuestions(questions, source) {
    if (!questions || questions.length === 0) return;

    // Accumulate unique questions throughout the session
    questions.forEach(q => {
      const existingIdx = capturedQuestions.findIndex(x => x.id === q.id || (x.content_text && x.content_text === q.content_text));
      if (existingIdx >= 0) {
        capturedQuestions[existingIdx] = { ...capturedQuestions[existingIdx], ...q };
      } else {
        capturedQuestions.push(q);
      }
    });

    persistCapturedQuestions();
    updateWidgetUI();
    renderScannedModalQuestions();

    // Auto-Save: Zero-Click auto save to EduQuest Pro database
    if (autoSaveEnabled) {
      autoSyncPendingQuestions();
    }
  }

  function autoSaveToEduQuest(questions) {
    if (!questions || questions.length === 0) return;
    if (isSavingInProgress) return;
    isSavingInProgress = true;

    addLog(`[LƯU CSDL] Đang gửi ${questions.length} câu hỏi về EduQuest (Port 8000)...`, "info");

    chrome.runtime.sendMessage(
      { action: "save_questions", questions: questions },
      (res) => {
        isSavingInProgress = false;
        if (res && res.success) {
          const inserted = typeof res.data?.inserted_count === "number" ? res.data.inserted_count : questions.length;
          
          if (inserted > 0) {
            addLog(`✓ [LƯU CSDL] Đã nạp thành công ${inserted} câu hỏi mới vào CSDL EduQuest Pro!`, "success");
            showFloatingToast(`⚡ Đã tự động lưu ${inserted} câu hỏi mới vào CSDL!`);
          } else {
            addLog(`✓ [LƯU CSDL] Đã đồng bộ ${questions.length} câu hỏi (CSDL đã có sẵn các câu này)`, "success");
          }

          // Mark saved questions
          questions.forEach(savedQ => {
            const item = capturedQuestions.find(cq => cq.id === savedQ.id || (cq.content_text && cq.content_text === savedQ.content_text));
            if (item) item.saved_to_db = true;
          });
          persistCapturedQuestions();
          updateWidgetUI();
          renderScannedModalQuestions();
        } else {
          const errDetail = res?.error || "Không kết nối được port 8000";
          addLog(`✕ [LƯU CSDL LỖI] ${errDetail}`, "error");
          showFloatingToast(`✕ Lỗi lưu CSDL: ${errDetail}`, true);
        }
      }
    );
  }

  function extractImagesFromElement(container) {
    const imgs = [];
    if (!container) return imgs;
    container.querySelectorAll("img").forEach(img => {
      const src = img.src || img.getAttribute("data-src");
      if (!src || src.startsWith("data:") || src.length <= 10) return;
      if (/loading|spinner|viogpt-loading|Robot|avatar|icon/i.test(src)) return;
      if (!imgs.includes(src)) {
        imgs.push(src);
      }
    });
    return imgs;
  }

  function extractImagesFromHtml(html) {
    const imgs = [];
    if (!html) return imgs;
    const matches = html.match(/<img[^>]+src=["']([^"']+)["']/g) || [];
    matches.forEach(m => {
      const src = m.match(/src=["']([^"']+)["']/);
      if (src && src[1] && !imgs.includes(src[1])) {
        if (!/loading|spinner|viogpt-loading|Robot|avatar|icon/i.test(src[1])) {
          imgs.push(src[1]);
        }
      }
    });
    return imgs;
  }

  // 4. Floating Widget with Auto-Save status & Quick Capture
  function injectWidget() {
    if (document.getElementById("eduquest-floating-widget")) return;

    const widget = document.createElement("div");
    widget.id = "eduquest-floating-widget";
    widget.className = "eduquest-widget";
    widget.innerHTML = `
      <div class="eduquest-badge" id="eduquest-toggle-btn" title="EduQuest Pro v1.3.15">
        <div class="eduquest-icon">⚡</div>
        <span class="eduquest-title">EduQuest</span>
        <span class="eduquest-counter" id="eduquest-count">${capturedQuestions.length}</span>
      </div>

      <div class="eduquest-panel" id="eduquest-panel" style="display: none; width: 350px;">
        <div class="eduquest-panel-header" style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <strong>EduQuest Pro</strong>
            <span style="font-size: 10px; background: #0284c7; color: white; padding: 2px 6px; border-radius: 4px; font-weight: 700;">v1.3.15</span>
          </div>
          <span class="eduquest-status" id="eduquest-server-status" style="font-size: 11px;">Đang kiểm tra...</span>
        </div>

        <div class="eduquest-panel-body">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding: 8px 10px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;">
            <span style="font-size: 12px; font-weight: 700; color: #15803d;">⚡ Tự động lưu (Zero-Click):</span>
            <input type="checkbox" id="eduquest-autosave-toggle" ${autoSaveEnabled ? "checked" : ""} style="cursor: pointer; width: 16px; height: 16px;" />
          </div>

          <!-- View Scanned Questions Button -->
          <button class="eduquest-btn" id="eduquest-view-scanned-btn" style="background: linear-gradient(135deg, #0284c7, #2563eb); color: white; font-weight: 700; width: 100%; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; gap: 6px; padding: 9px 12px; border-radius: 8px; border: none; cursor: pointer; box-shadow: 0 2px 5px rgba(37,99,235,0.25);">
            <span>👁️ Xem các câu hỏi đã quét được</span>
            <span id="eduquest-view-count" style="background: rgba(255,255,255,0.25); padding: 1px 7px; border-radius: 10px; font-size: 11px; font-weight: 700;">${capturedQuestions.length}</span>
          </button>

          <div class="eduquest-actions" style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px;">
            <button class="eduquest-btn primary" id="eduquest-harvest-all-btn" style="font-weight: 600;">🚀 Cào tất cả câu hỏi trên trang</button>
            <button class="eduquest-btn secondary" id="eduquest-scan-btn">🎯 Quét nhanh màn hình hiện tại</button>
          </div>

          <!-- Activity Debug Log Panel -->
          <div style="border-top: 1px solid #e2e8f0; padding-top: 10px; margin-top: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-size: 11.5px; font-weight: 700; color: #334155;">📋 Nhật ký Hoạt động (Debug Log):</span>
              <div style="display: flex; gap: 4px;">
                <button id="eduquest-copy-logs-btn" style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; color: #0284c7; cursor: pointer; font-size: 10.5px; padding: 2px 6px; font-weight: 600;">Sao chép</button>
                <button id="eduquest-clear-logs-btn" style="background: #fee2e2; border: 1px solid #fecdd3; border-radius: 4px; color: #b91c1c; cursor: pointer; font-size: 10.5px; padding: 2px 6px; font-weight: 600;">Xóa log</button>
              </div>
            </div>

            <!-- Filter Pills -->
            <div id="eduquest-log-filters" style="display: flex; gap: 4px; margin-bottom: 6px; flex-wrap: wrap;">
              <button class="eduquest-log-pill active" data-filter="all" style="font-size: 10px; padding: 2px 6px; border-radius: 4px; border: 1px solid #38bdf8; background: #0284c7; color: white; cursor: pointer; font-weight: 600;">Tất cả</button>
              <button class="eduquest-log-pill" data-filter="success" style="font-size: 10px; padding: 2px 6px; border-radius: 4px; border: 1px solid #334155; background: #1e293b; color: #4ade80; cursor: pointer;">Thành công</button>
              <button class="eduquest-log-pill" data-filter="skip" style="font-size: 10px; padding: 2px 6px; border-radius: 4px; border: 1px solid #334155; background: #1e293b; color: #fbbf24; cursor: pointer;">Bỏ qua</button>
              <button class="eduquest-log-pill" data-filter="net" style="font-size: 10px; padding: 2px 6px; border-radius: 4px; border: 1px solid #334155; background: #1e293b; color: #c084fc; cursor: pointer;">Mạng</button>
              <button class="eduquest-log-pill" data-filter="error" style="font-size: 10px; padding: 2px 6px; border-radius: 4px; border: 1px solid #334155; background: #1e293b; color: #f87171; cursor: pointer;">Lỗi</button>
            </div>

            <!-- Quick search in logs -->
            <input type="text" id="eduquest-log-search-input" placeholder="🔍 Tìm kiếm trong nhật ký..." style="width: 100%; box-sizing: border-box; font-size: 11px; padding: 4px 8px; border: 1px solid #cbd5e1; border-radius: 6px; margin-bottom: 6px; background: #f8fafc;" />

            <!-- Log Entries Console -->
            <div id="eduquest-activity-list" style="background: #090d16; border: 1px solid #1e293b; border-radius: 6px; padding: 8px 10px; max-height: 140px; overflow-y: auto; font-family: 'Fira Code', Consolas, monospace; font-size: 11px;">
              <!-- Filled dynamically -->
            </div>
          </div>
        </div>
      </div>

      <!-- Scanned Questions Modal Drawer -->
      <div id="eduquest-scanned-modal" class="eduquest-modal-overlay" style="display: none;">
        <div class="eduquest-modal-window">
          <div style="background: #0f172a; color: white; padding: 14px 20px; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 18px;">📋</span>
              <h3 style="margin: 0; font-size: 15px; font-weight: 700; color: #38bdf8;">Danh sách câu hỏi đã quét (<span id="modal-q-count">${capturedQuestions.length}</span> câu)</h3>
            </div>
            <button id="eduquest-modal-close-btn" style="background: #334155; border: none; color: #e2e8f0; font-size: 14px; width: 28px; height: 28px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center;">✕</button>
          </div>
          <div style="background: #f8fafc; padding: 10px 20px; border-bottom: 1px solid #e2e8f0; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
            <button id="eduquest-modal-save-all-btn" style="background: #10b981; color: white; border: none; padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer;">💾 Lưu tất cả vào CSDL</button>
            <button id="eduquest-modal-copy-btn" style="background: #e2e8f0; color: #1e293b; border: 1px solid #cbd5e1; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer;">📋 Sao chép JSON</button>
            <button id="eduquest-modal-clear-btn" style="background: #fee2e2; color: #b91c1c; border: 1px solid #fecdd3; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; margin-left: auto;">🗑️ Xóa danh sách</button>
          </div>
          <div id="eduquest-modal-questions-list" style="padding: 16px 20px; overflow-y: auto; flex: 1; display: flex; flex-direction: column; gap: 14px; background: #f1f5f9; max-height: calc(85vh - 120px);">
            <!-- Populated dynamically -->
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(widget);

    // Event listeners
    const toggleBtn = document.getElementById("eduquest-toggle-btn");
    const panel = document.getElementById("eduquest-panel");
    const harvestBtn = document.getElementById("eduquest-harvest-all-btn");
    const scanBtn = document.getElementById("eduquest-scan-btn");
    const autoToggle = document.getElementById("eduquest-autosave-toggle");
    const copyLogBtn = document.getElementById("eduquest-copy-logs-btn");
    const clearLogBtn = document.getElementById("eduquest-clear-logs-btn");
    const searchInput = document.getElementById("eduquest-log-search-input");
    const viewScannedBtn = document.getElementById("eduquest-view-scanned-btn");
    const modal = document.getElementById("eduquest-scanned-modal");
    const modalCloseBtn = document.getElementById("eduquest-modal-close-btn");
    const modalSaveAllBtn = document.getElementById("eduquest-modal-save-all-btn");
    const modalCopyBtn = document.getElementById("eduquest-modal-copy-btn");
    const modalClearBtn = document.getElementById("eduquest-modal-clear-btn");

    toggleBtn.addEventListener("click", () => {
      panel.style.display = panel.style.display === "none" ? "block" : "none";
      checkServer();
      renderActivityLogs();
    });

    if (viewScannedBtn && modal) {
      viewScannedBtn.addEventListener("click", () => {
        modal.style.display = "flex";
        renderScannedModalQuestions();
      });
    }

    if (modalCloseBtn && modal) {
      modalCloseBtn.addEventListener("click", () => {
        modal.style.display = "none";
      });
    }

    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.style.display = "none";
      });
    }

    if (modalSaveAllBtn) {
      modalSaveAllBtn.addEventListener("click", () => {
        if (capturedQuestions.length === 0) {
          showFloatingToast("Danh sách câu hỏi đang trống!", false);
          return;
        }
        addLog(`Lưu tất cả ${capturedQuestions.length} câu hỏi đã quét vào CSDL...`, "info");
        autoSaveToEduQuest(capturedQuestions);
      });
    }

    if (modalCopyBtn) {
      modalCopyBtn.addEventListener("click", () => {
        if (capturedQuestions.length === 0) {
          showFloatingToast("Danh sách trống!", false);
          return;
        }
        navigator.clipboard.writeText(JSON.stringify(capturedQuestions, null, 2)).then(() => {
          showFloatingToast(`Đã sao chép ${capturedQuestions.length} câu hỏi dưới dạng JSON!`);
        });
      });
    }

    if (modalClearBtn) {
      modalClearBtn.addEventListener("click", () => {
        if (confirm(`Bạn có chắc muốn xóa toàn bộ ${capturedQuestions.length} câu hỏi đã quét trong danh sách tạm này?`)) {
          capturedQuestions = [];
          savedQuestionIds.clear();
          savedTextSignatures.clear();
          persistCapturedQuestions();
          updateWidgetUI();
          renderScannedModalQuestions();
          addLog("Đã làm sạch toàn bộ danh sách câu hỏi đã quét và bộ nhớ đệm chống trùng", "info");
          showFloatingToast("Đã làm sạch danh sách câu hỏi. Đang quét lại màn hình...");
          setTimeout(() => {
            scanPageQuestions(true);
          }, 300);
        }
      });
    }

    autoToggle.addEventListener("change", (e) => {
      autoSaveEnabled = e.target.checked;
      localStorage.setItem("eduquest_autosave", autoSaveEnabled ? "true" : "false");
      addLog(autoSaveEnabled ? "Đã BẬT tự động lưu câu hỏi (Zero-Click)" : "Đã TẮT tự động lưu", "info");
      showFloatingToast(autoSaveEnabled ? "Đã BẬT tự động lưu câu hỏi (Zero-Click)!" : "Đã TẮT tự động lưu!");
    });

    // Log Filter Pills
    document.querySelectorAll(".eduquest-log-pill").forEach(pill => {
      pill.addEventListener("click", () => {
        document.querySelectorAll(".eduquest-log-pill").forEach(p => {
          p.style.background = "#1e293b";
          p.style.borderColor = "#334155";
          p.style.fontWeight = "normal";
          p.classList.remove("active");
        });
        pill.style.background = "#0284c7";
        pill.style.borderColor = "#38bdf8";
        pill.style.fontWeight = "bold";
        pill.classList.add("active");
        currentLogFilter = pill.getAttribute("data-filter") || "all";
        renderActivityLogs();
      });
    });

    // Log Keyword Search
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        logSearchQuery = e.target.value.trim();
        renderActivityLogs();
      });
    }

    if (clearLogBtn) {
      clearLogBtn.addEventListener("click", () => {
        if (confirm("Bạn có muốn xóa toàn bộ nhật ký debug hiện tại?")) {
          activityLogs = [];
          try {
            localStorage.removeItem("eduquest_ext_logs");
            if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
              chrome.storage.local.set({ eduquest_ext_logs: [] });
            }
          } catch (e) {}
          renderActivityLogs();
          showFloatingToast("Đã làm sạch nhật ký debug!");
        }
      });
    }

    if (harvestBtn) {
      harvestBtn.addEventListener("click", () => {
        harvestAllLessonQuestions();
      });
    }

    scanBtn.addEventListener("click", () => {
      addLog("Thực hiện quét sâu màn hình thủ công (Force Scan)...", "info");
      const found = scanPageQuestions(true);
      if (found.length > 0) {
        showFloatingToast(`Đã bắt thành công ${found.length} câu hỏi kèm đáp án!`);
      } else {
        showFloatingToast("Đã quét màn hình. Đang lắng nghe tiếp...", false);
      }
    });

    if (copyLogBtn) {
      copyLogBtn.addEventListener("click", () => {
        const text = activityLogs.map(l => `[${l.time}] [${l.source || getShortUrl()}] [${l.type.toUpperCase()}] ${l.msg}`).join("\n");
        navigator.clipboard.writeText(text).then(() => {
          showFloatingToast("Đã sao chép toàn bộ nhật ký debug!");
        });
      });
    }

    checkServer();
    renderActivityLogs();
    renderScannedModalQuestions();
  }

  // 5. Bulk Lesson & Practice Harvester (Walks tabs, steppers, and reveals all exercises)
  async function harvestAllLessonQuestions() {
    addLog("🚀 Bắt đầu quét & cào tất cả câu hỏi từ bài học / luyện tập trên trang này...", "info");
    showFloatingToast("🚀 Đang tự động quét tất cả câu hỏi bài học trên trang...");

    // Step 1: Expand any collapsed question accordions or details
    try {
      const expanders = document.querySelectorAll(
        ".collapse-btn, [data-toggle='collapse'], .accordion-toggle, details:not([open]) summary, " +
        ".btn-expand, .show-more, .btn-show-solution, [class*='expand']"
      );
      expanders.forEach(b => {
        try { b.click(); } catch(e) {}
      });
    } catch(e) {}

    let totalCollected = [];

    // Step 2: Check for question steppers/tabs/pills (e.g. 1, 2, 3, 4, 5... or Next buttons)
    const stepperBtns = Array.from(document.querySelectorAll(
      ".nav-question button, .question-nav button, .list-step button, .step-item, .pagination-question button, " +
      ".stepper-item, .item-step, [class*='step-number'], .question-stepper button, .pagination li a, .list-number-question button, " +
      ".btn-step, .quiz-stepper > div, .stepper > button, .list-step > div, .list-step > span, .list-step > a, .pagination-step li"
    )).filter(b => !b.disabled && b.offsetParent !== null);

    if (stepperBtns.length > 1) {
      addLog(`Phát hiện thanh chuyển câu gồm ${stepperBtns.length} câu hỏi. Đang duyệt tuần tự...`, "info");
      for (let i = 0; i < stepperBtns.length; i++) {
        try {
          stepperBtns[i].click();
          await new Promise(r => setTimeout(r, 900));
          const currentBatch = scanPageQuestions();
          if (currentBatch && currentBatch.length > 0) {
            currentBatch.forEach(q => {
              if (!totalCollected.some(existing => existing.id === q.id || existing.content_text === q.content_text)) {
                totalCollected.push(q);
              }
            });
          }
        } catch (e) {}
      }
    }

    // Step 3: Full DOM deep scan for all question containers on the page
    const finalScan = scanPageQuestions();
    if (finalScan && finalScan.length > 0) {
      finalScan.forEach(q => {
        if (!totalCollected.some(existing => existing.id === q.id || existing.content_text === q.content_text)) {
          totalCollected.push(q);
        }
      });
    }

    if (totalCollected.length > 0) {
      addLog(`🎉 Thu thập thành công ${totalCollected.length} câu hỏi bài học từ trang!`, "success");
      showFloatingToast(`🎉 Đã cào & lưu thành công ${totalCollected.length} câu hỏi bài học!`);
      autoSaveToEduQuest(totalCollected);
    } else {
      addLog("Không tìm thấy thêm câu hỏi mới trên trang bài học này.", "info");
      showFloatingToast("Không có câu hỏi mới hoặc tất cả đã được lưu trước đó!", false);
    }

    return totalCollected;
  }

  function checkServer() {
    chrome.runtime.sendMessage({ action: "check_server" }, (res) => {
      const statusEl = document.getElementById("eduquest-server-status");
      if (statusEl) {
        if (res && res.connected) {
          statusEl.innerText = "● Đã kết nối EduQuest";
          statusEl.style.color = "#10B981";
          // Auto-sync any pending questions when server is reachable
          autoSyncPendingQuestions();
        } else {
          statusEl.innerText = "○ Chưa mở EduQuest (8000)";
          statusEl.style.color = "#EF4444";
        }
      }
    });
  }

  function updateWidgetUI() {
    const savedCount = capturedQuestions.filter(q => q.saved_to_db).length;
    const totalCount = capturedQuestions.length;
    const countEl = document.getElementById("eduquest-count");
    if (countEl) countEl.innerText = totalCount;
    const viewCountEl = document.getElementById("eduquest-view-count");
    if (viewCountEl) {
      viewCountEl.innerText = `${savedCount}/${totalCount} đã lưu CSDL`;
    }
    const modalCountEl = document.getElementById("modal-q-count");
    if (modalCountEl) modalCountEl.innerText = `${totalCount} (${savedCount} đã lưu CSDL)`;
  }

  function renderScannedModalQuestions() {
    const listEl = document.getElementById("eduquest-modal-questions-list");
    if (!listEl) return;

    if (capturedQuestions.length === 0) {
      listEl.innerHTML = `
        <div style="text-align: center; padding: 40px 20px; color: #64748b;">
          <div style="font-size: 36px; margin-bottom: 10px;">🔍</div>
          <div style="font-size: 14.5px; font-weight: 700; color: #334155; margin-bottom: 6px;">Chưa có câu hỏi nào được quét trong phiên này</div>
          <div style="font-size: 12.5px; color: #64748b; line-height: 1.5;">Hãy mở bài luyện tập trên VioEdu, Hành Trang Số, Trạng Nguyên... hoặc nhấn "Cào tất cả câu hỏi" / "Quét nhanh màn hình" để bắt đầu thu thập.</div>
        </div>
      `;
      return;
    }

    listEl.innerHTML = capturedQuestions.map((q, idx) => {
      const isSaved = q.saved_to_db;
      const statusBadge = isSaved
        ? `<span class="eduquest-badge-tag" style="background: #dcfce7; color: #15803d; border: 1px solid #86efac;">✓ Đã lưu CSDL</span>`
        : `<span class="eduquest-badge-tag" style="background: #fef3c7; color: #b45309; border: 1px solid #fde68a;">⏳ Chờ lưu</span>`;

      let optionsHtml = "";
      if (Array.isArray(q.options) && q.options.length > 0) {
        optionsHtml = `
          <div class="eduquest-opt-grid">
            ${q.options.map(opt => `
              <div class="eduquest-opt-box ${opt.is_correct || opt.id === q.correct_answer ? 'correct' : ''}">
                <strong style="color: #2563eb; font-weight: 700;">${opt.id}.</strong>
                <span>${opt.content}</span>
                ${opt.is_correct || opt.id === q.correct_answer ? '<span style="margin-left: auto; color: #10b981; font-weight: 700;">✓</span>' : ''}
              </div>
            `).join("")}
          </div>
        `;
      } else if (q.question_type === "fill_blank") {
        optionsHtml = `
          <div style="margin-top: 8px; font-size: 12px; color: #64748b; font-style: italic;">
            ✏️ Dạng câu hỏi điền số / đáp án vào ô trống
          </div>
        `;
      }

      let imagesHtml = "";
      if (Array.isArray(q.images) && q.images.length > 0) {
        imagesHtml = `
          <div style="display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap;">
            ${q.images.map(img => `<img src="${img}" style="max-height: 90px; border-radius: 6px; border: 1px solid #e2e8f0; object-fit: contain; background: white;" />`).join("")}
          </div>
        `;
      }

      return `
        <div class="eduquest-card-item">
          <div class="eduquest-card-header">
            <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
              <span style="font-weight: 700; color: #1e40af; font-size: 13px;">Câu #${idx + 1}</span>
              <span class="eduquest-badge-tag" style="background: #e0f2fe; color: #0369a1;">${(q.source_platform || 'ONLINE').toUpperCase()}</span>
              <span class="eduquest-badge-tag" style="background: #f1f5f9; color: #475569;">Lớp ${q.grade || 2}</span>
              <span class="eduquest-badge-tag" style="background: #fdf4ff; color: #a21caf;">${q.subject === 'math' ? 'Toán' : q.subject}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              ${statusBadge}
              ${!isSaved ? `<button onclick="window.eduquestSaveSingleQuestion('${q.id}')" style="background: #2563eb; color: white; border: none; padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 600; cursor: pointer;">Lưu câu này</button>` : ''}
              <button onclick="window.eduquestDeleteSingleQuestion('${q.id}')" style="background: #fee2e2; color: #b91c1c; border: 1px solid #fecdd3; padding: 4px 8px; border-radius: 5px; font-size: 11px; font-weight: 600; cursor: pointer;" title="Xóa câu hỏi này">🗑️</button>
            </div>
          </div>
          <div style="font-size: 13.5px; color: #1e293b; line-height: 1.5; font-weight: 500; margin-bottom: 6px; white-space: pre-line;">
            ${q.content_text || q.content_html}
          </div>
          ${imagesHtml}
          ${optionsHtml}
        </div>
      `;
    }).join("");
  }

  window.eduquestSaveSingleQuestion = function (qid) {
    const q = capturedQuestions.find(item => item.id === qid);
    if (!q) return;
    autoSaveToEduQuest([q]);
  };

  window.eduquestDeleteSingleQuestion = function (qid) {
    const idx = capturedQuestions.findIndex(item => item.id === qid);
    if (idx >= 0) {
      const removed = capturedQuestions.splice(idx, 1)[0];
      rebuildSignatures();
      persistCapturedQuestions();
      updateWidgetUI();
      renderScannedModalQuestions();
      addLog(`Đã xóa câu hỏi #${idx + 1} khỏi danh sách tạm: '${(removed.content_text || "").substring(0, 30)}...'`, "info");
      showFloatingToast("Đã xóa câu hỏi khỏi danh sách tạm");
    }
  };

  // Live storage sync across Popup, Content Script, and other tabs
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
    chrome.storage.onChanged.addListener((changes, areaName) => {
      if (areaName === "local") {
        if (changes.eduquest_captured_questions) {
          const newQ = changes.eduquest_captured_questions.newValue;
          capturedQuestions = Array.isArray(newQ) ? newQ : [];
          rebuildSignatures();
          updateWidgetUI();
          renderScannedModalQuestions();
          if (capturedQuestions.length === 0) {
            addLog("Danh sách câu hỏi được làm sạch từ bên ngoài (Popup/Storage). Quét lại màn hình...", "info");
            setTimeout(() => {
              scanPageQuestions(true);
            }, 300);
          }
        }
        if (changes.eduquest_ext_logs) {
          const newLogs = changes.eduquest_ext_logs.newValue;
          activityLogs = Array.isArray(newLogs) ? newLogs : [];
          renderActivityLogs();
        }
      }
    });
  }

  // Cross-script messaging listener (Popup -> Content Script)
  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
      if (msg && msg.action === "clear_and_rescan") {
        capturedQuestions = [];
        savedQuestionIds.clear();
        savedTextSignatures.clear();
        persistCapturedQuestions();
        updateWidgetUI();
        renderScannedModalQuestions();
        addLog("Đã nhận lệnh làm sạch từ Popup. Kích hoạt quét lại màn hình...", "info");
        setTimeout(() => {
          scanPageQuestions(true);
        }, 300);
        sendResponse({ success: true });
        return true;
      }
      if (msg && msg.action === "force_scan") {
        addLog("Nhận lệnh quét màn hình từ Popup (Force Scan)...", "info");
        const found = scanPageQuestions(true);
        sendResponse({ success: true, count: found.length });
        return true;
      }
    });
  }

  function showFloatingToast(text, isError = false) {
    const toast = document.createElement("div");
    toast.className = `eduquest-toast ${isError ? "error" : "success"}`;
    toast.innerText = text;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  }

  // 6. Automatic Execution & Live Listeners for Real-Time Learning Transitions
  function init() {
    injectWidget();
    addLog("EduQuest Pro v1.3.15 đã khởi động trên " + window.location.hostname, "info");
    setTimeout(() => {
      scanPageQuestions(false, false);
      autoSyncPendingQuestions();
    }, 1000);
    setTimeout(() => {
      scanPageQuestions(false, false);
      autoSyncPendingQuestions();
    }, 3000);

    // Active heartbeat scan during active learning / practice / quiz (every 2.5s, silent background mode)
    setInterval(() => {
      if (isEduLearningActive() && autoSaveEnabled) {
        scanPageQuestions(false, true);
        autoSyncPendingQuestions();
      }
    }, 2500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Capture when student interacts with question or answers on VioEdu, Trang Nguyen, Hanh Trang So
  document.addEventListener("click", (e) => {
    const target = e.target;
    if (!target) return;

    // STRICT: Never trigger scanning when clicking inside EduQuest extension UI
    if (target.closest && target.closest("#eduquest-floating-widget, #eduquest-scanned-modal, .eduquest-widget, .eduquest-modal-overlay, .eduquest-toast, .eduquest-panel, [class*='eduquest'], [id*='eduquest']")) {
      return;
    }

    const interactive = target.closest(
      ".choice-answer-grid-2026, ._2UU-q, ._27IHb, [role='button'], " +
      "[class*='choice-answer'], [class*='btn--practice'], [class*='answer'], [class*='suggest'], " +
      "[class*='item'], button, label, input, .btn-next, .btn-submit, .btn-tiep, .Select, .Select-control"
    );
    if (interactive) {
      const btnText = (interactive.innerText || interactive.value || interactive.getAttribute("aria-label") || "thao tác").trim().replace(/\s+/g, " ").substring(0, 25);
      addLog(`[TƯƠNG TÁC] Phát hiện học sinh thao tác '${btnText}', kích hoạt quét câu hỏi...`, "info");

      // Immediate attempt on enclosing question card
      const enclosingCard = findEnclosingQuestionCard(target);
      if (enclosingCard) {
        setTimeout(() => {
          const q = extractQuestionFromElement(enclosingCard, 0, false);
          if (q) handleNewQuestions([q], "User Click Interaction");
        }, 150);
      }

      setTimeout(() => {
        scanPageQuestions(false, false);
        autoSyncPendingQuestions();
      }, 400);
      setTimeout(() => {
        scanPageQuestions(false, true);
        autoSyncPendingQuestions();
      }, 1200);
      setTimeout(() => {
        scanPageQuestions(false, true);
        autoSyncPendingQuestions();
      }, 2400);
    }
  });

  // Observe DOM changes (When user navigates questions or content updates)
  let scanDebounceTimer = null;
  const observer = new MutationObserver((mutations) => {
    const isOurWidget = mutations.some(m => m.target && (m.target.closest && m.target.closest("#eduquest-floating-widget, #eduquest-scanned-modal")));
    if (isOurWidget) return;

    clearTimeout(scanDebounceTimer);
    scanDebounceTimer = setTimeout(() => {
      if (isEduLearningActive() && autoSaveEnabled) {
        addLog("[DOM THAY ĐỔI] Giao diện trang cập nhật, tự động quét câu hỏi mới...", "info");
        scanPageQuestions(false, true);
        autoSyncPendingQuestions();
      }
    }, 800);
  });

  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true
  });
})();
