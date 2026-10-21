// EduQuest Pro - Collector Hub, Multi-file PDF & Image OCR Importer, Auto-Hunter & Auto-Crawl
const SUPPORTED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp"];
let selectedOcrFiles = [];
let ocrLightboxState = {
  zoom: 1.0,
  rotation: 0,
  panX: 0,
  panY: 0,
  isDragging: false,
  startX: 0,
  startY: 0,
  imageUrls: [],
  currentIndex: 0
};
let autoHunterTimer = null;
let autoHunterCountdown = 300; // 5 minutes countdown
let countdownInterval = null;

// Auth-gate 2026-10-12: mọi /api/* (trừ auth/version + 4 endpoint
// extension-sync) đều 401 khi thiếu Bearer session. Hub/bot VioEdu PHẢI qua
// wrapper này — tự gắn token, mở tường login khi 401 — thay vì fetch trần.
// Ưu tiên EduAuth.apiFetch (auth.js nạp trước file này); fallback fetch trần
// khi auth.js chưa sẵn (không bao giờ xảy ra ở index.html hiện tại).
async function apiFetch(path, options) {
  try {
    if (typeof EduAuth !== "undefined" && EduAuth && typeof EduAuth.apiFetch === "function") {
      return await EduAuth.apiFetch(path, options);
    }
  } catch (e) { throw e; }
  const base = (typeof API_BASE !== "undefined" && API_BASE) ? API_BASE : "";
  return fetch(base + String(path).replace(/^\/api/, ""), options || {});
}

// ============================================================================
// OCR Debug Live Log & Telemetry
// ============================================================================
let ocrLogList = [];

function appendOcrLog(message, type = "info") {
  const logBox = document.getElementById("ocr-live-log");
  const badge = document.getElementById("ocr-log-badge");
  const timeStr = getLogTimeVN();

  const typeLabels = {
    info: "[INFO]",
    upload: "[UPLOAD]",
    success: "[THÀNH CÔNG]",
    warning: "[CẢNH BÁO]",
    error: "[LỖI]",
    batch: "[ĐỐI SOÁT]",
    step: "[CÂU HỎI]",
    preview: "[XEM ẢNH]"
  };
  const typeTag = typeLabels[type] || `[${type.toUpperCase()}]`;
  const formattedLine = `[${timeStr}] ${typeTag} ${message}`;

  console.log(`[OCR-DEBUG] ${formattedLine}`);
  ocrLogList.push(formattedLine);
  if (ocrLogList.length > 200) {
    ocrLogList = ocrLogList.slice(-200);
  }

  const fullText = ocrLogList.join("\n");
  if (logBox) {
    logBox.textContent = fullText;
    logBox.dataset.hasLogs = "true";
    logBox.scrollTop = logBox.scrollHeight;
  }
  if (badge) badge.textContent = `${ocrLogList.length} bản ghi`;

  try {
    localStorage.setItem("eduquest_ocr_log", ocrLogList.slice(-60).join("\n"));
  } catch (e) {}
}
window.appendOcrLog = appendOcrLog;

function copyOcrLiveLog() {
  let text = ocrLogList.length > 0
    ? ocrLogList.join("\n")
    : (localStorage.getItem("eduquest_ocr_log") || (document.getElementById("ocr-live-log")?.textContent || ""));
  text = unSquishLogLines(text);
  if (!text.trim()) {
    showToast("Chưa có nội dung nhật ký để sao chép", "warning");
    return;
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text)
      .then(() => showToast("📋 Đã sao chép toàn bộ nhật ký bóc tách OCR!", "success"))
      .catch(() => fallbackCopyOcrLog(text));
  } else {
    fallbackCopyOcrLog(text);
  }
}
window.copyOcrLiveLog = copyOcrLiveLog;

function fallbackCopyOcrLog(text) {
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
    showToast("📋 Đã sao chép toàn bộ nhật ký bóc tách OCR!", "success");
  } catch (e) {
    showToast("Không thể sao chép nhật ký vào Clipboard", "error");
  }
}

function clearOcrLiveLog() {
  ocrLogList = [];
  const logBox = document.getElementById("ocr-live-log");
  const badge = document.getElementById("ocr-log-badge");
  if (logBox) {
    logBox.textContent = "[Hệ thống] Đã làm sạch màn hình nhật ký. Sẵn sàng bóc tách tệp mới.";
    logBox.dataset.hasLogs = "true";
  }
  if (badge) badge.textContent = "1 bản ghi";
  localStorage.removeItem("eduquest_ocr_log");
  showToast("🗑️ Đã xóa sạch màn hình nhật ký OCR", "info");
}
window.clearOcrLiveLog = clearOcrLiveLog;

function restoreOcrLog() {
  try {
    const saved = localStorage.getItem("eduquest_ocr_log");
    const logBox = document.getElementById("ocr-live-log");
    const badge = document.getElementById("ocr-log-badge");
    if (saved) {
      const clean = unSquishLogLines(saved);
      ocrLogList = clean.split("\n").filter(l => l.trim().length > 0);
      if (logBox && ocrLogList.length > 0) {
        logBox.textContent = ocrLogList.join("\n");
        logBox.dataset.hasLogs = "true";
        logBox.scrollTop = logBox.scrollHeight;
      }
      if (badge) badge.textContent = `${ocrLogList.length} bản ghi`;
    }
  } catch (e) {}
}
window.restoreOcrLog = restoreOcrLog;

function toggleOcrLogSection() {
  const sec = document.getElementById("ocr-log-section");
  if (!sec) return;
  const isHidden = (sec.style.display === "none" || !sec.style.display);
  sec.style.display = isHidden ? "block" : "none";
  const btn = document.getElementById("btn-toggle-ocr-log");
  if (btn) {
    btn.style.background = isHidden ? "#e0f2fe" : "";
    btn.style.borderColor = isHidden ? "#38bdf8" : "";
    btn.style.color = isHidden ? "#0369a1" : "";
  }
}
window.toggleOcrLogSection = toggleOcrLogSection;

function toggleOcrDropzone() {
  const dz = document.getElementById("pdf-dropzone");
  const btn = document.getElementById("btn-toggle-ocr-dropzone");
  if (!dz) return;
  const isHidden = (dz.style.display === "none");
  dz.style.display = isHidden ? "flex" : "none";
  if (btn) {
    btn.textContent = isHidden ? "▲ Thu gọn" : "▼ Kéo thả";
    btn.title = isHidden ? "Thu gọn vùng kéo thả" : "Mở rộng vùng kéo thả";
  }
}
window.toggleOcrDropzone = toggleOcrDropzone;

// ============================================================================
// 1. Dropzone & Multi-file Upload Handler
// ============================================================================
function setupDropzone() {
  const dropzone = document.getElementById("pdf-dropzone");
  const fileInput = document.getElementById("pdf-file-input");
  if (!dropzone || !fileInput) return;

  fileInput.setAttribute("accept", ".pdf,.png,.jpg,.jpeg,.webp,.bmp");
  fileInput.setAttribute("multiple", "multiple");

  // Prevent file input click event from bubbling to dropzone
  fileInput.addEventListener("click", (e) => e.stopPropagation());

  dropzone.addEventListener("click", (e) => {
    if (e.target !== fileInput) {
      fileInput.click();
    }
  });

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
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleOcrFilesSelection(e.dataTransfer.files);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleOcrFilesSelection(e.target.files);
    }
  });

  // Setup Lightbox Modal Interactive Events (Zoom & Pan)
  setupLightboxEvents();
}

function handlePdfUpload(file) {
  return handleOcrFilesSelection([file]);
}

function handleExamFileUpload(file) {
  return handleOcrFilesSelection([file]);
}

function handleOcrFilesSelection(fileList) {
  const newFiles = Array.from(fileList).filter(file => {
    const ext = "." + file.name.split(".").pop().toLowerCase();
    return SUPPORTED_EXTENSIONS.includes(ext);
  });

  if (newFiles.length === 0) {
    appendOcrLog("⚠️ Người dùng chọn tệp không đúng định dạng hỗ trợ (.pdf, .png, .jpg, .jpeg, .webp, .bmp).", "warning");
    showToast("Vui lòng chọn tệp định dạng PDF đề thi hoặc Ảnh (.png, .jpg, .jpeg, .webp, .bmp)", "error");
    return;
  }

  selectedOcrFiles = newFiles;
  renderSelectedOcrFilesChips();

  appendOcrLog(`📁 Đã nhận ${newFiles.length} tệp: ${newFiles.map(f => `${f.name} (${(f.size / 1024).toFixed(1)} KB)`).join(", ")}`, "info");

  // Automatically start OCR extraction for the selected files
  processSelectedFilesOcr();
}

function renderSelectedOcrFilesChips() {
  const bar = document.getElementById("ocr-selected-files-bar");
  const chipsContainer = document.getElementById("ocr-selected-files-chips");
  const countEl = document.getElementById("ocr-selected-count");

  if (!bar || !chipsContainer) return;

  if (selectedOcrFiles.length === 0) {
    bar.style.display = "none";
    return;
  }

  bar.style.display = "block";
  if (countEl) countEl.textContent = String(selectedOcrFiles.length);

  chipsContainer.innerHTML = selectedOcrFiles.map((file, idx) => {
    const isImage = !file.name.toLowerCase().endsWith(".pdf");
    const icon = isImage ? "🖼️" : "📄";
    const sizeKb = (file.size / 1024).toFixed(0);
    return `
      <div class="ocr-file-chip" title="${file.name}">
        <span>${icon}</span>
        <span style="max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.name}</span>
        <span style="color: #64748b; font-size: 11px;">(${sizeKb} KB)</span>
        <span class="chip-remove" onclick="removeSelectedOcrFile(${idx})" title="Bỏ tệp này">✕</span>
      </div>
    `;
  }).join("");
}

function removeSelectedOcrFile(idx) {
  if (idx >= 0 && idx < selectedOcrFiles.length) {
    const removed = selectedOcrFiles[idx];
    selectedOcrFiles.splice(idx, 1);
    renderSelectedOcrFilesChips();
    appendOcrLog(`🗑️ Đã gỡ tệp khỏi danh sách: ${removed.name}`, "info");
  }
}

function clearOcrSelectedFiles() {
  selectedOcrFiles = [];
  renderSelectedOcrFilesChips();
  const fileInput = document.getElementById("pdf-file-input");
  if (fileInput) fileInput.value = "";
  appendOcrLog("🗑️ Đã xóa sạch danh sách tệp đề thi đã chọn.", "info");
}

// ============================================================================
// 2. Process Files & Multi-File OCR Pipeline
// ============================================================================
async function processSelectedFilesOcr() {
  if (!selectedOcrFiles || selectedOcrFiles.length === 0) {
    showToast("Vui lòng chọn ít nhất 1 file đề thi hoặc ảnh", "warning");
    appendOcrLog("⚠️ Chưa chọn tệp đề thi nào để bóc tách.", "warning");
    return;
  }

  const loadingContainer = document.getElementById("ocr-loading-container");
  const loadingTitle = document.getElementById("ocr-loading-title");
  const loadingDesc = document.getElementById("ocr-loading-desc");
  const batchCard = document.getElementById("ocr-batch-progress-card");

  if (loadingContainer) loadingContainer.style.display = "block";
  if (batchCard) batchCard.style.display = "none";

  const allExtractedQuestions = [];
  const allImages = [];
  const totalFiles = selectedOcrFiles.length;

  appendOcrLog(`🚀 Bắt đầu quá trình bóc tách ${totalFiles} tệp đã chọn...`, "info");

  for (let i = 0; i < totalFiles; i++) {
    const file = selectedOcrFiles[i];
    const ext = "." + file.name.split(".").pop().toLowerCase();
    const isImage = [".png", ".jpg", ".jpeg", ".webp", ".bmp"].includes(ext);

    if (loadingTitle) {
      loadingTitle.textContent = `Đang bóc tách tệp ${i + 1}/${totalFiles}: ${file.name}...`;
    }
    if (loadingDesc) {
      loadingDesc.textContent = `Đang nhận diện văn bản (OCR), phân loại khối lớp và trích xuất phương án...`;
    }

    const ocrEngine = document.getElementById("ocr-engine-select")?.value || "ai_vision";
    const engineLabels = {
      "ai_vision": "AI Vision (Trực quan Đa tầng)",
      "rapid": "RapidOCR (PaddleOCR ONNX)",
      "vietocr": "VietOCR ONNX (Chuyên sâu)"
    };
    const engineLabel = engineLabels[ocrEngine] || ocrEngine;

    appendOcrLog(`⏳ [Tệp ${i + 1}/${totalFiles}] Đang gửi '${file.name}' (${(file.size / 1024).toFixed(1)} KB) | Động cơ chọn: ${engineLabel}...`, "upload");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("save_to_bank", "false");
    formData.append("engine", ocrEngine);

    try {
      const endpoint = isImage ? `${API_BASE}/import/image` : `${API_BASE}/import/pdf`;
      const startTime = performance.now();
      const res = await apiFetch(endpoint, {
        method: "POST",
        body: formData
      });
      const latency = ((performance.now() - startTime) / 1000).toFixed(2);

      if (!res.ok) {
        const errText = await res.text();
        appendOcrLog(`❌ [Tệp ${i + 1}/${totalFiles}] '${file.name}' lỗi HTTP ${res.status} (${latency}s): ${errText.substring(0, 150)}`, "error");
        showToast(`Lỗi xử lý file ${file.name}: HTTP ${res.status}`, "error");
        continue;
      }

      const data = await res.json();
      if (Array.isArray(data.ai_vision_logs) && data.ai_vision_logs.length > 0) {
        data.ai_vision_logs.forEach(logLine => {
          let logType = "info";
          if (logLine.includes("❌") || logLine.includes("lỗi") || logLine.includes("Error")) logType = "error";
          else if (logLine.includes("⚠️") || logLine.includes("hết hạn") || logLine.includes("Rate Limit")) logType = "warning";
          else if (logLine.includes("✅") || logLine.includes("thành công") || logLine.includes("✨")) logType = "success";
          appendOcrLog(logLine, logType);
        });
      }

      const qList = (data && (data.preview_questions || data.questions)) ? (data.preview_questions || data.questions) : [];
      const engineReported = data.engine_used || (qList[0] && qList[0].ocr_engine_used) || data.ocr_engine || ocrEngine;

      if (qList.length > 0) {
        appendOcrLog(`✅ [Tệp ${i + 1}/${totalFiles}] '${file.name}' bóc tách thành công ${qList.length} câu hỏi (${latency}s) [Động cơ: ${engineReported}]!`, "success");
        
        const serverImgUrl = data.image_url || data.source_image_url || null;
        let localFileUrl = null;
        if (isImage) {
          try { localFileUrl = URL.createObjectURL(file); } catch(e){}
        }
        const effectiveSourceUrl = serverImgUrl || localFileUrl;
        if (effectiveSourceUrl && !allImages.includes(effectiveSourceUrl)) {
          allImages.push(effectiveSourceUrl);
        }

        qList.forEach(q => {
          if ((!q.images || q.images.length === 0) && effectiveSourceUrl) {
            q.images = [effectiveSourceUrl];
          }
          if (!q.source_image_url && effectiveSourceUrl) {
            q.source_image_url = effectiveSourceUrl;
          }
          allExtractedQuestions.push({
            ...q,
            source_file_name: file.name
          });
          if (q.images && q.images.length > 0) {
            q.images.forEach(imgUrl => {
              if (!allImages.includes(imgUrl)) allImages.push(imgUrl);
            });
          }
        });
      } else {
        appendOcrLog(`⚠️ [Tệp ${i + 1}/${totalFiles}] '${file.name}' (${latency}s) [Động cơ: ${engineReported}] không tìm thấy khối câu hỏi hợp lệ.`, "warning");
      }
    } catch (err) {
      console.error(`Error processing file ${file.name}:`, err);
      appendOcrLog(`❌ [Tệp ${i + 1}/${totalFiles}] Lỗi kết nối khi gửi '${file.name}': ${err.message}`, "error");
      showToast(`Lỗi xử lý file ${file.name}: ${err.message}`, "error");
    }
  }

  if (loadingContainer) loadingContainer.style.display = "none";

  if (allExtractedQuestions.length === 0) {
    appendOcrLog(`❌ Quá trình kết thúc nhưng không có câu hỏi nào được bóc tách từ ${totalFiles} tệp.`, "error");
    showToast("⚠️ Không tìm thấy câu hỏi nào trong các tệp đã chọn. Vui lòng kiểm tra độ nét của ảnh hoặc nội dung PDF.", "error");
    return;
  }

  appendOcrLog(`🎯 Tổng cộng trích xuất thành công ${allExtractedQuestions.length} câu hỏi từ ${totalFiles} tệp. Khởi tạo quy trình đối soát...`, "batch");

  // Initialize OCR Batch Verification Flow
  startOcrBatchVerification(allExtractedQuestions, allImages);
}

