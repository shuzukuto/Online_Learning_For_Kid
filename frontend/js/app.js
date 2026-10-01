// EduQuest Pro - Core Application & Router
const APP_VERSION = "v1.0.17";
const API_BASE = "http://localhost:8000/api";

let lastKnownQuestionCount = null;
let realtimeSyncInterval = null;
const liveSyncChannel = ("BroadcastChannel" in window) ? new BroadcastChannel("eduquest_live_sync") : null;

const State = {
  currentView: "dashboard",
  selectedQuestionIds: new Set(),
  stats: null,
  cachedQuestions: [],
  filters: {
    platform: "all",
    subject: "all",
    grade: "",
    topic: "",
    question_type: "all",
    difficulty: "all",
    search: "",
    source_detail: "all",
    only_duplicates: false,
    sort_by: "q_number_asc",
    page: 1,
    page_size: 50
  }
};

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
    builder: { title: "Biên soạn & Trộn Đề thi", sub: "Tùy biến đề thi chuẩn format và xuất file Word (.docx)" },
    collector: { title: "Trung tâm Thu thập", sub: "Tiện ích Extension, Bóc tách PDF (TIMO, ASMO) & Cào tự động" },
    manual: { title: "Soạn thảo Câu hỏi Mới", sub: "Trình soạn câu hỏi với hiển thị công thức LaTeX trực tiếp" }
  };

  const headerInfo = titles[viewName] || { title: "EduQuest Pro", sub: "" };
  document.getElementById("page-main-title").innerText = headerInfo.title;
  document.getElementById("page-sub-title").innerText = headerInfo.sub;

  // View-specific initializers
  if (viewName === "dashboard") loadDashboardStats();
  if (viewName === "bank") loadQuestions();
  if (viewName === "builder") renderExamBuilderView();
  if (viewName === "collector") loadCollectorLogs();
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
    const res = await fetch(`${API_BASE}/stats`);
    const data = await res.json();
    State.stats = data;

    if (lastKnownQuestionCount === null) {
      lastKnownQuestionCount = data.total_questions || 0;
    }

    document.getElementById("stat-total-q").innerText = data.total_questions || 0;
    document.getElementById("stat-total-exams").innerText = data.total_exams || 0;

    // Platform counts
    const pVio = data.by_platform?.vioedu || 0;
    const pTn = data.by_platform?.tnmath || 0;
    const pTimo = (data.by_platform?.timo || 0) + (data.by_platform?.hkimo || 0) + (data.by_platform?.asmo || 0);
    const pHunter = data.by_platform?.internet_hunter || 0;
    const pHts = data.by_platform?.hanhtrangso || 0;
    const pManual = data.by_platform?.manual || 0;

    document.getElementById("stat-vioedu-count").innerText = pVio;
    document.getElementById("stat-tnmath-count").innerText = pTn;
    document.getElementById("stat-olympiad-count").innerText = pTimo;

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

// Render KaTeX formulas in an element
function renderMath(container) {
  if (window.renderMathInElement && container) {
    window.renderMathInElement(container, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true }
      ],
      throwOnError: false
    });
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

  // Load initial view
  switchView("dashboard");
});
