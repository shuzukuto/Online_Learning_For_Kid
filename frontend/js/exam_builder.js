// EduQuest Pro - Exam Builder, Auto Matrix Generator & Word Exporter
let examQuestionsList = [];

// ==========================================
// Auto Exam Matrix Generator Functions
// ==========================================
function validateMatrixCounts() {
  const total = parseInt(document.getElementById("matrix-total")?.value) || 0;
  const easy = parseInt(document.getElementById("matrix-easy")?.value) || 0;
  const med = parseInt(document.getElementById("matrix-medium")?.value) || 0;
  const hard = parseInt(document.getElementById("matrix-hard")?.value) || 0;
  const sum = easy + med + hard;

  const statusText = document.getElementById("matrix-status-text");
  if (!statusText) return;

  if (sum === total) {
    statusText.style.color = "#1e40af";
    statusText.innerHTML = `✓ Cơ cấu ma trận khớp: ${easy} Dễ + ${med} TB + ${hard} Khó = ${total} câu`;
  } else {
    statusText.style.color = "#b91c1c";
    statusText.innerHTML = `⚠️ Tổng các độ khó (${sum} câu: ${easy} Dễ + ${med} TB + ${hard} Khó) chưa khớp với Tổng số câu (${total} câu)`;
  }
}

function applyMatrixPreset(total, easy, med, hard) {
  const tEl = document.getElementById("matrix-total");
  const eEl = document.getElementById("matrix-easy");
  const mEl = document.getElementById("matrix-medium");
  const hEl = document.getElementById("matrix-hard");

  if (tEl) tEl.value = total;
  if (eEl) eEl.value = easy;
  if (mEl) mEl.value = med;
  if (hEl) hEl.value = hard;

  validateMatrixCounts();
  showToast(`Đã áp dụng mẫu ma trận ${total} câu (${easy} Dễ - ${med} TB - ${hard} Khó)`, "info");
}