// ============================================================================
// 3. OCR Batch Verification Progression Logic
// ============================================================================
function startOcrBatchVerification(questions, images) {
  if (!window.State && typeof State !== "undefined") {
    window.State = State;
  } else if (!window.State) {
    window.State = {};
  }

  // Initialize per-question OCR tracking status
  questions.forEach((q, idx) => {
    if (!q._ocrStatus) q._ocrStatus = "pending"; // 'pending' | 'saved' | 'skipped'
    q._ocrIndex = idx;
  });

  const primarySourceImg = (images && images.length > 0) ? images[0] : (questions[0] && (questions[0].source_image_url || (questions[0].images && questions[0].images[0]))) || null;

  window.State.ocrBatch = {
    items: questions,
    currentIndex: 0,
    processedCount: 0,
    savedCount: 0,
    skippedCount: 0,
    totalCount: questions.length,
    images: images || [],
    sourceImageUrl: primarySourceImg
  };

  // Switch to view-manual if not already active
  if (typeof switchView === "function" && window.State.currentView !== "manual") {
    switchView("manual");
  }

  const batchCard = document.getElementById("ocr-batch-progress-card");
  if (batchCard) {
    batchCard.style.display = "block";
    batchCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const modeBadge = document.getElementById("editor-mode-badge");
  if (modeBadge) {
    const firstQEngine = (questions[0] && questions[0].ocr_engine_used) || "OCR";
    modeBadge.textContent = `CHẾ ĐỘ: ĐÍNH CHÍNH & LƯU BÓC TÁCH [Động cơ: ${firstQEngine}] (${questions.length} CÂU)`;
    modeBadge.style.background = "#eff6ff";
    modeBadge.style.color = "#1d4ed8";
  }

  // Render question pills nav bar
  renderOcrQuestionsNavBar();

  // Load the first question into the manual editor form
  loadOcrQuestionToForm(0);

  appendOcrLog(`✨ Đã nạp Câu 1/${questions.length} vào trình Soạn thảo. Bạn có thể tự do chuyển qua lại giữa các câu hỏi hoặc Bỏ qua câu không phù hợp.`, "batch");

  showToast(`🎉 Đã bóc tách thành công ${questions.length} câu hỏi! Tự do duyệt qua lại và lưu từng câu.`, "success");
}

function renderOcrQuestionsNavBar() {
  const container = document.getElementById("ocr-questions-nav-bar");
  if (!container || !window.State.ocrBatch || !window.State.ocrBatch.items) return;

  const items = window.State.ocrBatch.items;
  const currentIdx = window.State.ocrBatch.currentIndex || 0;

  container.innerHTML = items.map((q, idx) => {
    const isActive = (idx === currentIdx);
    const status = q._ocrStatus || "pending";
    let icon = "⚪";
    let statusClass = "status-pending";
    let titleTooltip = `Câu ${idx + 1}: Chưa lưu`;

    if (status === "saved") {
      icon = "🟢";
      statusClass = "status-saved";
      titleTooltip = `Câu ${idx + 1}: Đã lưu vào CSDL`;
    } else if (status === "skipped") {
      icon = "❌";
      statusClass = "status-skipped";
      titleTooltip = `Câu ${idx + 1}: Đã bỏ qua`;
    }

    const activeClass = isActive ? "active" : "";

    return `
      <button type="button" 
        class="ocr-q-pill ${activeClass} ${statusClass}" 
        onclick="jumpToOcrQuestion(${idx})" 
        title="${titleTooltip}"
        data-index="${idx}">
        <span>${icon}</span>
        <span>Câu ${idx + 1}</span>
      </button>
    `;
  }).join("");
}

function jumpToOcrQuestion(index) {
  if (!window.State.ocrBatch || !window.State.ocrBatch.items) return;
  const total = window.State.ocrBatch.totalCount;
  if (index < 0 || index >= total) return;
  loadOcrQuestionToForm(index);
}

function loadOcrQuestionToForm(index) {
  if (!window.State.ocrBatch || !window.State.ocrBatch.items) return;
  const items = window.State.ocrBatch.items;
  if (index < 0 || index >= items.length) return;

  const q = items[index];
  window.State.ocrBatch.currentIndex = index;

  if (!q._rawOcrText) {
    q._rawOcrText = q.content_text || q.content_html || "";
  }

  // Fill manual question editor fields
  const elPlatform = document.getElementById("m-platform");
  const elGrade = document.getElementById("m-grade");
  const elSubject = document.getElementById("m-subject");
  const elTopic = document.getElementById("m-topic");
  const elContent = document.getElementById("m-content");
  const elOptA = document.getElementById("m-opt-a");
  const elOptB = document.getElementById("m-opt-b");
  const elOptC = document.getElementById("m-opt-c");
  const elOptD = document.getElementById("m-opt-d");
  const elCorrect = document.getElementById("m-correct");
  const elDiff = document.getElementById("m-diff");
  const elExplanation = document.getElementById("m-explanation");

  if (elPlatform) elPlatform.value = q.source_platform || "image_ocr";
  if (elGrade) elGrade.value = String(q.grade || 5);
  if (elSubject) elSubject.value = q.subject || "math";
  if (elTopic) elTopic.value = q.topic || q.exam_name || "Đề thi bóc tách (OCR/PDF)";
  if (elContent) elContent.value = q.content_text || q.content_html || "";

  const opts = q.options || [];

  // Helper to extract clean content from option (string or object)
  function getCleanOptContent(opt) {
    if (!opt) return "";
    if (typeof opt === "string") {
      return opt.replace(/^\(?[A-Da-d]\)?[\.\:\)\-]\s*/, "").trim();
    }
    if (typeof opt === "object") {
      const c = (opt.content !== undefined) ? opt.content : ((opt.text !== undefined) ? opt.text : (opt.value || ""));
      return typeof c === "string" ? c.replace(/^\(?[A-Da-d]\)?[\.\:\)\-]\s*/, "").trim() : String(c);
    }
    return String(opt);
  }

  function findOptionMatch(letter, idx) {
    if (!Array.isArray(opts)) return null;
    const byId = opts.find(o => typeof o === "object" && o && String(o.id || o.key || o.label).toUpperCase() === letter);
    if (byId) return byId;
    const byStr = opts.find(o => typeof o === "string" && new RegExp(`^\\(?${letter}\\)?[\\.\\:\\)\\-]`, "i").test(o.trim()));
    if (byStr) return byStr;
    return opts[idx] || null;
  }

  const optA = findOptionMatch("A", 0);
  const optB = findOptionMatch("B", 1);
  const optC = findOptionMatch("C", 2);
  const optD = findOptionMatch("D", 3);

  if (elOptA) elOptA.value = getCleanOptContent(optA);
  if (elOptB) elOptB.value = getCleanOptContent(optB);
  if (elOptC) elOptC.value = getCleanOptContent(optC);
  if (elOptD) elOptD.value = getCleanOptContent(optD);

  // Determine correct answer
  let correctOpt = (q.correct_answer || "").toString().trim().toUpperCase();
  if (!correctOpt && Array.isArray(opts)) {
    const foundCorrect = opts.find(o => o && (o.is_correct === true || o.is_correct === "true"));
    if (foundCorrect) correctOpt = String(foundCorrect.id || "").toUpperCase();
  }
  const matchLetter = correctOpt.match(/^([A-D])/i);
  const finalLetter = matchLetter ? matchLetter[1].toUpperCase() : (["A", "B", "C", "D"].includes(correctOpt) ? correctOpt : "A");
  if (elCorrect) elCorrect.value = finalLetter;

  if (elDiff) elDiff.value = q.difficulty || "medium";
  if (elExplanation) elExplanation.value = q.explanation || "";

  // Sync OCR question images to the manual image gallery (only if question has cropped diagrams/images)
  const qImages = (q.images && q.images.length > 0) ? [...q.images] : [];
  if (typeof window.manualImageUrls !== "undefined" || typeof manualImageUrls !== "undefined") {
    window.manualImageUrls = [...qImages];
    if (typeof manualImageUrls !== "undefined") manualImageUrls = window.manualImageUrls;
    if (typeof renderManualImageGallery === "function") renderManualImageGallery();
  }

  // Update Live KaTeX Preview (with images)
  if (typeof updateManualPreviewWithImages === "function") {
    updateManualPreviewWithImages();
  } else {
    const mPreview = document.getElementById("m-preview-box");
    if (mPreview) {
      const rawVal = elContent ? elContent.value : "";
      if (rawVal.trim()) {
        mPreview.innerHTML = `<div style="font-size: 14.5px; line-height: 1.6;">${rawVal.replace(/\n/g, '<br/>')}</div>`;
        if (typeof renderMath === "function") renderMath(mPreview);
      } else {
        mPreview.innerHTML = `<p style="color: #94a3b8; font-style: italic;">Nội dung câu hỏi và công thức toán sẽ hiển thị thử tại đây khi bạn nhập...</p>`;
      }
    }
  }

  // Update Batch Progress Indicators
  const total = window.State.ocrBatch.totalCount;
  const saved = window.State.ocrBatch.savedCount || 0;
  const skipped = window.State.ocrBatch.skippedCount || 0;
  const processed = saved + skipped;
  window.State.ocrBatch.processedCount = processed;

  const statusBadge = document.getElementById("ocr-batch-status-badge");
  const stepLabel = document.getElementById("ocr-batch-current-step");
  const progressText = document.getElementById("ocr-batch-progress-text");
  const progressBarFill = document.getElementById("ocr-batch-progress-bar-fill");
  const prevBtn = document.getElementById("btn-ocr-prev-q");
  const nextBtn = document.getElementById("btn-ocr-next-q");
  const discardBtn = document.getElementById("btn-ocr-discard-q");

  if (statusBadge) statusBadge.textContent = `✨ ĐÃ BÓC TÁCH: ${total} CÂU HỎI`;
  if (stepLabel) {
    const curStatus = q._ocrStatus === "saved" ? " [🟢 Đã lưu]" : q._ocrStatus === "skipped" ? " [❌ Đã bỏ qua]" : "";
    stepLabel.textContent = `Câu ${index + 1} / ${total}${curStatus}`;
  }
  if (progressText) progressText.textContent = `Đã xử lý: ${processed} / ${total} câu (Lưu: ${saved}, Bỏ qua: ${skipped})`;
  if (progressBarFill) {
    const pct = total > 0 ? ((processed / total) * 100) : 0;
    progressBarFill.style.width = `${pct}%`;
  }
  if (prevBtn) prevBtn.disabled = (index === 0);
  if (nextBtn) nextBtn.disabled = (index >= total - 1);
  if (discardBtn) {
    discardBtn.disabled = (q._ocrStatus === "skipped");
  }

  // Update Source Image Preview in Banner
  const imgBar = document.getElementById("ocr-source-image-bar");
  const imgThumb = document.getElementById("ocr-source-image-thumb");
  const imgName = document.getElementById("ocr-source-image-name");

  const batchSource = (window.State.ocrBatch && window.State.ocrBatch.sourceImageUrl) ||
                      (window.State.ocrBatch && window.State.ocrBatch.images && window.State.ocrBatch.images[0]) || null;
  const currentImgUrl = (q.images && q.images.length > 0) ? q.images[0] : (q.source_image_url || batchSource);
  const displaySource = batchSource || currentImgUrl;

  if (displaySource && imgBar && imgThumb) {
    imgBar.style.display = "flex";
    imgThumb.src = displaySource;
    if (imgName) imgName.textContent = q.source_file_name || q.exam_name || "Ảnh đề thi gốc";
  } else if (imgBar) {
    imgBar.style.display = "none";
  }

  // Update Save Button Label
  const btnSave = document.getElementById("btn-submit-manual-q");
  if (btnSave) {
    if (q._ocrStatus === "saved") {
      btnSave.innerHTML = `💾 Cập nhật / Lưu lại Câu ${index + 1} vào Ngân hàng`;
    } else {
      btnSave.innerHTML = `💾 Lưu câu hỏi ${index + 1}/${total} vào Ngân hàng`;
    }
  }

  // Update questions nav bar highlight
  renderOcrQuestionsNavBar();

  // Telemetry log for loaded question
  const stemSummary = (q.content_text || q.content_html || "").trim().substring(0, 50);
  appendOcrLog(`📝 [Câu ${index + 1}/${total}] Đã nạp vào Form: "${stemSummary}..." | ${opts.length} phương án | Đáp án gợi ý: [${correctOpt}] | Trạng thái: ${q._ocrStatus || 'chưa lưu'}`, "info");
}

function navPrevOcrQuestion() {
  if (!window.State.ocrBatch) return;
  if (window.State.ocrBatch.currentIndex > 0) {
    appendOcrLog(`⏮️ Quay lại Câu ${window.State.ocrBatch.currentIndex} / ${window.State.ocrBatch.totalCount}`, "info");
    loadOcrQuestionToForm(window.State.ocrBatch.currentIndex - 1);
  }
}

function navNextOcrQuestion() {
  if (!window.State.ocrBatch || !window.State.ocrBatch.items) return;
  const currIdx = window.State.ocrBatch.currentIndex;
  const total = window.State.ocrBatch.totalCount;
  if (currIdx < total - 1) {
    appendOcrLog(`➡ Chuyển tới Câu ${currIdx + 2} / ${total}`, "info");
    loadOcrQuestionToForm(currIdx + 1);
  } else {
    showToast("Bạn đang ở câu cuối cùng của đợt bóc tách", "info");
  }
}

function discardCurrentOcrQuestion() {
  if (!window.State.ocrBatch || !window.State.ocrBatch.items) return;
  const batch = window.State.ocrBatch;
  const currIdx = batch.currentIndex;
  const total = batch.totalCount;
  const q = batch.items[currIdx];

  if (!q) return;

  if (q._ocrStatus !== "skipped") {
    if (q._ocrStatus === "saved" && batch.savedCount > 0) {
      batch.savedCount--;
    }
    q._ocrStatus = "skipped";
    batch.skippedCount = (batch.skippedCount || 0) + 1;
    batch.processedCount = (batch.savedCount || 0) + batch.skippedCount;
  }

  appendOcrLog(`🗑️ Đã bỏ qua Câu ${currIdx + 1}/${total} (loại bỏ khỏi danh sách cần lưu CSDL)`, "warning");
  showToast(`Đã bỏ qua Câu ${currIdx + 1}`, "info");

  // Move to next pending question if any, or next available
  let nextIdx = -1;
  for (let i = currIdx + 1; i < total; i++) {
    if (batch.items[i]._ocrStatus === "pending") {
      nextIdx = i;
      break;
    }
  }
  if (nextIdx === -1) {
    for (let i = 0; i < currIdx; i++) {
      if (batch.items[i]._ocrStatus === "pending") {
        nextIdx = i;
        break;
      }
    }
  }

  if (nextIdx !== -1) {
    loadOcrQuestionToForm(nextIdx);
  } else {
    loadOcrQuestionToForm(currIdx);
    if (batch.processedCount >= total) {
      showToast(`🎉 Toàn bộ ${total} câu hỏi đã được xử lý (Lưu: ${batch.savedCount || 0}, Bỏ qua: ${batch.skippedCount})!`, "success");
    }
  }
}

function skipCurrentOcrQuestion() {
  discardCurrentOcrQuestion();
}

async function saveAllRemainingOcrQuestions() {
  if (!window.State.ocrBatch || !window.State.ocrBatch.items) return;

  const remainingQuestions = window.State.ocrBatch.items.filter(q => q._ocrStatus !== "saved" && q._ocrStatus !== "skipped");

  if (remainingQuestions.length === 0) {
    showToast("Không còn câu hỏi nào chưa lưu hoặc chưa bỏ qua!", "info");
    completeOcrBatchSession();
    return;
  }

  appendOcrLog(`⚡ Bắt đầu Lưu nhanh toàn bộ ${remainingQuestions.length} câu hỏi chưa lưu vào Ngân hàng CSDL...`, "batch");
  try {
    const res = await apiFetch(`/api/questions/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions: remainingQuestions })
    });
    const data = await res.json();
    const count = data.inserted_count || remainingQuestions.length;
    remainingQuestions.forEach(q => { q._ocrStatus = "saved"; });
    window.State.ocrBatch.savedCount = (window.State.ocrBatch.savedCount || 0) + count;
    window.State.ocrBatch.processedCount = (window.State.ocrBatch.savedCount || 0) + (window.State.ocrBatch.skippedCount || 0);

    appendOcrLog(`✅ Đã lưu nhanh thành công ${count} câu hỏi vào CSDL!`, "success");
    showToast(`✓ Đã lưu nhanh thành công ${count} câu hỏi vào Ngân hàng!`, "success");

    if (typeof broadcastNewQuestions === "function") {
      broadcastNewQuestions(count, "Bóc tách Đề thi OCR");
    }

    renderOcrQuestionsNavBar();
    completeOcrBatchSession();
  } catch (err) {
    appendOcrLog(`❌ Lỗi khi lưu nhanh hàng loạt câu hỏi: ${err.message}`, "error");
    showToast(`Lỗi khi lưu câu hỏi: ${err.message}`, "error");
  }
}

function cancelOcrBatchSession() {
  appendOcrLog(`⏹️ Người dùng đã đóng/hủy phiên duyệt đính chính OCR.`, "warning");
  window.State.ocrBatch = null;
  const batchCard = document.getElementById("ocr-batch-progress-card");
  if (batchCard) batchCard.style.display = "none";
  if (typeof resetManualForm === "function") resetManualForm();
  showToast("Đã đóng phiên bóc tách OCR", "info");
}

function completeOcrBatchSession() {
  const processed = window.State.ocrBatch ? (window.State.ocrBatch.processedCount || window.State.ocrBatch.totalCount) : 0;
  appendOcrLog(`🏁 Hoàn thành phiên duyệt OCR! Đã kiểm tra & nạp ${processed} câu hỏi vào CSDL.`, "success");
  window.State.ocrBatch = null;

  const batchCard = document.getElementById("ocr-batch-progress-card");
  if (batchCard) batchCard.style.display = "none";

  if (typeof resetManualForm === "function") resetManualForm();

  showToast(`🎉 Chúc mừng! Bạn đã hoàn thành kiểm tra và lưu ${processed} câu hỏi vào Ngân hàng CSDL!`, "success");

  loadDashboardStats();
  if (typeof State !== "undefined" && State.currentView === "bank") {
    loadQuestions();
  }
}

// ============================================================================
// 4. Lightbox Image Zoom & Pan Modal
// ============================================================================
function setupLightboxEvents() {
  const viewport = document.getElementById("zoom-viewport");
  if (!viewport) return;

  // Mouse wheel zoom
  viewport.addEventListener("wheel", (e) => {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.2 : -0.2;
    zoomImage(delta);
  }, { passive: false });

  // Mouse drag to pan
  viewport.addEventListener("mousedown", (e) => {
    ocrLightboxState.isDragging = true;
    ocrLightboxState.startX = e.clientX - ocrLightboxState.panX;
    ocrLightboxState.startY = e.clientY - ocrLightboxState.panY;
    viewport.style.cursor = "grabbing";
  });

  window.addEventListener("mousemove", (e) => {
    if (!ocrLightboxState.isDragging) return;
    ocrLightboxState.panX = e.clientX - ocrLightboxState.startX;
    ocrLightboxState.panY = e.clientY - ocrLightboxState.startY;
    applyImageTransform();
  });

  window.addEventListener("mouseup", () => {
    if (ocrLightboxState.isDragging) {
      ocrLightboxState.isDragging = false;
      const vp = document.getElementById("zoom-viewport");
      if (vp) vp.style.cursor = "grab";
    }
  });

  // ESC key to close modal
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const modal = document.getElementById("modal-image-zoom");
      if (modal && modal.style.display === "flex") {
        closeImageZoomModal();
      }
    }
  });
}

function openCurrentQuestionImageZoom() {
  let imgUrl = null;
  let title = "Ảnh đề thi";
  const candidateList = [];

  // 1. From active OCR batch
  if (window.State && window.State.ocrBatch) {
    const batch = window.State.ocrBatch;
    if (batch.items && typeof batch.currentIndex === "number") {
      const q = batch.items[batch.currentIndex];
      if (q) {
        if (q.source_image_url) candidateList.push(q.source_image_url);
        if (q.images && q.images.length > 0) candidateList.push(...q.images);
        title = q.source_file_name || q.exam_name || "Ảnh đề thi gốc";
      }
    }
    if (batch.sourceImageUrl) candidateList.push(batch.sourceImageUrl);
    if (batch.images && batch.images.length > 0) candidateList.push(...batch.images);
  }

  // 2. From manual question attached images
  const mImages = (typeof window.manualImageUrls !== "undefined" && window.manualImageUrls) || (typeof manualImageUrls !== "undefined" && manualImageUrls);
  if (mImages && mImages.length > 0) {
    candidateList.push(...mImages);
    if (!title || title === "Ảnh đề thi") title = "Ảnh đính kèm câu hỏi";
  }

  // 3. From OCR source image thumb
  const thumb = document.getElementById("ocr-source-image-thumb");
  if (thumb && thumb.src && !thumb.src.endsWith("#") && thumb.src !== window.location.href) {
    candidateList.push(thumb.src);
  }

  // 4. From selected files
  if (typeof selectedOcrFiles !== "undefined" && selectedOcrFiles && selectedOcrFiles.length > 0) {
    for (const f of selectedOcrFiles) {
      if (f && f.type && f.type.startsWith("image/")) {
        try {
          const blobUrl = URL.createObjectURL(f);
          candidateList.push(blobUrl);
          if (!title || title === "Ảnh đề thi") title = f.name;
        } catch (e) {}
      }
    }
  }

  // Deduplicate candidates
  const uniqueUrls = [];
  candidateList.forEach(u => {
    if (u && typeof u === "string" && !uniqueUrls.includes(u)) uniqueUrls.push(u);
  });

  if (uniqueUrls.length > 0) {
    ocrLightboxState.imageUrls = uniqueUrls;
    ocrLightboxState.currentIndex = 0;
    imgUrl = uniqueUrls[0];
  } else if (ocrLightboxState.imageUrls && ocrLightboxState.imageUrls.length > 0) {
    imgUrl = ocrLightboxState.imageUrls[0];
  }

  if (!imgUrl) {
    appendOcrLog(`⚠️ Phóng to ảnh: Không tìm thấy ảnh hoặc tệp xem trước để hiển thị`, "warning");
    showToast("Không tìm thấy ảnh xem trước để phóng to", "warning");
    return;
  }

  appendOcrLog(`🔍 Mở cửa sổ xem chi tiết / phóng to ảnh: "${title}" (Zoom 100%)`, "info");

  const modal = document.getElementById("modal-image-zoom");
  const targetImg = document.getElementById("zoom-target-img");
  const modalTitle = document.getElementById("zoom-modal-title");
  const pageLabel = document.getElementById("zoom-modal-page");

  if (targetImg) targetImg.src = imgUrl;
  if (modalTitle) modalTitle.textContent = `Bản xem trước chi tiết: ${title}`;
  if (pageLabel) {
    const totalImgs = Math.max(1, ocrLightboxState.imageUrls.length);
    pageLabel.textContent = `${ocrLightboxState.currentIndex + 1}/${totalImgs}`;
  }

  resetImageZoom();

  if (modal) modal.style.display = "flex";
}
window.openCurrentQuestionImageZoom = openCurrentQuestionImageZoom;
window.openImageZoomModal = openCurrentQuestionImageZoom;

function closeImageZoomModal() {
  const modal = document.getElementById("modal-image-zoom");
  if (modal) modal.style.display = "none";
  resetImageZoom();
}

function zoomImage(delta) {
  ocrLightboxState.zoom = Math.max(0.5, Math.min(4.0, ocrLightboxState.zoom + delta));
  applyImageTransform();
}

function resetImageZoom() {
  ocrLightboxState.zoom = 1.0;
  ocrLightboxState.rotation = 0;
  ocrLightboxState.panX = 0;
  ocrLightboxState.panY = 0;
  applyImageTransform();
}

function rotateImageZoom() {
  ocrLightboxState.rotation = (ocrLightboxState.rotation + 90) % 360;
  applyImageTransform();
}

function navZoomImage(dir) {
  if (!ocrLightboxState.imageUrls || ocrLightboxState.imageUrls.length <= 1) return;
  let newIdx = ocrLightboxState.currentIndex + dir;
  if (newIdx < 0) newIdx = ocrLightboxState.imageUrls.length - 1;
  if (newIdx >= ocrLightboxState.imageUrls.length) newIdx = 0;

  ocrLightboxState.currentIndex = newIdx;
  const newUrl = ocrLightboxState.imageUrls[newIdx];
  const targetImg = document.getElementById("zoom-target-img");
  const pageLabel = document.getElementById("zoom-modal-page");

  if (targetImg) targetImg.src = newUrl;
  if (pageLabel) pageLabel.textContent = `${newIdx + 1}/${ocrLightboxState.imageUrls.length}`;
  resetImageZoom();
}

function applyImageTransform() {
  const targetImg = document.getElementById("zoom-target-img");
  const levelLabel = document.getElementById("zoom-modal-level");

  if (targetImg) {
    targetImg.style.transform = `translate(${ocrLightboxState.panX}px, ${ocrLightboxState.panY}px) scale(${ocrLightboxState.zoom}) rotate(${ocrLightboxState.rotation}deg)`;
  }
  if (levelLabel) {
    levelLabel.textContent = `${Math.round(ocrLightboxState.zoom * 100)}%`;
  }
}


// -------------------------------------------------------------
// Universal Log Utilities (VN 24h Time & Safe Formatting)
// -------------------------------------------------------------
function getLogTimeVN(d = new Date()) {
  try {
    const formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Ho_Chi_Minh',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    return formatter.format(d);
  } catch (e) {
    const pad = (n) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }
}

function unSquishLogLines(rawText) {
  if (!rawText || !rawText.trim()) return "";
  let s = String(rawText);
  // Tách các dòng log bị dính liền dạng: ...nội dung[HH:mm:ss]...
  s = s.replace(/([^\n])\s*(\[\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?\])/g, (m, p1, p2) => p1 + "\n" + p2);
  // Tách các dòng bắt đầu bằng icon/emoji hoặc mũi tên mục tiêu nếu bị dính
  s = s.replace(/([^\n])\s*(->\s*Danh sách mục tiêu:|🚀|🤖|⏳|✅|❌|⚠️|📋|🔄|💡)/g, (m, p1, p2) => p1 + "\n" + p2);
  return s.split("\n").map(l => l.trimEnd()).filter(l => l.trim().length > 0).join("\n");
}

let scraperLogLines = [];
let isManualScrapeActive = false;

// Tự động đồng bộ các bản ghi nhật ký của Bot nền 24/7 từ máy chủ vào màn hình live log
async function syncScraperLiveLogsFromServer() {
  if (isManualScrapeActive) return;
  const logBox = document.getElementById("scraper-live-log");
  const toolbar = document.getElementById("scraper-log-toolbar");
  if (!logBox) return;

  try {
    const res = await apiFetch(`/api/collect/logs?platform=vioedu&limit=25`);
    const logs = await res.json();
    if (!logs || !Array.isArray(logs) || logs.length === 0) return;

    const formatted = [];
    for (const item of logs) {
      let timeStr = "";
      if (item.created_at) {
        try {
          timeStr = getLogTimeVN(new Date(item.created_at));
        } catch (e) {
          timeStr = String(item.created_at).slice(11, 19);
        }
      }
      let icon = "ℹ️";
      if (item.status === "success") icon = "✅";
      else if (item.status === "running") icon = "🚀";
      else if (item.status === "error") icon = "⚠️";

      const prefix = timeStr ? `[${timeStr}] ` : "";
      const isAuto = (item.message || "").includes("[auto") || (item.message || "").includes("Tự động cào") || (item.message || "").includes("auto-");
      const tag = isAuto ? "🤖 [TỰ ĐỘNG NỀN 24/7] " : "";

      let extra = "";
      if ((item.message || "").includes("0 câu mới") && isAuto) {
        extra = "\n   💡 Ghi chú: Kích hoạt Adaptive Ledger Cooldown — các bài đã cào trước đó được giữ nguyên, tránh cào lặp.";
      } else if (item.items_count > 0) {
        extra = `\n   🎉 Thu hoạch thành công: Đã lưu +${item.items_count} câu hỏi mới vào Ngân hàng đề!`;
      }

      formatted.push(`${prefix}${icon} ${tag}${item.message}${extra}`);
    }

    if (formatted.length > 0) {
      const fullText = formatted.join("\n\n");
      scraperLogLines = formatted;
      logBox.textContent = fullText;
      logBox.style.display = "block";
      if (toolbar) toolbar.style.display = "flex";
      try {
        localStorage.setItem("eduquest_scraper_log", fullText);
      } catch (e) {}
    }
  } catch (err) {
    // network failure ignored
  }
}
window.syncScraperLiveLogsFromServer = syncScraperLiveLogsFromServer;

let isManualHunterActive = false;

// Tự động đồng bộ các bản ghi nhật ký Săn câu hỏi Internet từ máy chủ vào màn hình live log
async function syncHunterLiveLogsFromServer() {
  if (isManualHunterActive) return;
  const logBox = document.getElementById("hunter-live-log");
  const toolbar = document.getElementById("hunter-log-toolbar");
  if (!logBox) return;

  try {
    const res = await apiFetch(`/api/collect/logs?platform=internet_hunter&limit=25`);
    const logs = await res.json();
    if (!logs || !Array.isArray(logs) || logs.length === 0) return;

    const formatted = [];
    for (const item of logs) {
      let timeStr = "";
      if (item.created_at) {
        try {
          timeStr = getLogTimeVN(new Date(item.created_at));
        } catch (e) {
          timeStr = String(item.created_at).slice(11, 19);
        }
      }
      let icon = "🌐";
      if (item.status === "success") icon = "✅";
      else if (item.status === "error") icon = "⚠️";

      const prefix = timeStr ? `[${timeStr}] ` : "";
      formatted.push(`${prefix}${icon} ${item.message}`);
    }

    if (formatted.length > 0) {
      const fullText = formatted.join("\n\n");
      logBox.textContent = fullText;
      logBox.style.display = "block";
      if (toolbar) toolbar.style.display = "flex";
      try {
        localStorage.setItem("eduquest_hunter_log", fullText);
      } catch (e) {}
    }
  } catch (err) {
    // network failure ignored
  }
}
window.syncHunterLiveLogsFromServer = syncHunterLiveLogsFromServer;

function renderScraperLog() {
  const logBox = document.getElementById("scraper-live-log");
  const toolbar = document.getElementById("scraper-log-toolbar");
  if (!logBox) return;
  const fullText = scraperLogLines.join("\n") + (scraperLogLines.length > 0 ? "\n" : "");
  logBox.textContent = fullText;
  if (scraperLogLines.length > 0) {
    logBox.style.display = "block";
    logBox.scrollTop = logBox.scrollHeight;
    if (toolbar) toolbar.style.display = "flex";
  }
  try {
    localStorage.setItem("eduquest_scraper_log", fullText);
  } catch (e) {}
}

// Scraper Log Actions (Copy & Clear)
function copyScraperLiveLog() {
  let text = scraperLogLines.length > 0
    ? scraperLogLines.join("\n")
    : (localStorage.getItem("eduquest_scraper_log") || (document.getElementById("scraper-live-log")?.textContent || ""));
  text = unSquishLogLines(text);
  if (!text.trim()) {
    showToast("Chưa có nội dung nhật ký để sao chép", "error");
    return;
  }
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
  scraperLogLines = [];
  const logBox = document.getElementById("scraper-live-log");
  const toolbar = document.getElementById("scraper-log-toolbar");
  if (logBox) {
    logBox.textContent = "";
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
  const grade = parseInt(document.getElementById("scraper-grade").value) || 2;
  const btn = document.getElementById("btn-run-scraper");

  if (!username || !password) {
    showToast("Vui lòng nhập Tên đăng nhập và Mật khẩu tài khoản VioEdu để bot đăng nhập ngầm, hoặc nhấn '🌐 Cào diện rộng (3 môn)' để cào tự động không cần tài khoản!", "warning");
    return;
  }

  const logBox = document.getElementById("scraper-live-log");
  const toolbar = document.getElementById("scraper-log-toolbar");
  isManualScrapeActive = true;
  if (logBox) logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";

  const timeNow = getLogTimeVN();
  scraperLogLines = [
    `[${timeNow}] 🚀 [Bước 1/5] Khởi chạy Bot Đăng nhập Ngầm cho nền tảng ${platform.toUpperCase()}...`,
    `[${timeNow}] 🔑 [Bước 2/5] Đang kết nối tài khoản ${username} và kiểm tra quyền truy cập...`,
    `[${timeNow}] 🌐 [Bước 3/5] Đang khởi động trình duyệt ngầm Chromium để vượt bảo vệ và đồng bộ phiên...`,
    `[${timeNow}] ⏳ Đang rà soát vòng thi và bài luyện tập, vui lòng chờ trong giây lát...`
  ];
  renderScraperLog();

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `⏳ Bot đang cào dữ liệu ngầm...`;
  }

  try {
    const res = await apiFetch(`/api/collect/run`, {
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
    const finishTime = getLogTimeVN();

    // Render logs in natural chronological sequence (Step 1 -> Step 5 -> Summary report)
    if (data.logs && Array.isArray(data.logs) && data.logs.length > 0) {
      scraperLogLines = [...data.logs];
    }

    if (data.success) {
      const fixedGrade = data.account_grade || grade;
      if (data.account_grade) {
        const gradeSelect = document.getElementById("scraper-grade");
        if (gradeSelect) gradeSelect.value = String(data.account_grade);
      }

      if (data.inserted_count > 0) {
        showToast(`Bot đã cào thành công ${data.inserted_count} câu hỏi mới (Khối ${fixedGrade})!`, "success");
        if (typeof broadcastNewQuestions === "function") {
          broadcastNewQuestions(data.inserted_count, `VioEdu Bot (Lớp ${fixedGrade})`);
        }
      } else {
        showToast(`Đã hoàn tất quét VioEdu (Khối ${fixedGrade}). Dữ liệu đã được cập nhật.`, "info");
      }

      loadDashboardStats();
      if (typeof State !== "undefined" && State.currentView === "bank") {
        loadQuestions();
      }
    } else {
      const errMsg = `[${finishTime}] ❌ Lỗi: ${data.error || "Không thể hoàn thành tiến trình cào dữ liệu."}`;
      scraperLogLines.push(errMsg);
      showToast(data.error || "Lỗi đăng nhập / cào dữ liệu VioEdu", "error");
    }

    renderScraperLog();

  } catch (err) {
    const errTime = getLogTimeVN();
    const excMsg = `[${errTime}] ❌ Ngoại lệ: ${err.message}`;
    scraperLogLines.push(excMsg);
    renderScraperLog();
    showToast("Lỗi kết nối máy chủ cào dữ liệu: " + err.message, "error");
  } finally {
    isManualScrapeActive = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "🚀 Cào theo tài khoản (vòng thi)";
    }
    loadCollectorLogs();
  }
}

// Cào diện rộng VioEdu qua cụm thống nhất: toàn curriculum 3 môn, không cần login.
// Bài mới cào trong 7 ngày tự bỏ qua (ledger), trừ khi tick "Cào lại bài cũ".
async function runVioEduBreadth() {
  const gradeVal = document.getElementById("scraper-grade")?.value || "2";
  const isAll = gradeVal === "all";
  const grades = isAll ? [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] : [parseInt(gradeVal) || 2];
  const gradeLabel = isAll ? "Tất cả các khối (1-12)" : `Khối ${gradeVal}`;
  const force = document.getElementById("vioedu-force-recrawl")?.checked || false;
  const btn = document.getElementById("btn-vioedu-breadth");

  const logBox = document.getElementById("scraper-live-log");
  const toolbar = document.getElementById("scraper-log-toolbar");
  isManualScrapeActive = true;
  if (logBox) logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";

  const timeNow = getLogTimeVN();
  scraperLogLines = [
    `[${timeNow}] 🌐 Cào diện rộng VioEdu ${gradeLabel} (Toán + Tiếng Việt + Tiếng Anh)...`,
    `[${timeNow}] Không cần đăng nhập — dùng GraphQL công khai, quét toàn bộ bài luyện tập...`
  ];
  renderScraperLog();
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `⏳ Đang quét ${gradeLabel}...`;
  }
  try {
    const res = await apiFetch(`/api/collect/vioedu-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "breadth",
        grades: grades,
        subjects: ["math", "vietnamese", "english"],
        max_questions: 12,
        force: force
      })
    });
    const data = await res.json();
    const finishTime = getLogTimeVN();
    if (data.success && data.background) {
      // Sweep chạy nền nhiều phút — poll tiến độ, không giữ nút
      scraperLogLines.unshift(`[${finishTime}] 🚀 Đã khởi động job ${data.job_id}. Đang quét nền, tự cập nhật tiến độ...`);
      renderScraperLog();
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = "🌐 Cào diện rộng (3 môn)";
      }
      refreshVioEduHubStatus();
      pollBreadthStatus(data.job_id);
      loadCollectorLogs();
      return;
    }
    if (data.success) {
      isManualScrapeActive = false;
      const st = data.stats || {};
      const detail = Object.entries(st).map(([k, v]) => `${k}: ${v}`).join(", ");
      scraperLogLines.unshift(`[${finishTime}] ✅ Cào diện rộng xong: ${data.count} câu mới, ${data.skills_visited} bài (${detail})`);
      showToast(`Đã thêm ${data.count} câu VioEdu mới Khối ${grade} (${data.skills_visited} bài)!`, "success");
      if (typeof broadcastNewQuestions === "function" && data.count > 0) {
        broadcastNewQuestions(data.count, `VioEdu Diện rộng (Lớp ${grade})`);
      }
      loadDashboardStats();
      if (typeof State !== "undefined" && State.currentView === "bank") {
        loadQuestions();
      }
    } else {
      isManualScrapeActive = false;
      scraperLogLines.unshift(`[${finishTime}] ❌ Lỗi: ${data.error || "Không thể cào diện rộng."}`);
      showToast(data.error || "Lỗi cào diện rộng VioEdu", "error");
    }
    renderScraperLog();
  } catch (err) {
    isManualScrapeActive = false;
    scraperLogLines.unshift(`[${getLogTimeVN()}] ❌ Ngoại lệ: ${err.message}`);
    renderScraperLog();
    showToast("Lỗi kết nối máy chủ: " + err.message, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "🌐 Cào diện rộng (3 môn)";
    }
    loadCollectorLogs();
  }
}

