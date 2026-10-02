// EduQuest Pro - Question Bank View with Deduplication, Diagnostics & Editing
if (!State.batchSelectedIds) {
  State.batchSelectedIds = new Set();
}
let cachedEditingQuestion = null;

async function loadQuestions() {
  const container = document.getElementById("questions-list-container");
  if (!container) return;

  container.innerHTML = `
    <div style="text-align: center; padding: 40px; color: #64748b;">
      <div style="font-size: 28px; margin-bottom: 8px;">⏳</div>
      <p>Đang tải danh sách câu hỏi...</p>
    </div>
  `;

  // Sync UI filters
  syncFilterChips();

  const params = new URLSearchParams();
  if (State.filters.platform && State.filters.platform !== "all") params.append("platform", State.filters.platform);
  if (State.filters.subject && State.filters.subject !== "all") params.append("subject", State.filters.subject);
  if (State.filters.grade) params.append("grade", State.filters.grade);
  if (State.filters.question_type && State.filters.question_type !== "all") params.append("question_type", State.filters.question_type);
  if (State.filters.difficulty && State.filters.difficulty !== "all") params.append("difficulty", State.filters.difficulty);
  if (State.filters.search) params.append("search", State.filters.search);
  if (State.filters.source_detail && State.filters.source_detail !== "all") params.append("source_detail", State.filters.source_detail);
  if (State.filters.only_duplicates) params.append("only_duplicates", "true");
  if (State.filters.sort_by) params.append("sort_by", State.filters.sort_by);
  params.append("page", State.filters.page);
  params.append("page_size", State.filters.page_size);

  try {
    const res = await fetch(`${API_BASE}/questions?${params.toString()}`);
    const data = await res.json();
    State.cachedQuestions = data.items || [];

    const totalCountEl = document.getElementById("bank-total-count");
    if (totalCountEl) {
      const activeFilterDetails = [];
      if (State.filters.subject && State.filters.subject !== "all") {
        const subNames = { math: "Toán", vietnamese: "Tiếng Việt", english: "Tiếng Anh", science: "Khoa học", informatics: "Tin học" };
        activeFilterDetails.push(subNames[State.filters.subject] || State.filters.subject);
      }
      if (State.filters.grade) {
        activeFilterDetails.push(`Lớp ${State.filters.grade}`);
      }
      if (State.filters.platform && State.filters.platform !== "all") {
        const platNames = { internet_hunter: "Săn Internet", hanhtrangso: "Hành Trang Số", vioedu: "VioEdu", tnmath: "Trạng Nguyên", olympiad: "Olympic", manual: "Tự biên soạn" };
        activeFilterDetails.push(platNames[State.filters.platform] || State.filters.platform.toUpperCase());
      }
      if (State.filters.source_detail && State.filters.source_detail !== "all") {
        activeFilterDetails.push(State.filters.source_detail);
      }
      if (State.filters.search) {
        activeFilterDetails.push(`"${State.filters.search}"`);
      }
      if (State.filters.only_duplicates) {
        activeFilterDetails.push("Trùng lặp");
      }

      const totalInDB = State.stats ? (State.stats.total_questions || data.total) : data.total;
      const isShowAll = (State.filters.page_size || 50) >= 9999;

      if (activeFilterDetails.length > 0) {
        totalCountEl.innerHTML = `
          <span style="color: #475569; font-weight: 500;">Hiển thị: </span>
          <strong style="color: #1e40af; font-size: 14.5px;">${data.total || 0}</strong>
          <span style="color: #64748b; font-size: 12px; margin: 0 4px;">/ tổng ${totalInDB} câu CSDL</span>
          <span style="font-size: 11px; background: #eff6ff; color: #1d4ed8; padding: 2px 7px; border-radius: 4px; border: 1px solid #bfdbfe; margin-left: 4px;">
            Đang lọc: ${activeFilterDetails.join(", ")}
          </span>
          <button onclick="resetFilters()" style="margin-left: 8px; background: #fee2e2; border: 1px solid #fca5a5; color: #dc2626; font-size: 11.5px; font-weight: 700; cursor: pointer; padding: 2px 8px; border-radius: 4px;" title="Bỏ lọc để xem toàn bộ tất cả câu hỏi">✕ Bỏ lọc</button>
        `;
      } else {
        totalCountEl.innerHTML = `
          <span style="color: #475569; font-weight: 500;">Tổng câu hỏi: </span>
          <strong style="color: #16a34a; font-size: 15px;">${data.total || 0}</strong>
          <span style="color: #64748b; font-size: 12.5px; margin-left: 3px;">câu (Toàn bộ CSDL)</span>
          ${!isShowAll && data.total_pages > 1 ? `<span style="font-size: 11.5px; color: #64748b; margin-left: 5px;">— Trang ${data.page}/${data.total_pages}</span>` : ''}
        `;
      }
    }

    if (!data.items || data.items.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 60px 20px; background: white; border-radius: 14px; border: 1px dashed #cbd5e1;">
          <div style="font-size: 36px; margin-bottom: 12px;">🔍</div>
          <h3 style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">Không tìm thấy câu hỏi phù hợp</h3>
          <p style="font-size: 13.5px; color: #64748b; margin-bottom: 16px;">Hãy thử điều chỉnh bộ lọc hoặc nạp thêm câu hỏi mới từ Trung tâm Thu thập.</p>
          <button class="btn btn-primary" onclick="resetFilters()">Đặt lại bộ lọc</button>
        </div>
      `;
      renderPagination(0, 1);
      return;
    }

    container.innerHTML = data.items.map((q, idx) => renderQuestionCard(q, idx)).join("");

    // Render KaTeX for all math formulas in this container
    renderMath(container);

    // Sync Batch Action Toolbar & Header Checkbox
    if (typeof updateBatchToolbar === "function") {
      updateBatchToolbar();
    }

    // Render pagination
    renderPagination(data.total_pages, data.page, data.total);

  } catch (err) {
    console.error("Error loading questions:", err);
    container.innerHTML = `<div style="padding: 20px; color: #ef4444; text-align: center;">Lỗi tải dữ liệu: ${err.message}</div>`;
  }
}

function renderQuestionCard(q, idx) {
  const isSelected = State.selectedQuestionIds.has(q.id);
  const isBatchSelected = State.batchSelectedIds && State.batchSelectedIds.has(q.id);
  // Permanent global question number across the entire database
  const qNumber = q.q_number || ((State.filters.page - 1) * State.filters.page_size + idx + 1);

  const typeMap = {
    single_choice: "Trắc nghiệm 1 đáp án",
    multiple_choice: "Nhiều đáp án",
    fill_blank: "Điền số/từ vào ô trống",
    matching: "Ghép nối cặp",
    essay: "Tự luận"
  };

  const diffMap = {
    easy: "Dễ",
    medium: "Trung bình",
    hard: "Khó",
    olympiad: "Olympic"
  };

  const subMap = {
    math: "📐 Toán",
    vietnamese: "📖 Tiếng Việt",
    english: "🇬🇧 Tiếng Anh",
    science: "🔬 Khoa học",
    history_geo: "🏛️ Lịch sử - Địa lý",
    informatics: "💻 Tin học"
  };

  // Source Detail Badge
  let sourceDetailHtml = "";
  const rawDetail = (q.source_detail || "").trim();
  const rawPlat = (q.source_platform || "").trim().toLowerCase();

  // Guard against duplicate tag rendering if source_detail is identical to platform or raw "internet_hunter"
  if (rawDetail && rawDetail.toLowerCase() !== rawPlat && rawDetail.toLowerCase() !== "internet_hunter" && rawDetail.toLowerCase() !== "internet hunter") {
    let cls = "tag-source-detail";
    const sLower = rawDetail.toLowerCase();
    if (sLower.includes("codemath") || sLower.includes("timo") || sLower.includes("olympiad") || sLower.includes("hkimo") || sLower.includes("sasmo") || sLower.includes("asmo") || sLower.includes("seamo") || sLower.includes("fmo") || sLower.includes("ikmc")) {
      cls += " tag-source-codemath";
    } else if (sLower.includes("hành trang số") || sLower.includes("sgk") || sLower.includes("sbt") || sLower.includes("cánh diều") || sLower.includes("tri thức") || sLower.includes("chân trời")) {
      cls += " tag-source-sgk";
    } else if (sLower.includes("vioedu")) {
      cls += " tag-source-vioedu";
    } else if (sLower.includes("trạng nguyên")) {
      cls += " tag-source-trangnguyen";
    } else if (sLower.includes("ioe") || sLower.includes("english")) {
      cls += " tag-source-ioe";
    } else if (sLower.includes("kho đề") || sLower.includes("khoade")) {
      cls += " tag-source-khoade";
    } else if (sLower.includes("khoa học")) {
      cls += " tag-source-science";
    } else if (sLower.includes("tin học")) {
      cls += " tag-source-informatics";
    } else if (sLower.includes("olympic")) {
      cls += " tag-source-olympic";
    }
    sourceDetailHtml = `<span class="${cls}">🌐 ${rawDetail}</span>`;
  }

  // Options rendering
  let optionsHtml = "";
  if (q.options && q.options.length > 0) {
    optionsHtml = `
      <div class="options-grid">
        ${q.options.map(opt => `
          <div class="option-box ${opt.is_correct || opt.id === q.correct_answer ? 'is-correct-target' : ''}">
            <div class="opt-letter">${opt.id}</div>
            <div class="opt-content">${opt.content}</div>
          </div>
        `).join("")}
      </div>
    `;
  }

  // Local images rendering
  let imagesHtml = "";
  if (q.images && q.images.length > 0) {
    imagesHtml = `
      <div style="display: flex; gap: 12px; margin-bottom: 14px; flex-wrap: wrap;">
        ${q.images.map(img => `
          <img src="${img}" style="max-height: 180px; max-width: 100%; border-radius: 8px; border: 1px solid #e2e8f0; object-fit: contain;" alt="Hình ảnh câu hỏi" />
        `).join("")}
      </div>
    `;
  }

  const platformLabelMap = {
    vioedu: "VIOEDU",
    tnmath: "TRẠNG NGUYÊN",
    hanhtrangso: "HÀNH TRANG SỐ",
    internet_hunter: "INTERNET HUNTER",
    manual: "THỦ CÔNG",
    timo: "TIMO",
    hkimo: "HKIMO",
    asmo: "ASMO"
  };
  const platBadgeText = platformLabelMap[q.source_platform] || (q.source_platform || "").toUpperCase();

  return `
    <div class="question-card ${isBatchSelected ? 'is-batch-selected' : ''}" id="qcard-${q.id}">
      <div class="card-header">
        <div class="card-tags" style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
          <label class="q-batch-checkbox-wrap" style="display: inline-flex; align-items: center; margin-right: 4px; cursor: pointer;" title="Chọn câu hỏi này để thực hiện tác vụ hàng loạt">
            <input 
              type="checkbox" 
              class="q-batch-checkbox" 
              data-qid="${q.id}" 
              ${isBatchSelected ? 'checked' : ''} 
              onchange="toggleBatchQuestion('${q.id}', this.checked)" 
              style="width: 17px; height: 17px; cursor: pointer; accent-color: #2563eb; border-radius: 4px;"
            />
          </label>
          <span class="q-number-pill">Câu ${qNumber}</span>
          <span class="tag-badge subject-${q.subject || 'math'}">${subMap[q.subject] || q.subject || '📐 Toán'}</span>
          <span class="tag-badge platform-${q.source_platform}">${platBadgeText}</span>
          ${sourceDetailHtml}
          <span class="tag-grade">Lớp ${q.grade || 5}</span>
          <span class="tag-grade">${typeMap[q.question_type] || q.question_type}</span>
          <span class="tag-grade" style="background: #f1f5f9; color: #475569;">${diffMap[q.difficulty] || q.difficulty}</span>
          <span class="tag-topic">${q.topic || q.exam_name || ""}</span>
        </div>
        <div style="font-size: 12.5px; color: #1e3a8a; font-family: monospace; font-weight: 700; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          ${q.created_at ? `<span class="tag-timestamp">🕒 ${typeof formatDateTimeVN === 'function' ? formatDateTimeVN(q.created_at) : q.created_at}</span>` : ''}
          <span>ID: #${qNumber} <span style="font-size: 11px; color: #94a3b8; font-weight: normal;">(#${q.id.substring(0, 8)})</span></span>
        </div>
      </div>

      <div class="card-content">
        ${q.content_html}
      </div>

      ${imagesHtml}
      ${optionsHtml}

      <div class="solution-collapse" id="solution-${q.id}">
        <div style="font-weight: 700; color: #10b981; margin-bottom: 4px;">
          ✓ Đáp án: ${q.correct_answer || "Chưa cập nhật"}
        </div>
        <div style="color: #334155; line-height: 1.6;">
          ${q.explanation || "Không có giải thích chi tiết cho câu hỏi này."}
        </div>
      </div>

      <div class="card-footer">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <button class="btn ${isSelected ? 'btn-success' : 'btn-outline-primary'} btn-sm" onclick="toggleSelectQuestion('${q.id}')">
            ${isSelected ? '✓ Đã chọn vào Đề thi' : '+ Thêm vào Đề thi'}
          </button>
          <button class="btn btn-secondary btn-sm" onclick="toggleSolution('${q.id}')">
            💡 Đáp án & Lời giải
          </button>
        </div>
        <div class="card-actions" style="display: flex; align-items: center; gap: 6px;">
          <button class="btn btn-secondary btn-sm" title="Chỉnh sửa câu hỏi & đáp án" onclick="openEditQuestionModal('${q.id}')" style="font-weight: 600;">
            ✏️ Sửa
          </button>
          <button class="btn btn-secondary btn-sm" title="Sao chép LaTeX" onclick="copyLatex('${q.id}')">
            LaTeX
          </button>
          <button class="btn btn-secondary btn-sm" style="color: #ef4444;" title="Xóa câu hỏi" onclick="confirmDeleteQuestion('${q.id}', event)">
            ✕
          </button>
        </div>
      </div>
    </div>
  `;
}

function toggleSolution(qid) {
  const card = document.getElementById(`qcard-${qid}`);
  const el = document.getElementById(`solution-${qid}`);
  if (el) {
    const isOpen = el.classList.toggle("open");
    if (card) {
      card.classList.toggle("show-solution", isOpen);
    }
    if (isOpen) {
      renderMath(el);
    }
  }
}

function toggleSelectQuestion(qid) {
  if (State.selectedQuestionIds.has(qid)) {
    State.selectedQuestionIds.delete(qid);
    showToast("Đã bỏ chọn câu hỏi khỏi Đề thi", "info");
  } else {
    State.selectedQuestionIds.add(qid);
    showToast(`Đã thêm câu hỏi vào Đề thi (Tổng: ${State.selectedQuestionIds.size} câu)`);
  }
  updateSelectedBadge();
  const card = document.getElementById(`qcard-${qid}`);
  if (card) {
    const btn = card.querySelector(".btn-sm");
    const isSelected = State.selectedQuestionIds.has(qid);
    btn.className = `btn ${isSelected ? 'btn-success' : 'btn-outline-primary'} btn-sm`;
    btn.innerText = isSelected ? '✓ Đã chọn vào Đề thi' : '+ Thêm vào Đề thi';
  }
}

function updateSelectedBadge() {
  const badge = document.getElementById("selected-q-count");
  if (badge) badge.innerText = State.selectedQuestionIds.size;
}

function copyLatex(qid) {
  const q = State.cachedQuestions.find(item => item.id === qid);
  if (!q) return;
  const content = q.content_text || q.content_html;
  navigator.clipboard.writeText(content).then(() => {
    showToast("Đã sao chép nội dung câu hỏi!");
  });
}

async function confirmDeleteQuestion(qid, event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  if (document.activeElement && typeof document.activeElement.blur === "function") {
    document.activeElement.blur();
  }
  if (!confirm("Bạn có chắc chắn muốn xóa câu hỏi này khỏi ngân hàng?")) return;

  const card = document.getElementById(`qcard-${qid}`);
  const currentScrollY = window.scrollY;

  try {
    const res = await fetch(`${API_BASE}/questions/${qid}`, { method: "DELETE" });
    const data = await res.json();
    if (data.success) {
      showToast("Đã xóa câu hỏi thành công");
      State.selectedQuestionIds.delete(qid);
      if (State.batchSelectedIds) State.batchSelectedIds.delete(qid);
      updateSelectedBadge();
      if (typeof updateBatchToolbar === "function") updateBatchToolbar();

      // Cập nhật State.cachedQuestions
      State.cachedQuestions = State.cachedQuestions.filter(item => item.id !== qid);

      // Hiệu ứng xóa mượt mà
      if (card) {
        card.style.transition = "all 0.35s cubic-bezier(0.4, 0, 0.2, 1)";
        card.style.opacity = "0";
        card.style.transform = "translateY(-12px) scale(0.97)";
        card.style.maxHeight = card.offsetHeight + "px";
        card.offsetHeight; // trigger reflow
        card.style.maxHeight = "0px";
        card.style.marginTop = "0px";
        card.style.marginBottom = "0px";
        card.style.paddingTop = "0px";
        card.style.paddingBottom = "0px";
        card.style.borderWidth = "0px";
        card.style.overflow = "hidden";

        setTimeout(() => {
          card.remove();
          const container = document.getElementById("questions-list-container");
          if (container && container.querySelectorAll(".question-card").length === 0) {
            loadQuestions();
          }
        }, 360);
      }

      // Cập nhật bộ đếm hiển thị trên UI
      updateBankCountersAfterDelete(1);
      loadDashboardStats();
      window.scrollTo({ top: currentScrollY, behavior: "instant" });
    } else {
      showToast(data.detail || "Không thể xóa câu hỏi", "error");
    }
  } catch (err) {
    showToast("Lỗi kết nối khi xóa câu hỏi", "error");
  }
}

function updateBankCountersAfterDelete(deletedCount) {
  const totalCountEl = document.getElementById("bank-total-count");
  if (totalCountEl) {
    const match = totalCountEl.innerText.match(/^(\d+)/);
    if (match) {
      const current = parseInt(match[1]);
      const nextCount = Math.max(0, current - deletedCount);
      totalCountEl.innerText = `${nextCount} câu hỏi`;
    }
  }
}

function syncFilterChips() {
  document.querySelectorAll(".chip").forEach(chip => {
    chip.classList.toggle("active", chip.dataset.platform === State.filters.platform);
  });
  document.querySelectorAll(".subject-tab").forEach(tab => {
    tab.classList.toggle("active", tab.dataset.subject === State.filters.subject);
  });
  const subSel = document.getElementById("filter-subject");
  if (subSel) subSel.value = State.filters.subject || "all";
  const gradeSel = document.getElementById("filter-grade");
  if (gradeSel) gradeSel.value = State.filters.grade || "";
  const sizeSel = document.getElementById("filter-page-size");
  if (sizeSel) sizeSel.value = State.filters.page_size || 50;
  const sourceSel = document.getElementById("filter-source-detail");
  if (sourceSel) sourceSel.value = State.filters.source_detail || "all";
  const dupeChk = document.getElementById("filter-only-dupes");
  if (dupeChk) dupeChk.checked = !!State.filters.only_duplicates;
  const sortSel = document.getElementById("filter-sort");
  if (sortSel) sortSel.value = State.filters.sort_by || "q_number_asc";
}

function setPlatformFilter(plat) {
  State.filters.platform = plat;
  State.filters.page = 1;
  loadQuestions();
}

function setSubjectFilter(sub) {
  State.filters.subject = sub;
  State.filters.page = 1;
  const subSel = document.getElementById("filter-subject");
  if (subSel) subSel.value = sub;
  loadQuestions();
}

function setPageSize(size) {
  State.filters.page_size = parseInt(size) || 50;
  State.filters.page = 1;
  const sizeSel = document.getElementById("filter-page-size");
  if (sizeSel) sizeSel.value = size;
  loadQuestions();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resetFilters() {
  State.filters = {
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
    page_size: State.filters.page_size || 50
  };
  const searchInput = document.getElementById("search-input");
  if (searchInput) searchInput.value = "";
  const clearBtn = document.getElementById("search-clear-btn");
  if (clearBtn) clearBtn.style.display = "none";
  const filterGrade = document.getElementById("filter-grade");
  if (filterGrade) filterGrade.value = "";
  const filterSub = document.getElementById("filter-subject");
  if (filterSub) filterSub.value = "all";
  const filterType = document.getElementById("filter-type");
  if (filterType) filterType.value = "all";
  const filterDiff = document.getElementById("filter-diff");
  if (filterDiff) filterDiff.value = "all";
  const filterSrc = document.getElementById("filter-source-detail");
  if (filterSrc) filterSrc.value = "all";
  const dupeChk = document.getElementById("filter-only-dupes");
  if (dupeChk) dupeChk.checked = false;
  const sortSel = document.getElementById("filter-sort");
  if (sortSel) sortSel.value = "q_number_asc";
  loadQuestions();
}

function renderPagination(totalPages, currentPage, totalItems = 0) {
  const container = document.getElementById("pagination-container");
  if (!container) return;

  const currentSize = State.filters.page_size || 50;
  const isShowAll = currentSize >= 9999;

  let sizeOptions = [15, 30, 50, 100, 9999];
  let sizeOptionsHtml = sizeOptions.map(sz => {
    const label = sz >= 9999 ? "Tất cả (Xem hết)" : `${sz} câu / trang`;
    return `<option value="${sz}" ${sz === currentSize ? 'selected' : ''}>${label}</option>`;
  }).join("");

  let paginationButtonsHtml = "";
  if (totalPages > 1 && !isShowAll) {
    paginationButtonsHtml = `
      <div style="display: flex; gap: 4px; align-items: center; justify-content: center; flex-wrap: wrap;">
        <button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">« Trước</button>
    `;
    for (let i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
        paginationButtonsHtml += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
      } else if (i === currentPage - 3 || i === currentPage + 3) {
        paginationButtonsHtml += `<span style="padding: 0 4px; color: #94a3b8;">...</span>`;
      }
    }
    paginationButtonsHtml += `
        <button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">Sau »</button>
      </div>
    `;
  }

  const startIdx = isShowAll ? 1 : (currentPage - 1) * currentSize + 1;
  const endIdx = isShowAll ? totalItems : Math.min(currentPage * currentSize, totalItems);

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; flex-wrap: wrap; gap: 12px; padding: 14px 18px; background: white; border-radius: 12px; border: 1px solid #e2e8f0; margin-top: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
      <div style="font-size: 13px; color: #475569; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
        <span>📊 Đang xem câu <strong>${totalItems > 0 ? startIdx : 0} - ${endIdx}</strong> / tổng <strong>${totalItems}</strong> câu</span>
        ${!isShowAll && totalItems > currentSize ? `<button onclick="setPageSize(9999)" style="background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; font-size: 11.5px; font-weight: 700; cursor: pointer; padding: 3px 10px; border-radius: 6px;" title="Hiển thị tất cả trên 1 trang không cần chuyển trang">👁️ Xem tất cả trên 1 trang</button>` : ''}
        ${isShowAll ? `<span style="font-size: 12px; color: #16a34a; font-weight: 700; background: #f0fdf4; border: 1px solid #bbf7d0; padding: 2px 8px; border-radius: 6px;">✓ Đang hiển thị toàn bộ</span>` : ''}
      </div>

      ${paginationButtonsHtml}

      <div style="display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: #64748b;">
        <span>Số câu / trang:</span>
        <select onchange="setPageSize(this.value)" style="padding: 5px 10px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; font-weight: 700; color: #1e40af; background: #eff6ff; cursor: pointer;">
          ${sizeOptionsHtml}
        </select>
      </div>
    </div>
  `;
}

function goToPage(page) {
  State.filters.page = page;
  loadQuestions();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Search debounce & Clear button
let searchTimeout = null;
function handleSearchInput(val) {
  const clearBtn = document.getElementById("search-clear-btn");
  if (clearBtn) {
    clearBtn.style.display = val.trim().length > 0 ? "inline-flex" : "none";
  }
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    State.filters.search = val.trim();
    State.filters.page = 1;
    loadQuestions();
  }, 350);
}

function clearSearchInput() {
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("search-clear-btn");
  if (searchInput) {
    searchInput.value = "";
    searchInput.focus();
  }
  if (clearBtn) {
    clearBtn.style.display = "none";
  }
  clearTimeout(searchTimeout);
  State.filters.search = "";
  State.filters.page = 1;
  loadQuestions();
}

// ==========================================
// Question Editing Modal Handlers
// ==========================================
async function openEditQuestionModal(qid) {
  let q = State.cachedQuestions.find(item => item.id === qid);
  if (!q) {
    try {
      const res = await fetch(`${API_BASE}/questions/${qid}`);
      q = await res.json();
    } catch (e) {
      showToast("Không tìm thấy thông tin câu hỏi", "error");
      return;
    }
  }
  cachedEditingQuestion = q;

  document.getElementById("edit-q-id").value = q.id;
  const qNumBadge = document.getElementById("edit-q-num-badge");
  if (qNumBadge) qNumBadge.innerText = q.q_number ? `#${q.q_number}` : `#${q.id.substring(0, 8)}`;
  document.getElementById("edit-q-subject").value = q.subject || "math";
  document.getElementById("edit-q-grade").value = q.grade || 5;
  document.getElementById("edit-q-diff").value = q.difficulty || "medium";
  document.getElementById("edit-q-topic").value = q.topic || "";
  document.getElementById("edit-q-type").value = q.question_type || "single_choice";
  document.getElementById("edit-q-content").value = q.content_text || q.content_html || "";
  document.getElementById("edit-q-correct").value = q.correct_answer || "A";
  document.getElementById("edit-q-explanation").value = q.explanation || "";

  // Options A, B, C, D
  document.getElementById("edit-q-opt-a").value = "";
  document.getElementById("edit-q-opt-b").value = "";
  document.getElementById("edit-q-opt-c").value = "";
  document.getElementById("edit-q-opt-d").value = "";

  if (q.options && q.options.length > 0) {
    q.options.forEach(opt => {
      const idUpper = (opt.id || "").toUpperCase();
      if (idUpper === "A") document.getElementById("edit-q-opt-a").value = opt.content || "";
      if (idUpper === "B") document.getElementById("edit-q-opt-b").value = opt.content || "";
      if (idUpper === "C") document.getElementById("edit-q-opt-c").value = opt.content || "";
      if (idUpper === "D") document.getElementById("edit-q-opt-d").value = opt.content || "";
    });
  }

  updateEditQuestionPreview();
  document.getElementById("modal-edit-question").classList.add("open");
}

function closeEditQuestionModal() {
  const modal = document.getElementById("modal-edit-question");
  if (modal) modal.classList.remove("open");
  cachedEditingQuestion = null;
}

function updateEditQuestionPreview() {
  const content = document.getElementById("edit-q-content").value.trim();
  const preview = document.getElementById("edit-q-preview");
  if (!preview) return;

  if (!content) {
    preview.innerHTML = `<span style="color: #94a3b8; font-style: italic;">Chưa nhập nội dung câu hỏi</span>`;
    return;
  }
  preview.innerHTML = content.replace(/\n/g, "<br/>");
  renderMath(preview);
}

async function saveEditedQuestion() {
  const qid = document.getElementById("edit-q-id").value;
  const content = document.getElementById("edit-q-content").value.trim();

  if (!content) {
    showToast("Vui lòng nhập nội dung câu hỏi", "error");
    return;
  }

  const optA = document.getElementById("edit-q-opt-a").value.trim();
  const optB = document.getElementById("edit-q-opt-b").value.trim();
  const optC = document.getElementById("edit-q-opt-c").value.trim();
  const optD = document.getElementById("edit-q-opt-d").value.trim();
  const correct = document.getElementById("edit-q-correct").value;

  const options = [];
  if (optA) options.push({ id: "A", content: optA, is_correct: correct === "A" });
  if (optB) options.push({ id: "B", content: optB, is_correct: correct === "B" });
  if (optC) options.push({ id: "C", content: optC, is_correct: correct === "C" });
  if (optD) options.push({ id: "D", content: optD, is_correct: correct === "D" });

  const payload = {
    id: qid,
    q_number: cachedEditingQuestion?.q_number,
    source_platform: cachedEditingQuestion?.source_platform || "manual",
    source_detail: cachedEditingQuestion?.source_detail || "",
    grade: parseInt(document.getElementById("edit-q-grade").value) || 5,
    subject: document.getElementById("edit-q-subject").value || "math",
    topic: document.getElementById("edit-q-topic").value.trim(),
    question_type: document.getElementById("edit-q-type").value,
    content_html: `<p>${content}</p>`,
    content_text: content,
    options: options,
    correct_answer: correct,
    difficulty: document.getElementById("edit-q-diff").value,
    explanation: document.getElementById("edit-q-explanation").value.trim()
  };

  try {
    const res = await fetch(`${API_BASE}/questions/${qid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast("Đã lưu cập nhật câu hỏi thành công!");
      closeEditQuestionModal();
      loadQuestions();
      loadDashboardStats();
    } else {
      showToast(data.message || "Lỗi lưu câu hỏi", "error");
    }
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  }
}

// ==========================================
// Duplicates Management Handlers
// ==========================================
async function openDuplicatesModal() {
  const modal = document.getElementById("modal-duplicates");
  const container = document.getElementById("duplicates-list-container");
  const summaryText = document.getElementById("dupe-summary-text");
  if (!modal || !container) return;

  modal.classList.add("open");
  container.innerHTML = `
    <div style="text-align: center; padding: 30px; color: #64748b;">
      <div style="font-size: 24px; margin-bottom: 6px;">⏳</div>
      <p>Đang quét đối chiếu toàn bộ CSDL tìm câu hỏi trùng lặp...</p>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/questions/duplicates`);
    const data = await res.json();

    if (!data.success) {
      container.innerHTML = `<div style="color: #ef4444; padding: 20px;">Lỗi: ${data.message}</div>`;
      return;
    }

    if (summaryText) {
      summaryText.innerText = `Phát hiện: ${data.total_duplicate_groups} nhóm câu hỏi trùng lặp (${data.total_duplicate_copies} bản sao dư thừa)`;
    }

    if (data.groups.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 40px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; color: #15803d;">
          <div style="font-size: 32px; margin-bottom: 8px;">🎉</div>
          <div style="font-weight: 700; font-size: 15px;">Tuyệt vời! Không có câu hỏi trùng lặp nào trong CSDL.</div>
          <p style="font-size: 12.5px; color: #166534; margin-top: 4px;">Hệ thống đang hoạt động tối ưu với 100% câu hỏi độc nhất.</p>
        </div>
      `;
      const btnClean = document.getElementById("btn-clean-dupes-auto");
      if (btnClean) btnClean.style.display = "none";
      return;
    }

    const btnClean = document.getElementById("btn-clean-dupes-auto");
    if (btnClean) btnClean.style.display = "block";

    container.innerHTML = data.groups.map((grp, gIdx) => `
      <div class="dupe-group-box">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px;">
          <div style="font-weight: 700; font-size: 13px; color: #be123c;">
            Nhóm ${gIdx + 1} (${grp.duplicate_count} bản ghi giống nhau):
          </div>
          <span style="font-size: 11px; background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 10px; font-weight: 700;">
            ${grp.duplicate_count} copies
          </span>
        </div>
        <div style="font-size: 13px; line-height: 1.5; color: #1e293b; background: #f8fafc; padding: 8px 12px; border-radius: 6px;">
          ${grp.content_text_preview}
        </div>
        <div style="display: flex; flex-direction: column; gap: 4px; margin-top: 4px;">
          ${grp.items.map((item, iIdx) => `
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; padding: 4px 8px; border-radius: 4px; background: ${iIdx === 0 ? '#ecfdf5' : '#ffffff'}; border: 1px solid ${iIdx === 0 ? '#a7f3d0' : '#f1f5f9'};">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-weight: 700; color: ${iIdx === 0 ? '#047857' : '#64748b'};">
                  ${iIdx === 0 ? '✓ BẢN GỐC (CŨ NHẤT)' : `Bản sao #${iIdx}`}
                </span>
                <span style="color: #64748b;">ID: #${item.id.substring(0, 10)}</span>
                <span class="tag-badge platform-${item.source_platform}">${item.source_platform}</span>
                <span style="color: #94a3b8; font-size: 11px;">${item.created_at || ''}</span>
              </div>
              ${iIdx > 0 ? `
                <button class="btn btn-secondary btn-sm" onclick="deleteSingleDuplicate('${item.id}')" style="color: #ef4444; font-size: 11px; padding: 2px 8px;">
                  Xóa bản sao
                </button>
              ` : `
                <span style="font-size: 11px; color: #059669; font-weight: 700;">Giữ lại</span>
              `}
            </div>
          `).join("")}
        </div>
      </div>
    `).join("");

    renderMath(container);

  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444; padding: 20px;">Lỗi: ${err.message}</div>`;
  }
}

function closeDuplicatesModal() {
  const modal = document.getElementById("modal-duplicates");
  if (modal) modal.classList.remove("open");
}

async function cleanDuplicatesAuto() {
  if (!confirm("Hệ thống sẽ giữ lại bản ghi cũ nhất của mỗi câu hỏi và xóa tất cả các bản sao thừa. Bạn có chắc chắn muốn thực hiện?")) return;

  const btn = document.getElementById("btn-clean-dupes-auto");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Đang dọn dẹp...";
  }

  try {
    const res = await fetch(`${API_BASE}/questions/duplicates/clean`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "keep_oldest" })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Đã dọn dẹp sạch ${data.deleted_count} câu hỏi trùng lặp!`);
      closeDuplicatesModal();
      loadQuestions();
      loadDashboardStats();
    } else {
      showToast(data.message || "Lỗi khi dọn câu hỏi", "error");
    }
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "🧹 Xóa sạch bản sao (1-Click)";
    }
  }
}

async function deleteSingleDuplicate(id) {
  try {
    const res = await fetch(`${API_BASE}/questions/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (data.success) {
      showToast("Đã xóa bản sao trùng lặp");
      openDuplicatesModal();
      loadDashboardStats();
      loadQuestions();
    }
  } catch (err) {
    showToast("Lỗi xóa", "error");
  }
}