async function autoGenerateExamByMatrix() {
  const btn = document.getElementById("btn-auto-matrix");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Đang tạo đề...";
  }

  const subject = document.getElementById("matrix-subject")?.value || "math";
  const grade = parseInt(document.getElementById("matrix-grade")?.value) || 5;
  const total = parseInt(document.getElementById("matrix-total")?.value) || 20;
  const easy = parseInt(document.getElementById("matrix-easy")?.value) || 8;
  const medium = parseInt(document.getElementById("matrix-medium")?.value) || 8;
  const hard = parseInt(document.getElementById("matrix-hard")?.value) || 4;
  const topic = document.getElementById("matrix-topic")?.value.trim() || undefined;

  const payload = {
    subject,
    grade,
    total_questions: total,
    easy_count: easy,
    medium_count: medium,
    hard_count: hard,
    topic: topic || undefined,
    title: `ĐỀ THI ${subject.toUpperCase()} LỚP ${grade}`
  };

  try {
    const res = await fetch(`${API_BASE}/exams/auto-generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (!data.success) {
      showToast(data.message || "Không thể tạo đề theo ma trận", "error");
      return;
    }

    if (!data.question_ids || data.question_ids.length === 0) {
      showToast("Không tìm thấy câu hỏi phù hợp trong CSDL để tạo ma trận đề", "error");
      return;
    }

    State.selectedQuestionIds = new Set(data.question_ids);
    updateSelectedBadge();

    const divScore = data.diversity_score !== undefined ? `${data.diversity_score}%` : "100%";
    showToast(`✓ Đã tự động tạo đề thi đa dạng (${data.count} câu, độ đa dạng ${divScore} - không trùng dạng bài)!`, "success");
    renderExamBuilderView();

  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "🎲 Tự động Tạo Đề theo Ma trận";
    }
  }
}

// ==========================================
// Exam Builder View Rendering & Management
// ==========================================
let currentExamDiversity = null;

async function renderExamBuilderView(skipFetch = false) {
  const container = document.getElementById("exam-builder-content");
  if (!container) return;

  const count = State.selectedQuestionIds.size;
  const countPill = document.getElementById("builder-count-pill");
  if (countPill) countPill.innerText = `${count} câu đã chọn`;

  if (count === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 50px 20px; background: white; border-radius: 14px; border: 1px dashed #cbd5e1;">
        <div style="font-size: 38px; margin-bottom: 12px;">📝</div>
        <h3 style="font-size: 16px; font-weight: 700; margin-bottom: 6px;">Chưa có câu hỏi nào trong Đề thi</h3>
        <p style="font-size: 13.5px; color: #64748b; margin-bottom: 18px; max-width: 500px; margin-left: auto; margin-right: auto;">
          Hãy dùng <strong>Ma trận Tạo Đề Tự Động</strong> ở khung trên để máy tính chọn đề ngay trong 1 click, hoặc chọn câu hỏi thủ công từ <strong>Ngân hàng Câu hỏi</strong>.
        </p>
        <button class="btn btn-secondary" onclick="switchView('bank')">Đến Ngân hàng Câu hỏi →</button>
      </div>
    `;
    return;
  }

  if (!skipFetch) {
    container.innerHTML = `
      <div style="text-align: center; padding: 40px; color: #64748b;">
        <div style="font-size: 24px; margin-bottom: 8px;">⏳</div>
        <p>Đang chuẩn bị đề thi & kiểm tra độ đa dạng dạng bài...</p>
      </div>
    `;

    try {
      const qIds = Array.from(State.selectedQuestionIds);
      const fetchPromises = qIds.map(id => fetch(`${API_BASE}/questions/${id}`).then(r => r.json()));
      examQuestionsList = await Promise.all(fetchPromises);
    } catch (err) {
      console.error("Error preparing exam:", err);
      container.innerHTML = `<div style="color: #ef4444; padding: 20px;">Lỗi tải chi tiết câu hỏi: ${err.message}</div>`;
      return;
    }
  }

  // Analyze diversity
  let divData = { diversity_score: 100, duplicate_count: 0, duplicate_question_ids: [], archetypes: {} };
  try {
    const qIds = examQuestionsList.map(q => q.id);
    const divRes = await fetch(`${API_BASE}/exams/analyze-diversity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_ids: qIds })
    });
    if (divRes.ok) {
      divData = await divRes.json();
      currentExamDiversity = divData;
    }
  } catch (err) {
    console.warn("Could not analyze exam diversity:", err);
  }

  const dupIdsSet = new Set(divData.duplicate_question_ids || []);
  const duplicateCount = divData.duplicate_count || 0;
  const diversityScore = divData.diversity_score !== undefined ? divData.diversity_score : 100;

  const currentExamCode = document.getElementById("exam-code-input")?.value || "101";

  container.innerHTML = `
    <div class="exam-builder-layout">
      <!-- Left: Configuration Form -->
      <div class="exam-sidebar-card">
        <h3 style="font-size: 15px; font-weight: 700; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px;">
          Cấu hình Đề thi Mẫu In
        </h3>

        <div class="form-group">
          <label class="form-label">Tiêu đề Kỳ thi / Bài kiểm tra</label>
          <input type="text" id="exam-title-input" class="form-control" value="ĐỀ KHẢO SÁT CHẤT LƯỢNG MÔN TOÁN" />
        </div>

        <div class="form-group">
          <label class="form-label">Tên Trường / Đơn vị tổ chức</label>
          <input type="text" id="exam-header-input" class="form-control" value="PHÒNG GIÁO DỤC VÀ ĐÀO TẠO - TRƯỜNG CLC" />
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div class="form-group">
            <label class="form-label">Khối lớp</label>
            <select id="exam-grade-input" class="form-control">
              ${[1,2,3,4,5,6,7,8,9,10,11,12].map(g => `<option value="${g}" ${g === 5 ? 'selected' : ''}>Khối ${g}</option>`).join("")}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Thời gian (phút)</label>
            <input type="number" id="exam-duration-input" class="form-control" value="45" />
          </div>
        </div>

        <div class="form-group">
          <label class="form-label" style="display: flex; justify-content: space-between; align-items: center;">
            <span>Mã đề thi</span>
            <span style="font-size: 11px; color: #64748b;">(Dùng khi trộn đề)</span>
          </label>
          <div style="display: flex; gap: 6px; align-items: center;">
            <input type="text" id="exam-code-input" class="form-control" value="${currentExamCode}" style="font-weight: 700; width: 85px;" />
            <div style="display: flex; gap: 4px; flex-wrap: wrap;">
              ${['101', '102', '103', '104'].map(c => `
                <button type="button" class="btn btn-secondary btn-sm" onclick="setExamCodePreset('${c}')" style="padding: 2px 7px; font-size: 11px; font-weight: 600;">${c}</button>
              `).join("")}
            </div>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Ghi chú đề thi</label>
          <input type="text" id="exam-notes-input" class="form-control" value="Cán bộ coi thi không giải thích gì thêm." />
        </div>

        <div style="display: flex; flex-direction: column; gap: 9px; margin-top: 10px;">
          <button class="btn btn-success" onclick="exportExamPDF()" id="btn-export-pdf" style="font-weight: 700; background: #059669; border-color: #059669; color: white;">
            📑 Xuất Đề thi PDF
          </button>
          <button class="btn btn-primary" onclick="exportExamWordDocx()" id="btn-export-docx" style="font-weight: 700;">
            📄 Xuất file Word (.docx)
          </button>

          <div style="border-top: 1px dashed #cbd5e1; margin: 4px 0;"></div>
          <div style="font-size: 11.5px; font-weight: 700; color: #334155; margin-bottom: 2px;">⚡ Công cụ Trộn đề & Đa dạng hóa:</div>

          <button class="btn btn-secondary" onclick="shuffleExamQuestions()" title="Đảo ngẫu nhiên thứ tự các câu hỏi">
            🔀 Đảo thứ tự câu hỏi
          </button>
          <button class="btn btn-secondary" onclick="shuffleExamOptions()" title="Đảo ngẫu nhiên vị trí các đáp án A, B, C, D và tự động đồng bộ đáp án đúng">
            🎲 Đảo phương án A-B-C-D
          </button>
          <button class="btn btn-secondary" onclick="shuffleExamBoth()" style="background: #eff6ff; border-color: #93c5fd; color: #1e40af; font-weight: 700;" title="Đảo toàn diện cả câu hỏi lẫn đáp án">
            🔀🎲 Trộn toàn diện (Đề & Đáp án)
          </button>

          ${duplicateCount > 0 ? `
            <button class="btn btn-warning" onclick="autoDeduplicateAndDiversifyExam()" id="btn-sidebar-diversify" style="background: #f59e0b; color: white; border: none; font-weight: 700; padding: 8px 12px; border-radius: 8px;">
              🛡️ Lọc sạch câu trùng dạng (${duplicateCount} câu)
            </button>
          ` : ''}

          <button class="btn btn-secondary" style="color: #ef4444;" onclick="clearExamSelection()">
            ✕ Xóa tất cả (${count} câu)
          </button>
        </div>
      </div>

      <!-- Right: Ordered Questions Preview List -->
      <div style="display: flex; flex-direction: column; gap: 14px;" id="exam-preview-container">
        
        <!-- Exam Diversity / Health Banner -->
        ${duplicateCount > 0 ? `
          <div style="background: #fffbeb; border: 1.5px solid #f59e0b; border-radius: 12px; padding: 14px 18px; box-shadow: 0 2px 6px rgba(245, 158, 11, 0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
              <div>
                <div style="font-weight: 800; color: #b45309; font-size: 14px; display: flex; align-items: center; gap: 8px;">
                  <span>⚠️</span> Phát hiện ${duplicateCount} câu hỏi trùng dạng bài / chỉ khác số liệu!
                  <span style="font-size: 12px; background: #fef3c7; border: 1px solid #fcd34d; padding: 2px 8px; border-radius: 12px;">Độ đa dạng: ${diversityScore}%</span>
                </div>
                <div style="font-size: 12.5px; color: #78350f; margin-top: 4px;">
                  Đề thi đang có nhiều câu hỏi cùng dạng bài toán chỉ khác số liệu (xem các câu viền vàng bên dưới). Hãy bấm nút bên phải để tự động thay thế bằng các câu hỏi hoàn toàn khác nhau về nội dung lẫn cách làm!
                </div>
              </div>
              <button class="btn btn-warning" onclick="autoDeduplicateAndDiversifyExam()" id="btn-smart-diversify" style="background: #f59e0b; color: white; border: none; font-weight: 700; padding: 8px 16px; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 4px rgba(217, 119, 6, 0.3);">
                <span>🛡️</span> 1-Click Thay thế Câu trùng dạng
              </button>
            </div>
          </div>
        ` : `
          <div style="background: #ecfdf5; border: 1.5px solid #10b981; border-radius: 12px; padding: 12px 18px; box-shadow: 0 2px 6px rgba(16, 185, 129, 0.08);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
              <div style="display: flex; align-items: center; gap: 8px; color: #065f46; font-size: 13.5px; font-weight: 700;">
                <span>✨</span> Đề thi đạt chuẩn đa dạng ${diversityScore}%
                <span style="font-size: 12px; font-weight: 500; color: #047857;">(Tất cả câu hỏi khác nhau về nội dung & cách giải)</span>
              </div>
              <div style="display: gap; gap: 6px; flex-wrap: wrap;">
                <span class="tag-badge" style="background: #d1fae5; color: #065f46; font-size: 11px; font-weight: 700;">
                  ✓ ${Object.keys(divData.archetypes || {}).length} dạng bài phong phú
                </span>
              </div>
            </div>
          </div>
        `}

        ${examQuestionsList.map((q, idx) => {
          const isDup = dupIdsSet.has(q.id);
          return `
            <div class="question-card" style="margin-bottom: 0; ${isDup ? 'border: 1.5px solid #f59e0b; background: #fffdfa;' : ''}">
              <div class="card-header">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span class="q-number-pill">Câu ${idx + 1}</span>
                  <span style="font-size: 11.5px; color: #1e40af; background: #eff6ff; padding: 2px 7px; border-radius: 6px; font-weight: 700; border: 1px solid #bfdbfe;">
                    ID: #${q.q_number || q.id.substring(0, 8)}
                  </span>
                  <span class="tag-badge platform-${q.source_platform}">${q.source_platform}</span>
                  <span class="tag-grade">Lớp ${q.grade || 5}</span>
                  <span class="tag-grade" style="background: #f1f5f9; color: #475569;">${q.difficulty}</span>
                  ${isDup ? `
                    <span class="tag-badge" style="background: #fef3c7; color: #b45309; border: 1px solid #fde68a; font-weight: 700;">
                      ⚠️ Trùng mẫu câu (Chỉ khác số)
                    </span>
                  ` : ''}
                </div>
                <div style="display: flex; gap: 6px; align-items: center;">
                  <button class="btn btn-secondary btn-sm" style="color: #0284c7; border-color: #bae6fd; font-weight: 600;" onclick="swapQuestionInExam('${q.id}')" title="Đổi ngay câu này sang một dạng bài khác">
                    🔄 Đổi câu khác
                  </button>
                  <button class="btn btn-secondary btn-sm" style="color: #ef4444;" onclick="removeQuestionFromExam('${q.id}')">
                    Xóa khỏi đề
                  </button>
                </div>
              </div>

              <div class="card-content" style="font-size: 14px; margin-bottom: 8px;">
                ${q.content_html}
              </div>

              ${q.options && q.options.length > 0 ? `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; font-size: 13px; color: #334155;">
                  ${q.options.map(o => `
                    <div><strong>${o.id}.</strong> ${o.content}</div>
                  `).join("")}
                </div>
              ` : ''}
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;

  renderMath(document.getElementById("exam-preview-container"));
}

function setExamCodePreset(code) {
  const el = document.getElementById("exam-code-input");
  if (el) el.value = code;
  showToast(`Đã chọn Mã đề thi: ${code}`, "info");
}

async function autoDeduplicateAndDiversifyExam() {
  const btn = document.getElementById("btn-smart-diversify");
  const sBtn = document.getElementById("btn-sidebar-diversify");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Đang đổi câu trùng...";
  }
  if (sBtn) {
    sBtn.disabled = true;
    sBtn.innerText = "⏳ Đang đổi...";
  }

  const subject = document.getElementById("matrix-subject")?.value || "math";
  const grade = parseInt(document.getElementById("exam-grade-input")?.value || document.getElementById("matrix-grade")?.value) || 5;
  const qIds = Array.from(State.selectedQuestionIds);

  try {
    const res = await fetch(`${API_BASE}/exams/diversify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_ids: qIds, subject, grade })
    });
    const data = await res.json();
    if (!data.success) {
      showToast(data.message || "Không thể lọc câu trùng", "error");
      return;
    }

    State.selectedQuestionIds = new Set(data.question_ids);
    updateSelectedBadge();
    showToast(`✓ Đã thay thế thành công ${data.replacements_count} câu trùng dạng bằng các câu hỏi mới đa dạng nội dung & cách giải!`, "success");
    await renderExamBuilderView();
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "🛡️ 1-Click Thay thế Câu trùng dạng";
    }
    if (sBtn) {
      sBtn.disabled = false;
    }
  }
}