// Trạng thái cụm VioEdu: auto on/off + ledger + job gần nhất
async function refreshVioEduHubStatus() {
  const box = document.getElementById("vioedu-hub-status");
  const txt = document.getElementById("vioedu-hub-status-text");
  if (!box || !txt) return;
  try {
    const res = await apiFetch(`/api/collect/vioedu-plan`);
    const data = await res.json();
    if (!data.success) {
      txt.textContent = "⚪ Trung tâm thu thập: Vui lòng đăng nhập tài khoản quản trị để đồng bộ.";
      box.style.display = "block";
      return;
    }
    const nextGradeTxt = (data.auto_enabled && data.next_grade) ? ` | 🎯 Kế tiếp: Khối ${data.next_grade}/12` : "";
    const autoTxt = data.auto_enabled ? `🟢 Tự động nền 24/7: BẬT${nextGradeTxt}` : "⚪ Tự động nền 24/7: TẮT";
    const jobs = Object.entries(data.recent_jobs || {});
    const last = jobs.length ? jobs[jobs.length - 1] : null;
    const lastTxt = last ? `Job gần nhất: ${last[0]} (${last[1].status}, +${last[1].count || 0} câu, ${last[1].skills_visited || 0} bài)` : "Chưa có job nào";
    const runTxt = (data.running_jobs || []).length ? ` | ⏳ Đang chạy: ${data.running_jobs.join(", ")}` : "";
    // Heartbeat: scheduler tick mỗi vòng (kể cả khi TẮT/skip) → phân biệt
    // "bot sống nhưng nhàn" với "bot chết". Quá 2×interval không tick = chết.
    let hbTxt = " | 💓 Bot: chưa có tín hiệu";
    try {
      const hb = data.heartbeat || {};
      if (hb.tick_at) {
        const ageMin = Math.round((Date.now() - new Date(hb.tick_at).getTime()) / 60000);
        const ivMin = Math.max(10, Math.round((parseInt(data.interval_sec) || 21600) / 60));
        const alive = ageMin <= ivMin * 2 + 5;
        hbTxt = alive
          ? ` | 💓 Bot sống (tick ${ageMin} phút trước: ${hb.note || ""})`
          : ` | 🔴 Bot mất tín hiệu ${ageMin} phút (tick cuối: ${hb.note || "?"})`;
      }
    } catch (e) { /* giữ text mặc định */ }
    // User 2026-10-14: hien TK VioEdu bot dang dung (hay anonymous).
    const sessTxt = data.vioedu_logged_in
      ? ` | 🔑 TK VioEdu: ${data.vioedu_account || "?"}`
      : " | ⚪ Chưa nhập TK VioEdu (cào anonymous)";
    txt.textContent = `${autoTxt} | 📒 Đã cào: ${data.ledger_skills || 0} bài | ${lastTxt}${runTxt}${hbTxt}${sessTxt}`;
    box.style.display = "block";

    // Đồng bộ trạng thái giao diện Toggle & Badge
    const botToggle = document.getElementById("bot-auto-crawl-toggle");
    const botBadge = document.getElementById("bot-auto-crawl-badge");
    const botCountdown = document.getElementById("bot-countdown-display");
    if (botToggle) botToggle.checked = !!data.auto_enabled;
    if (botBadge) botBadge.style.display = data.auto_enabled ? "inline-flex" : "none";
    if (botCountdown) {
      botCountdown.innerText = data.auto_enabled ? `Khối ${data.next_grade || 2}` : "Đã dừng";
    }

    // Tự động kéo nhật ký cào nền mới nhất từ server vào live log
    syncScraperLiveLogsFromServer();
  } catch (e) {
    if (txt) {
      txt.textContent = "⚪ Trung tâm thu thập: Vui lòng đăng nhập tài khoản quản trị để đồng bộ.";
      box.style.display = "block";
    }
  }
}

// Poll tiến độ job breadth nền mỗi 15s (tối đa ~20 phút), không giữ nút bấm
async function pollBreadthStatus(jobId, tries = 0) {
  const MAX_TRIES = 80;
  try {
    const res = await apiFetch(`/api/collect/breadth-status?job_id=${encodeURIComponent(jobId)}`);
    const data = await res.json();
    const st = data.status || "running";
    if (st === "done") {
      isManualScrapeActive = false;
      const detail = Object.entries(data.stats || {}).map(([k, v]) => `${k}: ${v}`).join(", ");
      scraperLogLines.unshift(`[${getLogTimeVN()}] ✅ Cào diện rộng xong: ${data.count} câu mới, ${data.skills_visited} bài (${detail})`);
      showToast(`Đã thêm ${data.count} câu VioEdu mới (${data.skills_visited} bài)!`, "success");
      if (typeof broadcastNewQuestions === "function" && data.count > 0) {
        broadcastNewQuestions(data.count, "VioEdu Diện rộng");
      }
      loadDashboardStats();
      renderScraperLog();
      loadCollectorLogs();
      refreshVioEduHubStatus();
      return;
    }
    if (st === "error") {
      isManualScrapeActive = false;
      scraperLogLines.unshift(`[${getLogTimeVN()}] ❌ Cào diện rộng lỗi: ${data.error || "?"}`);
      showToast("Cào diện rộng lỗi: " + (data.error || "?"), "error");
      renderScraperLog();
      loadCollectorLogs();
      refreshVioEduHubStatus();
      return;
    }
  } catch (e) {
    // Mất phiên (apiFetch ném lỗi 401 + đã mở tường login): dừng poll ngay,
    // không retry mù 20 phút (mỗi lần retry lại mở tường).
    if (/401|đăng nhập|hết hạn/i.test((e && e.message) || "")) {
      isManualScrapeActive = false;
      scraperLogLines.unshift(`[${getLogTimeVN()}] 🔐 Phiên đăng nhập hết hạn — đã dừng theo dõi job ${jobId}. Đăng nhập lại rồi bấm Cào diện rộng để chạy job mới.`);
      renderScraperLog();
      return;
    }
    /* thử lại kỳ sau */
  }
  if (tries < MAX_TRIES) {
    setTimeout(() => pollBreadthStatus(jobId, tries + 1), 15000);
  } else {
    isManualScrapeActive = false;
    scraperLogLines.unshift(`[${getLogTimeVN()}] ℹ️ Job ${jobId} quá 20 phút — xem kết quả ở Nhật ký Thu thập.`);
    renderScraperLog();
  }
}

// Load Collector Logs
async function loadCollectorLogs() {
  const listEl = document.getElementById("collector-logs-list");
  if (!listEl) return;

  try {
    const res = await apiFetch(`/api/collect/logs`);
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
          ${typeof formatDateTimeVN === 'function' ? formatDateTimeVN(l.created_at) : (l.created_at || '')}
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Error loading logs:", err);
  }
}

async function copyCollectorLogs() {
  try {
    const res = await apiFetch(`/api/collect/logs`);
    const logs = await res.json();
    if (!logs || logs.length === 0) {
      showToast("Chưa có nhật ký nào để sao chép", "error");
      return;
    }
    const text = logs.map(l => `[${typeof formatDateTimeVN === 'function' ? formatDateTimeVN(l.created_at) : (l.created_at || '')}] [${l.platform.toUpperCase()}] [${l.status.toUpperCase()}] ${l.message}`).join("\n");
    await navigator.clipboard.writeText(text);
    showToast("Đã sao chép toàn bộ nhật ký debug vào clipboard!");
  } catch (err) {
    showToast("Lỗi sao chép: " + err.message, "error");
  }
}

async function clearAllCollectorLogs() {
  if (!confirm("Bạn có chắc chắn muốn xóa sạch toàn bộ nhật ký hoạt động thu thập?")) return;
  try {
    const res = await apiFetch(`/api/collect/logs`, { method: "DELETE" });
    const data = await res.json();
    showToast(data.message || "Đã xóa toàn bộ nhật ký");
    loadCollectorLogs();
  } catch (err) {
    showToast("Lỗi xóa nhật ký", "error");
  }
}

// Target URLs list for Internet Hunter & Universal Multi-Grade Presets
let hunterTargetUrls = [];

function getHunterGradeValue(targetGrade) {
  const raw = targetGrade !== undefined ? targetGrade : (document.getElementById("hunter-grade")?.value || localStorage.getItem("eduquest_default_grade") || localStorage.getItem("eduquest_selected_grade") || "2");
  if (raw === "all") return "all";
  return Math.max(1, Math.min(12, parseInt(raw) || 2));
}

function getHunterStorageKey(targetGrade) {
  const g = getHunterGradeValue(targetGrade);
  return g === "all" ? "eduquest_hunter_urls_all" : `eduquest_hunter_urls_g${g}`;
}