// ==========================================
// Database Diagnostics & Auto-Fix Handlers
// ==========================================
async function openDiagnosticsModal() {
  const modal = document.getElementById("modal-db-diagnostics");
  const container = document.getElementById("db-diag-content");
  if (!modal || !container) return;

  modal.classList.add("open");
  container.innerHTML = `
    <div style="text-align: center; padding: 30px; color: #64748b;">
      <div style="font-size: 24px; margin-bottom: 6px;">🩺</div>
      <p>Đang kiểm tra toàn vẹn và phân tích cơ sở dữ liệu SQLite...</p>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/database/diagnostics`);
    const data = await res.json();

    if (!data.success) {
      container.innerHTML = `<div style="color: #ef4444; padding: 20px;">Lỗi: ${data.message}</div>`;
      return;
    }

    const diag = data.diagnostics;
    const isIntegrityOk = diag.sqlite_integrity === "ok";

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-radius: 8px; margin-bottom: 14px; background: ${isIntegrityOk ? '#f0fdf4' : '#fef2f2'}; border: 1px solid ${isIntegrityOk ? '#bbf7d0' : '#fecdd3'};">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-size: 20px;">${isIntegrityOk ? '🛡️' : '⚠️'}</span>
          <div>
            <div style="font-weight: 700; font-size: 13.5px; color: ${isIntegrityOk ? '#15803d' : '#b91c1c'};">
              Trạng thái Toàn vẹn SQLite: ${diag.sqlite_integrity.toUpperCase()}
            </div>
            <div style="font-size: 12px; color: #64748b;">PRAGMA integrity_check xác thực cấu trúc B-Tree cơ sở dữ liệu</div>
          </div>
        </div>
        <span style="font-size: 12px; font-weight: 700; color: ${isIntegrityOk ? '#166534' : '#991b1b'};">
          ${isIntegrityOk ? 'Cấu trúc hoàn hảo' : 'Phát hiện sự cố'}
        </span>
      </div>

      <div class="diag-stat-grid">
        <div class="diag-stat-card">
          <div class="diag-stat-num">${diag.total_questions}</div>
          <div class="diag-stat-label">Tổng số bản ghi</div>
        </div>
        <div class="diag-stat-card">
          <div class="diag-stat-num" style="color: #0284c7;">${diag.unique_questions}</div>
          <div class="diag-stat-label">Câu hỏi độc nhất</div>
        </div>
        <div class="diag-stat-card">
          <div class="diag-stat-num" style="color: ${diag.duplicate_copies_count > 0 ? '#e11d48' : '#10b981'};">
            ${diag.duplicate_copies_count}
          </div>
          <div class="diag-stat-label">Bản sao trùng lặp</div>
        </div>
        <div class="diag-stat-card">
          <div class="diag-stat-num" style="color: #64748b;">${diag.anomalies?.no_options || 0}</div>
          <div class="diag-stat-label">Câu điền số/tự luận</div>
        </div>
        <div class="diag-stat-card">
          <div class="diag-stat-num" style="color: #d97706;">${diag.anomalies?.no_correct_answer || 0}</div>
          <div class="diag-stat-label">Chưa gán đáp án</div>
        </div>
        <div class="diag-stat-card">
          <div class="diag-stat-num" style="color: #64748b;">${diag.anomalies?.no_explanation || 0}</div>
          <div class="diag-stat-label">Chưa có lời giải</div>
        </div>
      </div>

      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px;">
        <div style="font-weight: 700; font-size: 13px; color: #334155; margin-bottom: 8px;">
          📊 Bảng dữ liệu trong Cơ sở dữ liệu:
        </div>
        <div style="display: flex; gap: 20px; font-size: 12.5px; color: #475569;">
          <div>Bảng <code>questions</code>: <strong>${diag.table_stats?.questions || 0}</strong> dòng</div>
          <div>Bảng <code>exams</code>: <strong>${diag.table_stats?.exams || 0}</strong> dòng</div>
          <div>Bảng <code>system_logs</code>: <strong>${diag.table_stats?.system_logs || 0}</strong> dòng</div>
        </div>
      </div>
    `;

  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444; padding: 20px;">Lỗi: ${err.message}</div>`;
  }
}