async function swapQuestionInExam(qid) {
  const subject = document.getElementById("matrix-subject")?.value || "math";
  const grade = parseInt(document.getElementById("exam-grade-input")?.value || document.getElementById("matrix-grade")?.value) || 5;
  const qIds = Array.from(State.selectedQuestionIds);

  showToast("⏳ Đang tìm câu hỏi khác dạng bài...", "info");
  try {
    const res = await fetch(`${API_BASE}/exams/swap-question`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: qid, question_ids: qIds, subject, grade })
    });
    const data = await res.json();
    if (!data.success || !data.new_id) {
      showToast(data.detail || "Không tìm thấy câu hỏi thay thế phù hợp", "error");
      return;
    }

    const newIds = qIds.map(id => id === qid ? data.new_id : id);
    State.selectedQuestionIds = new Set(newIds);
    updateSelectedBadge();
    showToast("✓ Đã đổi sang câu hỏi mới khác hẳn dạng bài!", "success");
    await renderExamBuilderView();
  } catch (err) {
    showToast(`Lỗi: ${err.message}`, "error");
  }
}

function removeQuestionFromExam(qid) {
  State.selectedQuestionIds.delete(qid);
  updateSelectedBadge();
  showToast("Đã bỏ câu hỏi khỏi đề", "info");
  renderExamBuilderView();
}