function getDefaultHunterUrlsForGrade(gradeVal) {
  const timeNow = typeof getLogTimeVN === "function" ? getLogTimeVN() : "Mặc định";

  // Danh mục nguồn mặc định toàn diện cho tất cả các khối (Khối 1 đến 12)
  if (gradeVal === "all") {
    return [
      { id: "def_all_hts", url: "https://hanhtrangso.nxbgd.vn/sach-dien-tu", name: "Hành trang số (Kho SGK GDPT 2018 Lớp 1-12)", tag: "Toán GDPT", icon: "📘", active: true, addedAt: timeNow },
      { id: "def_all_lgh", url: "https://loigiaihay.com/", name: "Lời Giải Hay (Kho đề thi trắc nghiệm Toán, Văn, Anh 1-12)", tag: "Đa môn GDPT", icon: "📐", active: true, addedAt: timeNow },
      { id: "def_all_vj", url: "https://vietjack.com/", name: "VietJack (Trắc nghiệm & Đề thi 1-12 có đáp án)", tag: "Trắc nghiệm", icon: "📚", active: true, addedAt: timeNow },
      { id: "def_all_olm", url: "https://olm.vn/", name: "OLM.vn (Học trực tuyến & luyện đề Lớp 1-12 ĐH Sư Phạm)", tag: "Tương tác", icon: "🎓", active: true, addedAt: timeNow },
      { id: "def_all_thcs_toanmath", url: "https://thcs.toanmath.com/", name: "THCS TOANMATH (Đề thi & Tài liệu trắc nghiệm Toán 6-9)", tag: "Toán THCS", icon: "📐", active: true, addedAt: timeNow },
      { id: "def_all_toanmath", url: "https://toanmath.com/", name: "TOANMATH (Đề thi thử THPT & Chuyên đề Toán 10-12)", tag: "Toán THPT", icon: "📐", active: true, addedAt: timeNow },
      { id: "def_all_tech12h", url: "https://tech12h.com/", name: "Tech12h (Bài tập trắc nghiệm & Đề kiểm tra 1-12)", tag: "Trắc nghiệm", icon: "📑", active: true, addedAt: timeNow },
      { id: "def_all_vndoc", url: "https://vndoc.com/", name: "VnDoc (Kho tài liệu & Đề thi học kỳ 1-12)", tag: "Tài liệu", icon: "📋", active: true, addedAt: timeNow },
      { id: "def_all_vioedu", url: "https://vio.edu.vn/skill-list", name: "VioEdu (Đấu trường Toán học FPT Lớp 1-9)", tag: "Toán VioEdu", icon: "⚡", active: true, addedAt: timeNow },
      { id: "def_all_tnmath", url: "https://tnmath.edu.vn/", name: "Trạng Nguyên Toán (Sân chơi Toán Tiểu học 1-5)", tag: "Trạng Nguyên", icon: "👑", active: true, addedAt: timeNow },
      { id: "def_all_ioe", url: "https://ioe.vn/", name: "IOE (Cuộc thi Olympic Tiếng Anh Internet 1-12)", tag: "Olympic", icon: "🎧", active: true, addedAt: timeNow },
      { id: "def_all_ta123", url: "https://www.tienganh123.com/", name: "Tiếng Anh 123 (Chương trình Tiếng Anh 1-12)", tag: "Tiếng Anh", icon: "🇬🇧", active: true, addedAt: timeNow },
      { id: "def_all_k5", url: "https://www.k5learning.com/free-math-worksheets", name: "K5 Learning (Worksheets Toán & Reading US Common Core)", tag: "US Math", icon: "📑", active: true, addedAt: timeNow },
      { id: "def_all_ixl", url: "https://www.ixl.com/math", name: "IXL Learning (Kỹ năng Toán thích ứng Grade 1-12)", tag: "US Math", icon: "🎯", active: true, addedAt: timeNow },
      { id: "def_all_khan", url: "https://www.khanacademy.org/math", name: "Khan Academy (Học liệu Toán Quốc tế K-12)", tag: "Quốc tế", icon: "🌱", active: true, addedAt: timeNow },
      { id: "def_all_ccms", url: "https://www.commoncoresheets.com", name: "Common Core Math Sheets (Trình tạo đề bài tập K-12)", tag: "US Math", icon: "📋", active: true, addedAt: timeNow },
      { id: "def_all_edu", url: "https://www.education.com/worksheets/", name: "Education.com (Phiếu bài tập Math & ELA K-12)", tag: "Quốc tế", icon: "📑", active: true, addedAt: timeNow },
      { id: "def_all_ikmc", url: "https://kangaroo-math.vn", name: "Kangaroo Math IKMC (Toán tư duy Quốc tế 1-12)", tag: "Olympic", icon: "🦘", active: true, addedAt: timeNow },
      { id: "def_all_timo", url: "https://codemath.vn/khoa-hoc/timo", name: "Olympic TIMO & ASMO (Toán Song ngữ Anh - Việt)", tag: "Olympic", icon: "🏅", active: true, addedAt: timeNow },
      { id: "def_all_mp", url: "https://www.mathplayground.com/", name: "Math Playground (Game Toán tương tác & logic)", tag: "Tương tác", icon: "🎮", active: true, addedAt: timeNow }
    ];
  }

  const grade = Math.max(1, Math.min(12, parseInt(gradeVal) || 5));

  const lghMathSlugs = {
    1: "de-thi-de-kiem-tra-toan-lop-1-ket-noi-tri-thuc-c1211.html",
    2: "de-thi-de-kiem-tra-toan-lop-2-ket-noi-tri-thuc-c1212.html",
    3: "de-thi-de-kiem-tra-toan-lop-3-ket-noi-tri-thuc-c1215.html",
    4: "de-thi-de-kiem-tra-toan-lop-4-ket-noi-tri-thuc-c1636.html",
    5: "de-thi-de-kiem-tra-toan-lop-5-ket-noi-tri-thuc-c1990.html",
    6: "de-thi-de-kiem-tra-toan-lop-6-ket-noi-tri-thuc-c1022.html",
    7: "de-thi-de-kiem-tra-toan-lop-7-ket-noi-tri-thuc-c1097.html",
    8: "de-thi-de-kiem-tra-toan-lop-8-ket-noi-tri-thuc-c1612.html",
    9: "de-thi-de-kiem-tra-toan-lop-9-ket-noi-tri-thuc-c1984.html",
    10: "v2/tu-luyen-trac-nghiem-toan-10-ket-noi-tri-thuc-c980.html",
    11: "de-thi-de-kiem-tra-toan-lop-11-ket-noi-tri-thuc-c1623.html",
    12: "de-thi-de-kiem-tra-toan-lop-12-ket-noi-tri-thuc-c1964.html"
  };

  const lghVnSlugs = {
    2: "de-thi-de-kiem-tra-tieng-viet-lop-2-ket-noi-tri-thuc-c1213.html",
    3: "de-thi-de-kiem-tra-tieng-viet-lop-3-ket-noi-tri-thuc-c2269.html",
    4: "de-thi-de-kiem-tra-tieng-viet-lop-4-ket-noi-tri-thuc-c1796.html",
    5: "de-thi-de-kiem-tra-tieng-viet-lop-5-ket-noi-tri-thuc-c1994.html",
    6: "v2/tu-luyen-tu-luyen-van-6-kntt-c788.html",
    7: "v2/tu-luyen-tu-luyen-van-7-c761.html",
    8: "v2/tu-luyen-trac-nghiem-van-8-ket-noi-tri-thuc-c1453.html",
    9: "de-thi-de-kiem-tra-van-9-ket-noi-tri-thuc-c1968.html",
    10: "v2/tu-luyen-trac-nghiem-ngu-van-10-ket-noi-tri-thuc-c959.html",
    11: "v2/tu-luyen-trac-nghiem-van-11-ket-noi-tri-thuc-c1481.html",
    12: "de-thi-de-kiem-tra-van-12-ket-noi-tri-thuc-c1972.html"
  };

  const lghEnSlugs = {
    2: "de-thi-de-kiem-tra-tieng-anh-lop-2-ket-noi-tri-thuc-c1217.html",
    3: "de-thi-de-kiem-tra-tieng-anh-lop-3-global-success-c1218.html",
    4: "de-thi-de-kiem-tra-tieng-anh-lop-4-global-success-c1627.html",
    5: "de-thi-de-kiem-tra-tieng-anh-lop-5-global-success-c2008.html",
    6: "de-thi-de-kiem-tra-tieng-anh-lop-6-global-success-c1160.html",
    7: "de-thi-de-kiem-tra-tieng-anh-lop-7-global-success-c1182.html",
    8: "de-thi-de-kiem-tra-tieng-anh-lop-8-global-success-c1658.html",
    9: "de-thi-de-kiem-tra-tieng-anh-lop-9-global-success-c2003.html",
    10: "de-thi-de-kiem-tra-tieng-anh-lop-10-global-success-c1192.html",
    11: "v2/tu-luyen-trac-nghiem-tieng-anh-11-global-success-c1445.html",
    12: "v2/tu-luyen-trac-nghiem-tieng-anh-12-global-success-c1907.html"
  };

  const vietjackExamUrls = {
    1: "https://vietjack.com/de-kiem-tra-lop-1/de-kiem-tra-toan-lop-1.jsp",
    2: "https://vietjack.com/de-kiem-tra-lop-2/de-kiem-tra-toan-lop-2.jsp",
    3: "https://vietjack.com/de-kiem-tra-lop-3/de-kiem-tra-toan-lop-3.jsp",
    4: "https://vietjack.com/de-kiem-tra-toan-lop-4/index.jsp",
    5: "https://vietjack.com/de-kiem-tra-toan-5/index.jsp",
    6: "https://vietjack.com/de-kiem-tra-lop-6/de-kiem-tra-toan-6.jsp",
    7: "https://vietjack.com/de-kiem-tra-lop-7/de-kiem-tra-toan-7.jsp",
    8: "https://vietjack.com/de-kiem-tra-lop-8/de-kiem-tra-toan-8.jsp",
    9: "https://vietjack.com/de-kiem-tra-lop-9/de-kiem-tra-toan-9.jsp",
    10: "https://vietjack.com/de-kiem-tra-lop-10/de-kiem-tra-toan-10.jsp",
    11: "https://vietjack.com/de-kiem-tra-lop-11/de-kiem-tra-toan-11.jsp",
    12: "https://vietjack.com/de-kiem-tra-lop-12/de-kiem-tra-toan-12.jsp"
  };

  const vietjackTracNghiemUrls = {
    2: "https://vietjack.com/de-kiem-tra-lop-2/bai-tap-toan-lop-2.jsp",
    3: "https://vietjack.com/giai-toan-lop-3/bai-tap-trac-nghiem-toan-lop-3-co-dap-an.jsp",
    4: "https://vietjack.com/giai-toan-lop-4/bai-tap-trac-nghiem-toan-lop-4-co-dap-an.jsp",
    5: "https://vietjack.com/giai-toan-lop-5/bai-tap-trac-nghiem-toan-lop-5-co-dap-an.jsp",
    6: "https://vietjack.com/toan-6-ket-noi/bai-tap-trac-nghiem-toan-lop-6.jsp",
    7: "https://vietjack.com/toan-7-kn/trac-nghiem-toan-lop-7-ket-noi.jsp",
    8: "https://vietjack.com/toan-8-kn/trac-nghiem-toan-8-ket-noi.jsp",
    9: "https://vietjack.com/toan-9-kn/trac-nghiem-toan-lop-9.jsp",
    10: "https://vietjack.com/toan-10-kn/trac-nghiem-toan-lop-10-ket-noi.jsp",
    11: "https://vietjack.com/toan-11-kn/trac-nghiem-toan-11-ket-noi.jsp",
    12: "https://vietjack.com/toan-12-kn/trac-nghiem-toan-lop-12.jsp"
  };

  const k5Slugs = {
    1: "first-grade-1",
    2: "second-grade-2",
    3: "third-grade-3",
    4: "fourth-grade-4",
    5: "fifth-grade-5",
    6: "sixth-grade-6"
  };

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

  const defaults = [];

  // 1. SGK Hành Trang Số (NXB Giáo Dục Việt Nam)
  defaults.push({
    id: `def_hts_g${grade}`,
    url: `https://hanhtrangso.nxbgd.vn/sach-dien-tu?book_active=0&classes=${grade}`,
    name: `Hành trang số (SGK Toán Lớp ${grade})`,
    tag: "Toán GDPT",
    icon: "📘",
    active: true,
    addedAt: timeNow
  });

  // 2. Lời Giải Hay (Toán)
  if (lghMathSlugs[grade]) {
    defaults.push({
      id: `def_lgh_math_g${grade}`,
      url: `https://loigiaihay.com/${lghMathSlugs[grade]}`,
      name: `Lời Giải Hay (Đề thi Toán Lớp ${grade})`,
      tag: "Toán",
      icon: "📐",
      active: true,
      addedAt: timeNow
    });
  }

  // 3. VietJack (Đề kiểm tra Toán)
  if (vietjackExamUrls[grade]) {
    defaults.push({
      id: `def_vj_exam_g${grade}`,
      url: vietjackExamUrls[grade],
      name: `VietJack (Bộ đề thi Toán Lớp ${grade})`,
      tag: "Toán",
      icon: "📚",
      active: true,
      addedAt: timeNow
    });
  }

  // 4. VietJack (Trắc nghiệm Toán)
  if (vietjackTracNghiemUrls[grade]) {
    defaults.push({
      id: `def_vj_tn_g${grade}`,
      url: vietjackTracNghiemUrls[grade],
      name: `VietJack (Trắc nghiệm Toán Lớp ${grade})`,
      tag: "Trắc nghiệm",
      icon: "📝",
      active: true,
      addedAt: timeNow
    });
  }

  // 5. OLM.vn (Học tập & Luyện tập)
  defaults.push({
    id: `def_olm_g${grade}`,
    url: `https://olm.vn/lop-${grade}`,
    name: `OLM.vn (Khóa luyện tập Lớp ${grade})`,
    tag: "Tương tác",
    icon: "🎓",
    active: true,
    addedAt: timeNow
  });

  // 6. TOANMATH (THCS 6-9 hoặc THPT 10-12)
  if (grade >= 6 && grade <= 9) {
    defaults.push({
      id: `def_thcs_toanmath_g${grade}`,
      url: `https://thcs.toanmath.com/`,
      name: `THCS TOANMATH (Tài liệu Toán Lớp ${grade})`,
      tag: "Toán THCS",
      icon: "📐",
      active: true,
      addedAt: timeNow
    });
  } else if (grade >= 10 && grade <= 12) {
    defaults.push({
      id: `def_toanmath_g${grade}`,
      url: `https://toanmath.com/`,
      name: `TOANMATH (Đề thi thử & Chuyên đề Toán Lớp ${grade})`,
      tag: "Toán THPT",
      icon: "📐",
      active: true,
      addedAt: timeNow
    });
  }

  // 6b. Tech12h (Trắc nghiệm GDPT)
  defaults.push({
    id: `def_tech12h_g${grade}`,
    url: `https://tech12h.com/`,
    name: `Tech12h (Trắc nghiệm & Đề thi GDPT Lớp ${grade})`,
    tag: "Trắc nghiệm",
    icon: "📑",
    active: true,
    addedAt: timeNow
  });

  // 7. Lời Giải Hay (Tiếng Việt / Ngữ Văn)
  if (lghVnSlugs[grade]) {
    defaults.push({
      id: `def_lgh_vn_g${grade}`,
      url: `https://loigiaihay.com/${lghVnSlugs[grade]}`,
      name: `Lời Giải Hay (${grade <= 5 ? "Tiếng Việt" : "Ngữ Văn"} Lớp ${grade})`,
      tag: grade <= 5 ? "Tiếng Việt" : "Ngữ Văn",
      icon: "📖",
      active: true,
      addedAt: timeNow
    });
  }

  // 8. Lời Giải Hay (Tiếng Anh)
  if (lghEnSlugs[grade]) {
    defaults.push({
      id: `def_lgh_en_g${grade}`,
      url: `https://loigiaihay.com/${lghEnSlugs[grade]}`,
      name: `Lời Giải Hay (Tiếng Anh Lớp ${grade})`,
      tag: "Tiếng Anh",
      icon: "🇬🇧",
      active: true,
      addedAt: timeNow
    });
  }

  // 9. VioEdu & Trạng Nguyên
  if (grade <= 9) {
    defaults.push({
      id: `def_vioedu_g${grade}`,
      url: `https://vio.edu.vn/skill-list`,
      name: `VioEdu (Đấu trường Toán học Lớp ${grade})`,
      tag: "Toán VioEdu",
      icon: "⚡",
      active: true,
      addedAt: timeNow
    });
  }
  if (grade <= 5) {
    defaults.push({
      id: `def_tnmath_g${grade}`,
      url: `https://tnmath.edu.vn/`,
      name: `Trạng Nguyên Toán Lớp ${grade}`,
      tag: "Trạng Nguyên",
      icon: "👑",
      active: true,
      addedAt: timeNow
    });
  }

  // 10. K5 Learning (Worksheets Tiểu học 1-6)
  if (k5Slugs[grade]) {
    defaults.push({
      id: `def_k5_g${grade}`,
      url: `https://www.k5learning.com/free-math-worksheets/${k5Slugs[grade]}`,
      name: `K5 Learning (Worksheets Grade ${grade})`,
      tag: "US Math",
      icon: "📑",
      active: true,
      addedAt: timeNow
    });
  }

  // 11. IXL Learning (Math Grade 1-12)
  defaults.push({
    id: `def_ixl_g${grade}`,
    url: `https://www.ixl.com/math/grade-${grade}`,
    name: `IXL Learning (Math Grade ${grade})`,
    tag: "US Math",
    icon: "🎯",
    active: true,
    addedAt: timeNow
  });

  // 12. Khan Academy (Grade 1-12)
  defaults.push({
    id: `def_khan_g${grade}`,
    url: `https://www.khanacademy.org/math/${khanSlugs[grade] || "algebra"}`,
    name: `Khan Academy (Math Grade ${grade})`,
    tag: "Quốc tế",
    icon: "🌱",
    active: true,
    addedAt: timeNow
  });

  // 13. Olympic Kangaroo Math (IKMC)
  const ikmcLevel = grade <= 2 ? 'Ecolier 1-2' : grade <= 4 ? 'Ecolier 3-4' : grade <= 6 ? 'Benjamin 5-6' : grade <= 8 ? 'Cadet 7-8' : grade <= 10 ? 'Junior 9-10' : 'Student 11-12';
  defaults.push({
    id: `def_kangaroo_g${grade}`,
    url: `https://kangaroo-math.vn`,
    name: `Kangaroo Math IKMC (${ikmcLevel})`,
    tag: "Olympic",
    icon: "🦘",
    active: true,
    addedAt: timeNow
  });

  // 14. Olympic TIMO / CodeMath
  defaults.push({
    id: `def_timo_g${grade}`,
    url: `https://codemath.vn/khoa-hoc/timo`,
    name: `Olympic TIMO (Toán Tư duy Song ngữ Lớp ${grade})`,
    tag: "Olympic",
    icon: "🏅",
    active: true,
    addedAt: timeNow
  });

  // 15. Tiếng Anh 123 (Tiểu học 1-5)
  if (grade <= 5) {
    defaults.push({
      id: `def_tienganh123_g${grade}`,
      url: `https://www.tienganh123.com/lop-${grade}-moi.html`,
      name: `Tiếng Anh 123 (Lớp ${grade})`,
      tag: "Tiếng Anh",
      icon: "🎧",
      active: true,
      addedAt: timeNow
    });
  }

  return defaults;
}

function loadHunterTargetUrls(targetGrade) {
  const g = getHunterGradeValue(targetGrade);
  const key = getHunterStorageKey(targetGrade);
  try {
    const rawGrade = localStorage.getItem(key);
    if (rawGrade) {
      const parsed = JSON.parse(rawGrade);
      if (Array.isArray(parsed) && parsed.length > 0) {
        hunterTargetUrls = parsed;
      } else {
        hunterTargetUrls = getDefaultHunterUrlsForGrade(g);
        saveHunterTargetUrls(g, false);
      }
    } else {
      hunterTargetUrls = getDefaultHunterUrlsForGrade(g);
      saveHunterTargetUrls(g, false);
    }
  } catch (e) {
    hunterTargetUrls = getDefaultHunterUrlsForGrade(g);
  }
}

function saveHunterTargetUrls(targetGrade, shouldRender = true) {
  const g = getHunterGradeValue(targetGrade);
  const key = getHunterStorageKey(targetGrade);
  localStorage.setItem(key, JSON.stringify(hunterTargetUrls));
  localStorage.setItem("eduquest_hunter_urls", JSON.stringify(hunterTargetUrls));
  if (shouldRender) {
    renderHunterUrlsList();
  }
}

