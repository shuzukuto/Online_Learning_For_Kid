// EduQuest Pro - Core Application & Router
// Version hien thi duoc cap nhat dong tu /api/version (backend/version.py la nguon duy nhat).
// APP_VERSION giu lam gia tri fallback khi backend chua san sang.
let APP_VERSION = "v1.2.5";
const API_BASE = (typeof window !== "undefined" && window.location && window.location.origin && window.location.origin.startsWith("http"))
  ? `${window.location.origin}/api`
  : "http://localhost:8000/api";

let lastKnownQuestionCount = null;
let realtimeSyncInterval = null;
const liveSyncChannel = ("BroadcastChannel" in window) ? new BroadcastChannel("eduquest_live_sync") : null;

const State = {
  currentView: "dashboard",
  selectedQuestionIds: new Set(),
  stats: null,
  cachedQuestions: [],
  ocrBatch: null,
  filters: {
    platform: "all",
    subject: "all",
    grade: "",
    topic: "",
    question_type: "all",
    difficulty: "all",
    search: "",
    source_detail: "all",
    created_date: "",
    only_duplicates: false,
    sort_by: "q_number_asc",
    page: 1,
    page_size: 50
  }
};
window.State = State;

// UI Notifications
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "all 0.2s ease";
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

/**
 * Chuyển đổi thời gian ISO 8601 / Date sang định dạng tiếng Việt chuẩn: HH:mm DD/MM/YYYY
 * Ví dụ: "2026-10-02T07:31:00.123456" -> "07:31 02/10/2026"
 */
function formatDateTimeVN(dateInput) {
  if (!dateInput) return "";
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  const pad = (n) => String(n).padStart(2, '0');
  const hh = pad(d.getHours());
  const mm = pad(d.getMinutes());
  const dd = pad(d.getDate());
  const MM = pad(d.getMonth() + 1);
  const yyyy = d.getFullYear();
  return `${hh}:${mm} ${dd}/${MM}/${yyyy}`;
}
window.formatDateTimeVN = formatDateTimeVN;

// View Routing
function switchView(viewName) {
  State.currentView = viewName;

  document.querySelectorAll(".nav-item").forEach(item => {
    item.classList.toggle("active", item.dataset.view === viewName);
  });

  document.querySelectorAll(".view-container").forEach(view => {
    view.classList.toggle("active", view.id === `view-${viewName}`);
  });

  const titles = {
    dashboard: { title: "Tổng quan Ngân hàng", sub: "Thống kê câu hỏi từ các nền tảng và hoạt động gần đây" },
    bank: { title: "Ngân hàng Câu hỏi", sub: "Tìm kiếm, lọc nâng cao và xem trước công thức Toán học" },
    practice: { title: "Đấu trường Luyện tập Trực tuyến", sub: "Làm bài thi tính giờ, chấm điểm tự động, phân tích năng lực & huy hiệu thành tích" },
    builder: { title: "Biên soạn & Trộn Đề thi", sub: "Tùy biến đề thi chuẩn format và xuất file Word (.docx)" },
    collector: { title: "Trung tâm Thu thập", sub: "Tiện ích Extension, Bóc tách PDF (TIMO, ASMO) & Cào tự động" },
    manual: { title: "Soạn thảo Câu hỏi Mới", sub: "Trình soạn câu hỏi với hiển thị công thức LaTeX trực tiếp" },
    "admin-users": { title: "Quản trị Tài khoản", sub: "Duyệt tài khoản • phân quyền admin/user • khóa & xóa (chỉ admin)" }
  };

  const headerInfo = titles[viewName] || { title: "EduQuest Pro", sub: "" };
  document.getElementById("page-main-title").innerText = headerInfo.title;
  document.getElementById("page-sub-title").innerText = headerInfo.sub;

  // View-specific initializers
  if (viewName === "dashboard") loadDashboardStats();
  if (viewName === "bank") loadQuestions();
  if (viewName === "practice" && typeof initPracticeView === "function") initPracticeView();
  if (viewName === "builder") renderExamBuilderView();
  if (viewName === "collector") {
    if (typeof restoreCollectorSettings === "function") restoreCollectorSettings();
    loadCollectorLogs();
  }
  if (viewName === "admin-users" && window.EduAuth) window.EduAuth.loadAdminUsers();
}

