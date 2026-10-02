// EduQuest Pro - Collector Hub, PDF & Image OCR Importer, Auto-Hunter & Auto-Crawl
const SUPPORTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp"];
let currentUploadedFile = null;
let currentUploadedImageUrl = null;
let currentReviewedQuestions = [];
let autoHunterTimer = null;
let autoHunterCountdown = 300; // 5 minutes countdown
let countdownInterval = null;

function setupDropzone() {
  const dropzone = document.getElementById("pdf-dropzone");
  const fileInput = document.getElementById("pdf-file-input");
  if (!dropzone || !fileInput) return;

  fileInput.setAttribute("accept", ".pdf,.png,.jpg,.jpeg,.webp,.bmp");

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
      handleExamFileUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleExamFileUpload(e.target.files[0]);
    }
  });
}

function handlePdfUpload(file) {
  return handleExamFileUpload(file);
}

async function handleExamFileUpload(file) {
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!SUPPORTED_EXTENSIONS.includes(ext)) {
    showToast("Vui lòng chọn file định dạng PDF đề thi hoặc Ảnh (.png, .jpg, .jpeg, .webp, .bmp)", "error");
    return;
  }

  currentUploadedFile = file;
  const isImage = [".png", ".jpg", ".jpeg", ".webp", ".bmp"].includes(ext);

  const resultContainer = document.getElementById("pdf-result-container");
  if (!resultContainer) return;
  resultContainer.style.display = "block";

  // Image Preview Container if it is an image
  let imagePreviewHtml = "";
  if (isImage) {
    if (currentUploadedImageUrl) URL.revokeObjectURL(currentUploadedImageUrl);
    currentUploadedImageUrl = URL.createObjectURL(file);
    imagePreviewHtml = `
      <div id="image-preview-container" class="image-preview-container">
        <div class="image-preview-toolbar">
          <span>🖼️ Bản xem trước ảnh đề thi gốc: <strong>${file.name}</strong> (${(file.size/1024).toFixed(1)} KB)</span>
        </div>
        <img id="image-preview-img" src="${currentUploadedImageUrl}" alt="Ảnh xem trước đề thi" />
      </div>
    `;
  } else {
    imagePreviewHtml = `<div id="image-preview-container" style="display: none;"></div>`;
  }

  resultContainer.innerHTML = `
    ${imagePreviewHtml}
    <div style="text-align: center; padding: 30px; color: #64748b; background: white; border: 1px solid #e2e8f0; border-radius: 14px;">
      <div style="font-size: 28px; margin-bottom: 8px;">⏳</div>
      <p>Đang phân tích cấu trúc, nhận diện văn bản (OCR) & bóc tách câu hỏi từ file <strong>${file.name}</strong>...</p>
    </div>
  `;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("save_to_bank", "false"); // Preview & audit first

  try {
    const endpoint = isImage ? `${API_BASE}/import/image` : `${API_BASE}/import/pdf`;
    const res = await fetch(endpoint, {
      method: "POST",
      body: formData
    });
    const data = await res.json();

    if (!data.success || !data.preview_questions || data.preview_questions.length === 0) {
      resultContainer.innerHTML = `
        ${imagePreviewHtml}
        <div style="padding: 20px; background: #fff1f2; border: 1px solid #fecdd3; border-radius: 10px; color: #be123c;">
          ⚠️ Không tìm thấy câu hỏi trắc nghiệm nào trong tệp này. Vui lòng kiểm tra độ nét của ảnh hoặc định dạng PDF.
        </div>
      `;
      return;
    }

    currentReviewedQuestions = data.preview_questions.map((q, idx) => ({
      ...q,
      selected: true,
      idx: idx
    }));

    renderOcrReviewTable(data.total_extracted, file.name, isImage);

  } catch (err) {
    resultContainer.innerHTML = `
      ${imagePreviewHtml}
      <div style="color: #ef4444; padding: 20px; background: white; border: 1px solid #fee2e2; border-radius: 10px;">
        Lỗi xử lý file: ${err.message}
      </div>
    `;
  }
}