function closeDiagnosticsModal() {
  const modal = document.getElementById("modal-db-diagnostics");
  if (modal) modal.classList.remove("open");
}

async function runDbAutoFix() {
  const btn = document.getElementById("btn-db-fix");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Đang sửa chữa CSDL...";
  }

  try {
    const res = await fetch(`${API_BASE}/database/diagnostics/fix`, { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast(`Đã tự động sửa chữa CSDL thành công! Đã xóa ${data.details?.deleted_duplicates || 0} bản sao trùng lặp.`);
      openDiagnosticsModal();
      loadDashboardStats();
      loadQuestions();
    } else {
      showToast(data.message || "Lỗi khi sửa chữa CSDL", "error");
    }
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "🛠️ Tự động Sửa Chữa Toàn Diện";
    }
  }
}

// ----------------- Batch Operations: Multiple Selection & Actions -----------------

function toggleBatchQuestion(qid, isChecked) {
  if (!State.batchSelectedIds) State.batchSelectedIds = new Set();
  const card = document.getElementById(`qcard-${qid}`);
  if (isChecked) {
    State.batchSelectedIds.add(qid);
    if (card) card.classList.add("is-batch-selected");
  } else {
    State.batchSelectedIds.delete(qid);
    if (card) card.classList.remove("is-batch-selected");
  }
  updateBatchToolbar();
}