function viewAllQuestionsInBank() {
  if (typeof resetFilters === "function") {
    resetFilters();
  } else {
    State.filters.platform = "all";
    State.filters.subject = "all";
    State.filters.grade = "";
    State.filters.search = "";
    State.filters.source_detail = "all";
    State.filters.only_duplicates = false;
    State.filters.page = 1;
    State.filters.page_size = 50;
  }
  switchView("bank");
}

// Load Dashboard Data
async function loadDashboardStats() {
  try {
    // Giu badge version dong bo voi backend (nguon duy nhat backend/version.py)
    fetch(`${API_BASE}/version`).then(r => r.ok ? r.json() : null).then(v => {
      if (v && v.app_version) {
        APP_VERSION = v.app_version;
        document.querySelectorAll(".app-version-badge").forEach(el => el.textContent = APP_VERSION);
        const sv = document.getElementById("sidebar-version-tag");
        if (sv) sv.textContent = `Phiên bản: ${APP_VERSION}`;
        const ct = document.getElementById("sidebar-cache-tag");
        if (ct && v.cache_buster) ct.textContent = `assets: v${v.cache_buster}`;
      }
    }).catch(() => {});
    const res = await fetch(`${API_BASE}/stats`);
    const data = await res.json();
    State.stats = data;

    if (lastKnownQuestionCount === null) {
      lastKnownQuestionCount = data.total_questions || 0;
    }

    const elTotalQ = document.getElementById("stat-total-q");
    if (elTotalQ) elTotalQ.innerText = data.total_questions || 0;
    const elTotalExams = document.getElementById("stat-total-exams");
    if (elTotalExams) elTotalExams.innerText = data.total_exams || 0;

    // Platform counts
    const pVio = data.by_platform?.vioedu || 0;
    const pTn = data.by_platform?.tnmath || 0;
    const pTimo = (data.by_platform?.timo || 0) + (data.by_platform?.hkimo || 0) + (data.by_platform?.asmo || 0);
    const pHunter = data.by_platform?.internet_hunter || 0;
    const pHts = data.by_platform?.hanhtrangso || 0;
    const pManual = data.by_platform?.manual || 0;

    const elVio = document.getElementById("stat-vioedu-count");
    if (elVio) elVio.innerText = pVio;
    const elTn = document.getElementById("stat-tnmath-count");
    if (elTn) elTn.innerText = pTn;
    const elOlym = document.getElementById("stat-olympiad-count");
    if (elOlym) elOlym.innerText = pTimo;

    // Render platform grid
    const pGrid = document.getElementById("dashboard-platform-grid");
    if (pGrid) {
      pGrid.innerHTML = `
        <div class="platform-pill-card" onclick="filterByPlatform('internet_hunter')">
          <div>
            <div class="platform-title">🌐 Săn từ Internet</div>
            <span style="font-size: 11.5px; color: #64748b;">CodeMath, Blog, Web</span>
          </div>
          <div class="platform-count" style="color: #0284c7;">${pHunter}</div>
        </div>
        <div class="platform-pill-card" onclick="filterByPlatform('hanhtrangso')">
          <div>
            <div class="platform-title">📚 Hành Trang Số</div>
            <span style="font-size: 11.5px; color: #64748b;">SGK & Bài tập NXB GD</span>
          </div>
          <div class="platform-count" style="color: #0d9488;">${pHts}</div>
        </div>
        <div class="platform-pill-card" onclick="filterByPlatform('vioedu')">
          <div>
            <div class="platform-title">⭐ VioEdu (FPT)</div>
            <span style="font-size: 11.5px; color: #64748b;">Luyện tập & Đấu trường</span>
          </div>
          <div class="platform-count">${pVio}</div>
        </div>
        <div class="platform-pill-card" onclick="filterByPlatform('tnmath')">
          <div>
            <div class="platform-title">📖 Trạng Nguyên</div>
            <span style="font-size: 11.5px; color: #64748b;">Toán & Tiếng Việt</span>
          </div>
          <div class="platform-count">${pTn}</div>
        </div>
        <div class="platform-pill-card" onclick="filterByPlatform('olympiad')">
          <div>
            <div class="platform-title">🏆 Olympic Quốc tế</div>
            <span style="font-size: 11.5px; color: #64748b;">TIMO, HKIMO, ASMO</span>
          </div>
          <div class="platform-count" style="color: #d97706;">${pTimo}</div>
        </div>
        <div class="platform-pill-card" onclick="filterByPlatform('manual')">
          <div>
            <div class="platform-title">✏️ Tự biên soạn</div>
            <span style="font-size: 11.5px; color: #64748b;">Giáo viên tạo thủ công</span>
          </div>
          <div class="platform-count">${pManual}</div>
        </div>
      `;
    }

    // Render subjects grid
    const sGrid = document.getElementById("dashboard-subject-grid");
    if (sGrid) {
      const sMath = data.by_subject?.math || 0;
      const sVn = data.by_subject?.vietnamese || 0;
      const sEng = data.by_subject?.english || 0;
      const sSci = data.by_subject?.science || 0;
      const sInf = data.by_subject?.informatics || 0;

      sGrid.innerHTML = `
        <div class="platform-pill-card" style="border-left: 4px solid #2563eb;" onclick="filterBySubject('math')">
          <div>
            <div class="platform-title">📐 Toán học</div>
            <span style="font-size: 11.5px; color: #64748b;">VioEdu, TIMO, SGK...</span>
          </div>
          <div class="platform-count" style="color: #2563eb;">${sMath}</div>
        </div>
        <div class="platform-pill-card" style="border-left: 4px solid #e11d48;" onclick="filterBySubject('vietnamese')">
          <div>
            <div class="platform-title">📖 Tiếng Việt</div>
            <span style="font-size: 11.5px; color: #64748b;">Trạng Nguyên, SGK</span>
          </div>
          <div class="platform-count" style="color: #e11d48;">${sVn}</div>
        </div>
        <div class="platform-pill-card" style="border-left: 4px solid #0d9488;" onclick="filterBySubject('english')">
          <div>
            <div class="platform-title">🇬🇧 Tiếng Anh</div>
            <span style="font-size: 11.5px; color: #64748b;">IOE, Olympic English</span>
          </div>
          <div class="platform-count" style="color: #0d9488;">${sEng}</div>
        </div>
        <div class="platform-pill-card" style="border-left: 4px solid #d97706;" onclick="filterBySubject('science')">
          <div>
            <div class="platform-title">🔬 Khoa học & TNXH</div>
            <span style="font-size: 11.5px; color: #64748b;">Khám phá tự nhiên</span>
          </div>
          <div class="platform-count" style="color: #d97706;">${sSci}</div>
        </div>
        <div class="platform-pill-card" style="border-left: 4px solid #7c3aed;" onclick="filterBySubject('informatics')">
          <div>
            <div class="platform-title">💻 Tin học</div>
            <span style="font-size: 11.5px; color: #64748b;">Tin học cơ bản & trẻ</span>
          </div>
          <div class="platform-count" style="color: #7c3aed;">${sInf}</div>
        </div>
      `;
    }

    // Render recent questions
    const recList = document.getElementById("dashboard-recent-list");
    if (recList && data.recent_questions) {
      if (data.recent_questions.length === 0) {
        recList.innerHTML = `<p style="color: #64748b; font-size: 13px; text-align: center; padding: 20px;">Chưa có câu hỏi nào. Hãy nạp bộ câu hỏi mẫu hoặc mở Trung tâm Thu thập!</p>`;
      } else {
        recList.innerHTML = data.recent_questions.map(q => `
          <div style="padding: 12px 16px; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <span class="tag-badge subject-${q.subject || 'math'}">${(q.subject || 'math').toUpperCase()}</span>
              <span class="tag-badge platform-${q.source_platform}">${q.source_platform.toUpperCase()}</span>
              <span style="font-family: monospace; font-size: 11.5px; font-weight: 700; color: #1e40af; background: #eff6ff; padding: 2px 7px; border-radius: 5px; border: 1px solid #bfdbfe; margin-left: 6px;">ID: #${q.q_number || q.id.substring(0, 8)}</span>
              <span style="font-weight: 600; font-size: 13.5px; margin-left: 8px;">${q.exam_name || "Bài tập"}</span>
              <p style="font-size: 13px; color: #475569; margin-top: 4px;">${(q.content_text || "").substring(0, 90)}...</p>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="filterBySubject('${q.subject || 'math'}')">Xem</button>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Error loading stats:", err);
  }
}

function filterByPlatform(plat) {
  State.filters.platform = plat;
  switchView("bank");
}

function filterBySubject(sub) {
  State.filters.subject = sub;
  switchView("bank");
}

// Seed initial samples
async function seedSampleQuestions() {
  try {
    const res = await fetch(`${API_BASE}/init-samples`, { method: "POST" });
    const data = await res.json();
    showToast(data.message || "Đã nạp câu hỏi mẫu thành công!");
    if (typeof broadcastNewQuestions === "function") {
      broadcastNewQuestions(null, "Nạp mẫu");
    }
    loadDashboardStats();
    if (State.currentView === "bank") loadQuestions();
  } catch (err) {
    showToast("Lỗi nạp câu hỏi mẫu", "error");
  }
}

/**
 * Chuẩn hóa biểu thức toán học và ký hiệu khoa học (Canonical 4-stage pipeline)
 * Bảo vệ tuyệt đối các khối KaTeX sẵn có, tự động bọc công thức thô thành khối hoàn chỉnh.
 */
function formatMathSymbols(str) {
  if (!str) return "";
  let s = String(str);

  // BƯỚC -1: Lột dấu $ quanh số lẻ ($50$ -> 50). Dữ liệu sinh tự động bọc
  // số thường trong math delimiter; giữ lại sẽ lộ "$50$" trên màn hình
  // (cơ chế bảo vệ currency bên dưới khôi phục nguyên dấu $).
  if (typeof stripBareNumberDelimiters === "function") {
    s = stripBareNumberDelimiters(s);
  } else {
    s = s.replace(/\$(\s*\d(?:[\d\s.,+\-*/=()<>]*\d)?\s*)\$/g, (m, inner) => (/[A-Za-z\\]/.test(inner) ? m : inner));
  }

  // ---------------------------------------------------------
  // BƯỚC 0: Nhận diện và bảo vệ ký hiệu tiền tệ ($3, $20, $ 50, 3$, ...)
  // Thay thế dấu $ tiền tệ thành <span class="currency-dollar">$</span> trước khi tìm khối toán học
  // ---------------------------------------------------------
  // 1. Dấu $ đứng trước số tiền: $3, $20, $ 50, $3.5, $100,000 (theo sau bởi dấu câu, khoảng trắng hoặc hết chuỗi, không phải biến số như $3x)
  s = s.replace(/(^|[\s\(>«"“'])\$\s*(\d+(?:[.,]\d+)?)(?=[\s\.,;:!?\)<»"”']|$)/g, '$1<span class="currency-dollar">$</span>$2');
  // 2. Dấu $ đứng sau số: 3$, 50 $, 100$ (không đứng sau toán tử toán học như = 0$, + 5$, v.v.)
  s = s.replace(/(\b\d+(?:[.,]\d+)?)\s*\$(?=[\s.,;:!?«»"”']|$)/g, '$1<span class="currency-dollar">$</span>');

  // ---------------------------------------------------------
  // BƯỚC 1: Bảo vệ toàn bộ các khối toán học sẵn có
  // ---------------------------------------------------------
  const mathBlocks = [];
  const saveMath = (match) => {
    const idx = mathBlocks.length;
    mathBlocks.push(match);
    return `___MATH_BLOCK_${idx}___`;
  };

  // Nhận diện: $$...$$, \[...\], \(...\), $...$ (nội dung không rỗng)
  // Nếu nội dung bên trong $...$ chứa câu tiếng Việt (kết thúc câu . , ? , ! ) hoặc chữ tiếng Việt có dấu thanh
  // thì KHÔNG coi đó là công thức toán học.
  const vietnameseAccentRegex = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]/;
  const sentenceEndRegex = /[\.?!]\s+/;

  const mathBlockRegex = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$(?:\\\$|[^\$\n])+?\$)/g;
  s = s.replace(mathBlockRegex, (match) => {
    if (match.startsWith("$") && !match.startsWith("$$") && match.endsWith("$")) {
      const inner = match.slice(1, -1);
      if (sentenceEndRegex.test(inner) || vietnameseAccentRegex.test(inner)) {
        return match;
      }
    }
    return saveMath(match);
  });

  // ---------------------------------------------------------
  // BƯỚC 2: Nhận diện biểu thức toán thô chưa bọc delimiter
  // Ví dụ: M=\frac{3}{4}+\frac{2}{5} hoặc \frac{1}{2} + \frac{3}{4}
  // ---------------------------------------------------------
  const formulaRegex = /(^|[\s:;,\(])((?:[A-Za-z]\s*=\s*)?(?:\\frac\{[^{}]+\}\{[^{}]+\}|\\sqrt\{[^{}]+\}|[0-9]+|[+\-*/=><\(\)\.]|\s+)*(?:\\frac\{[^{}]+\}\{[^{}]+\}|\\sqrt\{[^{}]+\})(?:\\frac\{[^{}]+\}\{[^{}]+\}|\\sqrt\{[^{}]+\}|[0-9]+|[+\-*/=><\(\)\.]|\s+)*)([\s\.,;:!?\)]|$)/g;

  s = s.replace(formulaRegex, (match, prefix, formulaGroup, suffix) => {
    let raw = formulaGroup;
    const leadingSpace = raw.match(/^\s*/)[0];
    const trailingSpace = raw.match(/\s*$/)[0];
    raw = raw.trim();

    // Tách dấu câu tiếng Việt nếu bị dính ở cuối (., :, ;)
    let trailingPunct = "";
    const punctMatch = raw.match(/[\.,;:!?]+$/);
    if (punctMatch) {
      trailingPunct = punctMatch[0];
      raw = raw.slice(0, -trailingPunct.length).trim();
    }

    // Tách cặp ngoặc đơn bao trọn bên ngoài nếu có: (formula) -> ($formula$)
    if (raw.startsWith("(") && raw.endsWith(")")) {
      let depth = 0;
      let allEnclosed = true;
      for (let i = 0; i < raw.length - 1; i++) {
        if (raw[i] === "(") depth++;
        else if (raw[i] === ")") {
          depth--;
          if (depth === 0) { allEnclosed = false; break; }
        }
      }
      if (allEnclosed && depth === 1) {
        prefix += "(";
        suffix = ")" + suffix;
        raw = raw.slice(1, -1).trim();
      }
    }
    if (!raw) return match;

    const idx = mathBlocks.length;
    mathBlocks.push(`$${raw}$`);
    return `${prefix}${leadingSpace}___MATH_BLOCK_${idx}___${trailingPunct}${trailingSpace}${suffix}`;
  });

  // Xử lý vét cạn cho các phân số hoặc căn thức đơn lẻ nếu còn sót
  s = s.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, (match, num, den) => {
    const idx = mathBlocks.length;
    mathBlocks.push(`$\\frac{${num}}{${den}}$`);
    return `___MATH_BLOCK_${idx}___`;
  });

  s = s.replace(/\\sqrt\{([^{}]+)\}/g, (match, inner) => {
    const idx = mathBlocks.length;
    mathBlocks.push(`$\\sqrt{${inner}}$`);
    return `___MATH_BLOCK_${idx}___`;
  });

  // ---------------------------------------------------------
  // BƯỚC 3: Xử lý ký hiệu đơn vị và công thức hóa học trong văn bản thường
  // ---------------------------------------------------------
  s = s.replace(/(\b(?:m|cm|dm|mm|km))\^2\b/g, '$1²');
  s = s.replace(/(\b(?:m|cm|dm|mm|km))\^3\b/g, '$1³');
  s = s.replace(/\bH2O\b/g, 'H₂O');
  s = s.replace(/\bCO2\b/g, 'CO₂');
  s = s.replace(/\bO2\b/g, 'O₂');
  s = s.replace(/\bN2\b/g, 'N₂');
  s = s.replace(/\bH2SO4\b/g, 'H₂SO₄');
  s = s.replace(/\bCaCO3\b/g, 'CaCO₃');

  // ---------------------------------------------------------
  // BƯỚC 4: Khôi phục an toàn các khối toán học bằng hàm callback
  // ---------------------------------------------------------
  for (let idx = 0; idx < mathBlocks.length; idx++) {
    s = s.replace(`___MATH_BLOCK_${idx}___`, () => mathBlocks[idx]);
  }

  return s;
}
window.formatMathSymbols = formatMathSymbols;

// Placeholder token: protects currency patterns ($50000$, $100000$) from being
// parsed as KaTeX math delimiters. Uses \u0001/\u0002 control chars — never a
// backslash, so a failed restore can NEVER render a stray "\" before digits.
const CURRENCY_TOKEN_OPEN = "";
const CURRENCY_TOKEN_CLOSE = "";

// Bare-number delimiters ($50$, $50000$) are plain numbers wrongly wrapped in
// math delimiters by data generators. Render them as TEXT (drop the dollars),
// never via KaTeX. Real formulas (contain a backslash or letters, e.g.
// fractions, units, variables) still go through KaTeX untouched.
//
// Pure helper — kept out of renderMath so node tests can call it directly.
function stripBareNumberDelimiters(str) {
  if (!str || typeof str !== "string") return str || "";
  // Match $...$ whose inner is ONLY digits/operators/spaces (no letters,
  // no backslash, no ^_{}). $48 + 27$ -> text; $A$, $\frac{}{}$, $7^{2024}$,
  // $165\text{ km}$ all keep their dollars for KaTeX.
  return str.replace(/\$(\s*\d(?:[\d\s.,+\-*/=()<>]*\d)?\s*)\$/g, (m, inner) => {
    // Safety: a letter or backslash inside means a real formula — keep it.
    if (/[A-Za-z\\]/.test(inner)) return m;
    return inner;
  });
}

// Pure helper: replace currency $...$ (digits inside, no letters/backslash —
// i.e. NOT a formula like $\frac{}{}$ or $\text{}$) with placeholder tokens.
// Real formulas are returned byte-identical.
function escapeCurrencyForKatex(str) {
  if (!str || typeof str !== "string") return str || "";
  return str.replace(/\$(\s*\d[\d\s.,]*)\$/g, (m, inner) => {
    // Safety: if inner contains a letter or backslash it is a formula — keep.
    if (/[A-Za-z\\]/.test(inner)) return m;
    return CURRENCY_TOKEN_OPEN + inner + CURRENCY_TOKEN_CLOSE;
  });
}

// Pure helper: restore placeholders back to the original $...$ text.
function restoreCurrencyAfterKatex(str) {
  if (!str || typeof str !== "string") return str || "";
  return str
    .split(CURRENCY_TOKEN_OPEN).join("$")
    .split(CURRENCY_TOKEN_CLOSE).join("$");
}

// Render KaTeX formulas in an element
function renderMath(container) {
  if (!container || !window.renderMathInElement) return;

  // 1. Quét các text nodes trong container, thay các cụm tiền tệ $50000$
  // bằng placeholder (không bao giờ dùng backslash để escape).
  const walker = document.createTreeWalker(
    container,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode(node) {
        if (!node.nodeValue || !node.nodeValue.includes('$')) {
          return NodeFilter.FILTER_REJECT;
        }
        const parent = node.parentElement;
        if (parent && (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE' || parent.classList.contains('katex'))) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    },
    false
  );

  const matchedNodes = [];
  let current;
  while ((current = walker.nextNode())) {
    matchedNodes.push(current);
  }

  matchedNodes.forEach(node => {
    // Lột $ quanh số lẻ TRƯỚC ($50$ -> 50 hiện text thường), rồi mới bảo vệ
    // currency còn sót. Không có bước này, khôi phục currency trả nguyên $50$.
    node.nodeValue = stripBareNumberDelimiters(node.nodeValue);
    node.nodeValue = escapeCurrencyForKatex(node.nodeValue);
  });

  try {
    window.renderMathInElement(container, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true }
      ],
      throwOnError: false
    });
  } finally {
    // 2. Khôi phục placeholder về $...$ gốc sau khi render hoàn tất
    const restoreIn = (node) => {
      if (node.nodeValue && (node.nodeValue.includes(CURRENCY_TOKEN_OPEN) || node.nodeValue.includes(CURRENCY_TOKEN_CLOSE))) {
        node.nodeValue = restoreCurrencyAfterKatex(node.nodeValue);
      }
    };
    matchedNodes.forEach(restoreIn);

    // Quét bổ sung phòng trường hợp KaTeX chia tách text nodes
    const cleanupWalker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          if (node.nodeValue && (node.nodeValue.includes(CURRENCY_TOKEN_OPEN) || node.nodeValue.includes(CURRENCY_TOKEN_CLOSE))) {
            const parent = node.parentElement;
            if (parent && (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE' || parent.classList.contains('katex'))) {
              return NodeFilter.FILTER_REJECT;
            }
            return NodeFilter.FILTER_ACCEPT;
          }
          return NodeFilter.FILTER_REJECT;
        }
      },
      false
    );
    let cNode;
    while ((cNode = cleanupWalker.nextNode())) {
      restoreIn(cNode);
    }
  }
}

// Real-time synchronization & live reload
function startRealtimeSync() {
  // 1. Multi-tab broadcast channel
  if (liveSyncChannel) {
    liveSyncChannel.onmessage = (event) => {
      if (event.data && event.data.type === "new_questions") {
        onNewQuestionsDetected(event.data.count, event.data.source);
      }
    };
  }

  // 2. Heartbeat polling every 3 seconds to catch questions saved from Extension / background scraper
  if (realtimeSyncInterval) clearInterval(realtimeSyncInterval);
  realtimeSyncInterval = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/stats`);
      if (!res.ok) return;
      const data = await res.json();
      const currentCount = data.total_questions || 0;

      if (lastKnownQuestionCount !== null && currentCount > lastKnownQuestionCount) {
        const added = currentCount - lastKnownQuestionCount;
        lastKnownQuestionCount = currentCount;
        onNewQuestionsDetected(added, "Tự động phát hiện");
      } else if (lastKnownQuestionCount === null) {
        lastKnownQuestionCount = currentCount;
      }
    } catch (e) {
      // Quietly ignore network blips during polling
    }
  }, 3000);
}

