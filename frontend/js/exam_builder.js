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

    showToast(`Đã tự động tạo đề thi với ${data.count} câu hỏi theo ma trận!`);
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
async function renderExamBuilderView() {
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

  container.innerHTML = `
    <div style="text-align: center; padding: 40px; color: #64748b;">
      <div style="font-size: 24px; margin-bottom: 8px;">⏳</div>
      <p>Đang chuẩn bị đề thi...</p>
    </div>
  `;

  try {
    const qIds = Array.from(State.selectedQuestionIds);
    const fetchPromises = qIds.map(id => fetch(`${API_BASE}/questions/${id}`).then(r => r.json()));
    examQuestionsList = await Promise.all(fetchPromises);

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
            <label class="form-label">Ghi chú đề thi</label>
            <input type="text" id="exam-notes-input" class="form-control" value="Cán bộ coi thi không giải thích gì thêm." />
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 10px;">
            <button class="btn btn-primary" onclick="exportExamWordDocx()" id="btn-export-docx" style="font-weight: 700;">
              📄 Xuất file Word (.docx)
            </button>
            <button class="btn btn-secondary" onclick="shuffleExamQuestions()">
              🔀 Trộn ngẫu nhiên thứ tự câu hỏi
            </button>
            <button class="btn btn-secondary" style="color: #ef4444;" onclick="clearExamSelection()">
              ✕ Xóa tất cả (${count} câu)
            </button>
          </div>
        </div>

        <!-- Right: Ordered Questions Preview List -->
        <div style="display: flex; flex-direction: column; gap: 14px;" id="exam-preview-container">
          ${examQuestionsList.map((q, idx) => `
            <div class="question-card" style="margin-bottom: 0;">
              <div class="card-header">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <span class="q-number-pill">Câu ${idx + 1}</span>
                  <span style="font-size: 11.5px; color: #1e40af; background: #eff6ff; padding: 2px 7px; border-radius: 6px; font-weight: 700; border: 1px solid #bfdbfe;">
                    ID: #${q.q_number || q.id.substring(0, 8)}
                  </span>
                  <span class="tag-badge platform-${q.source_platform}">${q.source_platform}</span>
                  <span class="tag-grade">Lớp ${q.grade || 5}</span>
                  <span class="tag-grade" style="background: #f1f5f9; color: #475569;">${q.difficulty}</span>
                </div>
                <button class="btn btn-secondary btn-sm" style="color: #ef4444;" onclick="removeQuestionFromExam('${q.id}')">
                  Xóa khỏi đề
                </button>
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
          `).join("")}
        </div>
      </div>
    `;

    renderMath(document.getElementById("exam-preview-container"));

  } catch (err) {
    console.error("Error preparing exam:", err);
    container.innerHTML = `<div style="color: #ef4444; padding: 20px;">Lỗi tải chi tiết câu hỏi: ${err.message}</div>`;
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
  showToast("Đã trộn ngẫu nhiên thứ tự các câu hỏi!");
  renderExamBuilderView();
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
    a.download = `De_thi_${payload.grade}_${payload.title.replace(/\s+/g, '_').substring(0, 25)}.docx`;
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