function renderOcrReviewTable(totalExtracted, filename, isImage) {
  const resultContainer = document.getElementById("pdf-result-container");
  if (!resultContainer) return;

  const rowsHtml = currentReviewedQuestions.map((q, idx) => {
    const cleanStem = q.content_text || q.content_html || "";
    const options = q.options || [
      { id: "A", content: "" }, { id: "B", content: "" }, { id: "C", content: "" }, { id: "D", content: "" }
    ];
    const correctOpt = q.correct_answer || (options.find(o => o.is_correct)?.id) || "A";

    return `
      <tr id="ocr-row-${idx}" class="${q.selected ? 'selected' : ''}">
        <td style="width: 40px; text-align: center;">
          <input type="checkbox" id="ocr-check-${idx}" ${q.selected ? 'checked' : ''} onchange="toggleOcrQuestionSelect(${idx}, this.checked)" />
        </td>
        <td style="width: 65px; font-weight: 800; color: #2563eb;">
          Câu ${idx + 1}
        </td>
        <td>
          <div style="display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">
            <select id="ocr-sub-${idx}" class="form-control" style="width: 140px; font-size: 12px; height: 32px;" onchange="updateOcrQuestionField(${idx}, 'subject', this.value)">
              <option value="math" ${q.subject === 'math' ? 'selected' : ''}>Toán học</option>
              <option value="vietnamese" ${q.subject === 'vietnamese' ? 'selected' : ''}>Tiếng Việt</option>
              <option value="english" ${q.subject === 'english' ? 'selected' : ''}>Tiếng Anh</option>
              <option value="science" ${q.subject === 'science' ? 'selected' : ''}>Khoa học</option>
            </select>
            <select id="ocr-grade-${idx}" class="form-control" style="width: 110px; font-size: 12px; height: 32px;" onchange="updateOcrQuestionField(${idx}, 'grade', parseInt(this.value))">
              ${[1,2,3,4,5,6,7,8,9,10,11,12].map(g => `<option value="${g}" ${g === (q.grade || 5) ? 'selected' : ''}>Lớp ${g}</option>`).join("")}
            </select>
          </div>
          <textarea id="ocr-stem-${idx}" class="ocr-stem-editor" placeholder="Nội dung câu hỏi..." oninput="onOcrStemInput(${idx}, this.value)">${cleanStem}</textarea>
          <div id="ocr-stem-preview-${idx}" class="stem-live-preview">${typeof formatMathSymbols === 'function' ? formatMathSymbols(cleanStem) : cleanStem}</div>
        </td>
        <td style="width: 380px;">
          <div style="display: flex; flex-direction: column; gap: 4px;">
            ${options.map(opt => `
              <div style="display: flex; align-items: center; gap: 6px;">
                <input type="radio" name="ocr-correct-${idx}" value="${opt.id}" ${correctOpt === opt.id ? 'checked' : ''} onchange="updateOcrCorrectAnswer(${idx}, '${opt.id}')" title="Chọn đáp án đúng" />
                <strong style="min-width: 18px;">${opt.id}.</strong>
                <input type="text" id="ocr-opt-${idx}-${opt.id}" class="ocr-option-input" value="${opt.content || ''}" oninput="updateOcrOptionContent(${idx}, '${opt.id}', this.value)" placeholder="Phương án ${opt.id}" />
              </div>
            `).join("")}
          </div>
        </td>
      </tr>
    `;
  }).join("");

  const imagePreviewHtml = (isImage && currentUploadedImageUrl) ? `
    <div id="image-preview-container" class="image-preview-container">
      <div class="image-preview-toolbar">
        <span>🖼️ Bản xem trước ảnh đề thi gốc: <strong>${filename}</strong></span>
      </div>
      <img id="image-preview-img" src="${currentUploadedImageUrl}" alt="Ảnh xem trước đề thi" />
    </div>
  ` : '';

  resultContainer.innerHTML = `
    ${imagePreviewHtml}
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 14px; padding: 22px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
        <div>
          <h4 style="font-size: 16px; font-weight: 800; color: #0f172a; margin-bottom: 2px;">
            🔍 Bảng Đối Soát Câu Hỏi Bóc Tách (${totalExtracted} câu)
          </h4>
          <span style="font-size: 12.5px; color: #64748b;">
            Tệp nguồn: <strong>${filename}</strong> • Bạn có thể chỉnh sửa nội dung, phương án và chọn đáp án trước khi lưu.
          </span>
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
          <button class="btn btn-secondary btn-sm" onclick="cancelOcrReview()" style="color: #ef4444;">
            ✕ Hủy bỏ
          </button>
          <button class="btn btn-success" id="btn-save-ocr-bank" onclick="saveOcrReviewedQuestions()">
            ✓ Lưu <span id="ocr-selected-count">${totalExtracted}</span> câu đã chọn vào Ngân hàng
          </button>
        </div>
      </div>

      <div style="overflow-x: auto; max-height: 520px; overflow-y: auto;">
        <table class="audit-review-table" id="ocr-review-table">
          <thead>
            <tr>
              <th style="width: 40px; text-align: center;">
                <input type="checkbox" id="ocr-select-all" checked onchange="toggleOcrSelectAll(this.checked)" title="Chọn tất cả" />
              </th>
              <th style="width: 65px;">STT</th>
              <th>Nội dung câu hỏi (Chỉnh sửa & KaTeX Preview)</th>
              <th style="width: 380px;">Phương án (A, B, C, D) & Đáp án đúng (○)</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Render KaTeX in previews
  currentReviewedQuestions.forEach((_, idx) => {
    const prevEl = document.getElementById(`ocr-stem-preview-${idx}`);
    if (prevEl && typeof renderMath === "function") {
      renderMath(prevEl);
    }
  });
}

function onOcrStemInput(idx, val) {
  if (currentReviewedQuestions[idx]) {
    currentReviewedQuestions[idx].content_text = val;
    currentReviewedQuestions[idx].content_html = val;
  }
  const prevEl = document.getElementById(`ocr-stem-preview-${idx}`);
  if (prevEl) {
    prevEl.innerHTML = typeof formatMathSymbols === 'function' ? formatMathSymbols(val) : val;
    if (typeof renderMath === "function") renderMath(prevEl);
  }
}

function updateOcrOptionContent(idx, optId, val) {
  if (currentReviewedQuestions[idx]) {
    if (!currentReviewedQuestions[idx].options) currentReviewedQuestions[idx].options = [];
    const opt = currentReviewedQuestions[idx].options.find(o => o.id === optId);
    if (opt) {
      opt.content = val;
    } else {
      currentReviewedQuestions[idx].options.push({ id: optId, content: val, is_correct: false });
    }
  }
}

function updateOcrCorrectAnswer(idx, optId) {
  if (currentReviewedQuestions[idx]) {
    currentReviewedQuestions[idx].correct_answer = optId;
    if (currentReviewedQuestions[idx].options) {
      currentReviewedQuestions[idx].options.forEach(o => {
        o.is_correct = (o.id === optId);
      });
    }
  }
}

function updateOcrQuestionField(idx, field, val) {
  if (currentReviewedQuestions[idx]) {
    currentReviewedQuestions[idx][field] = val;
  }
}

function toggleOcrQuestionSelect(idx, checked) {
  if (currentReviewedQuestions[idx]) {
    currentReviewedQuestions[idx].selected = checked;
    const row = document.getElementById(`ocr-row-${idx}`);
    if (row) row.classList.toggle("selected", checked);
  }
  updateOcrSelectedCounter();
}

function toggleOcrSelectAll(checked) {
  currentReviewedQuestions.forEach((q, idx) => {
    q.selected = checked;
    const cb = document.getElementById(`ocr-check-${idx}`);
    if (cb) cb.checked = checked;
    const row = document.getElementById(`ocr-row-${idx}`);
    if (row) row.classList.toggle("selected", checked);
  });
  updateOcrSelectedCounter();
}

function updateOcrSelectedCounter() {
  const selectedCount = currentReviewedQuestions.filter(q => q.selected).length;
  const countEl = document.getElementById("ocr-selected-count");
  if (countEl) countEl.innerText = String(selectedCount);
  const btnSave = document.getElementById("btn-save-ocr-bank");
  if (btnSave) btnSave.disabled = (selectedCount === 0);
}

async function saveOcrReviewedQuestions() {
  const selectedQuestions = currentReviewedQuestions.filter(q => q.selected);
  if (!selectedQuestions || selectedQuestions.length === 0) {
    showToast("Vui lòng chọn ít nhất 1 câu hỏi để lưu vào Ngân hàng", "warning");
    return;
  }

  const btnSave = document.getElementById("btn-save-ocr-bank");
  if (btnSave) {
    btnSave.disabled = true;
    btnSave.innerText = "⏳ Đang lưu vào Ngân hàng...";
  }

  try {
    const payload = selectedQuestions.map(q => ({
      ...q,
      images: q.images || (currentUploadedImageUrl ? [currentUploadedImageUrl] : [])
    }));

    const res = await fetch(`${API_BASE}/questions/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions: payload })
    });
    const data = await res.json();

    showToast(`✓ Đã lưu thành công ${data.inserted_count || selectedQuestions.length} câu hỏi vào Ngân hàng!`, "success");

    if (typeof broadcastNewQuestions === "function") {
      broadcastNewQuestions(data.inserted_count || selectedQuestions.length, "Bóc tách Đề thi & OCR");
    }

    cancelOcrReview();
    loadDashboardStats();
    if (typeof State !== "undefined" && State.currentView === "bank") loadQuestions();

  } catch (err) {
    showToast(`Lỗi khi lưu câu hỏi: ${err.message}`, "error");
    if (btnSave) {
      btnSave.disabled = false;
      btnSave.innerText = "✓ Lưu câu đã chọn";
    }
  }
}