function toggleSelectAllPage(isChecked) {
  if (!State.batchSelectedIds) State.batchSelectedIds = new Set();
  const checkboxes = document.querySelectorAll(".q-batch-checkbox");
  checkboxes.forEach(cb => {
    const qid = cb.dataset.qid;
    cb.checked = isChecked;
    const card = document.getElementById(`qcard-${qid}`);
    if (isChecked) {
      State.batchSelectedIds.add(qid);
      if (card) card.classList.add("is-batch-selected");
    } else {
      State.batchSelectedIds.delete(qid);
      if (card) card.classList.remove("is-batch-selected");
    }
  });
  updateBatchToolbar();
}

function selectAllPage() {
  const chk = document.getElementById("chk-select-all-page");
  if (chk) chk.checked = true;
  toggleSelectAllPage(true);
}

function deselectAllBatch() {
  if (!State.batchSelectedIds) State.batchSelectedIds = new Set();
  State.batchSelectedIds.clear();
  document.querySelectorAll(".q-batch-checkbox").forEach(cb => cb.checked = false);
  document.querySelectorAll(".question-card.is-batch-selected").forEach(card => card.classList.remove("is-batch-selected"));
  const chk = document.getElementById("chk-select-all-page");
  if (chk) chk.checked = false;
  updateBatchToolbar();
}