function addPresetHunterTarget(url, name, tag, icon) {
  if (!url) return;
  const existingIdx = hunterTargetUrls.findIndex(u => u.url.toLowerCase() === url.toLowerCase());
  if (existingIdx >= 0) {
    const existing = hunterTargetUrls[existingIdx];
    existing.active = true;
    if (name) existing.name = name;
    if (tag) existing.tag = tag;
    if (icon) existing.icon = icon;
    // Move to top so user clearly sees it
    hunterTargetUrls.splice(existingIdx, 1);
    hunterTargetUrls.unshift(existing);
    saveHunterTargetUrls();
    showToast(`✓ Đã đưa nguồn "${name || url}" lên đầu danh sách cào (đang bật)!`, "success");
    return;
  }
  const newEntry = {
    id: "url_" + Date.now() + "_" + Math.random().toString(36).substr(2, 4),
    url: url,
    name: name || "",
    tag: tag || "Gợi ý",
    icon: icon || "🌐",
    active: true,
    addedAt: getLogTimeVN()
  };
  hunterTargetUrls.unshift(newEntry);
  saveHunterTargetUrls();
  showToast(`✓ Đã thêm nguồn "${name || url}" vào danh sách cào!`, "success");
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

  // Support multiple items separated by comma, semicolon or newline
  const rawItems = val.split(/[\n,;]+/).map(s => s.trim()).filter(s => s.length > 0);
  if (rawItems.length === 0) return;

  let addedCount = 0;
  for (const item of rawItems) {
    let finalUrl = item;
    let tagName = "Tự nhập";
    let icon = "🌐";
    let itemName = "";

    // Normalize URL
    if (/^https?:\/\//i.test(finalUrl)) {
      // already full URL
    } else if (/^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(\/.*)?$/i.test(finalUrl)) {
      finalUrl = "https://" + finalUrl;
    } else {
      // Keyword search query
      finalUrl = "https://www.google.com/search?q=" + encodeURIComponent(finalUrl);
      tagName = "Từ khóa";
      icon = "🔍";
      itemName = item;
    }

    const existingIdx = hunterTargetUrls.findIndex(u => u.url.toLowerCase() === finalUrl.toLowerCase());
    if (existingIdx >= 0) {
      hunterTargetUrls[existingIdx].active = true;
      const moved = hunterTargetUrls.splice(existingIdx, 1)[0];
      hunterTargetUrls.unshift(moved);
      addedCount++;
    } else {
      const newEntry = {
        id: "url_" + Date.now() + "_" + Math.random().toString(36).substr(2, 4),
        url: finalUrl,
        name: itemName,
        tag: tagName,
        icon: icon,
        active: true,
        addedAt: getLogTimeVN()
      };
      hunterTargetUrls.unshift(newEntry);
      addedCount++;
    }
  }

  saveHunterTargetUrls();
  input.value = "";
  showToast(`✓ Đã thêm/kích hoạt ${addedCount} nguồn vào danh sách cào dữ liệu!`, "success");
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

function toggleAllHunterUrls(status) {
  if (hunterTargetUrls.length === 0) return;
  hunterTargetUrls.forEach(u => u.active = !!status);
  saveHunterTargetUrls();
  showToast(status ? "Đã bật tất cả nguồn cào" : "Đã tạm dừng tất cả nguồn cào", "info");
}

function resetHunterUrlsToDefault() {
  const g = getHunterGradeValue();
  hunterTargetUrls = getDefaultHunterUrlsForGrade(g);
  saveHunterTargetUrls(g);
  const label = g === "all" ? "Tất cả các khối (1-12)" : `Khối ${g}`;
  showToast(`Đã khôi phục danh sách web cào mặc định ${label}!`, "success");
}

function clearAllHunterTargetUrls() {
  if (hunterTargetUrls.length === 0) return;
  const g = getHunterGradeValue();
  const label = g === "all" ? "Tất cả các khối" : `Khối ${g}`;
  if (!confirm(`Bạn có chắc chắn muốn xóa toàn bộ các link web đã lưu trong ${label}?`)) return;
  hunterTargetUrls = [];
  saveHunterTargetUrls(g);
  showToast("Đã dọn sạch danh sách web cào.");
}

function renderHunterUrlsList() {
  const container = document.getElementById("hunter-urls-container");
  const countBadge = document.getElementById("hunter-urls-count");
  const activeBadge = document.getElementById("hunter-urls-active-count");
  const resetBadge = document.getElementById("hunter-reset-grade-badge");
  const clearBtn = document.getElementById("btn-clear-hunter-urls");
  const currentGrade = getHunterGradeValue();
  const gradeLabel = currentGrade === "all" ? "Tất cả các khối (1-12)" : `Khối ${currentGrade}`;

  const activeCount = hunterTargetUrls.filter(u => u.active).length;
  if (countBadge) countBadge.innerText = hunterTargetUrls.length;
  if (activeBadge) activeBadge.innerText = `(Đang bật cào: ${activeCount}/${hunterTargetUrls.length})`;
  if (resetBadge) resetBadge.innerText = currentGrade === "all" ? "Tất cả" : String(currentGrade);
  if (clearBtn) clearBtn.style.display = hunterTargetUrls.length > 0 ? "inline" : "none";
  if (!container) return;

  if (hunterTargetUrls.length === 0) {
    container.innerHTML = `
      <div style="font-size: 12px; color: #94a3b8; font-style: italic; padding: 14px 16px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 8px;">
        <span>Chưa có liên kết web nào trong ${gradeLabel}.</span>
        <button type="button" class="btn btn-secondary btn-sm" onclick="resetHunterUrlsToDefault()" style="font-size: 11px; padding: 4px 12px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; font-weight: 700; border-radius: 6px;">
          🔄 Nạp lại danh sách nguồn mặc định ${gradeLabel}
        </button>
      </div>
    `;
    return;
  }

  container.innerHTML = hunterTargetUrls.map(item => {
    let statusPill = `<span style="font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 600; background: #f1f5f9; color: #64748b; white-space: nowrap; flex-shrink: 0;" title="Nguồn chưa được chạy thử">⚪ Sẵn sàng</span>`;
    if (item.lastStatus === 'success') {
      statusPill = `<span style="font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 700; background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; white-space: nowrap; flex-shrink: 0;" title="Hoạt động tốt: Thu thập được ${item.lastYield || 0} câu hỏi (${item.lastChecked || ''})">🟢 ${item.lastCode || 200} (+${item.lastYield || 0} câu)</span>`;
    } else if (item.lastStatus === 'empty') {
      statusPill = `<span style="font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 700; background: #fef9c3; color: #a16207; border: 1px solid #fef08a; white-space: nowrap; flex-shrink: 0;" title="Kết nối 200 OK nhưng chưa tìm thấy câu hỏi hoặc đã có sẵn trong CSDL (${item.lastChecked || ''})">🟡 200 (0 câu mới)</span>`;
    } else if (item.lastStatus === 'error') {
      statusPill = `<span style="font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 700; background: #fee2e2; color: #b91c1c; border: 1px solid #fecdd3; white-space: nowrap; flex-shrink: 0;" title="Lỗi kết nối hoặc chặn bot (${item.lastCode || 500})">🔴 ${item.lastCode || 'Lỗi'}</span>`;
    }

    return `
      <div id="hunter-item-${item.id}" style="display: flex; align-items: center; justify-content: space-between; padding: 7px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;">
          <input type="checkbox" ${item.active ? 'checked' : ''} onchange="toggleHunterUrlActive('${item.id}')" title="${item.active ? 'Đang bật cào: Bỏ chọn để tạm dừng' : 'Đang tạm dừng: Tích chọn để cào'}" style="cursor: pointer; width: 15px; height: 15px; flex-shrink: 0;" />
          <span style="font-size: 14px; flex-shrink: 0;">${item.icon || '🌐'}</span>
          ${item.tag ? `<span style="font-size: 10.5px; background: #e0f2fe; color: #0369a1; padding: 1px 6px; border-radius: 8px; font-weight: 700; white-space: nowrap; flex-shrink: 0;">${item.tag}</span>` : ''}
          <span style="font-size: 12px; font-weight: 600; color: ${item.active ? '#1e293b' : '#94a3b8'}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.name ? item.name + ' - ' + item.url : item.url}">
            ${item.name ? `<strong style="color: ${item.active ? '#0f172a' : '#94a3b8'}; margin-right: 4px;">${item.name}:</strong>` : ''}<span style="font-family: monospace; font-size: 11.5px; color: ${item.active ? '#0284c7' : '#94a3b8'}; text-decoration: ${item.active ? 'none' : 'line-through'}; font-weight: 400;">${item.url}</span>
          </span>
          ${statusPill}
          <span style="font-size: 10.5px; color: #94a3b8; margin-left: 4px; white-space: nowrap; flex-shrink: 0;">[${item.addedAt || 'Mặc định'}]</span>
        </div>
        <div style="display: flex; align-items: center; gap: 4px; flex-shrink: 0;">
          <button type="button" class="btn btn-secondary btn-sm" id="btn-test-${item.id}" onclick="testSingleHunterSource('${item.id}', '${item.url}')" title="Kiểm tra trực tiếp kết nối và bóc tách câu hỏi từ nguồn này" style="font-size: 10.5px; padding: 2px 7px; background: #fff; border: 1px solid #cbd5e1; color: #0f172a; border-radius: 4px; font-weight: 600; white-space: nowrap;">
            ⚡ Thử nguồn
          </button>
          <a href="${item.url}" target="_blank" rel="noopener noreferrer" style="color: #64748b; font-size: 12px; text-decoration: none; padding: 2px 5px; border-radius: 4px;" title="Mở trang web trong tab mới" onmouseover="this.style.background='#e2e8f0'" onmouseout="this.style.background='none'">
            🔗
          </a>
          <button type="button" onclick="removeHunterTargetUrl('${item.id}')" style="background: none; border: none; color: #94a3b8; font-size: 14px; cursor: pointer; padding: 2px 6px; border-radius: 4px; line-height: 1;" title="Xóa link này" onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='#94a3b8'">
            ✕
          </button>
        </div>
      </div>
    `;
  }).join("");
}

// Single-source isolated test-crawling with real-time telemetry
async function testSingleHunterSource(id, url) {
  const btn = document.getElementById(`btn-test-${id}`);
  const logBox = document.getElementById("hunter-live-log");
  const toolbar = document.getElementById("hunter-log-toolbar");
  const gradeVal = document.getElementById("hunter-grade")?.value || "2";
  const subject = document.getElementById("hunter-subject")?.value || "math";
  const g = gradeVal === "all" ? 2 : (parseInt(gradeVal) || 2);

  if (logBox) logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `⏳ Đang thử...`;
  }

  const timeNow = getLogTimeVN();
  const testStartLine = `[${timeNow}] 🔍 [KIỂM TRA NGUỒN ĐỘC LẬP] Đang kết nối tới: ${url} (Khối ${g}, Môn ${subject.toUpperCase()})...`;
  if (logBox) {
    const cur = (logBox.textContent || "").trim();
    logBox.textContent = cur ? testStartLine + "\n\n" + cur : testStartLine;
    localStorage.setItem("eduquest_hunter_log", logBox.textContent);
  }

  try {
    const res = await apiFetch(`/api/hunter/test-source`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, grade: g, subject: subject })
    });
    const data = await res.json();
    const finishTime = getLogTimeVN();

    const targetItem = hunterTargetUrls.find(u => u.id === id);
    if (targetItem) {
      targetItem.lastStatus = data.status || (data.success ? "success" : "error");
      targetItem.lastCode = data.status_code || 200;
      targetItem.lastYield = data.questions_found || 0;
      targetItem.lastChecked = finishTime;
      saveHunterTargetUrls(undefined, true);
    }

    let reportLine = `[${finishTime}] ${data.success && data.questions_found > 0 ? '✅' : (data.success ? '🟡' : '❌')} KẾT QUẢ KIỂM TRA NGUỒN: ${url}\n`;
    reportLine += `   • Trạng thái HTTP: ${data.status_code || 200} (${data.status || 'chưa rõ'})\n`;
    reportLine += `   • Độ trễ máy chủ: ${data.latency_ms || 0}ms\n`;
    reportLine += `   • Số câu hỏi bóc tách: ${data.questions_found || 0} câu\n`;
    if (data.sample && data.sample.content_text) {
      reportLine += `   • Mẫu câu hỏi: "${data.sample.content_text}..."\n`;
    }
    reportLine += `   • Đánh giá & Hướng dẫn: ${data.advice || data.message || ''}`;

    if (logBox) {
      logBox.textContent = reportLine + "\n\n" + (logBox.textContent || "");
      localStorage.setItem("eduquest_hunter_log", logBox.textContent);
    }

    if (data.success && data.questions_found > 0) {
      showToast(`✓ Nguồn hoạt động rất tốt! Thu được ${data.questions_found} câu hỏi (${data.latency_ms}ms)`, "success");
    } else if (data.success) {
      showToast(`ℹ️ Kết nối 200 OK (${data.latency_ms}ms) nhưng chưa tìm thấy câu hỏi`, "warning");
    } else {
      showToast(`❌ Lỗi kiểm tra nguồn: ${data.error || "Không thể kết nối"}`, "error");
    }
  } catch (err) {
    const errTime = getLogTimeVN();
    const errReport = `[${errTime}] ❌ Lỗi kết nối kiểm tra nguồn: ${err.message}`;
    if (logBox) {
      logBox.textContent = errReport + "\n\n" + (logBox.textContent || "");
      localStorage.setItem("eduquest_hunter_log", logBox.textContent);
    }
    showToast(`Lỗi kiểm tra nguồn: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `⚡ Thử nguồn`;
    }
  }
}
window.testSingleHunterSource = testSingleHunterSource;

// Check live VioEdu credentials & session validity
async function checkVioEduSessionLive() {
  const username = document.getElementById("scraper-username")?.value.trim();
  const password = document.getElementById("scraper-password")?.value.trim();
  const statusEl = document.getElementById("vioedu-hub-status");
  const statusText = document.getElementById("vioedu-hub-status-text");
  const logBox = document.getElementById("scraper-live-log");
  const toolbar = document.getElementById("scraper-log-toolbar");
  const btn = document.getElementById("btn-vioedu-check-session");

  if (statusEl) statusEl.style.display = "block";
  if (logBox) logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `⏳ Đang kiểm tra...`;
  }

  const timeNow = getLogTimeVN();
  const checkLog = `[${timeNow}] 🔍 [KIỂM TRA TÀI KHOẢN VIOEDU] Đang kết nối tới máy chủ VioEdu để xác thực phiên...`;
  scraperLogLines.unshift(checkLog);
  renderScraperLog();

  try {
    const res = await apiFetch(`/api/collect/check-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: "vioedu", username: username, password: password })
    });
    const data = await res.json();
    const finishTime = getLogTimeVN();

    if (data.success && (data.logged_in || data.student_name)) {
      const who = data.student_name || username;
      const gr = data.grade ? ` (Khối ${data.grade})` : '';
      const okMsg = `[${finishTime}] ✅ Xác thực VioEdu THÀNH CÔNG! Tài khoản học sinh: ${who}${gr} hợp lệ và sẵn sàng cào.`;
      scraperLogLines.unshift(okMsg);
      renderScraperLog();
      if (statusText) {
        statusText.innerHTML = `🟢 <strong>Tài khoản VioEdu hợp lệ:</strong> ${who}${gr} — sẵn sàng cho bot cào và scheduler 24/7.`;
        statusText.style.color = "#15803d";
      }
      showToast(`Tài khoản VioEdu "${who}" hợp lệ và sẵn sàng cào!`, "success");
    } else {
      const errMsg = `[${finishTime}] ⚠️ Kiểm tra VioEdu: ${data.message || data.error || "Tài khoản hoặc mật khẩu không chính xác."}`;
      scraperLogLines.unshift(errMsg);
      renderScraperLog();
      if (statusText) {
        statusText.innerHTML = `🔴 <strong>Chưa hợp lệ:</strong> ${data.message || data.error || "Vui lòng nhập chính xác username & password."}`;
        statusText.style.color = "#dc2626";
      }
      showToast(data.message || data.error || "Chưa thể xác thực tài khoản VioEdu", "error");
    }
  } catch (err) {
    const errTime = getLogTimeVN();
    const exc = `[${errTime}] ❌ Lỗi kết nối máy chủ kiểm tra: ${err.message}`;
    scraperLogLines.unshift(exc);
    renderScraperLog();
    showToast("Lỗi kiểm tra tài khoản: " + err.message, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `🔍 Kiểm tra tài khoản`;
    }
  }
}
window.checkVioEduSessionLive = checkVioEduSessionLive;

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
  const rawText = logBox ? (logBox.textContent || "") : (localStorage.getItem("eduquest_hunter_log") || "");
  const text = unSquishLogLines(rawText.trim());
  if (!text) {
    showToast("Chưa có nội dung nhật ký để sao chép", "error");
    return;
  }
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
    logBox.textContent = "";
    logBox.style.display = "none";
  }
  if (toolbar) toolbar.style.display = "none";
  localStorage.removeItem("eduquest_hunter_log");
  showToast("Đã xóa sạch màn hình nhật ký Săn câu hỏi", "info");
}

// Internet Question Hunter Runner (Newest on Top & Clean Line Separation)
async function runInternetHunter(isAuto = false) {
  const subject = document.getElementById("hunter-subject")?.value || "all";
  const gradeVal = document.getElementById("hunter-grade")?.value || "5";
  const isAllGrades = gradeVal === "all";
  const grade = isAllGrades ? "all" : (parseInt(gradeVal) || 5);
  const activeCustomUrls = hunterTargetUrls.filter(u => u.active).map(u => u.url);
  const logBox = document.getElementById("hunter-live-log");
  const toolbar = document.getElementById("hunter-log-toolbar");
  const btn = document.getElementById("btn-run-hunter");

  if (logBox) logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";
  isManualHunterActive = true;
  if (!isAuto && btn) {
    btn.disabled = true;
    btn.innerText = isAllGrades ? "⏳ Đang cào tuần tự Khối 1-12..." : "⏳ Đang quét internet...";
  }

  const timeNow = getLogTimeVN();

  if (isAllGrades) {
    // -------------------------------------------------------------------------
    // CÀO TUẦN TỰ TỪ KHỐI 1 ĐẾN KHỐI 12
    // -------------------------------------------------------------------------
    const runHeader = `[${timeNow}] ${isAuto ? "🔄 [TỰ ĐỘNG ĐỊNH KỲ]" : "⚡ [THỦ CÔNG]"} 🌟 BẮT ĐẦU SĂN CÂU HỎI TUẦN TỰ TỪ KHỐI 1 ĐẾN KHỐI 12 (Môn: ${subject.toUpperCase()})...`;
    const targetsLine = `-> Mục tiêu: Quét tuần tự lần lượt 12 khối lớp theo chuẩn GDPT 2018 & Quốc tế...`;
    const newRunText = `${runHeader}\n${targetsLine}`;

    const previousText = logBox ? (logBox.textContent || "").trim() : "";
    if (logBox) {
      logBox.textContent = previousText ? newRunText + "\n\n" + previousText : newRunText;
      localStorage.setItem("eduquest_hunter_log", logBox.textContent);
    }

    let totalNewSaved = 0;
    let totalDupes = 0;
    let allScrapedSources = [];

    try {
      for (let g = 1; g <= 12; g++) {
        const gradeTime = getLogTimeVN();
        let urlsForGrade = [];
        const gradeKey = `eduquest_hunter_urls_g${g}`;
        const rawGradeUrls = localStorage.getItem(gradeKey);
        if (rawGradeUrls) {
          try {
            const parsed = JSON.parse(rawGradeUrls);
            urlsForGrade = parsed.filter(u => u.active).map(u => u.url);
          } catch (e) {}
        }
        if (urlsForGrade.length === 0) {
          urlsForGrade = activeCustomUrls.slice();
        }

        const gradeStartLine = `[${gradeTime}] ⏳ [Khối ${g}/12] Đang cào dữ liệu cho Khối lớp ${g}...`;
        if (logBox) {
          logBox.textContent = gradeStartLine + "\n" + (logBox.textContent || "");
          localStorage.setItem("eduquest_hunter_log", logBox.textContent);
        }

        try {
          const res = await apiFetch(`/api/hunter/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              subject: subject,
              grade: g,
              custom_urls: urlsForGrade
            })
          });
          const data = await res.json();
          const gFinishTime = getLogTimeVN();
          if (data.success) {
            const newSaved = data.new_saved !== undefined ? data.new_saved : (data.total_harvested || 0);
            const dupes = data.skipped_duplicates || 0;
            totalNewSaved += newSaved;
            totalDupes += dupes;
            if (Array.isArray(data.sources_scraped)) {
              data.sources_scraped.forEach(s => {
                if (!allScrapedSources.includes(s)) allScrapedSources.push(s);
              });
            }
            const gDoneLine = `[${gFinishTime}] ✅ [Khối ${g}/12] Khối ${g}: Đã lưu +${newSaved} câu mới (${dupes} trùng lặp).`;
            if (logBox) {
              logBox.textContent = logBox.textContent.replace(gradeStartLine, gDoneLine);
              localStorage.setItem("eduquest_hunter_log", logBox.textContent);
            }
          } else {
            const gErrLine = `[${gFinishTime}] ⚠️ [Khối ${g}/12] Khối ${g}: ${data.error || "Không tìm thấy dữ liệu mới."}`;
            if (logBox) {
              logBox.textContent = logBox.textContent.replace(gradeStartLine, gErrLine);
              localStorage.setItem("eduquest_hunter_log", logBox.textContent);
            }
          }
        } catch (gErr) {
          const gErrTime = getLogTimeVN();
          const gFailLine = `[${gErrTime}] ❌ [Khối ${g}/12] Lỗi kết nối Khối ${g}: ${gErr.message}`;
          if (logBox) {
            logBox.textContent = logBox.textContent.replace(gradeStartLine, gFailLine);
            localStorage.setItem("eduquest_hunter_log", logBox.textContent);
          }
        }

        loadDashboardStats();
        await new Promise(r => setTimeout(r, 300));
      }

      const finishAllTime = getLogTimeVN();
      let summaryLine = `[${finishAllTime}] 🏁 HOÀN TẤT CÀO TUẦN TỰ 12 KHỐI LỚP (Khối 1 -> 12)!\n   🎉 TỔNG KẾT: Đã lưu thành công ${totalNewSaved} câu hỏi MỚI vào CSDL (Bỏ qua ${totalDupes} câu trùng).`;
      if (allScrapedSources.length > 0) {
        summaryLine += `\n   🌐 Nguồn đã rà soát: ${allScrapedSources.slice(0, 4).join(', ')}${allScrapedSources.length > 4 ? '...' : ''}`;
      }
      if (logBox) {
        logBox.textContent = summaryLine + "\n" + (logBox.textContent || "");
        localStorage.setItem("eduquest_hunter_log", logBox.textContent);
      }
      showToast(`🎉 Hoàn tất cào tuần tự 12 khối lớp! Đã lưu ${totalNewSaved} câu mới.`, "success");
      if (typeof broadcastNewQuestions === "function" && totalNewSaved > 0) {
        broadcastNewQuestions(totalNewSaved, "Săn tuần tự 12 Khối");
      }
      loadCollectorLogs();
      if (State.currentView === "bank") loadQuestions();
    } catch (allErr) {
      const finishTime = getLogTimeVN();
      const errLine = `[${finishTime}] Lỗi cào tuần tự: ${allErr.message}`;
      if (logBox) {
        logBox.textContent = errLine + "\n" + (logBox.textContent || "");
        localStorage.setItem("eduquest_hunter_log", logBox.textContent);
      }
      if (!isAuto) showToast("Lỗi khi cào tuần tự các khối", "error");
    } finally {
      isManualHunterActive = false;
      if (!isAuto && btn) {
        btn.disabled = false;
        btn.innerText = "⚡ Bắt đầu Săn câu hỏi từ Internet";
      }
    }
    return;
  }

  const gradeLabel = `Khối ${grade}`;
  const runHeader = `[${timeNow}] ${isAuto ? "🔄 [TỰ ĐỘNG ĐỊNH KỲ]" : "⚡ [THỦ CÔNG]"} Săn câu hỏi Internet [Môn: ${subject.toUpperCase()}, ${gradeLabel}]...`;
  const inProgressLine = `⏳ Đang kết nối ${activeCustomUrls.length > 0 ? activeCustomUrls.length + ' nguồn tùy chọn' : 'các nguồn mở uy tín theo chuẩn Bộ GD&ĐT'}...`;
  const startLog = `${runHeader}\n${inProgressLine}`;
  if (logBox) {
    const cur = (logBox.textContent || "").trim();
    logBox.textContent = cur ? startLog + "\n\n" + cur : startLog;
    localStorage.setItem("eduquest_hunter_log", logBox.textContent);
  }

  try {
    const res = await apiFetch(`/api/hunter/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: subject,
        grade: grade,
        custom_urls: activeCustomUrls
      })
    });

    const data = await res.json();
    const finishTime = getLogTimeVN();

    if (data.success) {
      const newSaved = data.new_saved !== undefined ? data.new_saved : data.total_harvested;
      const dupes = data.skipped_duplicates || 0;
      let finishLine = `[${finishTime}] ✅ Săn Internet thành công: Đã lưu ${newSaved} câu hỏi MỚI vào CSDL.`;
      if (dupes > 0) {
        finishLine += ` (Đã bỏ qua ${dupes} câu trùng lặp trong CSDL)`;
      }
      if (data.sources_scraped && data.sources_scraped.length > 0) {
        finishLine += `\n   🌐 Nguồn đã rà soát: ${data.sources_scraped.slice(0, 3).join(', ')}${data.sources_scraped.length > 3 ? '...' : ''}`;
      }
      if (Array.isArray(data.sources_report) && data.sources_report.length > 0) {
        data.sources_report.forEach(rep => {
          const item = hunterTargetUrls.find(u => u.url.toLowerCase() === rep.url.toLowerCase());
          if (item) {
            item.lastStatus = rep.status;
            item.lastCode = rep.status_code;
            item.lastYield = rep.questions_found;
            item.lastChecked = finishTime;
          }
        });
        saveHunterTargetUrls(undefined, true);
      }
      if (logBox) {
        if (logBox.textContent.includes(inProgressLine)) {
          logBox.textContent = logBox.textContent.replace(inProgressLine, finishLine);
        } else {
          const cur = (logBox.textContent || "").trim();
          logBox.textContent = cur ? finishLine + "\n" + cur : finishLine;
        }
        localStorage.setItem("eduquest_hunter_log", logBox.textContent);
      }
      showToast(`Đã săn thành công ${newSaved} câu hỏi mới từ Internet!`, "success");
      if (typeof broadcastNewQuestions === "function" && newSaved > 0) {
        broadcastNewQuestions(newSaved, "Săn Internet");
      }
      loadDashboardStats();
      loadCollectorLogs();
      if (State.currentView === "bank") loadQuestions();
    } else {
      const errorLine = `[${finishTime}] Thông báo: ${data.error || "Không tìm thấy dữ liệu mới."}`;
      if (logBox) {
        if (logBox.textContent.includes(inProgressLine)) {
          logBox.textContent = logBox.textContent.replace(inProgressLine, errorLine);
        } else {
          const cur = (logBox.textContent || "").trim();
          logBox.textContent = cur ? errorLine + "\n" + cur : errorLine;
        }
        localStorage.setItem("eduquest_hunter_log", logBox.textContent);
      }
    }
  } catch (err) {
    const finishTime = getLogTimeVN();
    const errorLine = `[${finishTime}] Lỗi kết nối: ${err.message}`;
    if (logBox) {
      if (logBox.textContent.includes(inProgressLine)) {
        logBox.textContent = logBox.textContent.replace(inProgressLine, errorLine);
      } else {
        const cur = (logBox.textContent || "").trim();
        logBox.textContent = cur ? errorLine + "\n" + cur : errorLine;
      }
      localStorage.setItem("eduquest_hunter_log", logBox.textContent);
    }
    if (!isAuto) showToast("Lỗi khi săn câu hỏi Internet", "error");
  } finally {
    isManualHunterActive = false;
    if (!isAuto && btn) {
      btn.disabled = false;
      btn.innerText = "⚡ Bắt đầu Săn câu hỏi từ Internet";
    }
  }
}