function clearExamSelection() {
  if (!confirm("Bạn có muốn xóa toàn bộ câu hỏi đã chọn trong đề thi này?")) return;
  State.selectedQuestionIds.clear();
  updateSelectedBadge();
  renderExamBuilderView();
}

function shuffleExamQuestions() {
  for (let i = examQuestionsList.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [examQuestionsList[i], examQuestionsList[j]] = [examQuestionsList[j], examQuestionsList[i]];
  }
  State.selectedQuestionIds = new Set(examQuestionsList.map(q => q.id));
  showToast("🔀 Đã trộn ngẫu nhiên thứ tự các câu hỏi!");
  renderExamBuilderView(true);
}

async function shuffleExamOptions() {
  const qIds = Array.from(State.selectedQuestionIds);
  if (qIds.length === 0) return;

  try {
    const res = await fetch(`${API_BASE}/exams/shuffle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_ids: qIds, shuffle_order: false, shuffle_options: true })
    });
    const data = await res.json();
    if (data.success && data.questions) {
      examQuestionsList = data.questions;
      showToast("🎲 Đã xáo trộn các đáp án A-B-C-D và tự động cập nhật đáp án đúng!", "success");
      renderExamBuilderView(true);
    }
  } catch (err) {
    showToast(`Lỗi xáo trộn đáp án: ${err.message}`, "error");
  }
}

async function shuffleExamBoth() {
  const qIds = Array.from(State.selectedQuestionIds);
  if (qIds.length === 0) return;

  try {
    const res = await fetch(`${API_BASE}/exams/shuffle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_ids: qIds, shuffle_order: true, shuffle_options: true })
    });
    const data = await res.json();
    if (data.success && data.questions) {
      examQuestionsList = data.questions;
      State.selectedQuestionIds = new Set(data.question_ids);
      showToast("🔀🎲 Đã trộn ngẫu nhiên cả câu hỏi và phương án A-B-C-D!", "success");
      renderExamBuilderView(true);
    }
  } catch (err) {
    showToast(`Lỗi trộn toàn diện: ${err.message}`, "error");
  }
}

