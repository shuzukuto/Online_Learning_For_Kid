// EduQuest Pro - Collector Hub, PDF Importer & Auto-Hunter
let lastExtractedPdfQuestions = [];
let autoHunterTimer = null;
let autoHunterCountdown = 300; // 5 minutes countdown
let countdownInterval = null;

function setupDropzone() {
  const dropzone = document.getElementById("pdf-dropzone");
  const fileInput = document.getElementById("pdf-file-input");
  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handlePdfUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handlePdfUpload(e.target.files[0]);
    }
  });
}

async function handlePdfUpload(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showToast("Vui lòng chọn file định dạng PDF đề thi", "error");
    return;
  }

  const resultContainer = document.getElementById("pdf-result-container");
  resultContainer.style.display = "block";
  resultContainer.innerHTML = `
    <div style="text-align: center; padding: 30px; color: #64748b;">
      <div style="font-size: 28px; margin-bottom: 8px;">⏳</div>
      <p>Đang phân tích cấu trúc & bóc tách câu hỏi từ file <strong>${file.name}</strong>...</p>
    </div>
  `;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("save_to_bank", "false"); // Just preview first

  try {
    const res = await fetch(`${API_BASE}/import/pdf`, {
      method: "POST",
      body: formData
    });
    const data = await res.json();

    if (!data.success || !data.preview_questions || data.preview_questions.length === 0) {
      resultContainer.innerHTML = `
        <div style="padding: 20px; background: #fff1f2; border: 1px solid #fecdd3; border-radius: 10px; color: #be123c;">
          ⚠️ Không tìm thấy câu hỏi nào theo định dạng chuẩn trong file PDF này.
        </div>
      `;
      return;
    }

    lastExtractedPdfQuestions = data.preview_questions;

    resultContainer.innerHTML = `
      <div style="background: white; border: 1px solid #e2e8f0; border-radius: 14px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <div>
            <h4 style="font-size: 15px; font-weight: 700;">Đã bóc tách thành công: ${data.total_extracted} câu hỏi</h4>
            <span style="font-size: 12.5px; color: #64748b;">Nguồn phát hiện: ${data.preview_questions[0].source_platform.toUpperCase()} - Khối ${data.preview_questions[0].grade}</span>
          </div>
          <button class="btn btn-success" id="btn-save-extracted-pdf" onclick="saveExtractedPdfToBank()">
            ✓ Lưu toàn bộ ${data.total_extracted} câu vào Ngân hàng
          </button>
        </div>

        <div style="display: flex; flex-direction: column; gap: 12px; max-height: 480px; overflow-y: auto;">
          ${data.preview_questions.map((q, idx) => `
            <div style="padding: 12px 14px; border: 1px solid #f1f5f9; border-radius: 8px; background: #f8fafc;">
              <div style="font-weight: 700; font-size: 13px; color: #2563eb; margin-bottom: 4px;">
                Câu ${idx + 1} (${q.question_type})
              </div>
              <div style="font-size: 13.5px; margin-bottom: 6px;">${q.content_text}</div>
              ${q.options && q.options.length > 0 ? `
                <div style="font-size: 12.5px; color: #475569; display: flex; gap: 14px; flex-wrap: wrap;">
                  ${q.options.map(o => `<span><strong>${o.id}.</strong> ${o.content}</span>`).join("")}
                </div>
              ` : ''}
            </div>
          `).join("")}
        </div>
      </div>
    `;

    renderMath(resultContainer);

  } catch (err) {
    resultContainer.innerHTML = `<div style="color: #ef4444; padding: 20px;">Lỗi xử lý file PDF: ${err.message}</div>`;
  }
}

