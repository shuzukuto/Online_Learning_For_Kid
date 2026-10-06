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

// ============================================================================
// OCR Debug Live Log & Telemetry
// ============================================================================
function appendOcrLog(message, type = "info") {
  const logBox = document.getElementById("ocr-live-log");
  const badge = document.getElementById("ocr-log-badge");
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const timeStr = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

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

  if (logBox) {
    if (!logBox.dataset.hasLogs) {
      logBox.innerText = formattedLine;
      logBox.dataset.hasLogs = "true";
    } else {
      logBox.innerText += "\n" + formattedLine;
    }
    // Auto-scroll to bottom
    logBox.scrollTop = logBox.scrollHeight;

    // Update badge count
    const lines = logBox.innerText.trim().split("\n");
    if (badge) badge.textContent = `${lines.length} bản ghi`;

    // Persist up to 60 lines in localStorage
    try {
      const stored = lines.slice(-60).join("\n");
      localStorage.setItem("eduquest_ocr_log", stored);
    } catch (e) {}
  }
}
window.appendOcrLog = appendOcrLog;

function copyOcrLiveLog() {
  const logBox = document.getElementById("ocr-live-log");
  if (!logBox || !logBox.innerText.trim()) {
    showToast("Chưa có nội dung nhật ký để sao chép", "warning");
    return;
  }
  const text = logBox.innerText.trim();
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
  const logBox = document.getElementById("ocr-live-log");
  const badge = document.getElementById("ocr-log-badge");
  if (logBox) {
    logBox.innerText = "[Hệ thống] Đã làm sạch màn hình nhật ký. Sẵn sàng bóc tách tệp mới.";
    logBox.dataset.hasLogs = "true";
    if (badge) badge.textContent = "1 bản ghi";
  }
  localStorage.removeItem("eduquest_ocr_log");
  showToast("🗑️ Đã xóa sạch màn hình nhật ký OCR", "info");
}
window.clearOcrLiveLog = clearOcrLiveLog;