// Dynamic Preset Generator for Grades 1 to 12
function updateGradePresetsUI(gradeVal) {
  const isAll = gradeVal === "all";
  const grade = isAll ? "all" : Math.max(1, Math.min(12, parseInt(gradeVal) || 5));
  const container = document.getElementById("hunter-grade-presets-container");

  // 1. Update Harvest Button label badge
  const btnLabel = document.getElementById("harvest-grade-btn-label");
  if (btnLabel) btnLabel.innerText = isAll ? "1-12" : String(grade);
  const quickBtn = document.getElementById("btn-harvest-grade-quick") || document.getElementById("btn-harvest-grade2");
  if (quickBtn) {
    quickBtn.title = isAll
      ? "Nạp nhanh bộ câu hỏi Toán cho Tất cả các khối (Khối 1 đến 12)"
      : `Nạp nhanh bộ câu hỏi Toán Khối ${grade} (Tiếng Việt, Tiếng Anh & Olympic)`;
  }

  if (!container) return;

  if (isAll) {
    container.innerHTML = `
      <!-- Category 1: Nguồn GDPT Toàn diện (Khối 1 - 12) -->
      <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
        <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🇻🇳 GDPT Việt Nam (1 - 12):</span>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://hanhtrangso.nxbgd.vn/sach-dien-tu', 'Hành trang số SGK 1-12', 'Toán GDPT', '📘')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;">
          📘 Hành trang số (SGK 1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://loigiaihay.com/', 'Lời Giải Hay (1-12)', 'Toán, Văn, Anh', '📐')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fdf4ff; color: #a21caf; border: 1px solid #f5d0fe;">
          📐 Lời Giải Hay (1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://olm.vn/', 'OLM.vn (K-12)', 'Tương tác', '🎓')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fdf2f8; color: #9d174d; border: 1px solid #fbcfe8;">
          🎓 OLM.vn (1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://vietjack.com/', 'VietJack (Đề thi 1-12)', 'Trắc nghiệm', '📚')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fafaf9; color: #44403c; border: 1px solid #e7e5e4;">
          📚 VietJack (1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://thcs.toanmath.com/', 'THCS TOANMATH (6-9)', 'Toán THCS', '📐')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;">
          📐 THCS TOANMATH (6-9)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://toanmath.com/', 'TOANMATH (10-12)', 'Toán THPT', '📐')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;">
          📐 TOANMATH (10-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://tech12h.com/', 'Tech12h (Trắc nghiệm SGK)', 'Trắc nghiệm', '📑')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f8fafc; color: #0284c7; border: 1px solid #bae6fd;">
          📑 Tech12h (1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://vio.edu.vn/skill-list', 'VioEdu (1-9)', 'VioEdu', '⚡')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0;">
          ⚡ VioEdu (1-9)
        </button>
      </div>

      <!-- Category 2: US Math & Tiếng Anh (K-12) -->
      <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
        <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🇬🇧 US Math & Anh (K-12):</span>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.k5learning.com/free-math-worksheets', 'K5 Learning Worksheets', 'US Math', '📑')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fefce8; color: #a16207; border: 1px solid #fef08a;">
          📑 K5 Learning (K-6)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.ixl.com/math', 'IXL Math K-12', 'US Math', '🎯')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;">
          🎯 IXL Math (1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.khanacademy.org/math', 'Khan Academy Math', 'Quốc tế', '🌱')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0;">
          🌱 Khan Academy (1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://ioe.vn/', 'IOE Olympic Tiếng Anh', 'Olympic', '🎧')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa;">
          🎧 IOE Tiếng Anh (1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.tienganh123.com/', 'Tiếng Anh 123', 'Tiếng Anh', '🇬🇧')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;">
          🇬🇧 Tiếng Anh 123
        </button>
      </div>

      <!-- Category 3: Olympic Song ngữ (1 - 12) -->
      <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
        <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🏆 Olympic Song ngữ:</span>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://kangaroo-math.vn', 'Olympic Kangaroo IKMC', 'Olympic', '🦘')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa;">
          🦘 Kangaroo Math IKMC (1-12)
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://codemath.vn/khoa-hoc/timo', 'Olympic TIMO Song ngữ', 'Olympic', '🏅')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fef3c7; color: #b45309; border: 1px solid #fde68a;">
          🏅 TIMO & ASMO Song ngữ
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.mathplayground.com/', 'Math Playground Game', 'Tương tác', '🎮')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f5f3ff; color: #6d28d9; border: 1px solid #ddd6fe;">
          🎮 Math Playground
        </button>
      </div>

      <!-- Actions: Thêm toàn bộ nguồn vào danh sách cào -->
      <div style="display: flex; justify-content: flex-end; margin-top: 4px;">
        <button type="button" class="btn btn-secondary btn-sm" onclick="addAllGradePresetsToHunter()" style="font-size: 11px; padding: 4px 10px; border-radius: 6px; background: #e0e7ff; color: #4338ca; border: 1px solid #c7d2fe; font-weight: 700; display: inline-flex; align-items: center; gap: 4px;">
          ✨ Thêm tất cả gợi ý Toàn diện vào Danh sách cào
        </button>
      </div>
    `;
    return;
  }

  const lghMathSlugs = {
    1: "de-thi-de-kiem-tra-toan-lop-1-ket-noi-tri-thuc-c1211.html",
    2: "de-thi-de-kiem-tra-toan-lop-2-ket-noi-tri-thuc-c1212.html",
    3: "de-thi-de-kiem-tra-toan-lop-3-ket-noi-tri-thuc-c1215.html",
    4: "de-thi-de-kiem-tra-toan-lop-4-ket-noi-tri-thuc-c1636.html",
    5: "de-thi-de-kiem-tra-toan-lop-5-ket-noi-tri-thuc-c1990.html",
    6: "de-thi-de-kiem-tra-toan-lop-6-ket-noi-tri-thuc-c1022.html",
    7: "de-thi-de-kiem-tra-toan-lop-7-ket-noi-tri-thuc-c1097.html",
    8: "de-thi-de-kiem-tra-toan-lop-8-ket-noi-tri-thuc-c1612.html",
    9: "de-thi-de-kiem-tra-toan-lop-9-ket-noi-tri-thuc-c1984.html",
    10: "v2/tu-luyen-trac-nghiem-toan-10-ket-noi-tri-thuc-c980.html",
    11: "de-thi-de-kiem-tra-toan-lop-11-ket-noi-tri-thuc-c1623.html",
    12: "de-thi-de-kiem-tra-toan-lop-12-ket-noi-tri-thuc-c1964.html"
  };

  const vietjackExamUrls = {
    1: "https://vietjack.com/de-kiem-tra-lop-1/de-kiem-tra-toan-lop-1.jsp",
    2: "https://vietjack.com/de-kiem-tra-lop-2/de-kiem-tra-toan-lop-2.jsp",
    3: "https://vietjack.com/de-kiem-tra-lop-3/de-kiem-tra-toan-lop-3.jsp",
    4: "https://vietjack.com/de-kiem-tra-toan-lop-4/index.jsp",
    5: "https://vietjack.com/de-kiem-tra-toan-5/index.jsp",
    6: "https://vietjack.com/de-kiem-tra-lop-6/de-kiem-tra-toan-6.jsp",
    7: "https://vietjack.com/de-kiem-tra-lop-7/de-kiem-tra-toan-7.jsp",
    8: "https://vietjack.com/de-kiem-tra-lop-8/de-kiem-tra-toan-8.jsp",
    9: "https://vietjack.com/de-kiem-tra-lop-9/de-kiem-tra-toan-9.jsp",
    10: "https://vietjack.com/de-kiem-tra-lop-10/de-kiem-tra-toan-10.jsp",
    11: "https://vietjack.com/de-kiem-tra-lop-11/de-kiem-tra-toan-11.jsp",
    12: "https://vietjack.com/de-kiem-tra-lop-12/de-kiem-tra-toan-12.jsp"
  };

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
  const khanUrl = `https://www.khanacademy.org/math/${khanSlugs[grade] || "algebra"}`;

  const lghMathUrl = lghMathSlugs[grade] ? `https://loigiaihay.com/${lghMathSlugs[grade]}` : "";
  const vjUrl = vietjackExamUrls[grade] || "";
  const toanmathUrl = grade >= 10 ? "https://toanmath.com/" : (grade >= 6 ? "https://thcs.toanmath.com/" : "");

  container.innerHTML = `
    <!-- Category 1: Toán Tiếng Việt Khối ${grade} -->
    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
      <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🇻🇳 Toán ${grade} Tiếng Việt:</span>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://hanhtrangso.nxbgd.vn/sach-dien-tu?book_active=0&classes=${grade}', 'Hành trang số SGK ${grade}', 'Toán GDPT', '📘')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;">
        📘 Hành trang số (SGK Toán ${grade})
      </button>
      ${lghMathUrl ? `
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('${lghMathUrl}', 'Lời Giải Hay Toán ${grade}', 'Toán', '📐')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fdf4ff; color: #a21caf; border: 1px solid #f5d0fe;">
        📐 Lời Giải Hay (Toán ${grade})
      </button>` : ''}
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://olm.vn/lop-${grade}', 'OLM.vn Lớp ${grade}', 'Tương tác', '🎓')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fdf2f8; color: #9d174d; border: 1px solid #fbcfe8;">
        🎓 OLM.vn Lớp ${grade}
      </button>
      ${vjUrl ? `
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('${vjUrl}', 'VietJack Đề thi Toán ${grade}', 'Toán', '📚')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fafaf9; color: #44403c; border: 1px solid #e7e5e4;">
        📚 VietJack Toán ${grade}
      </button>` : ''}
      ${toanmathUrl ? `
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('${toanmathUrl}', 'TOANMATH Lớp ${grade}', 'Toán ${grade >= 10 ? 'THPT' : 'THCS'}', '📐')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;">
        📐 TOANMATH Lớp ${grade}
      </button>` : ''}
      ${grade <= 9 ? `
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://vio.edu.vn/skill-list', 'VioEdu Luyện tập ${grade}', 'VioEdu', '⚡')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0;">
        ⚡ VioEdu Luyện tập
      </button>` : ''}
      ${grade <= 5 ? `
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://tnmath.edu.vn/', 'Trạng Nguyên Toán ${grade}', 'Trạng Nguyên', '👑')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fff1f2; color: #be123c; border: 1px solid #fecdd3;">
        👑 Trạng Nguyên Toán
      </button>` : ''}
    </div>

    <!-- Category 2: Math Grade ${grade} English -->
    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
      <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🇬🇧 Math Grade ${grade} (Anh):</span>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('${k5Url}', 'K5 Learning Worksheets', 'US Math', '📑')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fefce8; color: #a16207; border: 1px solid #fef08a;">
        📑 K5 Learning Worksheets
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.ixl.com/math/grade-${grade}', 'IXL Math Grade ${grade}', 'US Math', '🎯')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;">
        🎯 IXL Math Skills
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('${khanUrl}', 'Khan Academy Math', 'Quốc tế', '🌱')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0;">
        🌱 Khan Academy Math
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://www.commoncoresheets.com', 'Common Core Math Sheets', 'US Math', '📋')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #f8fafc; color: #334155; border: 1px solid #cbd5e1;">
        📋 Common Core Math
      </button>
    </div>

    <!-- Category 3: Olympic Song ngữ Khối ${grade} -->
    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
      <span style="font-size: 11.5px; color: #1e293b; font-weight: 700; min-width: 140px;">🏆 Olympic Khối ${grade}:</span>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://kangaroo-math.vn', 'Olympic Kangaroo IKMC', 'Olympic', '🦘')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa;">
        🦘 Kangaroo Math (IKMC Khối ${grade <= 2 ? '1-2' : grade <= 4 ? '3-4' : grade <= 6 ? '5-6' : grade <= 8 ? '7-8' : '9-12'})
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://codemath.vn/khoa-hoc/timo', 'Olympic TIMO Song ngữ', 'Olympic', '🏅')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fef3c7; color: #b45309; border: 1px solid #fde68a;">
        🏅 TIMO Khối ${grade} Song ngữ
      </button>
      <button type="button" class="btn btn-secondary btn-sm" onclick="addPresetHunterTarget('https://codemath.vn/khoa-hoc/sasmo', 'Olympic SASMO Singapore Math', 'Olympic', '🥇')" style="font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #fef3c7; color: #b45309; border: 1px solid #fde68a;">
        🥇 SASMO Singapore Math
      </button>
    </div>

    <!-- Actions: Thêm toàn bộ nguồn vào danh sách cào -->
    <div style="display: flex; justify-content: flex-end; margin-top: 4px;">
      <button type="button" class="btn btn-secondary btn-sm" onclick="addAllGradePresetsToHunter()" style="font-size: 11px; padding: 4px 10px; border-radius: 6px; background: #e0e7ff; color: #4338ca; border: 1px solid #c7d2fe; font-weight: 700; display: inline-flex; align-items: center; gap: 4px;">
        ✨ Thêm tất cả gợi ý Khối ${grade} vào Danh sách cào
      </button>
    </div>
  `;
}

function addAllGradePresetsToHunter() {
  const g = getHunterGradeValue();
  const defaultItems = getDefaultHunterUrlsForGrade(g);
  let addedCount = 0;
  for (const item of defaultItems) {
    if (!hunterTargetUrls.some(existing => existing.url.toLowerCase() === item.url.toLowerCase())) {
      hunterTargetUrls.unshift({
        ...item,
        id: "url_" + Date.now() + "_" + Math.random().toString(36).substr(2, 4),
        active: true,
        addedAt: getLogTimeVN()
      });
      addedCount++;
    }
  }
  saveHunterTargetUrls(g);
  const label = g === "all" ? "Tất cả các khối (1-12)" : `Khối ${g}`;
  if (addedCount > 0) {
    showToast(`Đã thêm ${addedCount} nguồn mở ${label} vào danh sách cào!`, "success");
  } else {
    showToast(`Tất cả nguồn ${label} đã có sẵn trong danh sách cào!`, "info");
  }
}

function openFacebookGroup(url) {
  window.open(url, "_blank");
  showToast("Đang mở Facebook! Tiện ích EduQuest Extension sẽ tự động bắt câu hỏi khi bạn lướt bài viết.", "info");
}

// Quick 1-Click Multi-Source Harvester for Any Grade Math (English + Vietnamese + Olympic)
async function harvestCurrentGradeMathQuick() {
  const g = getHunterGradeValue();
  const isAll = g === "all";
  const btn = document.getElementById("btn-harvest-grade-quick") || document.getElementById("btn-harvest-grade2");
  const logBox = document.getElementById("hunter-live-log");
  const toolbar = document.getElementById("hunter-log-toolbar");

  if (logBox) logBox.style.display = "block";
  if (toolbar) toolbar.style.display = "flex";
  if (btn) {
    btn.disabled = true;
    btn.innerText = isAll ? "⏳ Đang nạp đề Toán tuần tự Khối 1-12..." : `⏳ Đang nạp đề Toán Khối ${g}...`;
  }

  const timeNow = getLogTimeVN();
  const runHeader = isAll
    ? `[${timeNow}] 🌟 [NẠP NHANH TOÁN 1-12] Cào tuần tự từ Khối 1 đến Khối 12 qua đa nguồn Tiếng Việt (VioEdu, Trạng Nguyên, OLM, VnDoc, SGK Hành Trang Số) & Tiếng Anh (K5 Learning, IXL, Khan Academy, Olympic Kangaroo, TIMO, SASMO)...`
    : `[${timeNow}] 🌟 [NẠP NHANH TOÁN KHỐI ${g}] Quét đa nguồn Tiếng Việt (VioEdu, Trạng Nguyên, OLM, VnDoc, SGK Hành Trang Số) & Tiếng Anh (K5 Learning, IXL, Khan Academy, Olympic Kangaroo, TIMO, SASMO)...`;
  const inProgressLine = isAll
    ? `⏳ Đang kết nối và thu thập đề Toán lần lượt từ Khối 1 đến Khối 12...`
    : `⏳ Đang kết nối các kho học liệu Toán Khối ${g}...`;

  const newRunText = `${runHeader}\n${inProgressLine}`;
  const previousText = logBox ? (logBox.textContent || "").trim() : "";
  if (logBox) {
    logBox.textContent = previousText ? newRunText + "\n\n" + previousText : newRunText;
    localStorage.setItem("eduquest_hunter_log", logBox.textContent);
  }

  try {
    const res = await apiFetch(`/api/hunter/harvest-by-grade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grade: g, subject: "math" })
    });
    const data = await res.json();
    const finishTime = getLogTimeVN();

    if (data.success) {
      const savedCount = (typeof data.new_saved === "number") ? data.new_saved : data.total_harvested;
      const skipInfo = (typeof data.skipped_interactive === "number" && data.skipped_interactive > 0)
        ? ` (bỏ qua ${data.skipped_interactive} nguồn mở-tay)` : "";
      const finishLabel = isAll ? "Tất cả Khối 1-12" : `Toán Khối ${g}`;
      const finishLine = `[${finishTime}] Thu thập thành công! Đã lưu ${savedCount} câu hỏi mới ${finishLabel}${skipInfo} (tổng thu ${data.total_harvested}, loại trùng ${data.skipped_duplicates || 0}).`;
      if (logBox) {
        if (logBox.textContent.includes(inProgressLine)) {
          logBox.textContent = logBox.textContent.replace(inProgressLine, finishLine);
        } else {
          const cur = (logBox.textContent || "").trim();
          logBox.textContent = cur ? finishLine + "\n" + cur : finishLine;
        }
        localStorage.setItem("eduquest_hunter_log", logBox.textContent);
      }
      showToast(`Đã lưu ${savedCount} câu hỏi mới ${finishLabel}${skipInfo}!`);
      if (typeof broadcastNewQuestions === "function") {
        broadcastNewQuestions(savedCount, `${finishLabel} Đa Nguồn`);
      }
      loadDashboardStats();
      loadCollectorLogs();
      if (State.currentView === "bank") loadQuestions();
    } else {
      const errLine = `[${finishTime}] Thông báo: ${data.error || `Không thể thu thập dữ liệu Toán.`}`;
      if (logBox) {
        if (logBox.textContent.includes(inProgressLine)) {
          logBox.textContent = logBox.textContent.replace(inProgressLine, errLine);
        }
        localStorage.setItem("eduquest_hunter_log", logBox.textContent);
      }
      showToast(data.error || "Không thể thu thập dữ liệu", "error");
    }
  } catch (err) {
    const finishTime = getLogTimeVN();
    const errLine = `[${finishTime}] Lỗi kết nối máy chủ: ${err.message}`;
    if (logBox) {
      if (logBox.textContent.includes(inProgressLine)) {
        logBox.textContent = logBox.textContent.replace(inProgressLine, errLine);
      }
      localStorage.setItem("eduquest_hunter_log", logBox.textContent);
    }
    showToast(`Lỗi khi nạp nhanh đề Toán: ` + err.message, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      const lbl = isAll ? "1-12" : String(g);
      btn.innerHTML = `✨ Nạp nhanh Đề Toán Khối <span id="harvest-grade-btn-label">${lbl}</span> Toàn diện (Anh & Việt)`;
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
  const g = grade === "all" ? "all" : (parseInt(grade) || 5);
  localStorage.setItem("eduquest_default_grade", g);
  localStorage.setItem("eduquest_selected_grade", g);
  applyGradeToAllSelectors(g);
  updateGradePresetsUI(g);
  loadHunterTargetUrls(g);
  renderHunterUrlsList();
  showToast(g === "all" ? "Đã lưu Tất cả các khối (1-12) làm mặc định!" : `Đã lưu Khối lớp ${g} làm mặc định toàn hệ thống!`);
}

function onGradeSelectChanged(grade) {
  const g = grade === "all" ? "all" : (parseInt(grade) || 5);
  localStorage.setItem("eduquest_selected_grade", g);
  applyGradeToAllSelectors(g);
  updateGradePresetsUI(g);
  loadHunterTargetUrls(g);
  renderHunterUrlsList();
}

function applyGradeToAllSelectors(grade) {
  // Apply to collector tools, builder and manual creation forms, never restrict Question Bank view
  const ids = ["global-default-grade", "hunter-grade", "scraper-grade", "m-grade", "matrix-grade"];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      const opt = el.querySelector(`option[value="${grade}"]`);
      if (opt) el.value = grade;
    }
  });
  const btnLabel = document.getElementById("harvest-grade-btn-label");
  if (btnLabel) btnLabel.innerText = grade === "all" ? "1-12" : String(grade);
}

// ----------------- R1: Bot Auto-Crawl 5-Minute Periodic Loop -----------------
let botAutoCountdown = 300;
let botAutoInterval = null;

// Hub thống nhất: toggle bật/tắt scheduler nền 24/7 trên server
// (server tự quét bài cũ theo ledger 7 ngày, không cần mở tab).
// Vòng lặp countdown trong tab cũ được dừng để tránh cào trùng 2 nơi.
async function toggleBotAutoCrawl(enable) {
  localStorage.setItem("eduquest_bot_autocrawl", enable ? "true" : "false");
  const badge = document.getElementById("bot-auto-crawl-badge");
  const toggle = document.getElementById("bot-auto-crawl-toggle");
  stopBotAutoCrawlLoop();
  try {
    const gradeVal = document.getElementById("scraper-grade")?.value || "all";
    const grades = (gradeVal === "all" || !gradeVal)
      ? [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
      : [parseInt(gradeVal) || 2];
    const res = await apiFetch(`/api/collect/vioedu-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "auto",
        grades: grades,
        subjects: ["math", "vietnamese", "english"],
        auto_enabled: !!enable
      })
    });
    const data = await res.json();
    const on = !!(data.success && data.enabled);
    if (toggle) toggle.checked = on;
    if (badge) badge.style.display = on ? "inline-flex" : "none";
    showToast(on ? "Đã BẬT tự động cào nền 24/7 (server tự xoay tua 1-12, không cần mở tab)!"
                 : "Đã TẮT tự động cào nền.", on ? "success" : undefined);
  } catch (e) {
    if (toggle) toggle.checked = false;
    if (badge) badge.style.display = "none";
    showToast("Không kết nối được server để bật/tắt tự động cào.", "error");
  }
  refreshVioEduHubStatus();
}