async function saveExtractedPdfToBank() {
  if (!lastExtractedPdfQuestions || lastExtractedPdfQuestions.length === 0) return;
  const btn = document.getElementById("btn-save-extracted-pdf");
  btn.disabled = true;
  btn.innerText = "Đang lưu vào ngân hàng...";

  try {
    const res = await fetch(`${API_BASE}/questions/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions: lastExtractedPdfQuestions })
    });
    const data = await res.json();
    showToast(`Thành công! Đã lưu ${data.inserted_count} câu hỏi vào Ngân hàng.`);
    btn.innerText = "✓ Đã lưu xong!";
    if (typeof broadcastNewQuestions === "function") {
      broadcastNewQuestions(data.inserted_count, "Bóc tách PDF");
    }
    loadDashboardStats();
    if (State.currentView === "bank") loadQuestions();
  } catch (err) {
    showToast("Lỗi lưu câu hỏi", "error");
    btn.disabled = false;
  }
}

// Scraper Runner
async function runAutoScraper() {
  const platform = document.getElementById("scraper-platform").value;
  const username = document.getElementById("scraper-username").value.trim();
  const password = document.getElementById("scraper-password").value.trim();
  const roundId = document.getElementById("scraper-round").value.trim();
  const grade = parseInt(document.getElementById("scraper-grade").value) || 5;

  const logBox = document.getElementById("scraper-live-log");
  logBox.style.display = "block";
  logBox.innerText = `[${new Date().toLocaleTimeString()}] Bắt đầu kết nối đến nền tảng ${platform.toUpperCase()}...\n`;
  localStorage.setItem("eduquest_scraper_log", logBox.innerText);

  try {
    logBox.innerText += `[${new Date().toLocaleTimeString()}] Đang xác thực tài khoản ${username || "(Ẩn danh)"}...\n`;
    localStorage.setItem("eduquest_scraper_log", logBox.innerText);

    const res = await fetch(`${API_BASE}/collect/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform: platform,
        action: "login",
        username: username,
        password: password,
        round_id: roundId,
        grade: grade
      })
    });

    const data = await res.json();
    if (data.success) {
      logBox.innerText += `[${new Date().toLocaleTimeString()}] Đăng nhập thành công! Token đã được cấp phát.\n`;
      logBox.innerText += `[${new Date().toLocaleTimeString()}] Gợi ý: Hãy cài đặt Tiện ích Extension để bắt câu hỏi 1-click trực tiếp trong phiên học mà không cần nhập mật khẩu lại.\n`;
      showToast("Kết nối tài khoản thành công!");
    } else {
      logBox.innerText += `[${new Date().toLocaleTimeString()}] Thông báo: ${data.error || "Chưa thể kết nối trực tiếp hoặc tài khoản chưa chính xác."}\n`;
      logBox.innerText += `[${new Date().toLocaleTimeString()}] => Hãy sử dụng Tiện ích Trình duyệt (Chrome Extension) để cào câu hỏi khi đang đăng nhập trên trình duyệt.\n`;
    }
    localStorage.setItem("eduquest_scraper_log", logBox.innerText);
    loadCollectorLogs();
  } catch (err) {
    logBox.innerText += `[${new Date().toLocaleTimeString()}] Lỗi: ${err.message}\n`;
    localStorage.setItem("eduquest_scraper_log", logBox.innerText);
  }
}