function updateBatchToolbar() {
  if (!State.batchSelectedIds) State.batchSelectedIds = new Set();
  const count = State.batchSelectedIds.size;
  const toolbar = document.getElementById("batch-action-toolbar");
  const countEl = document.getElementById("batch-toolbar-count");
  const delCountEl = document.getElementById("batch-delete-btn-count");
  const labelEl = document.getElementById("page-selected-count-label");
  const chkAll = document.getElementById("chk-select-all-page");

  if (countEl) countEl.innerText = count;
  if (delCountEl) delCountEl.innerText = count;
  if (labelEl) labelEl.innerText = `(Đã chọn ${count} câu)`;

  if (toolbar) {
    if (count >= 1) {
      toolbar.classList.add("active");
    } else {
      toolbar.classList.remove("active");
    }
  }

  // Check if all on current page are selected
  const pageCheckboxes = document.querySelectorAll(".q-batch-checkbox");
  if (pageCheckboxes.length > 0 && chkAll) {
    const allChecked = Array.from(pageCheckboxes).every(cb => cb.checked);
    chkAll.checked = allChecked;
  }
}

async function executeBulkDelete() {
  if (!State.batchSelectedIds || State.batchSelectedIds.size === 0) {
    showToast("Vui lòng chọn ít nhất 1 câu hỏi để xóa hàng loạt", "error");
    return;
  }
  const count = State.batchSelectedIds.size;
  if (!confirm(`Bạn có chắc chắn muốn xóa ${count} câu hỏi đã chọn? Thao tác này không thể hoàn tác.`)) {
    return;
  }

  if (document.activeElement && typeof document.activeElement.blur === "function") {
    document.activeElement.blur();
  }
  const currentScrollY = window.scrollY;
  const idsToDelete = Array.from(State.batchSelectedIds);

  try {
    const res = await fetch(`${API_BASE}/questions/bulk-delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_ids: idsToDelete })
    });
    const data = await res.json();
    if (data.success || data.status === "success") {
      const deletedCount = data.deleted_count || idsToDelete.length;
      showToast(`Đã xóa thành công ${deletedCount} câu hỏi!`);

      // Animate and remove cards
      idsToDelete.forEach(qid => {
        State.selectedQuestionIds.delete(qid);
        State.batchSelectedIds.delete(qid);
        State.cachedQuestions = State.cachedQuestions.filter(item => item.id !== qid);

        const card = document.getElementById(`qcard-${qid}`);
        if (card) {
          card.style.transition = "all 0.35s cubic-bezier(0.4, 0, 0.2, 1)";
          card.style.opacity = "0";
          card.style.transform = "translateY(-12px) scale(0.97)";
          card.style.maxHeight = card.offsetHeight + "px";
          card.offsetHeight;
          card.style.maxHeight = "0px";
          card.style.marginTop = "0px";
          card.style.marginBottom = "0px";
          card.style.paddingTop = "0px";
          card.style.paddingBottom = "0px";
          card.style.borderWidth = "0px";
          card.style.overflow = "hidden";
          setTimeout(() => card.remove(), 360);
        }
      });

      updateSelectedBadge();
      updateBatchToolbar();
      updateBankCountersAfterDelete(deletedCount);
      loadDashboardStats();
      window.scrollTo({ top: currentScrollY, behavior: "instant" });

      setTimeout(() => {
        const container = document.getElementById("questions-list-container");
        if (container && container.querySelectorAll(".question-card").length === 0) {
          loadQuestions();
        }
      }, 400);
    } else {
      showToast(data.detail || data.message || "Lỗi khi xóa hàng loạt", "error");
    }
  } catch (err) {
    showToast(`Lỗi kết nối khi xóa hàng loạt: ${err.message}`, "error");
  }
}

async function executeBulkUpdateGrade() {
  if (!State.batchSelectedIds || State.batchSelectedIds.size === 0) {
    showToast("Vui lòng chọn ít nhất 1 câu hỏi để đổi khối lớp", "error");
    return;
  }
  const gradeSelect = document.getElementById("batch-target-grade");
  const targetGrade = parseInt(gradeSelect?.value) || 5;
  const idsToUpdate = Array.from(State.batchSelectedIds);

  try {
    const res = await fetch(`${API_BASE}/questions/bulk-update-grade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_ids: idsToUpdate, grade: targetGrade })
    });
    const data = await res.json();
    if (data.success || data.status === "success") {
      const updatedCount = data.updated_count || idsToUpdate.length;
      showToast(`Đã cập nhật khối lớp thành Lớp ${targetGrade} cho ${updatedCount} câu hỏi!`);

      // Update cards in-place
      idsToUpdate.forEach(qid => {
        const card = document.getElementById(`qcard-${qid}`);
        if (card) {
          const gradeTags = card.querySelectorAll(".tag-grade");
          gradeTags.forEach(gt => {
            if (gt.innerText.includes("Lớp")) {
              gt.innerText = `Lớp ${targetGrade}`;
            }
          });
        }
        const cachedItem = State.cachedQuestions.find(item => item.id === qid);
        if (cachedItem) cachedItem.grade = targetGrade;
      });

      loadDashboardStats();
    } else {
      showToast(data.detail || data.message || "Lỗi khi đổi khối lớp", "error");
    }
  } catch (err) {
    showToast(`Lỗi kết nối khi đổi khối lớp: ${err.message}`, "error");
  }
}