function cancelOcrReview() {
  currentReviewedQuestions = [];
  if (currentUploadedImageUrl) {
    URL.revokeObjectURL(currentUploadedImageUrl);
    currentUploadedImageUrl = null;
  }
  const resultContainer = document.getElementById("pdf-result-container");
  if (resultContainer) {
    resultContainer.innerHTML = "";
    resultContainer.style.display = "none";
  }
  showToast("Đã đóng bảng đối soát", "info");
}

// Scraper Log Actions (Copy & Clear)
function copyScraperLiveLog() {
  const logBox = document.getElementById("scraper-live-log");
  if (!logBox || !logBox.innerText.trim()) {
    showToast("Chưa có nội dung nhật ký để sao chép", "error");
    return;
  }
  const text = logBox.innerText.trim();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text)
      .then(() => showToast("Đã sao chép toàn bộ nhật ký Bot!", "success"))
      .catch(() => fallbackCopyScraperLog(text));
  } else {
    fallbackCopyScraperLog(text);
  }
}

function fallbackCopyScraperLog(text) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    showToast("Đã sao chép toàn bộ nhật ký Bot!", "success");
  } catch (e) {
    showToast("Không thể sao chép nhật ký vào Clipboard", "error");
  }
}

function clearScraperLiveLog() {
  const logBox = document.getElementById("scraper-live-log");
  const toolbar = document.getElementById("scraper-log-toolbar");
  if (logBox) {
    logBox.innerText = "";
    logBox.style.display = "none";
  }
  if (toolbar) toolbar.style.display = "none";
  localStorage.removeItem("eduquest_scraper_log");
  showToast("Đã xóa sạch màn hình nhật ký Bot", "info");
}