// User 2026-10-14: xoay 1-12 dung "tai khoan dang nhap cao du lieu".
// Admin nhap TK VioEdu (form san co) 1 lan → server login, luu cookies phien
// → scheduler 24/7 cao bang TK nay. Mat khau KHONG luu tren server.
async function saveVioEduSession() {
  const user = document.getElementById("scraper-username")?.value?.trim();
  const pass = document.getElementById("scraper-password")?.value?.trim();
  if (!user || !pass) {
    showToast("Nhập Tài khoản + Mật khẩu VioEdu ở form trên trước khi lưu phiên.", "warning");
    return;
  }
  showToast("⏳ Đang đăng nhập VioEdu, lưu phiên cho bot 24/7...", undefined);
  try {
    const res = await apiFetch(`/api/collect/vioedu-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, password: pass })
    });
    const data = await res.json();
    if (data.success) {
      const pw = document.getElementById("scraper-password");
      if (pw) pw.value = "";  // khong giu mat khau trong DOM sau khi luu
      showToast(`✅ ${data.message || "Đã lưu phiên VioEdu — bot cào bằng TK này."}`, "success");
    } else {
      showToast(`❌ ${data.detail || data.message || "Đăng nhập VioEdu thất bại."}`, "error");
    }
  } catch (e) {
    showToast("Không kết nối được server để lưu phiên VioEdu.", "error");
  }
  refreshVioEduHubStatus();
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
    const res = await apiFetch(`/api/questions?sort_by=newest&page=1&page_size=24`);
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

  if (viewMode === "table") {
    container.innerHTML = `
      <div style="max-height: 460px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 8px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <thead style="background: #f8fafc; border-bottom: 2px solid #e2e8f0; position: sticky; top: 0; z-index: 10;">
            <tr>
              <th style="padding: 10px 12px; text-align: center; width: 50px;">STT</th>
              <th style="padding: 10px 12px; text-align: left; width: 100px;">Nền tảng</th>
              <th style="padding: 10px 12px; text-align: left; width: 110px;">Môn / Khối</th>
              <th style="padding: 10px 12px; text-align: left;">Nội dung câu hỏi</th>
              <th style="padding: 10px 12px; text-align: left; width: 150px;">Thời gian tạo</th>
              <th style="padding: 10px 12px; text-align: left; width: 90px;">Mã ID</th>
            </tr>
          </thead>
          <tbody>
            ${currentCapturedQuestions.map((q, idx) => `
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 12px; text-align: center; font-weight: 700; color: #64748b;">${idx + 1}</td>
                <td style="padding: 10px 12px;"><span class="tag-badge platform-${q.source_platform}">${q.source_platform}</span></td>
                <td style="padding: 10px 12px;">
                  <span class="tag-badge" style="background: #eff6ff; color: #1d4ed8; font-size: 11px;">${q.subject}</span>
                  <span class="tag-grade" style="font-size: 11px;">Lớp ${q.grade || 5}</span>
                </td>
                <td style="padding: 10px 12px; color: #1e293b;">
                  ${typeof formatMathSymbols === 'function' ? formatMathSymbols(q.content_text || q.content_html || '') : (q.content_text || q.content_html || '')}
                </td>
                <td style="padding: 10px 12px; white-space: nowrap;">
                  <span class="tag-timestamp">🕒 ${typeof formatDateTimeVN === 'function' ? formatDateTimeVN(q.created_at) : (q.created_at || '')}</span>
                </td>
                <td style="padding: 10px 12px; font-family: monospace; font-size: 11px; color: #64748b;">
                  #${q.q_number || q.id.substring(0, 8)}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
    if (typeof renderMath === "function") renderMath(container);
    return;
  }

  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 12px; max-height: 460px; overflow-y: auto;">
      ${currentCapturedQuestions.map((q, idx) => `
        <div style="padding: 14px; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <span class="q-number-pill" style="font-size: 12px;">Câu ${idx + 1}</span>
              <span class="tag-badge platform-${q.source_platform}">${q.source_platform}</span>
              <span class="tag-badge" style="background: #eff6ff; color: #1d4ed8;">${q.subject}</span>
              <span class="tag-grade">Lớp ${q.grade || 5}</span>
              ${q.created_at ? `<span class="tag-timestamp">🕒 ${typeof formatDateTimeVN === 'function' ? formatDateTimeVN(q.created_at) : q.created_at}</span>` : ''}
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
    const res = await apiFetch(`/api/questions/bulk`, {
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
  // 1. Restore grade for collector tools only (default to "2" as requested by user)
  let savedGrade = "2";
  try {
    savedGrade = localStorage.getItem("eduquest_default_grade") || "2";
    localStorage.setItem("eduquest_default_grade", savedGrade);
    localStorage.setItem("eduquest_selected_grade", savedGrade);
  } catch (e) {}

  try {
    applyGradeToAllSelectors(savedGrade);
    updateGradePresetsUI(savedGrade);
  } catch (e) {
    console.warn("restoreCollectorSettings grade presets error:", e);
  }

  // 2. Restore scraper credentials
  try {
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
  } catch (e) {}

  // 3. Restore auto-hunter toggle
  try {
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
  } catch (e) {}

  // 4. Hub VioEdu: đồng bộ toggle theo scheduler backend (không chạy loop tab cũ)
  try {
    apiFetch(`/api/collect/vioedu-plan`).then(r => r.json()).then(st => {
      const botToggle = document.getElementById("bot-auto-crawl-toggle");
      if (botToggle && st.success) {
        botToggle.checked = !!st.auto_enabled;
        const badge = document.getElementById("bot-auto-crawl-badge");
        if (badge) badge.style.display = st.auto_enabled ? "inline-flex" : "none";
      }
    }).catch(() => { /* giữ trạng thái localStorage */ });
  } catch (e) {}
  refreshVioEduHubStatus();

  // 5. Restore hunter target URLs list & presets for active grade
  try {
    const rawInit = (function() {
      try {
        return localStorage.getItem("eduquest_default_grade") || localStorage.getItem("eduquest_selected_grade") || "2";
      } catch (e) { return "2"; }
    })();
    const initGrade = rawInit === "all" ? "all" : (parseInt(rawInit) || 2);
    updateGradePresetsUI(initGrade);
    loadHunterTargetUrls(initGrade);
    renderHunterUrlsList();
  } catch (e) {
    console.warn("restoreCollectorSettings hunter urls error:", e);
  }

  // 6. Restore persistent live logs
  try {
    const savedHunterLog = localStorage.getItem("eduquest_hunter_log");
    const hunterLogBox = document.getElementById("hunter-live-log");
    const hunterToolbar = document.getElementById("hunter-log-toolbar");
    if (savedHunterLog && hunterLogBox) {
      const formatted = formatAndSortHunterLog(savedHunterLog);
      if (formatted) {
        hunterLogBox.style.display = "block";
        if (hunterToolbar) hunterToolbar.style.display = "flex";
        hunterLogBox.textContent = formatted;
        try { localStorage.setItem("eduquest_hunter_log", formatted); } catch (e) {}
      }
    }
  } catch (e) {}

  try {
    const savedScraperLog = localStorage.getItem("eduquest_scraper_log");
    const scraperLogBox = document.getElementById("scraper-live-log");
    const scraperToolbar = document.getElementById("scraper-log-toolbar");
    if (savedScraperLog && scraperLogBox) {
      const cleanLog = unSquishLogLines(savedScraperLog);
      scraperLogBox.style.display = "block";
      if (scraperToolbar) scraperToolbar.style.display = "flex";
      scraperLogBox.textContent = cleanLog;
      try { localStorage.setItem("eduquest_scraper_log", cleanLog); } catch (e) {}
    }
  } catch (e) {}

  // 7. Restore OCR live log
  try {
    restoreOcrLog();
  } catch (e) {}

  // 8. Refresh OCR Active Lexicon badge count
  try {
    refreshOcrLexiconCountBadge();
  } catch (e) {}

  // 9. Đồng bộ nhật ký bot nền 24/7 trực tiếp từ server
  try {
    syncScraperLiveLogsFromServer();
  } catch (e) {}

  // 10. Đồng bộ nhật ký săn câu hỏi Internet trực tiếp từ server
  try {
    syncHunterLiveLogsFromServer();
  } catch (e) {}

  // 11. Định kỳ 5s tự động cập nhật trạng thái bot nền và logs khi đang xem trang Collector
  if (!window._collectorPollInterval) {
    window._collectorPollInterval = setInterval(() => {
      const isCollectorActive = (typeof State !== "undefined" && State.currentView === "collector") ||
                                (document.getElementById("view-collector") && document.getElementById("view-collector").classList.contains("active"));
      if (isCollectorActive) {
        syncScraperLiveLogsFromServer();
        syncHunterLiveLogsFromServer();
        refreshVioEduHubStatus();
        loadCollectorLogs();
      }
    }, 5000);
  }
}

// ============================================================================
// OCR Active Lexicon Management (Từ điển Tự học OCR)
// ============================================================================

let ocrLexiconSearchDebounce = null;

async function refreshOcrLexiconCountBadge() {
  try {
    const res = await apiFetch(`/api/ocr/engine-status`);
    if (!res.ok) return;
    const data = await res.json();
    const count = data.total_learned_rules !== undefined ? data.total_learned_rules : 0;
    const badge = document.getElementById("ocr-lexicon-count-badge");
    if (badge) {
      badge.textContent = count;
    }
  } catch (err) {
    console.debug("Could not refresh OCR lexicon badge:", err);
  }
}
window.refreshOcrLexiconCountBadge = refreshOcrLexiconCountBadge;

function openOcrLexiconModal() {
  const modal = document.getElementById("modal-ocr-lexicon");
  if (modal) {
    modal.style.display = "flex";
    const searchInput = document.getElementById("lexicon-search-input");
    if (searchInput) searchInput.value = "";
    loadOcrLexiconRules("");
  }
}
window.openOcrLexiconModal = openOcrLexiconModal;

function closeOcrLexiconModal() {
  const modal = document.getElementById("modal-ocr-lexicon");
  if (modal) {
    modal.style.display = "none";
  }
}
window.closeOcrLexiconModal = closeOcrLexiconModal;

async function loadOcrLexiconRules(search = "") {
  const tbody = document.getElementById("ocr-lexicon-table-body");
  const stats = document.getElementById("lexicon-stats-text");
  if (!tbody) return;

  if (stats) stats.textContent = "Đang tải dữ liệu từ điển...";

  try {
    const res = await apiFetch(`/api/ocr/corrections?page=1&page_size=200&search=${encodeURIComponent(search)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = data.items || [];
    const total = data.total !== undefined ? data.total : items.length;

    if (stats) {
      stats.textContent = `Tổng cộng: ${total} quy tắc ${search ? `(khớp với "${search}")` : ""}`;
    }

    const badge = document.getElementById("ocr-lexicon-count-badge");
    if (badge && !search) badge.textContent = total;

    if (items.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 36px 20px; color: #94a3b8;">
            <div style="font-size: 32px; margin-bottom: 8px;">🧠</div>
            <div style="font-weight: 600; font-size: 13.5px; color: #64748b;">Chưa có quy tắc tự học nào ${search ? 'khớp với từ khóa' : 'trong từ điển'}</div>
            <div style="font-size: 12px; margin-top: 4px; color: #94a3b8;">
              Mỗi khi bạn sửa câu hỏi OCR trên Form và nhấn "Lưu", AI sẽ tự động so sánh và học các cụm từ đính chính mới tại đây.
            </div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map(item => {
      const isManual = item.source === "manual_rule";
      const sourceBadge = isManual
        ? `<span style="display: inline-block; padding: 2px 7px; font-size: 11px; border-radius: 4px; background: #e0f2fe; color: #0369a1; font-weight: 600;">Thủ công</span>`
        : `<span style="display: inline-block; padding: 2px 7px; font-size: 11px; border-radius: 4px; background: #fdf4ff; color: #9333ea; font-weight: 600;">🧠 Tự học (Form)</span>`;
      
      return `
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 9px 12px; font-family: monospace; font-weight: 600; color: #dc2626; background: #fef2f2; border-radius: 4px;">
            ${escapeHtmlCollector(item.wrong_text)}
          </td>
          <td style="padding: 9px 12px; font-weight: 600; color: #16a34a;">
            ${escapeHtmlCollector(item.correct_text)}
          </td>
          <td style="padding: 9px 12px; text-align: center;">
            <span style="display: inline-block; padding: 2px 8px; border-radius: 12px; background: #f1f5f9; color: #475569; font-size: 11px; font-weight: 700;">
              x${item.frequency || 1}
            </span>
          </td>
          <td style="padding: 9px 12px;">
            ${sourceBadge}
          </td>
          <td style="padding: 9px 12px; text-align: center;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="deleteOcrLexiconRule(${item.id})" style="padding: 2px 7px; font-size: 11.5px; color: #ef4444; border-color: #fecaca; background: white;" title="Xóa quy tắc này">
              🗑️ Xóa
            </button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    if (stats) stats.textContent = "Lỗi nạp từ điển";
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; padding: 24px; color: #ef4444;">
          ❌ Không thể tải danh sách quy tắc: ${err.message}
        </td>
      </tr>
    `;
  }
}
window.loadOcrLexiconRules = loadOcrLexiconRules;

function escapeHtmlCollector(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function filterOcrLexiconList() {
  clearTimeout(ocrLexiconSearchDebounce);
  ocrLexiconSearchDebounce = setTimeout(() => {
    const val = document.getElementById("lexicon-search-input")?.value || "";
    loadOcrLexiconRules(val);
  }, 250);
}
window.filterOcrLexiconList = filterOcrLexiconList;

async function submitManualLexiconRule() {
  const wrongEl = document.getElementById("lexicon-add-wrong");
  const correctEl = document.getElementById("lexicon-add-correct");
  if (!wrongEl || !correctEl) return;

  const wrong = wrongEl.value.trim();
  const correct = correctEl.value.trim();

  if (!wrong) {
    showToast("Vui lòng nhập cụm từ sai do OCR nhận diện", "error");
    wrongEl.focus();
    return;
  }
  if (!correct) {
    showToast("Vui lòng nhập cụm từ sửa đổi đúng", "error");
    correctEl.focus();
    return;
  }
  if (wrong.toLowerCase() === correct.toLowerCase()) {
    showToast("Từ gốc và từ đính chính không thể giống nhau", "warning");
    return;
  }

  try {
    const res = await apiFetch(`/api/ocr/corrections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wrong_text: wrong,
        correct_text: correct,
        source: "manual_rule"
      })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Lỗi lưu quy tắc");
    }
    showToast(`✓ Đã thêm quy tắc: "${wrong}" ➔ "${correct}"`, "success");
    wrongEl.value = "";
    correctEl.value = "";
    loadOcrLexiconRules(document.getElementById("lexicon-search-input")?.value || "");
    refreshOcrLexiconCountBadge();
  } catch (err) {
    showToast(`Lỗi thêm quy tắc: ${err.message}`, "error");
  }
}
window.submitManualLexiconRule = submitManualLexiconRule;

async function deleteOcrLexiconRule(id) {
  if (!confirm("Bạn có chắc chắn muốn xóa quy tắc đính chính này khỏi Từ điển AI?")) {
    return;
  }
  try {
    const res = await apiFetch(`/api/ocr/corrections/${id}`, {
      method: "DELETE"
    });
    if (!res.ok) throw new Error("Lỗi máy chủ khi xóa quy tắc");
    showToast("Đã xóa quy tắc khỏi từ điển", "info");
    loadOcrLexiconRules(document.getElementById("lexicon-search-input")?.value || "");
    refreshOcrLexiconCountBadge();
  } catch (err) {
    showToast(`Lỗi xóa quy tắc: ${err.message}`, "error");
  }
}
window.deleteOcrLexiconRule = deleteOcrLexiconRule;

async function clearAllOcrLexiconRules() {
  if (!confirm("⚠️ CẢNH BÁO: Thao tác này sẽ XÓA SẠCH toàn bộ các cụm từ tự học trong từ điển!\n\nBạn có chắc chắn muốn tiếp tục không?")) {
    return;
  }
  try {
    const res = await apiFetch(`/api/ocr/corrections/clear`, {
      method: "POST"
    });
    if (!res.ok) throw new Error("Lỗi khi xóa từ điển");
    const data = await res.json();
    showToast(`Đã dọn dẹp sạch ${data.cleared_count || 0} quy tắc trong từ điển`, "success");
    loadOcrLexiconRules("");
    refreshOcrLexiconCountBadge();
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  }
}
window.clearAllOcrLexiconRules = clearAllOcrLexiconRules;

// ============================================================================
// AI Vision (OpenRouter & OpenCode) Configuration Modal
// ============================================================================

async function openAiVisionModal() {
  const modal = document.getElementById("modal-ai-vision-config");
  if (modal) {
    modal.style.display = "flex";
    await loadAiVisionSettings();
  }
}
window.openAiVisionModal = openAiVisionModal;

function closeAiVisionModal() {
  const modal = document.getElementById("modal-ai-vision-config");
  if (modal) {
    modal.style.display = "none";
  }
}
window.closeAiVisionModal = closeAiVisionModal;

// State for AI Vision Multi-Model Fallback Chains
let currentOpenRouterModels = [];
let currentOpenCodeModels = [];
let currentCustomModels = [];
let availableOpenRouterModels = [];
let availableCustomModels = [];

function updatePipelinePreview() {
  const provider = document.getElementById("ai-vision-provider-select")?.value || "auto";
  const chainEl = document.getElementById("ai-vision-pipeline-chain");
  const countEl = document.getElementById("ai-vision-pipeline-count");
  if (!chainEl) return;

  const steps = [];
  if (provider === "9router_first") {
    currentCustomModels.forEach((m) => {
      steps.push({
        label: `9Router: ${m}`,
        short: m.split("/").pop(),
        type: "custom",
        isFree: m.includes(":free") || m.includes("free")
      });
    });
    currentOpenRouterModels.forEach((m) => {
      steps.push({
        label: `OpenRouter: ${m}`,
        short: m.replace(":free", "").split("/").pop(),
        type: "openrouter",
        isFree: m.includes(":free") || m.includes("free")
      });
    });
    currentOpenCodeModels.forEach((m) => {
      steps.push({
        label: `OpenCode: ${m}`,
        short: m,
        type: "opencode",
        isFree: false
      });
    });
  } else {
    if (provider === "auto" || provider === "openrouter") {
      currentOpenRouterModels.forEach((m) => {
        steps.push({
          label: `OpenRouter: ${m}`,
          short: m.replace(":free", "").split("/").pop(),
          type: "openrouter",
          isFree: m.includes(":free") || m.includes("free")
        });
      });
    }
    if (provider === "auto" || provider === "opencode") {
      currentOpenCodeModels.forEach((m) => {
        steps.push({
          label: `OpenCode: ${m}`,
          short: m,
          type: "opencode",
          isFree: false
        });
      });
    }
    if (provider === "auto" || provider === "custom") {
      currentCustomModels.forEach((m) => {
        steps.push({
          label: `9Router: ${m}`,
          short: m.split("/").pop(),
          type: "custom",
          isFree: m.includes(":free") || m.includes("free")
        });
      });
    }
  }

  if (countEl) {
    countEl.textContent = `${steps.length} model AI + 1 RapidOCR`;
  }

  if (steps.length === 0) {
    chainEl.innerHTML = `<span style="color: #ef4444; font-weight: 600;">⚠️ Chưa chọn model AI nào! Hệ thống sẽ chuyển thẳng sang RapidOCR.</span>`;
    return;
  }

  let html = "";
  steps.forEach((st, idx) => {
    const arrow = idx > 0 ? `<span style="color: #64748b; font-weight: 700; margin: 0 1px;">➔</span>` : '';
    html += `
      ${arrow}
      <span class="pipeline-step-badge badge-${st.type}" title="${st.label}">
        <strong>#${idx + 1}</strong> ${st.short} ${st.isFree ? '⭐ 0đ' : ''}
      </span>
    `;
  });
  html += `
    <span style="color: #64748b; font-weight: 700; margin: 0 1px;">➔</span>
    <span class="pipeline-step-badge badge-rapid" title="Fallback dự phòng cuối cùng nếu toàn bộ model AI gặp sự cố">
      🛡️ RapidOCR
    </span>
  `;
  chainEl.innerHTML = html;
}
window.updatePipelinePreview = updatePipelinePreview;

function renderOpenRouterModelsList() {
  const listEl = document.getElementById("ai-vision-openrouter-models-list");
  const countBadge = document.getElementById("ai-vision-openrouter-count-badge");
  if (!listEl) return;

  if (countBadge) {
    countBadge.textContent = `${currentOpenRouterModels.length} model`;
  }

  if (currentOpenRouterModels.length === 0) {
    listEl.innerHTML = `<div style="text-align: center; color: #94a3b8; font-size: 11px; padding: 10px;">Chưa chọn model nào. Hãy nhấn <strong>"Thêm vào chuỗi"</strong> hoặc <strong>"⭐ Thêm tất cả 0đ"</strong>.</div>`;
    updatePipelinePreview();
    return;
  }

  listEl.innerHTML = currentOpenRouterModels.map((m, idx) => {
    const isFirst = idx === 0;
    const isFree = m.includes(":free") || m.toLowerCase().includes("free");
    const freeBadge = isFree ? `<span style="font-size: 9.5px; background: #dcfce7; color: #15803d; padding: 1px 5px; border-radius: 4px; font-weight: 700; margin-left: 6px;">0đ</span>` : "";
    return `
      <div class="fallback-model-chip ${isFirst ? 'chip-primary' : ''}">
        <div style="display: flex; align-items: center; overflow: hidden; flex: 1;">
          <span class="fallback-chip-num ${isFirst ? 'num-first' : ''}">#${idx + 1}</span>
          <span class="fallback-chip-name" title="${m}">${m}</span>
          ${freeBadge}
        </div>
        <div class="fallback-chip-actions">
          ${idx > 0 ? `<button type="button" class="fallback-chip-btn" onclick="moveOpenRouterModel(${idx}, -1)" title="Ưu tiên cao hơn">▲</button>` : ''}
          ${idx < currentOpenRouterModels.length - 1 ? `<button type="button" class="fallback-chip-btn" onclick="moveOpenRouterModel(${idx}, 1)" title="Ưu tiên thấp hơn">▼</button>` : ''}
          <button type="button" class="fallback-chip-btn btn-del" onclick="removeOpenRouterModel(${idx})" title="Xóa khỏi chuỗi">✕</button>
        </div>
      </div>
    `;
  }).join("");

  updatePipelinePreview();
}
window.renderOpenRouterModelsList = renderOpenRouterModelsList;

function addOpenRouterModel(m) {
  if (!m || !m.trim()) return;
  m = m.trim();
  if (currentOpenRouterModels.includes(m)) {
    showToast(`Model '${m}' đã có trong chuỗi fallback!`, "warning");
    return;
  }
  currentOpenRouterModels.push(m);
  renderOpenRouterModelsList();
  showToast(`Đã thêm '${m}' vào chuỗi OpenRouter!`, "success");
}
window.addOpenRouterModel = addOpenRouterModel;

function addOpenRouterModelFromPicker() {
  const picker = document.getElementById("ai-vision-openrouter-picker");
  if (picker && picker.value) {
    addOpenRouterModel(picker.value);
  }
}
window.addOpenRouterModelFromPicker = addOpenRouterModelFromPicker;

function removeOpenRouterModel(idx) {
  if (idx >= 0 && idx < currentOpenRouterModels.length) {
    currentOpenRouterModels.splice(idx, 1);
    renderOpenRouterModelsList();
  }
}
window.removeOpenRouterModel = removeOpenRouterModel;

function moveOpenRouterModel(idx, dir) {
  const newIdx = idx + dir;
  if (newIdx >= 0 && newIdx < currentOpenRouterModels.length) {
    const temp = currentOpenRouterModels[idx];
    currentOpenRouterModels[idx] = currentOpenRouterModels[newIdx];
    currentOpenRouterModels[newIdx] = temp;
    renderOpenRouterModelsList();
  }
}
window.moveOpenRouterModel = moveOpenRouterModel;

function addAllFreeOpenRouterModels() {
  const defaultFree = [
    "dots-studio/dots-3-note-preview:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "thinkingmachines/inkling-small:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
  ];
  const listToAdd = (availableOpenRouterModels.length > 0)
    ? availableOpenRouterModels.filter(m => m.is_free).map(m => m.id)
    : defaultFree;

  let addedCount = 0;
  listToAdd.forEach(m => {
    if (!currentOpenRouterModels.includes(m)) {
      currentOpenRouterModels.push(m);
      addedCount++;
    }
  });
  renderOpenRouterModelsList();
  showToast(`Đã thêm ${addedCount} model 0đ vào chuỗi OpenRouter!`, "success");
}
window.addAllFreeOpenRouterModels = addAllFreeOpenRouterModels;

function resetOpenRouterModelsDefault() {
  currentOpenRouterModels = [
    "dots-studio/dots-3-note-preview:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "thinkingmachines/inkling-small:free"
  ];
  renderOpenRouterModelsList();
  showToast("Đã khôi phục chuỗi OpenRouter khuyên dùng!", "info");
}
window.resetOpenRouterModelsDefault = resetOpenRouterModelsDefault;

function renderOpenCodeModelsList() {
  const container = document.getElementById("ai-vision-opencode-models-list");
  const countBadge = document.getElementById("ai-vision-opencode-count-badge");
  if (!container) return;

  const defaultList = [
    { id: "gemini-3.6-flash", name: "Google Gemini 3.6 Flash (Zen ⭐ Khuyên dùng)", rec: true },
    { id: "gemini-2.5-flash", name: "Google Gemini 2.5 Flash (Zen Fast)", rec: false },
    { id: "claude-sonnet-4-5", name: "Claude Sonnet 4.5 Vision (Zen)", rec: false }
  ];

  if (countBadge) {
    countBadge.textContent = `${currentOpenCodeModels.length} model`;
  }

  container.innerHTML = defaultList.map(item => {
    const isChecked = currentOpenCodeModels.includes(item.id);
    const orderIdx = currentOpenCodeModels.indexOf(item.id);
    const orderBadge = isChecked
      ? `<span class="fallback-chip-num ${orderIdx === 0 ? 'num-first' : ''}" style="width: 18px; height: 18px; font-size: 9px; margin-right: 6px;">#${orderIdx + 1}</span>`
      : `<span style="width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; background: #e2e8f0; border-radius: 50%; font-size: 9px; color: #64748b; margin-right: 6px;">-</span>`;

    return `
      <label class="fallback-model-chip" style="cursor: pointer; margin: 0; user-select: none;">
        <div style="display: flex; align-items: center; gap: 6px;">
          <input type="checkbox" value="${item.id}" ${isChecked ? 'checked' : ''} onchange="toggleOpenCodeModel('${item.id}', this.checked)" style="cursor: pointer;" />
          ${orderBadge}
          <span style="font-weight: 600; color: #1e293b;">${item.name}</span>
        </div>
      </label>
    `;
  }).join("");

  updatePipelinePreview();
}
window.renderOpenCodeModelsList = renderOpenCodeModelsList;

function toggleOpenCodeModel(modelId, isChecked) {
  if (isChecked) {
    if (!currentOpenCodeModels.includes(modelId)) currentOpenCodeModels.push(modelId);
  } else {
    currentOpenCodeModels = currentOpenCodeModels.filter(m => m !== modelId);
  }
  renderOpenCodeModelsList();
}
window.toggleOpenCodeModel = toggleOpenCodeModel;

function renderCustomModelsList() {
  const listEl = document.getElementById("ai-vision-custom-models-list");
  const countBadge = document.getElementById("ai-vision-custom-count-badge");
  if (!listEl) return;

  if (countBadge) {
    countBadge.textContent = `${currentCustomModels.length} model`;
  }

  if (currentCustomModels.length === 0) {
    listEl.innerHTML = `<div style="text-align: center; color: #94a3b8; font-size: 11px; padding: 8px;">Chưa chọn model 9Router nào. Hãy chọn từ danh sách hoặc nhập tên model.</div>`;
    updatePipelinePreview();
    return;
  }

  listEl.innerHTML = currentCustomModels.map((m, idx) => {
    const isFirst = idx === 0;
    return `
      <div class="fallback-model-chip ${isFirst ? 'chip-primary' : ''}">
        <div style="display: flex; align-items: center; overflow: hidden; flex: 1;">
          <span class="fallback-chip-num ${isFirst ? 'num-first' : ''}">#${idx + 1}</span>
          <span class="fallback-chip-name" title="${m}">${m}</span>
        </div>
        <div class="fallback-chip-actions">
          ${idx > 0 ? `<button type="button" class="fallback-chip-btn" onclick="moveCustomModel(${idx}, -1)" title="Ưu tiên cao hơn">▲</button>` : ''}
          ${idx < currentCustomModels.length - 1 ? `<button type="button" class="fallback-chip-btn" onclick="moveCustomModel(${idx}, 1)" title="Ưu tiên thấp hơn">▼</button>` : ''}
          <button type="button" class="fallback-chip-btn btn-del" onclick="removeCustomModel(${idx})" title="Xóa khỏi chuỗi">✕</button>
        </div>
      </div>
    `;
  }).join("");

  updatePipelinePreview();
}
window.renderCustomModelsList = renderCustomModelsList;

function addCustomModel(m) {
  if (!m || !m.trim()) return;
  m = m.trim();
  if (currentCustomModels.includes(m)) {
    showToast(`Model '${m}' đã có trong chuỗi 9Router!`, "warning");
    return;
  }
  currentCustomModels.push(m);
  renderCustomModelsList();
  showToast(`Đã thêm '${m}' vào 9Router!`, "success");
}
window.addCustomModel = addCustomModel;

function addCustomModelFromInput() {
  const inputEl = document.getElementById("ai-vision-custom-input-model");
  const val = inputEl ? inputEl.value : "";
  if (val) {
    addCustomModel(val);
    if (inputEl) inputEl.value = "";
  }
}
window.addCustomModelFromInput = addCustomModelFromInput;

function removeCustomModel(idx) {
  if (idx >= 0 && idx < currentCustomModels.length) {
    currentCustomModels.splice(idx, 1);
    renderCustomModelsList();
  }
}
window.removeCustomModel = removeCustomModel;

function moveCustomModel(idx, dir) {
  const newIdx = idx + dir;
  if (newIdx >= 0 && newIdx < currentCustomModels.length) {
    const temp = currentCustomModels[idx];
    currentCustomModels[idx] = currentCustomModels[newIdx];
    currentCustomModels[newIdx] = temp;
    renderCustomModelsList();
  }
}
window.moveCustomModel = moveCustomModel;

function resetCustomModelsDefault() {
  currentCustomModels = [
    "openrouter/dots-studio/dots-3-note-preview:free",
    "openrouter/google/gemma-4-26b-a4b-it:free"
  ];
  renderCustomModelsList();
  showToast("Đã khôi phục chuỗi 9Router mặc định!", "info");
}
window.resetCustomModelsDefault = resetCustomModelsDefault;

async function loadAiVisionSettings() {
  try {
    const res = await apiFetch(`/api/ai-vision/settings`);
    if (!res.ok) return;
    const data = await res.json();
    const s = data.settings || {};

    const providerSelect = document.getElementById("ai-vision-provider-select");
    if (providerSelect && s.provider) providerSelect.value = s.provider;

    const orKey = document.getElementById("ai-vision-openrouter-key");
    if (orKey) {
      const masked = s.openrouter_api_key || "";
      // Backend tra ve key da mask (vd "sk-...abcd"): chi hien placeholder,
      // khong dien vao value de tranh ghi de key that khi luu.
      if (masked.includes("...") || masked === "***") {
        orKey.value = "";
        orKey.placeholder = `${masked} (đã lưu — nhập mới để thay đổi)`;
      } else {
        orKey.value = masked;
      }
    }

    if (Array.isArray(s.openrouter_models) && s.openrouter_models.length > 0) {
      currentOpenRouterModels = [...s.openrouter_models];
    } else if (s.openrouter_model) {
      currentOpenRouterModels = [s.openrouter_model];
    } else {
      currentOpenRouterModels = [
        "dots-studio/dots-3-note-preview:free",
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free"
      ];
    }

    const ocKey = document.getElementById("ai-vision-opencode-key");
    if (ocKey) {
      const masked = s.opencode_api_key || "";
      if (masked.includes("...") || masked === "***") {
        ocKey.value = "";
        ocKey.placeholder = `${masked} (đã lưu — nhập mới để thay đổi)`;
      } else {
        ocKey.value = masked;
      }
    }

    if (Array.isArray(s.opencode_models) && s.opencode_models.length > 0) {
      currentOpenCodeModels = [...s.opencode_models];
    } else if (s.opencode_model) {
      currentOpenCodeModels = [s.opencode_model];
    } else {
      currentOpenCodeModels = ["gemini-3.6-flash", "gemini-2.5-flash"];
    }

    const customUrl = document.getElementById("ai-vision-custom-url");
    if (customUrl) customUrl.value = s.custom_vision_url || "http://127.0.0.1:20129/v1";

    const customKey = document.getElementById("ai-vision-custom-key");
    if (customKey) {
      const masked = s.custom_vision_key || "";
      if (masked.includes("...") || masked === "***") {
        customKey.value = "";
        customKey.placeholder = `${masked} (đã lưu — nhập mới để thay đổi)`;
      } else {
        customKey.value = masked;
      }
    }

    if (Array.isArray(s.custom_vision_models) && s.custom_vision_models.length > 0) {
      currentCustomModels = [...s.custom_vision_models];
    } else if (s.custom_vision_model) {
      currentCustomModels = [s.custom_vision_model];
    } else {
      currentCustomModels = ["openrouter/dots-studio/dots-3-note-preview:free"];
    }

    renderOpenRouterModelsList();
    renderOpenCodeModelsList();
    renderCustomModelsList();
    updatePipelinePreview();
  } catch (err) {
    console.debug("Could not load AI Vision settings:", err);
  }
}
window.loadAiVisionSettings = loadAiVisionSettings;

async function saveAiVisionSettings() {
  const payload = {
    ai_vision_provider: document.getElementById("ai-vision-provider-select")?.value || "auto",
    openrouter_api_key: document.getElementById("ai-vision-openrouter-key")?.value || "",
    openrouter_models: currentOpenRouterModels,
    openrouter_model: currentOpenRouterModels[0] || "dots-studio/dots-3-note-preview:free",
    opencode_api_key: document.getElementById("ai-vision-opencode-key")?.value || "",
    opencode_models: currentOpenCodeModels,
    opencode_model: currentOpenCodeModels[0] || "gemini-3.6-flash",
    custom_vision_url: document.getElementById("ai-vision-custom-url")?.value || "http://127.0.0.1:20129/v1",
    custom_vision_key: document.getElementById("ai-vision-custom-key")?.value || "",
    custom_vision_models: currentCustomModels,
    custom_vision_model: currentCustomModels[0] || "openrouter/dots-studio/dots-3-note-preview:free"
  };

  try {
    const res = await apiFetch(`/api/ai-vision/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Lỗi lưu cấu hình");
    showToast("Đã lưu chuỗi cấu hình AI Vision thành công!", "success");
    closeAiVisionModal();
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  }
}
window.saveAiVisionSettings = saveAiVisionSettings;

async function testAiVisionConnection(provider = "custom") {
  let btn, statusEl, reqBody;

  if (provider === "openrouter") {
    btn = document.getElementById("btn-test-openrouter-connection");
    statusEl = document.getElementById("ai-vision-model-scan-status");
    reqBody = {
      provider: "openrouter",
      api_key: document.getElementById("ai-vision-openrouter-key")?.value || ""
    };
  } else if (provider === "opencode") {
    btn = document.getElementById("btn-test-opencode-connection");
    reqBody = {
      provider: "opencode",
      api_key: document.getElementById("ai-vision-opencode-key")?.value || ""
    };
  } else {
    // 9Router / Custom
    btn = document.getElementById("btn-test-custom-connection");
    statusEl = document.getElementById("ai-vision-custom-test-status");
    reqBody = {
      provider: "custom",
      base_url: document.getElementById("ai-vision-custom-url")?.value || "http://127.0.0.1:20129/v1",
      api_key: document.getElementById("ai-vision-custom-key")?.value || "",
      model: currentCustomModels[0] || "openrouter/dots-studio/dots-3-note-preview:free"
    };
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> Đang test...`;
  }
  if (statusEl) {
    statusEl.textContent = "Đang kiểm tra kết nối...";
    statusEl.style.color = "#0284c7";
  }

  try {
    const res = await apiFetch(`/api/ai-vision/test-connection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reqBody)
    });
    const data = await res.json();

    if (data.success) {
      if (statusEl) {
        statusEl.textContent = `✅ ${data.message}`;
        statusEl.style.color = "#059669";
      }
      showToast(data.message, "success");
    } else {
      if (statusEl) {
        statusEl.textContent = `❌ ${data.message}`;
        statusEl.style.color = "#dc2626";
      }
      showToast(data.message, "error");
    }
  } catch (err) {
    const msg = `Lỗi kiểm tra kết nối: ${err.message}`;
    if (statusEl) {
      statusEl.textContent = `❌ ${msg}`;
      statusEl.style.color = "#dc2626";
    }
    showToast(msg, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>🔌</span> Test connection`;
    }
  }
}
window.testAiVisionConnection = testAiVisionConnection;

async function scan9RouterModels() {
  const btn = document.getElementById("btn-scan-custom-models");
  const statusEl = document.getElementById("ai-vision-custom-test-status");
  const modelSelect = document.getElementById("ai-vision-custom-model-select");
  const baseUrl = document.getElementById("ai-vision-custom-url")?.value || "http://127.0.0.1:20129/v1";
  const apiKey = document.getElementById("ai-vision-custom-key")?.value || "";

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> Đang quét...`;
  }
  if (statusEl) {
    statusEl.textContent = "Đang lấy danh sách model từ 9Router...";
    statusEl.style.color = "#0284c7";
  }

  try {
    const res = await apiFetch(`/api/ai-vision/test-connection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: "custom",
        base_url: baseUrl,
        api_key: apiKey
      })
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.message);

    // Fetch models via backend endpoint (POST body — khong de key lo tren URL/log)
    const mRes = await apiFetch(`/api/ai-vision/models`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: "custom", base_url: baseUrl, api_key: apiKey })
    });
    if (mRes.ok) {
      const mData = await mRes.json();
      const list = mData.models || [];
      availableCustomModels = list;
      if (list.length > 0 && modelSelect) {
        modelSelect.innerHTML = `<option value="">-- Chọn từ 9Router (${list.length}) --</option>` + 
          list.map(m => `<option value="${m.id}">${m.id}</option>`).join("");
        modelSelect.style.display = "inline-block";
        if (statusEl) {
          statusEl.textContent = `✅ Đã tìm thấy ${list.length} model trên 9Router! Chọn dropdown hoặc nhấn "Thêm vào chuỗi".`;
          statusEl.style.color = "#059669";
        }
        showToast(`Tìm thấy ${list.length} model trên 9Router!`, "success");
        return;
      }
    }

    if (statusEl) {
      statusEl.textContent = `✅ ${data.message}`;
      statusEl.style.color = "#059669";
    }
    showToast(data.message, "success");
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = `❌ Lỗi: ${err.message}`;
      statusEl.style.color = "#dc2626";
    }
    showToast(`Lỗi quét model 9Router: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>🔄</span> Quét model`;
    }
  }
}
window.scan9RouterModels = scan9RouterModels;