function restoreOcrLog() {
  try {
    const saved = localStorage.getItem("eduquest_ocr_log");
    const logBox = document.getElementById("ocr-live-log");
    const badge = document.getElementById("ocr-log-badge");
    if (saved && logBox) {
      logBox.innerText = saved;
      logBox.dataset.hasLogs = "true";
      const lines = saved.trim().split("\n");
      if (badge) badge.textContent = `${lines.length} bản ghi`;
      logBox.scrollTop = logBox.scrollHeight;
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
      const res = await fetch(endpoint, {
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
      const qList = (data && (data.preview_questions || data.questions)) ? (data.preview_questions || data.questions) : [];
      const engineReported = data.engine_used || (qList[0] && qList[0].ocr_engine_used) || data.ocr_engine || ocrEngine;

      if (qList.length > 0) {
        appendOcrLog(`✅ [Tệp ${i + 1}/${totalFiles}] '${file.name}' bóc tách thành công ${qList.length} câu hỏi (${latency}s) [Động cơ: ${engineReported}]!`, "success");
        qList.forEach(q => {
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

  window.State.ocrBatch = {
    items: questions,
    currentIndex: 0,
    processedCount: 0,
    savedCount: 0,
    skippedCount: 0,
    totalCount: questions.length,
    images: images || []
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
  const optA = opts.find(o => o.id === "A") || opts[0];
  const optB = opts.find(o => o.id === "B") || opts[1];
  const optC = opts.find(o => o.id === "C") || opts[2];
  const optD = opts.find(o => o.id === "D") || opts[3];

  if (elOptA) elOptA.value = optA ? optA.content : "";
  if (elOptB) elOptB.value = optB ? optB.content : "";
  if (elOptC) elOptC.value = optC ? optC.content : "";
  if (elOptD) elOptD.value = optD ? optD.content : "";

  // Determine correct answer
  const correctOpt = q.correct_answer || (opts.find(o => o.is_correct)?.id) || "A";
  if (elCorrect) elCorrect.value = correctOpt;

  if (elDiff) elDiff.value = q.difficulty || "medium";
  if (elExplanation) elExplanation.value = q.explanation || "";

  // Sync OCR question images to the manual image gallery
  if (typeof manualImageUrls !== "undefined") {
    const qImages = (q.images && q.images.length > 0) ? [...q.images] : [];
    // If no question-specific images, try batch-level images
    if (qImages.length === 0 && window.State.ocrBatch.images && window.State.ocrBatch.images.length > 0) {
      qImages.push(...window.State.ocrBatch.images);
    }
    manualImageUrls = qImages;
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

  const currentImgUrl = (q.images && q.images.length > 0) ? q.images[0] : (window.State.ocrBatch.images[0] || null);

  if (currentImgUrl && imgBar && imgThumb) {
    imgBar.style.display = "flex";
    imgThumb.src = currentImgUrl;
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
    const res = await fetch(`${API_BASE}/questions/bulk`, {
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

  if (window.State.ocrBatch && window.State.ocrBatch.items) {
    const q = window.State.ocrBatch.items[window.State.ocrBatch.currentIndex];
    if (q && q.images && q.images.length > 0) {
      imgUrl = q.images[0];
      title = q.source_file_name || q.exam_name || "Ảnh đề thi gốc";
    }
    if (window.State.ocrBatch.images && window.State.ocrBatch.images.length > 0) {
      ocrLightboxState.imageUrls = window.State.ocrBatch.images;
      ocrLightboxState.currentIndex = ocrLightboxState.imageUrls.indexOf(imgUrl);
      if (ocrLightboxState.currentIndex < 0) ocrLightboxState.currentIndex = 0;
    }
  }

  if (!imgUrl && ocrLightboxState.imageUrls.length > 0) {
    imgUrl = ocrLightboxState.imageUrls[0];
  }

  if (!imgUrl) {
    const thumb = document.getElementById("ocr-source-image-thumb");
    if (thumb && thumb.src) imgUrl = thumb.src;
  }

  // Fallback to selected files if blob/preview available
  if (!imgUrl && typeof selectedOcrFiles !== "undefined" && selectedOcrFiles && selectedOcrFiles.length > 0) {
    const f = selectedOcrFiles[0];
    if (f && f.type && f.type.startsWith("image/")) {
      try {
        imgUrl = URL.createObjectURL(f);
        ocrLightboxState.imageUrls = [imgUrl];
        ocrLightboxState.currentIndex = 0;
        title = f.name;
      } catch (e) {}
    }
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
    const res = await fetch(`${API_BASE}/collect/logs`);
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
    const res = await fetch(`${API_BASE}/questions?sort_by=newest&page=1&page_size=24`);
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

  // 7. Restore OCR live log
  restoreOcrLog();

  // 8. Refresh OCR Active Lexicon badge count
  refreshOcrLexiconCountBadge();
}

// ============================================================================
// OCR Active Lexicon Management (Từ điển Tự học OCR)
// ============================================================================

let ocrLexiconSearchDebounce = null;

async function refreshOcrLexiconCountBadge() {
  try {
    const res = await fetch(`${API_BASE}/ocr/engine-status`);
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
    const url = `${API_BASE}/ocr/corrections?page=1&page_size=200&search=${encodeURIComponent(search)}`;
    const res = await fetch(url);
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
    const res = await fetch(`${API_BASE}/ocr/corrections`, {
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
    const res = await fetch(`${API_BASE}/ocr/corrections/${id}`, {
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
    const res = await fetch(`${API_BASE}/ocr/corrections/clear`, {
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

async function loadAiVisionSettings() {
  try {
    const res = await fetch(`${API_BASE}/ai-vision/settings`);
    if (!res.ok) return;
    const data = await res.json();
    const s = data.settings || {};

    const providerSelect = document.getElementById("ai-vision-provider-select");
    if (providerSelect && s.provider) providerSelect.value = s.provider;

    const orKey = document.getElementById("ai-vision-openrouter-key");
    if (orKey) orKey.value = s.openrouter_api_key || "";

    const orModel = document.getElementById("ai-vision-openrouter-model");
    if (orModel && s.openrouter_model) orModel.value = s.openrouter_model;

    const ocKey = document.getElementById("ai-vision-opencode-key");
    if (ocKey) ocKey.value = s.opencode_api_key || "";

    const ocModel = document.getElementById("ai-vision-opencode-model");
    if (ocModel && s.opencode_model) ocModel.value = s.opencode_model;

    const customUrl = document.getElementById("ai-vision-custom-url");
    if (customUrl) customUrl.value = s.custom_vision_url || "http://localhost:20128/v1";

    const customModel = document.getElementById("ai-vision-custom-model");
    if (customModel) customModel.value = s.custom_vision_model || "opencode/free";
  } catch (err) {
    console.debug("Could not load AI Vision settings:", err);
  }
}
window.loadAiVisionSettings = loadAiVisionSettings;

async function saveAiVisionSettings() {
  const payload = {
    ai_vision_provider: document.getElementById("ai-vision-provider-select")?.value || "auto",
    openrouter_api_key: document.getElementById("ai-vision-openrouter-key")?.value || "",
    openrouter_model: document.getElementById("ai-vision-openrouter-model")?.value || "google/gemini-2.0-flash-exp:free",
    opencode_api_key: document.getElementById("ai-vision-opencode-key")?.value || "",
    opencode_model: document.getElementById("ai-vision-opencode-model")?.value || "gemini-3.6-flash",
    custom_vision_url: document.getElementById("ai-vision-custom-url")?.value || "http://localhost:20128/v1",
    custom_vision_model: document.getElementById("ai-vision-custom-model")?.value || "opencode/free"
  };

  try {
    const res = await fetch(`${API_BASE}/ai-vision/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Lỗi lưu cấu hình");
    showToast("Đã lưu cấu hình AI Vision thành công!", "success");
    closeAiVisionModal();
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  }
}
window.saveAiVisionSettings = saveAiVisionSettings;

async function scanLiveVisionModels(provider = "openrouter") {
  const btn = document.getElementById("btn-scan-openrouter-models");
  const statusEl = document.getElementById("ai-vision-model-scan-status");
  const modelSelect = document.getElementById("ai-vision-openrouter-model");
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
    const res = await fetch(`${API_BASE}/ai-vision/models?provider=${encodeURIComponent(provider)}&api_key=${encodeURIComponent(apiKey)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.success || !data.models || data.models.length === 0) {
      throw new Error(data.error || "Không tìm thấy model Vision nào khả dụng");
    }

    const currentSelected = modelSelect ? modelSelect.value : "";
    let optionsHtml = "";

    // Group models: Free & Recommended first, then other Free, then Paid
    const freeModels = data.models.filter(m => m.is_free);
    const paidModels = data.models.filter(m => !m.is_free);

    if (freeModels.length > 0) {
      optionsHtml += `<optgroup label="🆓 Model Vision Miễn Phí (Hoạt động tốt)">`;
      freeModels.forEach(m => {
        const star = m.recommended ? " ⭐" : "";
        const sel = (m.id === currentSelected) ? "selected" : "";
        optionsHtml += `<option value="${m.id}" ${sel}>${m.name}${star} [0đ]</option>`;
      });
      optionsHtml += `</optgroup>`;
    }

    if (paidModels.length > 0) {
      optionsHtml += `<optgroup label="💳 Model Vision Trả Phí (Yêu cầu có nạp credit OpenRouter)">`;
      paidModels.slice(0, 30).forEach(m => {
        const sel = (m.id === currentSelected) ? "selected" : "";
        optionsHtml += `<option value="${m.id}" ${sel}>${m.name}</option>`;
      });
      optionsHtml += `</optgroup>`;
    }

    if (modelSelect) {
      modelSelect.innerHTML = optionsHtml;
      // If current was preserved or set first free recommended
      if (!currentSelected && freeModels.length > 0) {
        modelSelect.value = freeModels[0].id;
      }
    }

    if (statusEl) {
      statusEl.textContent = `✅ Đã tìm thấy ${data.total_found} model (${data.free_count} model 0đ)!`;
      statusEl.style.color = "#059669";
    }
    showToast(`Đã cập nhật ${data.total_found} model Vision từ OpenRouter!`, "success");
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

// Initialize Dropzone and restore settings when DOM loaded
document.addEventListener("DOMContentLoaded", () => {
  setupDropzone();
  restoreCollectorSettings();
});