async function exportExamWordDocx() {
  const btn = document.getElementById("btn-export-docx");
  btn.disabled = true;
  btn.innerText = "⏳ Đang tạo file Word...";

  const payload = {
    title: document.getElementById("exam-title-input")?.value || "ĐỀ KHẢO SÁT CHẤT LƯỢNG MÔN TOÁN",
    header_info: document.getElementById("exam-header-input")?.value || "PHÒNG GIÁO DỤC VÀ ĐÀO TẠO",
    grade: parseInt(document.getElementById("exam-grade-input")?.value) || 5,
    duration_minutes: parseInt(document.getElementById("exam-duration-input")?.value) || 45,
    notes: document.getElementById("exam-notes-input")?.value || "Cán bộ coi thi không giải thích gì thêm.",
    exam_code: document.getElementById("exam-code-input")?.value || "101",
    question_ids: examQuestionsList.map(q => q.id)
  };

  try {
    const res = await fetch(`${API_BASE}/export/docx`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Không thể xuất file");
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `De_thi_Lop${payload.grade}_Ma${payload.exam_code}_${payload.title.replace(/\s+/g, '_').substring(0, 20)}.docx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

    showToast("Đã xuất file Word (.docx) thành công!");
  } catch (err) {
    showToast(`Lỗi xuất file: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerText = "📄 Xuất file Word (.docx)";
  }
}

// Math and Science Symbols Normalizer
if (typeof formatMathSymbols !== "function" && typeof window.formatMathSymbols !== "function") {
  window.formatMathSymbols = function(str) {
    if (!str) return "";
    let s = String(str);

    const mathBlocks = [];
    const saveMath = (match) => {
      const idx = mathBlocks.length;
      mathBlocks.push(match);
      return `___MATH_BLOCK_${idx}___`;
    };

    const mathBlockRegex = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$(?:\\\$|[^\$\n])+?\$)/g;
    s = s.replace(mathBlockRegex, saveMath);

    const formulaRegex = /(^|[\s:;,\(])((?:[A-Za-z]\s*=\s*)?(?:\\frac\{[^{}]+\}\{[^{}]+\}|\\sqrt\{[^{}]+\}|[0-9]+|[+\-*/=><\(\)\.]|\s+)*(?:\\frac\{[^{}]+\}\{[^{}]+\}|\\sqrt\{[^{}]+\})(?:\\frac\{[^{}]+\}\{[^{}]+\}|\\sqrt\{[^{}]+\}|[0-9]+|[+\-*/=><\(\)\.]|\s+)*)([\s\.,;:!?\)]|$)/g;

    s = s.replace(formulaRegex, (match, prefix, formulaGroup, suffix) => {
      let raw = formulaGroup;
      const leadingSpace = raw.match(/^\s*/)[0];
      const trailingSpace = raw.match(/\s*$/)[0];
      raw = raw.trim();

      let trailingPunct = "";
      const punctMatch = raw.match(/[\.,;:!?]+$/);
      if (punctMatch) {
        trailingPunct = punctMatch[0];
        raw = raw.slice(0, -trailingPunct.length).trim();
      }
      if (!raw) return match;

      const idx = mathBlocks.length;
      mathBlocks.push(`$${raw}$`);
      return `${prefix}${leadingSpace}___MATH_BLOCK_${idx}___${trailingPunct}${trailingSpace}${suffix}`;
    });

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

    s = s.replace(/(\b(?:m|cm|dm|mm|km))\^2\b/g, '$1²');
    s = s.replace(/(\b(?:m|cm|dm|mm|km))\^3\b/g, '$1³');
    s = s.replace(/\bH2O\b/g, 'H₂O');
    s = s.replace(/\bCO2\b/g, 'CO₂');
    s = s.replace(/\bO2\b/g, 'O₂');
    s = s.replace(/\bN2\b/g, 'N₂');
    s = s.replace(/\bH2SO4\b/g, 'H₂SO₄');
    s = s.replace(/\bCaCO3\b/g, 'CaCO₃');

    for (let idx = 0; idx < mathBlocks.length; idx++) {
      s = s.replace(`___MATH_BLOCK_${idx}___`, () => mathBlocks[idx]);
    }

    return s;
  };
}