function onNewQuestionsDetected(addedCount, source) {
  const msg = addedCount ? `✨ Có ${addedCount} câu hỏi mới (${source || 'Hệ thống'})!` : "✨ Có câu hỏi mới được cập nhật!";
  showToast(msg, "success");

  // Always refresh dashboard stats
  loadDashboardStats();

  // If user is currently viewing the Question Bank, refresh the view immediately!
  if (State.currentView === "bank") {
    loadQuestions();
  }
}

function broadcastNewQuestions(count, source) {
  if (liveSyncChannel) {
    try {
      liveSyncChannel.postMessage({ type: "new_questions", count, source });
    } catch (e) {}
  }
}

// Init when page loads
document.addEventListener("DOMContentLoaded", () => {
  // Sync APP_VERSION to all version badges & sidebar footer
  document.querySelectorAll(".app-version-badge").forEach(el => el.textContent = APP_VERSION);
  const sidebarVer = document.getElementById("sidebar-version-tag");
  if (sidebarVer) sidebarVer.textContent = `Phiên bản: ${APP_VERSION}`;

  // Question Bank starts with all grades, all subjects, all platforms, 50 items per page
  State.filters.grade = "";
  State.filters.platform = "all";
  State.filters.subject = "all";
  State.filters.page_size = 50;

  // Setup nav click events
  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      switchView(item.dataset.view);
    });
  });

  // Start real-time background sync
  startRealtimeSync();

  // Login wall: ai có link đều mở được trang, nhưng phải đăng nhập mới
  // dùng được dữ liệu (backend gate 401 mọi /api/* trừ auth/version +
  // extension-sync). Không login → tường che toàn màn hình ngay.
  if (window.EduAuth && typeof window.EduAuth.requireLogin === "function") {
    window.EduAuth.requireLogin().then(function (ok) {
      if (ok) switchView("dashboard");
    });
  } else {
    // Load initial view
    switchView("dashboard");
  }
});