// Scraper Runner (Newest on Top)
async function runAutoScraper() {
  const platform = document.getElementById("scraper-platform").value;
  const username = document.getElementById("scraper-username").value.trim();
  const password = document.getElementById("scraper-password").value.trim();
  const roundId = document.getElementById("scraper-round").value.trim();
  const grade = parseInt(document.getElementById("scraper-grade").value) || 5;
  const btn = document.getElementById("btn-run-scraper");

  if (!username || !password) {
    showToast("Vui lòng nhập Tên đăng nhập và Mật khẩu tài khoản", "error");
    return;
  }

  const logBox = document.getElementById("scraper-live-log");
  const toolbar = document.getElementById("scraper-log-toolbar");
  logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";

  const timeNow = new Date().toLocaleTimeString();
  const initLines = [
    `[${timeNow}] Đang mở trình duyệt ngầm và kết nối tài khoản ${username}...`,
    `[${timeNow}] 🚀 Khởi chạy Bot Đăng nhập Ngầm cho nền tảng ${platform.toUpperCase()}...`
  ];
  logBox.innerText = initLines.join("\n") + "\n";
  localStorage.setItem("eduquest_scraper_log", logBox.innerText);

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `⏳ Bot đang cào dữ liệu ngầm...`;
  }

  try {
    const res = await fetch(`${API_BASE}/collect/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform: platform,
        action: "bot_crawl",
        username: username,
        password: password,
        round_id: roundId,
        grade: grade
      })
    });

    const data = await res.json();

    // Render logs with NEWEST ON TOP
    if (data.logs && Array.isArray(data.logs) && data.logs.length > 0) {
      const reversedLogs = [...data.logs].reverse();
      logBox.innerText = reversedLogs.join("\n") + "\n";
    }

    const finishTime = new Date().toLocaleTimeString();
    if (data.success) {
      const fixedGrade = data.account_grade || grade;
      if (data.account_grade) {
        const gradeSelect = document.getElementById("scraper-grade");
        if (gradeSelect) gradeSelect.value = String(data.account_grade);
      }

      if (data.inserted_count > 0) {
        const msg = `[${finishTime}] 🎉 Thành công xuất sắc! Đã lưu ${data.inserted_count} câu hỏi vào CSDL (Khối lớp cố định: Lớp ${fixedGrade})!\n`;
        logBox.innerText = msg + logBox.innerText;
        showToast(`Bot đã cào thành công ${data.inserted_count} câu hỏi mới (Khối ${fixedGrade})!`, "success");
        if (typeof broadcastNewQuestions === "function") {
          broadcastNewQuestions(data.inserted_count, `VioEdu Bot (Lớp ${fixedGrade})`);
        }
      } else {
        const msg = `[${finishTime}] ℹ️ Các câu hỏi đã có sẵn trong CSDL hoặc phòng thi hiện chưa mở câu hỏi mới.\n`;
        logBox.innerText = msg + logBox.innerText;
        showToast(`Đã hoàn tất quét VioEdu (Khối ${fixedGrade}). Dữ liệu đã được cập nhật.`, "info");
      }

      loadDashboardStats();
      if (typeof State !== "undefined" && State.currentView === "bank") {
        loadQuestions();
      }
    } else {
      const errMsg = `[${finishTime}] ❌ Lỗi: ${data.error || "Không thể hoàn thành tiến trình cào dữ liệu."}\n`;
      logBox.innerText = errMsg + logBox.innerText;
      showToast(data.error || "Lỗi đăng nhập / cào dữ liệu VioEdu", "error");
    }
  } catch (err) {
    const errTime = new Date().toLocaleTimeString();
    const excMsg = `[${errTime}] ❌ Ngoại lệ: ${err.message}\n`;
    logBox.innerText = excMsg + logBox.innerText;
    showToast("Lỗi kết nối máy chủ cào dữ liệu: " + err.message, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "🚀 Bắt đầu cào dữ liệu";
    }
    localStorage.setItem("eduquest_scraper_log", logBox.innerText);
    loadCollectorLogs();
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

// Hunter Log Actions (Copy, Clear & Smart Formatting)
function parseHunterTimeToMinutes(str) {
  const m = str.match(/\[(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AP]M))?\]/i);
  if (!m) return null;
  let h = parseInt(m[1], 10);
  const mins = parseInt(m[2], 10);
  const ampm = m[4] ? m[4].toUpperCase() : null;
  if (ampm === "PM" && h < 12) h += 12;
  else if (ampm === "AM" && h === 12) h = 0;
  return h * 60 + mins;
}

function formatAndSortHunterLog(rawText) {
  if (!rawText || !rawText.trim()) return "";
  
  // 1. Separate squished log lines with newlines
  let s = rawText.replace(/([^\n])\s*(->\s*Danh sách mục tiêu:)/g, "$1\n$2");
  s = s.replace(/([^\n])\s*(\[\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?\])/g, "$1\n$2");

  const lines = s.split("\n").map(l => l.trim()).filter(l => l.length > 0);
  if (lines.length === 0) return "";

  // 2. Group into runs (each run starts with a timestamp and "Săn câu hỏi" or similar keyword)
  const runs = [];
  let currentRun = [];
  for (const line of lines) {
    const isRunHeader = /\[\d{1,2}:\d{2}/.test(line) && (line.includes("Săn câu hỏi") || line.includes("Khởi chạy"));
    if (isRunHeader && currentRun.length > 0) {
      runs.push(currentRun);
      currentRun = [line];
    } else {
      currentRun.push(line);
    }
  }
  if (currentRun.length > 0) {
    runs.push(currentRun);
  }

  // 3. Determine if runs are sorted ascending (oldest first). If so, reverse so newest is on top!
  if (runs.length >= 2) {
    const times = [];
    for (let i = 0; i < Math.min(runs.length, 5); i++) {
      const t = parseHunterTimeToMinutes(runs[i][0]);
      if (t !== null) times.push(t);
    }
    if (times.length >= 2) {
      let increasing = 0;
      let decreasing = 0;
      for (let i = 0; i < times.length - 1; i++) {
        if (times[i + 1] > times[i]) increasing++;
        else if (times[i + 1] < times[i]) decreasing++;
      }
      if (increasing > decreasing) {
        runs.reverse();
      }
    }
  }

  // Cap at 60 runs to avoid huge storage bloat
  const cappedRuns = runs.slice(0, 60);
  return cappedRuns.map(r => r.join("\n")).join("\n\n");
}

function copyHunterLiveLog() {
  const logBox = document.getElementById("hunter-live-log");
  if (!logBox || !logBox.innerText.trim()) {
    showToast("Chưa có nội dung nhật ký để sao chép", "error");
    return;
  }
  const text = logBox.innerText.trim();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text)
      .then(() => showToast("Đã sao chép toàn bộ nhật ký Săn câu hỏi!", "success"))
      .catch(() => fallbackCopyHunterLog(text));
  } else {
    fallbackCopyHunterLog(text);
  }
}

function fallbackCopyHunterLog(text) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    showToast("Đã sao chép toàn bộ nhật ký Săn câu hỏi!", "success");
  } catch (e) {
    showToast("Không thể sao chép nhật ký vào Clipboard", "error");
  }
}

function clearHunterLiveLog() {
  const logBox = document.getElementById("hunter-live-log");
  const toolbar = document.getElementById("hunter-log-toolbar");
  if (logBox) {
    logBox.innerText = "";
    logBox.style.display = "none";
  }
  if (toolbar) toolbar.style.display = "none";
  localStorage.removeItem("eduquest_hunter_log");
  showToast("Đã xóa sạch màn hình nhật ký Săn câu hỏi", "info");
}

// Internet Question Hunter Runner (Newest on Top & Clean Line Separation)
async function runInternetHunter(isAuto = false) {
  const subject = document.getElementById("hunter-subject").value;
  const grade = parseInt(document.getElementById("hunter-grade").value) || 5;
  const activeCustomUrls = hunterTargetUrls.filter(u => u.active).map(u => u.url);
  const logBox = document.getElementById("hunter-live-log");
  const toolbar = document.getElementById("hunter-log-toolbar");
  const btn = document.getElementById("btn-run-hunter");

  if (logBox) logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";
  if (!isAuto && btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Đang quét internet...";
  }

  const timeNow = new Date().toLocaleTimeString();
  const runHeader = `[${timeNow}] ${isAuto ? "🔄 [TỰ ĐỘNG ĐỊNH KỲ]" : "⚡ [THỦ CÔNG]"} Săn câu hỏi (Môn: ${subject.toUpperCase()}, Khối ${grade})...`;
  const targetsLine = activeCustomUrls.length > 0
    ? `-> Danh sách mục tiêu: Sẽ cào ${activeCustomUrls.length} web/link: ${activeCustomUrls.slice(0, 2).join(', ')}${activeCustomUrls.length > 2 ? '...' : ''}`
    : '';
  const inProgressLine = `⏳ Đang kết nối và quét dữ liệu internet...`;

  const newRunLines = targetsLine ? [runHeader, targetsLine, inProgressLine] : [runHeader, inProgressLine];
  const newRunText = newRunLines.join("\n");

  // Prepend newest run on top
  const previousText = logBox ? (logBox.innerText || "").trim() : "";
  if (logBox) {
    logBox.innerText = previousText ? newRunText + "\n\n" + previousText : newRunText;
    localStorage.setItem("eduquest_hunter_log", logBox.innerText);
  }

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
    const finishTime = new Date().toLocaleTimeString();

    if (data.success) {
      const finishLine = `[${finishTime}] Thu thập thành công! Đã bóc tách và lưu ${data.total_harvested} câu hỏi vào CSDL.`;
      if (logBox) {
        if (logBox.innerText.includes(inProgressLine)) {
          logBox.innerText = logBox.innerText.replace(inProgressLine, finishLine);
        } else {
          const cur = (logBox.innerText || "").trim();
          logBox.innerText = cur ? finishLine + "\n" + cur : finishLine;
        }
        localStorage.setItem("eduquest_hunter_log", logBox.innerText);
      }
      showToast(`Đã săn thành công ${data.total_harvested} câu hỏi từ Internet!`);
      if (typeof broadcastNewQuestions === "function") {
        broadcastNewQuestions(data.total_harvested, "Săn Internet");
      }
      loadDashboardStats();
      loadCollectorLogs();
      if (State.currentView === "bank") loadQuestions();
    } else {
      const errorLine = `[${finishTime}] Thông báo: ${data.error || "Không tìm thấy dữ liệu mới."}`;
      if (logBox) {
        if (logBox.innerText.includes(inProgressLine)) {
          logBox.innerText = logBox.innerText.replace(inProgressLine, errorLine);
        } else {
          const cur = (logBox.innerText || "").trim();
          logBox.innerText = cur ? errorLine + "\n" + cur : errorLine;
        }
        localStorage.setItem("eduquest_hunter_log", logBox.innerText);
      }
    }
  } catch (err) {
    const finishTime = new Date().toLocaleTimeString();
    const errorLine = `[${finishTime}] Lỗi kết nối: ${err.message}`;
    if (logBox) {
      if (logBox.innerText.includes(inProgressLine)) {
        logBox.innerText = logBox.innerText.replace(inProgressLine, errorLine);
      } else {
        const cur = (logBox.innerText || "").trim();
        logBox.innerText = cur ? errorLine + "\n" + cur : errorLine;
      }
      localStorage.setItem("eduquest_hunter_log", logBox.innerText);
    }
    if (!isAuto) showToast("Lỗi khi săn câu hỏi Internet", "error");
  } finally {
    if (!isAuto && btn) {
      btn.disabled = false;
      btn.innerText = "⚡ Bắt đầu Săn câu hỏi từ Internet";
    }
  }
}

// Dynamic Preset Generator for Grades 1 to 12
function updateGradePresetsUI(gradeVal) {
  const grade = parseInt(gradeVal) || 2;
  const container = document.getElementById("hunter-grade-presets-container");

  // 1. Update Harvest Button label badge
  const btnLabel = document.getElementById("harvest-grade-btn-label");
  if (btnLabel) btnLabel.innerText = String(grade);
  const quickBtn = document.getElementById("btn-harvest-grade-quick") || document.getElementById("btn-harvest-grade2");
  if (quickBtn) {
    quickBtn.title = `Nạp nhanh bộ câu hỏi Toán Khối ${grade} (Tiếng Việt, Tiếng Anh & Olympic)`;
  }

  if (!container) return;

  // Slug maps for K5 & Khan
  const k5Slugs = {
    1: "first-grade-1",
    2: "second-grade-2",
    3: "third-grade-3",
    4: "fourth-grade-4",
    5: "fifth-grade-5",
    6: "sixth-grade-6"
  };
  const k5Url = k5Slugs[grade]
    ? `https://www.k5learning.com/free-math-worksheets/${k5Slugs[grade]}`
    : `https://www.k5learning.com/free-math-worksheets`;

  const khanSlugs = {
    1: "cc-1st-grade-math",
    2: "cc-2nd-grade-math",
    3: "cc-third-grade-math",
    4: "cc-fourth-grade-math",
    5: "cc-fifth-grade-math",
    6: "cc-sixth-grade-math",
    7: "cc-seventh-grade-math",
    8: "cc-eighth-grade-math",
    9: "algebra",
    10: "geometry",
    11: "algebra2",
    12: "calculus-1"
  };
  const khanUrl = `https://www.khanacademy.org/math/${khanSlugs[grade] || "early-math"}`;

  container.innerHTML = `
    <!-- Category 1: Toán Tiếng Việt Khối ${grade} -->
    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
      <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🇻🇳 Toán ${grade} Tiếng Việt:</span>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://hanhtrangso.nxbgd.vn/sach-dien-tu?book_active=0&classes=${grade}')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;">
        📘 Hành trang số (SGK Toán ${grade})
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://vio.edu.vn/luyen-tap')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0;">
        📐 VioEdu Luyện tập Toán ${grade}
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://tnmath.edu.vn/luyen-tap')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fff1f2; color: #be123c; border: 1px solid #fecdd3;">
        📖 Trạng Nguyên Toán ${grade}
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://olm.vn/chu-de/toan-lop-${grade}')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fdf2f8; color: #9d174d; border: 1px solid #fbcfe8;">
        🎓 OLM.vn Toán ${grade}
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://vndoc.com/toan-lop-${grade}')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdfa; color: #0f766e; border: 1px solid #99f6e4;">
        📝 VnDoc Phiếu Toán ${grade}
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://vietjack.com/toan-lop-${grade}/index.jsp')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fafaf9; color: #44403c; border: 1px solid #e7e5e4;">
        📚 VietJack Toán ${grade}
      </button>
    </div>

    <!-- Category 2: Math Grade ${grade} English -->
    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
      <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🇬🇧 Math Grade ${grade} (Anh):</span>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('${k5Url}')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fefce8; color: #a16207; border: 1px solid #fef08a;">
        📑 K5 Learning Worksheets
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.ixl.com/math/grade-${grade}')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;">
        🎯 IXL Math Grade ${grade} Skills
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('${khanUrl}')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0;">
        🌱 Khan Academy Math ${grade}
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.commoncoresheets.com')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f8fafc; color: #334155; border: 1px solid #cbd5e1;">
        📋 Common Core Math ${grade}
      </button>
    </div>

    <!-- Category 3: Olympic Song ngữ Khối ${grade} -->
    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
      <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🏆 Olympic Khối ${grade}:</span>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://kangaroo-math.vn')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa;">
        🦘 Kangaroo Math (IKMC Khối ${grade <= 2 ? '1-2' : grade <= 4 ? '3-4' : grade <= 6 ? '5-6' : grade <= 8 ? '7-8' : '9-12'})
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://codemath.vn/khoa-hoc/timo')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fef3c7; color: #b45309; border: 1px solid #fde68a;">
        🏅 TIMO Khối ${grade} Song ngữ
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://codemath.vn/khoa-hoc/sasmo')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fef3c7; color: #b45309; border: 1px solid #fde68a;">
        🥇 SASMO Singapore Lớp ${grade}
      </button>
    </div>
  `;
}

// Quick 1-Click Multi-Source Harvester for Any Grade Math (English + Vietnamese + Olympic)
async function harvestCurrentGradeMathQuick() {
  const gradeEl = document.getElementById("hunter-grade");
  const grade = parseInt(gradeEl?.value || localStorage.getItem("eduquest_selected_grade") || 2);
  const btn = document.getElementById("btn-harvest-grade-quick") || document.getElementById("btn-harvest-grade2");
  const logBox = document.getElementById("hunter-live-log");
  const toolbar = document.getElementById("hunter-log-toolbar");

  if (logBox) logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";
  if (btn) {
    btn.disabled = true;
    btn.innerText = `⏳ Đang nạp đề Toán Khối ${grade}...`;
  }

  const timeNow = new Date().toLocaleTimeString();
  const runHeader = `[${timeNow}] 🌟 [NẠP NHANH TOÁN KHỐI ${grade}] Quét đa nguồn Tiếng Việt (VioEdu, Trạng Nguyên, OLM, VnDoc, SGK Hành Trang Số) & Tiếng Anh (K5 Learning, IXL, Khan Academy, Olympic Kangaroo, TIMO, SASMO)...`;
  const inProgressLine = `⏳ Đang kết nối các kho học liệu Toán Khối ${grade}...`;

  const newRunText = `${runHeader}\n${inProgressLine}`;
  const previousText = logBox ? (logBox.innerText || "").trim() : "";
  if (logBox) {
    logBox.innerText = previousText ? newRunText + "\n\n" + previousText : newRunText;
    localStorage.setItem("eduquest_hunter_log", logBox.innerText);
  }

  try {
    const res = await fetch(`${API_BASE}/hunter/harvest-by-grade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grade: grade, subject: "math" })
    });
    const data = await res.json();
    const finishTime = new Date().toLocaleTimeString();

    if (data.success) {
      const finishLine = `[${finishTime}] Thu thập thành công! Đã bóc tách và nạp ${data.total_harvested} câu hỏi Toán Khối ${grade} (Anh & Việt & Olympic) vào Ngân hàng.`;
      if (logBox) {
        if (logBox.innerText.includes(inProgressLine)) {
          logBox.innerText = logBox.innerText.replace(inProgressLine, finishLine);
        } else {
          const cur = (logBox.innerText || "").trim();
          logBox.innerText = cur ? finishLine + "\n" + cur : finishLine;
        }
        localStorage.setItem("eduquest_hunter_log", logBox.innerText);
      }
      showToast(`Tuyệt vời! Đã nạp thành công ${data.total_harvested} câu hỏi Toán Khối ${grade} (Anh & Việt & Olympic)!`);
      if (typeof broadcastNewQuestions === "function") {
        broadcastNewQuestions(data.total_harvested, `Toán Khối ${grade} Đa Nguồn`);
      }
      loadDashboardStats();
      loadCollectorLogs();
      if (State.currentView === "bank") loadQuestions();
    } else {
      const errLine = `[${finishTime}] Thông báo: ${data.error || `Không thể thu thập dữ liệu Toán khối ${grade}.`}`;
      if (logBox) {
        if (logBox.innerText.includes(inProgressLine)) {
          logBox.innerText = logBox.innerText.replace(inProgressLine, errLine);
        }
        localStorage.setItem("eduquest_hunter_log", logBox.innerText);
      }
      showToast(data.error || "Không thể thu thập dữ liệu", "error");
    }
  } catch (err) {
    const finishTime = new Date().toLocaleTimeString();
    const errLine = `[${finishTime}] Lỗi kết nối máy chủ: ${err.message}`;
    if (logBox) {
      if (logBox.innerText.includes(inProgressLine)) {
        logBox.innerText = logBox.innerText.replace(inProgressLine, errLine);
      }
      localStorage.setItem("eduquest_hunter_log", logBox.innerText);
    }
    showToast(`Lỗi khi nạp nhanh đề Toán Khối ${grade}: ` + err.message, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `✨ Nạp nhanh Đề Toán Khối <span id="harvest-grade-btn-label">${grade}</span> Toàn diện (Anh & Việt)`;
    }
  }
}

// Backward-compatible alias for any code or button referencing harvestGrade2MathQuick
async function harvestGrade2MathQuick() {
  return harvestCurrentGradeMathQuick();
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
  updateGradePresetsUI(grade);
  showToast(`Đã lưu Khối lớp ${grade} làm mặc định toàn hệ thống!`);
}

function onGradeSelectChanged(grade) {
  localStorage.setItem("eduquest_selected_grade", grade);
  applyGradeToAllSelectors(grade);
  updateGradePresetsUI(grade);
}

function applyGradeToAllSelectors(grade) {
  // Apply to collector tools, builder and manual creation forms, never restrict Question Bank view
  const ids = ["global-default-grade", "hunter-grade", "scraper-grade", "m-grade", "matrix-grade"];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = grade;
  });
  const btnLabel = document.getElementById("harvest-grade-btn-label");
  if (btnLabel) btnLabel.innerText = String(grade);
}

// ----------------- R1: Bot Auto-Crawl 5-Minute Periodic Loop -----------------
let botAutoCountdown = 300;
let botAutoInterval = null;

function toggleBotAutoCrawl(enable) {
  localStorage.setItem("eduquest_bot_autocrawl", enable ? "true" : "false");
  const badge = document.getElementById("bot-auto-crawl-badge");
  const toggle = document.getElementById("bot-auto-crawl-toggle");
  if (toggle) toggle.checked = enable;

  if (enable) {
    if (badge) badge.style.display = "inline-flex";
    startBotAutoCrawlLoop();
    showToast("Đã BẬT chế độ Tự động cào VioEdu định kỳ (mỗi 5 phút)!");
  } else {
    if (badge) badge.style.display = "none";
    stopBotAutoCrawlLoop();
    showToast("Đã TẮT chế độ Tự động cào VioEdu.");
  }
}

function startBotAutoCrawlLoop() {
  stopBotAutoCrawlLoop();
  botAutoCountdown = 300;
  updateBotCountdownUI();

  botAutoInterval = setInterval(() => {
    botAutoCountdown--;
    updateBotCountdownUI();

    if (botAutoCountdown <= 0) {
      botAutoCountdown = 300;
      updateBotCountdownUI();
      // Auto trigger scraper
      const user = document.getElementById("scraper-username")?.value?.trim();
      const pass = document.getElementById("scraper-password")?.value?.trim();
      if (user && pass) {
        runAutoScraper();
      } else {
        showToast("⚠️ Vui lòng nhập tài khoản và mật khẩu VioEdu để tự động cào", "warning");
      }
    }
  }, 1000);
}

function stopBotAutoCrawlLoop() {
  if (botAutoInterval) clearInterval(botAutoInterval);
  botAutoInterval = null;
}

function updateBotCountdownUI() {
  const display = document.getElementById("bot-countdown-display");
  if (display) {
    const m = Math.floor(botAutoCountdown / 60).toString().padStart(2, '0');
    const s = (botAutoCountdown % 60).toString().padStart(2, '0');
    display.innerText = `${m}:${s}`;
  }
}

// ----------------- R6: Question Capture Logs Modal & Re-inject -----------------
let currentCapturedQuestions = [];

async function openCaptureLogsModal() {
  const modal = document.getElementById("modal-capture-logs");
  if (!modal) return;
  modal.style.display = "flex";

  const container = document.getElementById("capture-logs-content");
  if (container) {
    container.innerHTML = `<div style="text-align: center; padding: 30px; color: #64748b;">⏳ Đang tải nhật ký bắt câu hỏi...</div>`;
  }

  try {
    const res = await fetch(`${API_BASE}/questions?page=1&page_size=24`);
    if (res.ok) {
      const data = await res.json();
      currentCapturedQuestions = data.items || [];
    }
    renderCapturedQuestionsView("cards");
  } catch (err) {
    if (container) {
      container.innerHTML = `<div style="color: #ef4444; padding: 20px;">Lỗi nạp nhật ký: ${err.message}</div>`;
    }
  }
}

function closeCaptureLogsModal() {
  const modal = document.getElementById("modal-capture-logs");
  if (modal) modal.style.display = "none";
}

function renderCapturedQuestionsView(viewMode = "cards") {
  const container = document.getElementById("capture-logs-content");
  if (!container) return;

  if (!currentCapturedQuestions || currentCapturedQuestions.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 30px;">Chưa có câu hỏi nào trong nhật ký bắt.</div>`;
    return;
  }

  if (viewMode === "json") {
    const jsonStr = JSON.stringify(currentCapturedQuestions, null, 2);
    container.innerHTML = `
      <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
        <button class="btn btn-secondary btn-sm" onclick="copyCaptureLogsJson()">📋 Sao chép JSON</button>
      </div>
      <pre style="background: #0f172a; color: #38bdf8; padding: 16px; border-radius: 8px; font-size: 12px; max-height: 440px; overflow-y: auto; font-family: monospace;">${jsonStr}</pre>
    `;
    return;
  }

  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 12px; max-height: 460px; overflow-y: auto;">
      ${currentCapturedQuestions.map((q, idx) => `
        <div style="padding: 14px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="q-number-pill" style="font-size: 12px;">Câu ${idx + 1}</span>
              <span class="tag-badge platform-${q.source_platform}">${q.source_platform}</span>
              <span class="tag-badge" style="background: #eff6ff; color: #1d4ed8;">${q.subject}</span>
              <span class="tag-grade">Lớp ${q.grade || 5}</span>
            </div>
            <span style="font-size: 11.5px; color: #94a3b8; font-family: monospace;">ID: #${q.q_number || q.id.substring(0, 8)}</span>
          </div>

          <div style="font-size: 13.5px; color: #1e293b; margin-bottom: 8px;">
            ${typeof formatMathSymbols === 'function' ? formatMathSymbols(q.content_text || q.content_html || '') : (q.content_text || q.content_html || '')}
          </div>

          ${q.options && q.options.length > 0 ? `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 6px; font-size: 12.5px; color: #475569;">
              ${q.options.map(o => `<div><strong>${o.id}.</strong> ${typeof formatMathSymbols === 'function' ? formatMathSymbols(o.content || '') : (o.content || '')}</div>`).join('')}
            </div>
          ` : ''}
        </div>
      `).join('')}
    </div>
  `;

  if (typeof renderMath === "function") {
    renderMath(container);
  }
}

async function copyCaptureLogsJson() {
  try {
    const text = JSON.stringify(currentCapturedQuestions, null, 2);
    await navigator.clipboard.writeText(text);
    showToast("Đã sao chép toàn bộ JSON nhật ký bắt câu hỏi!");
  } catch (err) {
    showToast("Lỗi sao chép: " + err.message, "error");
  }
}

async function reinjectCapturedQuestions() {
  if (!currentCapturedQuestions || currentCapturedQuestions.length === 0) {
    showToast("Không có câu hỏi nào để nạp lại", "warning");
    return;
  }

  const btn = document.getElementById("btn-reinject-questions");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Đang làm sạch & nạp lại...";
  }

  try {
    const res = await fetch(`${API_BASE}/questions/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions: currentCapturedQuestions })
    });
    const data = await res.json();

    showToast(`✓ Đã làm sạch & nạp thành công ${data.inserted_count || currentCapturedQuestions.length} câu hỏi vào CSDL!`, "success");

    if (typeof broadcastNewQuestions === "function") {
      broadcastNewQuestions(data.inserted_count || currentCapturedQuestions.length, "Nạp lại từ Nhật ký bắt");
    }

    loadDashboardStats();
    if (typeof State !== "undefined" && State.currentView === "bank") loadQuestions();
    closeCaptureLogsModal();

  } catch (err) {
    showToast(`Lỗi khi nạp lại câu hỏi: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "⚡ Làm sạch & Nạp lại vào CSDL";
    }
  }
}

function restoreCollectorSettings() {
  // 1. Restore grade for collector tools only
  const savedGrade = localStorage.getItem("eduquest_default_grade") || localStorage.getItem("eduquest_selected_grade") || "5";
  applyGradeToAllSelectors(savedGrade);
  updateGradePresetsUI(savedGrade);

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

  // 4. Restore R1 Bot auto-crawl toggle & loop
  const isBotAuto = localStorage.getItem("eduquest_bot_autocrawl") === "true";
  const botToggle = document.getElementById("bot-auto-crawl-toggle");
  if (botToggle) {
    botToggle.checked = isBotAuto;
    if (isBotAuto) {
      const badge = document.getElementById("bot-auto-crawl-badge");
      if (badge) badge.style.display = "inline-flex";
      startBotAutoCrawlLoop();
    }
  }

  // 5. Restore hunter target URLs list
  loadHunterTargetUrls();
  renderHunterUrlsList();

  // 6. Restore persistent live logs
  const savedHunterLog = localStorage.getItem("eduquest_hunter_log");
  const hunterLogBox = document.getElementById("hunter-live-log");
  const hunterToolbar = document.getElementById("hunter-log-toolbar");
  if (savedHunterLog && hunterLogBox) {
    const formatted = formatAndSortHunterLog(savedHunterLog);
    if (formatted) {
      hunterLogBox.style.display = "block";
      if (hunterToolbar) hunterToolbar.style.display = "flex";
      hunterLogBox.innerText = formatted;
      localStorage.setItem("eduquest_hunter_log", formatted);
    }
  }

  const savedScraperLog = localStorage.getItem("eduquest_scraper_log");
  const scraperLogBox = document.getElementById("scraper-live-log");
  const scraperToolbar = document.getElementById("scraper-log-toolbar");
  if (savedScraperLog && scraperLogBox) {
    scraperLogBox.style.display = "block";
    if (scraperToolbar) scraperToolbar.style.display = "flex";
    scraperLogBox.innerText = savedScraperLog;
  }
}

// Initialize Dropzone and restore settings when DOM loaded
document.addEventListener("DOMContentLoaded", () => {
  setupDropzone();
  restoreCollectorSettings();
});