async function exportExamPDF() {
  const btn = document.getElementById("btn-export-pdf");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Đang tạo file PDF...";
  }

  const payload = {
    title: document.getElementById("exam-title-input")?.value || "ĐỀ KHẢO SÁT CHẤT LƯỢNG MÔN TOÁN",
    header_info: document.getElementById("exam-header-input")?.value || "PHÒNG GIÁO DỤC VÀ ĐÀO TẠO",
    grade: parseInt(document.getElementById("exam-grade-input")?.value) || 5,
    duration_minutes: parseInt(document.getElementById("exam-duration-input")?.value) || 45,
    notes: document.getElementById("exam-notes-input")?.value || "Cán bộ coi thi không giải thích gì thêm.",
    exam_code: document.getElementById("exam-code-input")?.value || "101",
    question_ids: examQuestionsList.map(q => q.id)
  };

  try {
    const res = await fetch(`${API_BASE}/export/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `De_thi_Lop${payload.grade}_Ma${payload.exam_code}_${payload.title.replace(/\s+/g, '_').substring(0, 20)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast("✓ Đã xuất Đề thi PDF chuẩn Bộ GD&ĐT thành công!", "success");
      return;
    }

    // Fallback if backend PDF generation returns error
    console.warn("Backend PDF endpoint returned status:", res.status, "- falling back to client print window");
    triggerClientPdfPrint(payload, examQuestionsList);

  } catch (err) {
    console.warn("Network error during PDF export, using client print fallback:", err);
    triggerClientPdfPrint(payload, examQuestionsList);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "📑 Xuất Đề thi PDF";
    }
  }
}