// Load Collector Logs
async function loadCollectorLogs() {
  const listEl = document.getElementById("collector-logs-list");
  if (!listEl) return;

  try {
    const res = await fetch(`${API_BASE}/collect/logs`);
    const logs = await res.json();

    if (!logs || logs.length === 0) {
      listEl.innerHTML = `<div style="text-align: center; color: #94a3b8; font-size: 13px; padding: 20px;">Chưa có hoạt động thu thập nào.</div>`;
      return;
    }

    listEl.innerHTML = logs.map(l => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border-bottom: 1px solid #f1f5f9; font-size: 13px;">
        <div>
          <span class="tag-badge platform-${l.platform}">${l.platform}</span>
          <span style="font-weight: 600; margin-left: 8px;">${l.message || "Thu thập câu hỏi"}</span>
        </div>
        <div style="color: #64748b; font-size: 12px;">
          ${new Date(l.created_at).toLocaleString("vi-VN")}
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Error loading logs:", err);
  }
}

async function copyCollectorLogs() {
  try {
    const res = await fetch(`${API_BASE}/collect/logs`);
    const logs = await res.json();
    if (!logs || logs.length === 0) {
      showToast("Chưa có nhật ký nào để sao chép", "error");
      return;
    }
    const text = logs.map(l => `[${new Date(l.created_at).toLocaleString("vi-VN")}] [${l.platform.toUpperCase()}] [${l.status.toUpperCase()}] ${l.message}`).join("\n");
    await navigator.clipboard.writeText(text);
    showToast("Đã sao chép toàn bộ nhật ký debug vào clipboard!");
  } catch (err) {
    showToast("Lỗi sao chép: " + err.message, "error");
  }
}

async function clearAllCollectorLogs() {
  if (!confirm("Bạn có chắc chắn muốn xóa sạch toàn bộ nhật ký hoạt động thu thập?")) return;
  try {
    const res = await fetch(`${API_BASE}/collect/logs`, { method: "DELETE" });
    const data = await res.json();
    showToast(data.message || "Đã xóa toàn bộ nhật ký");
    loadCollectorLogs();
  } catch (err) {
    showToast("Lỗi xóa nhật ký", "error");
  }
}

// Target URLs list for Internet Hunter
let hunterTargetUrls = [];

function loadHunterTargetUrls() {
  try {
    const raw = localStorage.getItem("eduquest_hunter_urls");
    hunterTargetUrls = raw ? JSON.parse(raw) : [];
  } catch (e) {
    hunterTargetUrls = [];
  }
}

function saveHunterTargetUrls() {
  localStorage.setItem("eduquest_hunter_urls", JSON.stringify(hunterTargetUrls));
  renderHunterUrlsList();
}

function addPresetHunterTarget(url) {
  if (!url) return;
  const exists = hunterTargetUrls.some(u => u.url.toLowerCase() === url.toLowerCase());
  if (exists) {
    showToast("Nguồn này đã có trong danh sách cào!", "info");
    return;
  }
  const newEntry = {
    id: "url_" + Date.now(),
    url: url,
    active: true,
    addedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  };
  hunterTargetUrls.unshift(newEntry);
  saveHunterTargetUrls();
  showToast("Đã thêm nguồn nhanh vào danh sách cào!");
}

function addHunterTargetUrl() {
  const input = document.getElementById("hunter-url-input");
  if (!input) return;
  const val = input.value.trim();
  if (!val) {
    showToast("Vui lòng nhập đường dẫn web hoặc từ khóa", "error");
    input.focus();
    return;
  }

  const exists = hunterTargetUrls.some(u => u.url.toLowerCase() === val.toLowerCase());
  if (exists) {
    showToast("Link này đã có trong danh sách cào!", "error");
    return;
  }

  const newEntry = {
    id: "url_" + Date.now(),
    url: val,
    active: true,
    addedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  };

  hunterTargetUrls.unshift(newEntry);
  saveHunterTargetUrls();
  input.value = "";
  showToast("Đã thêm trang web vào danh sách cào dữ liệu!");
}

function removeHunterTargetUrl(id) {
  hunterTargetUrls = hunterTargetUrls.filter(u => u.id !== id);
  saveHunterTargetUrls();
  showToast("Đã xóa khỏi danh sách cào.");
}

function toggleHunterUrlActive(id) {
  const item = hunterTargetUrls.find(u => u.id === id);
  if (item) {
    item.active = !item.active;
    saveHunterTargetUrls();
  }
}

function clearAllHunterTargetUrls() {
  if (hunterTargetUrls.length === 0) return;
  if (!confirm("Bạn có chắc chắn muốn xóa toàn bộ các link web đã lưu?")) return;
  hunterTargetUrls = [];
  saveHunterTargetUrls();
  showToast("Đã dọn sạch danh sách web cào.");
}

function renderHunterUrlsList() {
  const container = document.getElementById("hunter-urls-container");
  const countBadge = document.getElementById("hunter-urls-count");
  const clearBtn = document.getElementById("btn-clear-hunter-urls");

  if (countBadge) countBadge.innerText = hunterTargetUrls.length;
  if (clearBtn) clearBtn.style.display = hunterTargetUrls.length > 0 ? "inline" : "none";
  if (!container) return;

  if (hunterTargetUrls.length === 0) {
    container.innerHTML = `
      <div style="font-size: 12px; color: #94a3b8; font-style: italic; padding: 10px 14px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; text-align: center;">
        Chưa có link web nào. Nhập link và nhấn "➕ Thêm vào danh sách" để tự động cào câu hỏi.
      </div>
    `;
    return;
  }

  container.innerHTML = hunterTargetUrls.map(item => `
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 7px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px;">
      <div style="display: flex; align-items: center; gap: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;">
        <input type="checkbox" ${item.active ? 'checked' : ''} onchange="toggleHunterUrlActive('${item.id}')" title="${item.active ? 'Đang bật cào: Bỏ chọn để tạm dừng' : 'Đang tạm dừng: Tích chọn để cào'}" style="cursor: pointer; width: 15px; height: 15px;" />
        <span style="font-size: 14px;">🌐</span>
        <span style="font-family: monospace; font-size: 12.5px; color: ${item.active ? '#1e293b' : '#94a3b8'}; text-decoration: ${item.active ? 'none' : 'line-through'}; font-weight: 500; overflow: hidden; text-overflow: ellipsis;" title="${item.url}">
          ${item.url}
        </span>
        <span style="font-size: 11px; color: #94a3b8; margin-left: 6px; white-space: nowrap;">[${item.addedAt}]</span>
      </div>
      <button type="button" onclick="removeHunterTargetUrl('${item.id}')" style="background: none; border: none; color: #94a3b8; font-size: 14px; cursor: pointer; padding: 2px 6px; border-radius: 4px; line-height: 1;" title="Xóa link này" onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='#94a3b8'">
        ✕
      </button>
    </div>
  `).join("");
}

// Internet Question Hunter Runner
async function runInternetHunter(isAuto = false) {
  const subject = document.getElementById("hunter-subject").value;
  const grade = parseInt(document.getElementById("hunter-grade").value) || 5;
  const activeCustomUrls = hunterTargetUrls.filter(u => u.active).map(u => u.url);
  const logBox = document.getElementById("hunter-live-log");
  const btn = document.getElementById("btn-run-hunter");

  logBox.style.display = "block";
  if (!isAuto) {
    btn.disabled = true;
    btn.innerText = "⏳ Đang quét internet...";
  }

  let introLog = `[${new Date().toLocaleTimeString()}] ${isAuto ? "🔄 [TỰ ĐỘNG ĐỊNH KỲ]" : "⚡ [THỦ CÔNG]"} Săn câu hỏi (Môn: ${subject.toUpperCase()}, Khối ${grade})...\n`;
  if (activeCustomUrls.length > 0) {
    introLog += `-> Danh sách mục tiêu: Sẽ cào ${activeCustomUrls.length} web/link: ${activeCustomUrls.slice(0, 2).join(', ')}${activeCustomUrls.length > 2 ? '...' : ''}\n`;
  }
  logBox.innerText += introLog;
  localStorage.setItem("eduquest_hunter_log", logBox.innerText);

  try {
    const res = await fetch(`${API_BASE}/hunter/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: subject,
        grade: grade,
        custom_urls: activeCustomUrls
      })
    });

    const data = await res.json();
    if (data.success) {
      logBox.innerText += `[${new Date().toLocaleTimeString()}] Thu thập thành công! Đã bóc tách và lưu ${data.total_harvested} câu hỏi vào CSDL.\n`;
      localStorage.setItem("eduquest_hunter_log", logBox.innerText);
      showToast(`Đã săn thành công ${data.total_harvested} câu hỏi từ Internet!`);
      if (typeof broadcastNewQuestions === "function") {
        broadcastNewQuestions(data.total_harvested, "Săn Internet");
      }
      loadDashboardStats();
      loadCollectorLogs();
      if (State.currentView === "bank") loadQuestions();
    } else {
      logBox.innerText += `[${new Date().toLocaleTimeString()}] Thông báo: ${data.error || "Không tìm thấy dữ liệu mới."}\n`;
      localStorage.setItem("eduquest_hunter_log", logBox.innerText);
    }
  } catch (err) {
    logBox.innerText += `[${new Date().toLocaleTimeString()}] Lỗi kết nối: ${err.message}\n`;
    localStorage.setItem("eduquest_hunter_log", logBox.innerText);
    if (!isAuto) showToast("Lỗi khi săn câu hỏi Internet", "error");
  } finally {
    if (!isAuto) {
      btn.disabled = false;
      btn.innerText = "⚡ Bắt đầu Săn câu hỏi từ Internet";
    }
  }
}

// Auto-Hunter Loop Implementation
function toggleAutoHunter(enable) {
  localStorage.setItem("eduquest_autohunter", enable ? "true" : "false");
  const badge = document.getElementById("hunter-countdown-badge");
  
  if (enable) {
    if (badge) badge.style.display = "inline-flex";
    startAutoHunterLoop();
    showToast("Đã BẬT chế độ Tự động săn định kỳ (mỗi 5 phút)!");
  } else {
    if (badge) badge.style.display = "none";
    stopAutoHunterLoop();
    showToast("Đã TẮT chế độ Tự động săn định kỳ.");
  }
}

function startAutoHunterLoop() {
  stopAutoHunterLoop();
  autoHunterCountdown = 300; // 5 minutes = 300 seconds
  updateCountdownUI();

  countdownInterval = setInterval(() => {
    autoHunterCountdown--;
    updateCountdownUI();

    if (autoHunterCountdown <= 0) {
      runInternetHunter(true);
      autoHunterCountdown = 300;
    }
  }, 1000);
}

function stopAutoHunterLoop() {
  if (countdownInterval) clearInterval(countdownInterval);
  countdownInterval = null;
}

function updateCountdownUI() {
  const secEl = document.getElementById("hunter-countdown-sec");
  if (secEl) {
    const m = Math.floor(autoHunterCountdown / 60);
    const s = autoHunterCountdown % 60;
    secEl.innerText = `${m}m ${s < 10 ? '0' : ''}${s}s`;
  }
}

// Grade Persistence & Settings Management
function setDefaultGrade(grade) {
  localStorage.setItem("eduquest_default_grade", grade);
  localStorage.setItem("eduquest_selected_grade", grade);
  applyGradeToAllSelectors(grade);
  showToast(`Đã lưu Khối lớp ${grade} làm mặc định toàn hệ thống!`);
}

function onGradeSelectChanged(grade) {
  localStorage.setItem("eduquest_selected_grade", grade);
  applyGradeToAllSelectors(grade);
}

function applyGradeToAllSelectors(grade) {
  // Apply only to collector tools and manual creation forms, never restrict Question Bank view
  const ids = ["global-default-grade", "hunter-grade", "scraper-grade", "m-grade"];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = grade;
  });
}

function restoreCollectorSettings() {
  // 1. Restore grade for collector tools only
  const savedGrade = localStorage.getItem("eduquest_default_grade") || localStorage.getItem("eduquest_selected_grade") || "5";
  applyGradeToAllSelectors(savedGrade);

  // 2. Restore scraper credentials
  const savedPlat = localStorage.getItem("eduquest_scraper_plat");
  if (savedPlat) {
    const el = document.getElementById("scraper-platform");
    if (el) el.value = savedPlat;
  }

  const savedUser = localStorage.getItem("eduquest_scraper_user");
  if (savedUser) {
    const el = document.getElementById("scraper-username");
    if (el) el.value = savedUser;
  }

  const savedRound = localStorage.getItem("eduquest_scraper_round");
  if (savedRound) {
    const el = document.getElementById("scraper-round");
    if (el) el.value = savedRound;
  }

  // 3. Restore auto-hunter toggle
  const isAutoHunter = localStorage.getItem("eduquest_autohunter") === "true";
  const toggleEl = document.getElementById("hunter-auto-loop");
  if (toggleEl) {
    toggleEl.checked = isAutoHunter;
    if (isAutoHunter) {
      const badge = document.getElementById("hunter-countdown-badge");
      if (badge) badge.style.display = "inline-flex";
      startAutoHunterLoop();
    }
  }

  // 4. Restore hunter target URLs list
  loadHunterTargetUrls();
  renderHunterUrlsList();

  // 5. Restore persistent live logs
  const savedHunterLog = localStorage.getItem("eduquest_hunter_log");
  const hunterLogBox = document.getElementById("hunter-live-log");
  if (savedHunterLog && hunterLogBox) {
    hunterLogBox.style.display = "block";
    hunterLogBox.innerText = savedHunterLog;
  }

  const savedScraperLog = localStorage.getItem("eduquest_scraper_log");
  const scraperLogBox = document.getElementById("scraper-live-log");
  if (savedScraperLog && scraperLogBox) {
    scraperLogBox.style.display = "block";
    scraperLogBox.innerText = savedScraperLog;
  }
}

// Initialize Dropzone and restore settings when DOM loaded
document.addEventListener("DOMContentLoaded", () => {
  setupDropzone();
  restoreCollectorSettings();
});