async function scanLiveVisionModels(provider = "openrouter") {
  const btn = document.getElementById("btn-scan-openrouter-models");
  const statusEl = document.getElementById("ai-vision-model-scan-status");
  const pickerSelect = document.getElementById("ai-vision-openrouter-picker");
  const apiKey = document.getElementById("ai-vision-openrouter-key")?.value || "";

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> Đang quét...`;
  }
  if (statusEl) {
    statusEl.textContent = "Đang kết nối OpenRouter lấy danh sách model Vision...";
    statusEl.style.color = "#0284c7";
  }

  try {
    // POST body thay vi query-string de khong lo key trong URL/log server
    const res = await apiFetch(`/api/ai-vision/models`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.success || !data.models || data.models.length === 0) {
      throw new Error(data.error || "Không tìm thấy model Vision nào khả dụng");
    }

    availableOpenRouterModels = data.models || [];
    let optionsHtml = "";

    const freeModels = data.models.filter(m => m.is_free);
    const paidModels = data.models.filter(m => !m.is_free);

    if (freeModels.length > 0) {
      optionsHtml += `<optgroup label="🆓 Model Vision Miễn Phí 0đ (Hoạt động tốt)">`;
      freeModels.forEach(m => {
        const star = m.recommended ? " ⭐ Khuyên dùng" : "";
        optionsHtml += `<option value="${m.id}">${m.name}${star} [0đ]</option>`;
      });
      optionsHtml += `</optgroup>`;
    }

    if (paidModels.length > 0) {
      optionsHtml += `<optgroup label="💳 Model Vision Trả Phí">`;
      paidModels.slice(0, 30).forEach(m => {
        optionsHtml += `<option value="${m.id}">${m.name}</option>`;
      });
      optionsHtml += `</optgroup>`;
    }

    if (pickerSelect) {
      pickerSelect.innerHTML = optionsHtml;
    }

    if (statusEl) {
      statusEl.textContent = `✅ Đã tìm thấy ${data.total_found} model (${data.free_count} model 0đ)! Bạn có thể nhấn "+ Thêm vào chuỗi" hoặc "⭐ Thêm tất cả 0đ".`;
      statusEl.style.color = "#059669";
    }
    showToast(`Đã tìm thấy ${data.total_found} model (${data.free_count} model 0đ)!`, "success");
  } catch (err) {
    console.error("Scan models error:", err);
    if (statusEl) {
      statusEl.textContent = `❌ Lỗi quét: ${err.message}`;
      statusEl.style.color = "#dc2626";
    }
    showToast(`Lỗi quét model: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>🔄</span> Quét Model Mới`;
    }
  }
}
window.scanLiveVisionModels = scanLiveVisionModels;

// Initialize Dropzone and restore settings reliably across all DOM lifecycle stages
function initCollectorModule() {
  if (typeof setupDropzone === "function") setupDropzone();
  if (typeof restoreCollectorSettings === "function") restoreCollectorSettings();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initCollectorModule);
} else {
  // DOM is already interactive or complete
  initCollectorModule();
}
window.initCollectorModule = initCollectorModule;