function triggerClientPdfPrint(payload, questions) {
  let printArea = document.getElementById("printable-exam-area");
  if (!printArea) {
    printArea = document.createElement("div");
    printArea.id = "printable-exam-area";
    document.body.appendChild(printArea);
  }

  const totalQ = questions.length;
  const pointsPerQ = (10.0 / (totalQ || 1)).toFixed(2);
  const examCode = payload.exam_code || "101";

  const questionsHtml = questions.map((q, idx) => {
    const cleanStem = typeof formatMathSymbols === 'function' ? formatMathSymbols(q.content_text || q.content_html || "") : (q.content_text || q.content_html || "");
    const options = q.options || [];
    return `
      <div class="exam-question-item">
        <div style="margin-bottom: 4pt; text-align: justify;"><strong>Câu ${idx + 1}:</strong> ${cleanStem}</div>
        ${options.length > 0 ? `
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4pt 12pt; padding-left: 14pt; font-size: 11.5pt;">
            ${options.map(o => `<div><strong>${o.id}.</strong> ${typeof formatMathSymbols === 'function' ? formatMathSymbols(o.content || "") : (o.content || "")}</div>`).join("")}
          </div>
        ` : ''}
      </div>
    `;
  }).join("");

  const answerRows = questions.map((q, idx) => {
    const correctOpt = q.correct_answer || (q.options?.find(o => o.is_correct)?.id) || "A";
    return `<tr><td style="text-align: center; font-weight: bold;">Câu ${idx + 1}</td><td style="text-align: center; font-weight: bold;">${correctOpt}</td><td style="text-align: center;">${pointsPerQ}</td></tr>`;
  }).join("");

  printArea.innerHTML = `
    <div style="padding: 10mm;">
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 12pt;">
        <tr>
          <td style="width: 45%; text-align: center; vertical-align: top;">
            <div style="font-size: 10.5pt; font-weight: bold; text-transform: uppercase;">${payload.header_info}</div>
            <div style="font-weight: bold; font-size: 11pt; margin-top: 4pt;">MÃ ĐỀ THI: ${examCode}</div>
          </td>
          <td style="width: 55%; text-align: center; vertical-align: top;">
            <div style="font-size: 12.5pt; font-weight: bold; text-transform: uppercase;">${payload.title}</div>
            <div style="font-size: 11pt; font-weight: bold; margin-top: 2pt;">Khối lớp: ${payload.grade} - Thời gian: ${payload.duration_minutes} phút</div>
          </td>
        </tr>
      </table>

      <div style="border: 1px dashed #64748b; padding: 6pt 10pt; margin-bottom: 12pt; font-size: 11pt;">
        Họ và tên thí sinh: ............................................................................................ Lớp: .................... SBD: ....................
      </div>

      <div style="margin-bottom: 14pt;">
        ${questionsHtml}
      </div>

      <div class="exam-answer-page">
        <h3 style="text-align: center; text-transform: uppercase; margin-bottom: 12pt;">ĐÁP ÁN VÀ THANG ĐIỂM CHI TIẾT (MÃ ĐỀ ${examCode})</h3>
        <table style="width: 100%; border-collapse: collapse; border: 1px solid #000;">
          <thead>
            <tr style="background: #f1f5f9;">
              <th style="border: 1px solid #000; padding: 6pt;">Câu hỏi</th>
              <th style="border: 1px solid #000; padding: 6pt;">Đáp án đúng</th>
              <th style="border: 1px solid #000; padding: 6pt;">Thang điểm</th>
            </tr>
          </thead>
          <tbody>
            ${answerRows}
          </tbody>
        </table>
      </div>
    </div>
  `;

  if (typeof renderMath === "function") {
    renderMath(printArea);
  }

  setTimeout(() => {
    window.print();
    showToast("Đã mở cửa sổ in ấn / lưu PDF");
  }, 250);
}

