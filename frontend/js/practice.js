// EduQuest Pro - Interactive Practice Arena Engine (R5)
// Fully featured: HUD timer, Stepper grid, Instant grading, Review mode, Trending chart, Mastery & Badges

let practiceState = {
  activeTab: "start",
  inExam: false,
  examId: null,
  examTitle: "Bài Luyện Tập Trực Tuyến",
  subject: "math",
  grade: 5,
  questions: [],
  currentIndex: 0,
  userAnswers: {},       // { [questionId]: 'A' | 'B' | 'C' | 'D' }
  flaggedQuestions: new Set(),
  timerTotalSec: 900,
  timerRemainingSec: 900,
  timerInterval: null,
  timeSpentSec: 0,
  lastResult: null
};

// 8 Gamification Badges definitions
const BADGES_DEFINITIONS = [
  { id: "badge_first_step", title: "Khởi Đầu", desc: "Hoàn thành bài luyện tập đầu tiên", icon: "🌟" },
  { id: "badge_perfect_score", title: "Xạ Thủ Điểm 10", desc: "Đạt điểm tuyệt đối 10/10", icon: "🎯" },
  { id: "badge_speed_racer", title: "Tia Chớp Tốc Độ", desc: "Nộp bài dưới 50% thời gian với điểm ≥ 8.0", icon: "⚡" },
  { id: "badge_math_master", title: "Nhà Toán Học Nhí", desc: "Tỷ lệ trả lời đúng môn Toán đạt từ 85%", icon: "📐" },
  { id: "badge_scholar", title: "Trạng Nguyên", desc: "Tỷ lệ trả lời đúng môn Tiếng Việt đạt từ 85%", icon: "📖" },
  { id: "badge_persistent", title: "Chiến Binh Chăm Chỉ", desc: "Hoàn thành chuỗi từ 3 bài thi trở lên", icon: "🔥" },
  { id: "badge_multilingual", title: "Bách Khoa Song Ngữ", desc: "Luyện tập thành công cả Tiếng Việt và Tiếng Anh", icon: "🇬🇧" },
  { id: "badge_top_tier", title: "Bậc Thầy Đỉnh Cao", desc: "Đạt xếp loại Xuất sắc ở 2 bài thi liên tiếp", icon: "🏆" }
];

// Mathematical & Scientific Symbol Normalizer
function formatMathSymbols(str) {
  if (!str) return "";
  let s = String(str);
  
  // 1. Dấu nhân và chia
  s = s.replace(/\\times\b/g, '×').replace(/\\cdot\b/g, '·').replace(/\\div\b/g, '÷');
  
  // 2. Góc và tam giác
  s = s.replace(/\\angle\b/g, '∠').replace(/\\Delta\b/g, 'Δ');
  
  // 3. Ký tự Hy Lạp
  s = s.replace(/\\pi\b/g, 'π').replace(/\\alpha\b/g, 'α').replace(/\\beta\b/g, 'β')
       .replace(/\\theta\b/g, 'θ').replace(/\\gamma\b/g, 'γ').replace(/\\lambda\b/g, 'λ')
       .replace(/\\mu\b/g, 'μ').replace(/\\sigma\b/g, 'σ').replace(/\\omega\b/g, 'ω');
       
  // 4. So sánh
  s = s.replace(/\\le\b|\\leq\b/g, '≤').replace(/\\ge\b|\\geq\b/g, '≥').replace(/\\ne\b|\\neq\b/g, '≠').replace(/\\approx\b/g, '≈');
  
  // 5. Số mũ thông dụng
  s = s.replace(/\^2\b/g, '²').replace(/\^3\b/g, '³').replace(/\^0\b/g, '⁰').replace(/\^1\b/g, '¹');
  s = s.replace(/([a-zA-Z0-9])\^2/g, '$1²').replace(/([a-zA-Z0-9])\^3/g, '$1³');
  
  // 6. Công thức hóa học phổ biến
  s = s.replace(/\bH2O\b/g, 'H₂O').replace(/\bCO2\b/g, 'CO₂').replace(/\bO2\b/g, 'O₂')
       .replace(/\bN2\b/g, 'N₂').replace(/\bH2SO4\b/g, 'H₂SO₄').replace(/\bCaCO3\b/g, 'CaCO₃')
       .replace(/\bNaCl\b/g, 'NaCl').replace(/\bHCl\b/g, 'HCl');
       
  // 7. Fractions and roots
  s = s.replace(/(?<!\$)\\sqrt\{([^}]+)\}(?!\$)/g, '$\\sqrt{$1}$');
  s = s.replace(/(?<!\$)\\frac\{([^}]+)\}\{([^}]+)\}(?!\$)/g, '$\\frac{$1}{$2}$');
  
  return s;
}

// Global Keyboard Handler for Active Practice Arena
function handleArenaKeyDown(e) {
  if (!practiceState.inExam) return;
  // Ignore if user is typing in an input or textarea
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;

  const key = e.key.toUpperCase();
  if (['1', 'A'].includes(key)) {
    selectPracticeOption('A');
  } else if (['2', 'B'].includes(key)) {
    selectPracticeOption('B');
  } else if (['3', 'C'].includes(key)) {
    selectPracticeOption('C');
  } else if (['4', 'D'].includes(key)) {
    selectPracticeOption('D');
  } else if (e.key === 'ArrowRight' || e.key === 'PageDown') {
    nextPracticeQuestion();
  } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
    prevPracticeQuestion();
  } else if (['F', 'f'].includes(e.key)) {
    toggleFlagCurrentQuestion();
  }
}
window.addEventListener('keydown', handleArenaKeyDown);

// Initialize Practice View
function initPracticeView() {
  switchPracticeTab(practiceState.activeTab || "start");
  loadPracticeAnalytics();
  loadPracticeHistory();
}

// Switch Tabs inside Practice Lobby
function switchPracticeTab(tabId) {
  practiceState.activeTab = tabId;
  
  document.querySelectorAll(".practice-tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });

  const tabContents = {
    start: document.getElementById("tab-practice-start"),
    trending: document.getElementById("tab-practice-trending"),
    mastery: document.getElementById("tab-practice-mastery"),
    badges: document.getElementById("tab-practice-badges"),
    history: document.getElementById("tab-practice-history")
  };

  Object.keys(tabContents).forEach(key => {
    if (tabContents[key]) {
      tabContents[key].style.display = (key === tabId) ? "block" : "none";
    }
  });

  if (tabId === "trending") {
    renderTrendingChart();
  } else if (tabId === "mastery") {
    loadPracticeAnalytics();
  } else if (tabId === "badges") {
    loadPracticeAnalytics();
  } else if (tabId === "history") {
    loadPracticeHistory();
  }
}

// ----------------- Practice Session Generator & Runner -----------------

async function startPracticeSession() {
  const subject = document.getElementById("practice-subject-select")?.value || "math";
  const grade = parseInt(document.getElementById("practice-grade-select")?.value) || 5;
  const count = parseInt(document.getElementById("practice-count-select")?.value) || 10;
  const durationMin = parseInt(document.getElementById("practice-duration-select")?.value) || 15;
  const difficulty = document.getElementById("practice-difficulty-select")?.value || "all";

  const btnStart = document.getElementById("btn-start-practice");
  if (btnStart) {
    btnStart.disabled = true;
    btnStart.innerText = "⏳ Đang chuẩn bị đề thi...";
  }

  try {
    const payload = {
      subject: subject,
      grade: grade,
      count: count,
      duration_minutes: durationMin,
      difficulty: difficulty === "all" ? null : difficulty
    };

    let questions = [];
    let title = `Luyện tập ${getSubjectName(subject)} Khối ${grade}`;

    const res = await fetch(`${API_BASE}/practice/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      const data = await res.json();
      const sessionQuestions = data.questions || data.session?.questions || [];
      if (sessionQuestions.length > 0) {
        questions = sessionQuestions;
        title = data.exam_title || data.session?.title || title;
      }
    }

    // Fallback: If server returns empty, fetch directly from bank
    if (!questions || questions.length === 0) {
      const qRes = await fetch(`${API_BASE}/questions?subject=${subject}&grade=${grade}&page_size=${count}`);
      if (qRes.ok) {
        const qData = await qRes.json();
        if (qData.items && qData.items.length > 0) {
          questions = qData.items;
        }
      }
    }

    // Ultimate fallback if bank has fewer questions
    if (!questions || questions.length === 0) {
      const allQRes = await fetch(`${API_BASE}/questions?page_size=${count}`);
      if (allQRes.ok) {
        const allData = await allQRes.json();
        questions = allData.items || [];
      }
    }

    if (!questions || questions.length === 0) {
      showToast("Ngân hàng chưa có đủ câu hỏi cho lựa chọn này. Vui lòng nạp thêm câu hỏi!", "warning");
      return;
    }

    // Initialize practice session state
    practiceState.inExam = true;
    practiceState.examId = `prac_${Date.now()}`;
    practiceState.examTitle = title;
    practiceState.subject = subject;
    practiceState.grade = grade;
    practiceState.questions = questions;
    practiceState.currentIndex = 0;
    practiceState.userAnswers = {};
    practiceState.flaggedQuestions = new Set();
    practiceState.timerTotalSec = durationMin * 60;
    practiceState.timerRemainingSec = durationMin * 60;
    practiceState.timeSpentSec = 0;

    // Switch view elements
    document.getElementById("practice-lobby").style.display = "none";
    document.getElementById("practice-result-view").style.display = "none";
    document.getElementById("practice-active-arena").style.display = "block";

    // Setup HUD Title
    document.getElementById("arena-title-text").innerText = title;
    document.getElementById("arena-meta-text").innerText = `Môn: ${getSubjectName(subject)} • Khối ${grade} • ${questions.length} câu • ${durationMin} phút`;

    // Start HUD Timer
    startArenaTimer();

    // Render Question & Stepper
    renderArenaQuestion();
    renderStepperGrid();

    showToast(`Bắt đầu làm bài: ${title}! Chúc bạn làm bài thật tốt! 🚀`);

  } catch (err) {
    showToast(`Không thể tạo đề luyện tập: ${err.message}`, "error");
  } finally {
    if (btnStart) {
      btnStart.disabled = false;
      btnStart.innerText = "🚀 BẮT ĐẦU LÀM BÀI";
    }
  }
}

function startArenaTimer() {
  stopArenaTimer();
  updateArenaTimerUI();

  practiceState.timerInterval = setInterval(() => {
    practiceState.timerRemainingSec--;
    practiceState.timeSpentSec++;
    updateArenaTimerUI();

    if (practiceState.timerRemainingSec <= 0) {
      stopArenaTimer();
      showToast("⏰ Hết thời gian làm bài! Hệ thống tự động nộp bài...", "warning");
      submitPracticeExam(true);
    }
  }, 1000);
}

function stopArenaTimer() {
  if (practiceState.timerInterval) {
    clearInterval(practiceState.timerInterval);
    practiceState.timerInterval = null;
  }
}

function updateArenaTimerUI() {
  const timerBadge = document.getElementById("arena-timer");
  if (!timerBadge) return;

  const sec = Math.max(0, practiceState.timerRemainingSec);
  const m = Math.floor(sec / 60).toString().padStart(2, '0');
  const s = (sec % 60).toString().padStart(2, '0');
  timerBadge.innerText = `⏱️ ${m}:${s}`;

  // Color alerts
  timerBadge.classList.remove("warning", "danger");
  if (sec <= 60) {
    timerBadge.classList.add("danger");
  } else if (sec <= 180) {
    timerBadge.classList.add("warning");
  }
}

// Render Central Question
function renderArenaQuestion() {
  const total = practiceState.questions.length;
  const idx = practiceState.currentIndex;
  const q = practiceState.questions[idx];
  if (!q) return;

  // Question index pill & stem
  document.getElementById("arena-q-index-pill").innerText = `Câu ${idx + 1} / ${total}`;
  const stemEl = document.getElementById("arena-q-stem");
  const rawContent = q.content_html || q.content_text || "";
  stemEl.innerHTML = formatMathSymbols(rawContent);

  // Optional image preview
  const imgContainer = document.getElementById("arena-q-image-box");
  if (q.images && q.images.length > 0) {
    imgContainer.style.display = "block";
    imgContainer.innerHTML = `<img src="${q.images[0]}" alt="Hình ảnh câu hỏi" style="max-height: 240px; border-radius: 8px; border: 1px solid #cbd5e1;" />`;
  } else {
    imgContainer.style.display = "none";
    imgContainer.innerHTML = "";
  }

  // Options cards (A, B, C, D)
  const optionsGrid = document.getElementById("arena-options-container");
  const currentAnswer = practiceState.userAnswers[q.id];

  // Standardize options array
  let opts = q.options || [];
  if (!opts || opts.length === 0) {
    opts = [
      { id: "A", content: "Đáp án A" },
      { id: "B", content: "Đáp án B" },
      { id: "C", content: "Đáp án C" },
      { id: "D", content: "Đáp án D" }
    ];
  }

  optionsGrid.innerHTML = opts.map(opt => {
    const isSelected = (currentAnswer === opt.id);
    const content = formatMathSymbols(opt.content || "");
    return `
      <div class="arena-option-card ${isSelected ? 'selected' : ''}" onclick="selectPracticeOption('${opt.id}')">
        <div class="option-key-pill">${opt.id}</div>
        <div class="option-text-content">${content}</div>
        <div style="font-size: 11px; color: #94a3b8; font-weight: 700;">[Phím ${opt.id}]</div>
      </div>
    `;
  }).join("");

  // Flag button state
  const isFlagged = practiceState.flaggedQuestions.has(q.id);
  const btnFlag = document.getElementById("btn-flag-question");
  if (btnFlag) {
    btnFlag.innerHTML = isFlagged ? "🚩 Bỏ đánh dấu" : "🏳️ Đánh dấu xem lại";
    btnFlag.style.color = isFlagged ? "#d97706" : "#64748b";
  }

  // Update navigation button states
  const btnPrev = document.getElementById("btn-arena-prev");
  const btnNext = document.getElementById("btn-arena-next");
  if (btnPrev) btnPrev.disabled = (idx === 0);
  if (btnNext) btnNext.innerText = (idx === total - 1) ? "Nộp bài ✓" : "Câu tiếp ➡";

  // Progress Bar & Percentage
  const answeredCount = Object.keys(practiceState.userAnswers).length;
  const pct = Math.round((answeredCount / total) * 100);
  const progFill = document.getElementById("arena-progress-fill");
  const progText = document.getElementById("arena-progress-text");
  if (progFill) progFill.style.width = `${pct}%`;
  if (progText) progText.innerText = `Đã làm ${answeredCount}/${total} câu (${pct}%)`;

  // Render Math KaTeX
  if (typeof renderMath === "function") {
    renderMath(stemEl);
    renderMath(optionsGrid);
  }
}

// Select an option
function selectPracticeOption(optId) {
  const q = practiceState.questions[practiceState.currentIndex];
  if (!q) return;

  practiceState.userAnswers[q.id] = optId;
  renderArenaQuestion();
  renderStepperGrid();
}

// Toggle Flag
function toggleFlagCurrentQuestion() {
  const q = practiceState.questions[practiceState.currentIndex];
  if (!q) return;

  if (practiceState.flaggedQuestions.has(q.id)) {
    practiceState.flaggedQuestions.delete(q.id);
    showToast(`Đã bỏ đánh dấu Câu ${practiceState.currentIndex + 1}`);
  } else {
    practiceState.flaggedQuestions.add(q.id);
    showToast(`Đã gắn cờ xem lại Câu ${practiceState.currentIndex + 1} 🚩`, "info");
  }
  renderArenaQuestion();
  renderStepperGrid();
}

// Navigation
function nextPracticeQuestion() {
  const total = practiceState.questions.length;
  if (practiceState.currentIndex < total - 1) {
    practiceState.currentIndex++;
    renderArenaQuestion();
    renderStepperGrid();
  } else {
    // If at last question, trigger submit dialog
    confirmSubmitPracticeExam();
  }
}

function prevPracticeQuestion() {
  if (practiceState.currentIndex > 0) {
    practiceState.currentIndex--;
    renderArenaQuestion();
    renderStepperGrid();
  }
}

function jumpToPracticeQuestion(index) {
  if (index >= 0 && index < practiceState.questions.length) {
    practiceState.currentIndex = index;
    renderArenaQuestion();
    renderStepperGrid();
  }
}

// Stepper Navigation Grid
function renderStepperGrid() {
  const grid = document.getElementById("question-stepper-grid");
  if (!grid) return;

  const total = practiceState.questions.length;
  grid.innerHTML = practiceState.questions.map((q, idx) => {
    const isAnswered = !!practiceState.userAnswers[q.id];
    const isFlagged = practiceState.flaggedQuestions.has(q.id);
    const isCurrent = (idx === practiceState.currentIndex);

    let classes = ["stepper-btn"];
    if (isAnswered) classes.push("answered");
    if (isFlagged) classes.push("flagged");
    if (isCurrent) classes.push("current");

    return `
      <button class="${classes.join(' ')}" onclick="jumpToPracticeQuestion(${idx})" title="Câu ${idx + 1}${isFlagged ? ' (Đã gắn cờ)' : ''}">
        ${idx + 1}${isFlagged ? '🚩' : ''}
      </button>
    `;
  }).join("");
}

// Submit Verification Modal
function confirmSubmitPracticeExam() {
  const total = practiceState.questions.length;
  const answeredCount = Object.keys(practiceState.userAnswers).length;
  const unansweredCount = total - answeredCount;

  if (unansweredCount > 0) {
    const unansweredQuestions = [];
    practiceState.questions.forEach((q, idx) => {
      if (!practiceState.userAnswers[q.id]) {
        unansweredQuestions.push(idx + 1);
      }
    });

    const modal = document.getElementById("modal-submit-confirm");
    const warningMsg = document.getElementById("submit-confirm-msg");
    if (modal && warningMsg) {
      warningMsg.innerHTML = `
        <p style="font-size: 15px; color: #b91c1c; font-weight: 700; margin-bottom: 8px;">
          ⚠️ Bạn còn <strong>${unansweredCount} câu chưa làm</strong>!
        </p>
        <p style="font-size: 13.5px; color: #475569; margin-bottom: 12px;">
          Các câu chưa có câu trả lời: <strong>Câu ${unansweredQuestions.slice(0, 10).join(", ")}${unansweredQuestions.length > 10 ? '...' : ''}</strong>
        </p>
        <p style="font-size: 13px; color: #64748b;">
          Bạn có chắc chắn muốn nộp bài và chấm điểm ngay bây giờ không?
        </p>
      `;
      modal.style.display = "flex";
      return;
    }
  }

  // If all answered, submit directly
  submitPracticeExam(true);
}

function closeSubmitConfirmModal() {
  const modal = document.getElementById("modal-submit-confirm");
  if (modal) modal.style.display = "none";
}

// Grade and Submit Exam
async function submitPracticeExam(force = false) {
  closeSubmitConfirmModal();
  stopArenaTimer();

  const total = practiceState.questions.length;
  const durationSec = practiceState.timerTotalSec;
  const timeSpentSec = Math.min(durationSec, practiceState.timeSpentSec || 1);

  // Prepare payload
  const answersList = practiceState.questions.map(q => {
    const ans = practiceState.userAnswers[q.id] || "";
    return {
      question_id: q.id,
      selected_answer: ans,
      selected_option: ans,
      user_answer: ans
    };
  });

  const payload = {
    exam_id: practiceState.examId,
    exam_title: practiceState.examTitle,
    subject: practiceState.subject,
    grade: practiceState.grade,
    duration_seconds: durationSec,
    time_spent_seconds: timeSpentSec,
    answers: answersList
  };

  try {
    let result = null;

    // Send to backend
    const res = await fetch(`${API_BASE}/practice/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      result = await res.json();
    }

    // Local grading fallback if backend is unavailable
    if (!result) {
      let correct = 0;
      let wrong = 0;
      let skipped = 0;

      const detailedAnswers = practiceState.questions.map(q => {
        const userChoice = practiceState.userAnswers[q.id] || "";
        const correctChoice = q.correct_answer || (q.options?.find(o => o.is_correct)?.id) || "A";
        const isCorrect = (userChoice === correctChoice);

        if (!userChoice) {
          skipped++;
        } else if (isCorrect) {
          correct++;
        } else {
          wrong++;
        }

        return {
          question_id: q.id,
          stem: q.content_text || q.content_html,
          options: q.options,
          user_answer: userChoice,
          correct_answer: correctChoice,
          is_correct: isCorrect,
          explanation: q.explanation || "Lời giải chuẩn"
        };
      });

      const score10 = Number(((correct / total) * 10).toFixed(1));
      const score100 = Number(((correct / total) * 100).toFixed(0));

      let ranking = "Cần cố gắng";
      if (score10 >= 9.0) ranking = "Xuất sắc";
      else if (score10 >= 8.0) ranking = "Giỏi";
      else if (score10 >= 6.5) ranking = "Khá";
      else if (score10 >= 5.0) ranking = "Trung bình";

      result = {
        success: true,
        record_id: `rec_${Date.now()}`,
        score: score10,
        max_score: 10.0,
        score_100: score100,
        ranking: ranking,
        correct_count: correct,
        wrong_count: wrong,
        skipped_count: skipped,
        time_spent_seconds: timeSpentSec,
        duration_seconds: durationSec,
        new_badges: score10 === 10 ? ["badge_perfect_score"] : [],
        answers_detail: detailedAnswers
      };
    }

    // Save history record locally for offline resilience
    savePracticeHistoryLocal({
      id: result.record_id || `rec_${Date.now()}`,
      exam_title: practiceState.examTitle,
      subject: practiceState.subject,
      grade: practiceState.grade,
      score: result.score,
      max_score: result.max_score || 10.0,
      score_100: result.score_100 || (result.score * 10),
      ranking: result.ranking,
      correct_count: result.correct_count,
      wrong_count: result.wrong_count,
      skipped_count: result.skipped_count,
      time_spent_seconds: result.time_spent_seconds,
      duration_seconds: result.duration_seconds,
      created_at: new Date().toISOString(),
      answers_detail: result.answers_detail || result.results
    });

    practiceState.inExam = false;
    practiceState.lastResult = result;

    // Display Result & Review UI
    renderPracticeResultView(result);
    showToast(`Chúc mừng bạn đã hoàn thành bài thi với ${result.score} điểm! 🎉`);

  } catch (err) {
    showToast(`Lỗi khi nộp bài thi: ${err.message}`, "error");
  }
}

// ----------------- Results & Review Mode -----------------

function renderPracticeResultView(result) {
  document.getElementById("practice-active-arena").style.display = "none";
  document.getElementById("practice-lobby").style.display = "none";
  const resultView = document.getElementById("practice-result-view");
  resultView.style.display = "block";

  // Score & Rank
  const score10 = (result.score !== undefined) ? Number(result.score).toFixed(1) : "0.0";
  const score100 = (result.score_100 !== undefined) ? Number(result.score_100).toFixed(0) : (score10 * 10).toFixed(0);
  const ranking = result.ranking || "Khá";

  document.getElementById("result-score-10").innerText = `${score10} / 10`;
  document.getElementById("result-score-100").innerText = `(${score100} điểm)`;

  const rankPill = document.getElementById("result-rank-badge");
  rankPill.innerText = `Xếp loại: ${ranking}`;
  rankPill.className = "rank-badge-pill";
  if (ranking === "Xuất sắc") rankPill.classList.add("rank-xuat-sac");
  else if (ranking === "Giỏi") rankPill.classList.add("rank-gioi");
  else if (ranking === "Khá") rankPill.classList.add("rank-kha");
  else if (ranking === "Trung bình") rankPill.classList.add("rank-trung-binh");
  else rankPill.classList.add("rank-can-co-gang");

  // Stats Grid
  const total = (result.correct_count + result.wrong_count + result.skipped_count) || practiceState.questions.length;
  const timeSpentM = Math.floor(result.time_spent_seconds / 60);
  const timeSpentS = result.time_spent_seconds % 60;
  const accuracyPct = Math.round((result.correct_count / (total || 1)) * 100);

  document.getElementById("res-stat-time").innerText = `${timeSpentM}m ${timeSpentS < 10 ? '0' : ''}${timeSpentS}s`;
  document.getElementById("res-stat-correct").innerText = `${result.correct_count} câu`;
  document.getElementById("res-stat-wrong").innerText = `${result.wrong_count} câu`;
  document.getElementById("res-stat-skipped").innerText = `${result.skipped_count || 0} câu`;
  document.getElementById("res-stat-accuracy").innerText = `${accuracyPct}%`;

  // New Badges celebration banner
  const badgeBanner = document.getElementById("result-new-badges-banner");
  if (result.new_badges && result.new_badges.length > 0) {
    badgeBanner.style.display = "flex";
    const badgeNames = result.new_badges.map(bId => {
      const b = BADGES_DEFINITIONS.find(def => def.id === bId);
      return b ? `${b.icon} ${b.title}` : bId;
    }).join(", ");
    document.getElementById("result-new-badges-text").innerText = `Chúc mừng bạn đã mở khóa huy hiệu mới: ${badgeNames}!`;
  } else {
    badgeBanner.style.display = "none";
  }

  // Render Detailed Question Review Mode
  renderReviewQuestionsList(result.answers_detail || result.results || []);
}

function renderReviewQuestionsList(answersDetail) {
  const container = document.getElementById("practice-review-list");
  if (!container) return;

  if (!answersDetail || answersDetail.length === 0) {
    // If details are in practiceState.questions
    answersDetail = practiceState.questions.map(q => {
      const uAns = practiceState.userAnswers[q.id] || "";
      const cAns = q.correct_answer || (q.options?.find(o => o.is_correct)?.id) || "A";
      return {
        question_id: q.id,
        stem: q.content_text || q.content_html,
        options: q.options,
        user_answer: uAns,
        correct_answer: cAns,
        is_correct: (uAns === cAns),
        explanation: q.explanation || "Đáp án đúng theo chuẩn chương trình học."
      };
    });
  }

  container.innerHTML = answersDetail.map((item, idx) => {
    const isCorrect = item.is_correct;
    const userAns = item.user_answer || "Chưa trả lời";
    const correctAns = item.correct_answer || "A";
    const stem = formatMathSymbols(item.stem || item.content_text || item.content_html || "");
    const explanation = formatMathSymbols(item.explanation || "Lời giải chi tiết chuẩn.");

    const options = item.options || [
      { id: "A", content: "A" }, { id: "B", content: "B" }, { id: "C", content: "C" }, { id: "D", content: "D" }
    ];

    const optionsHtml = options.map(opt => {
      const isUserChoice = (item.user_answer === opt.id);
      const isCorrectChoice = (correctAns === opt.id);

      let optClass = "review-option";
      let badge = "";
      if (isCorrectChoice) {
        optClass += " correct-choice";
        badge = `<span style="color: #059669; font-weight: 800;">✓ Đáp án đúng</span>`;
      } else if (isUserChoice && !isCorrectChoice) {
        optClass += " user-wrong-choice";
        badge = `<span style="color: #dc2626; font-weight: 800;">✗ Lựa chọn của bạn</span>`;
      }

      return `
        <div class="${optClass}">
          <div><strong>${opt.id}.</strong> ${formatMathSymbols(opt.content || "")}</div>
          ${badge}
        </div>
      `;
    }).join("");

    return `
      <div class="review-q-item ${isCorrect ? 'is-correct' : 'is-wrong'}">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: 800; font-size: 14px; color: ${isCorrect ? '#15803d' : '#b91c1c'};">
            Câu ${idx + 1}: ${isCorrect ? '✓ ĐÚNG' : '✗ SAI'}
          </span>
          <span style="font-size: 12px; color: #64748b;">
            Bạn chọn: <strong>${userAns}</strong> • Đáp án đúng: <strong style="color: #15803d;">${correctAns}</strong>
          </span>
        </div>

        <div style="font-size: 14.5px; line-height: 1.5; color: #1e293b;">
          ${stem}
        </div>

        <div style="display: flex; flex-direction: column; gap: 4px; margin-top: 6px;">
          ${optionsHtml}
        </div>

        <div class="explanation-box" style="margin-top: 8px;">
          <strong>💡 Hướng dẫn giải chi tiết:</strong><br/>
          ${explanation}
        </div>
      </div>
    `;
  }).join("");

  if (typeof renderMath === "function") {
    renderMath(container);
  }
}

function returnToPracticeLobby() {
  document.getElementById("practice-result-view").style.display = "none";
  document.getElementById("practice-active-arena").style.display = "none";
  document.getElementById("practice-lobby").style.display = "block";
  switchPracticeTab("start");
  loadPracticeAnalytics();
  loadPracticeHistory();
}

// ----------------- Analytics, Trending Chart & Mastery -----------------

// Canvas Responsive Trending Score Chart
function renderTrendingChart() {
  const canvas = document.getElementById("trending-score-canvas");
  if (!canvas) return;

  const history = getLocalPracticeHistory();
  const summaryEl = document.getElementById("trending-summary-stats");

  if (!history || history.length === 0) {
    if (summaryEl) {
      summaryEl.innerHTML = `<div style="text-align: center; color: #94a3b8; padding: 24px;">Chưa có lịch sử làm bài để vẽ biểu đồ xu hướng. Hãy làm bài kiểm tra đầu tiên!</div>`;
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "14px 'Plus Jakarta Sans', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Chưa có dữ liệu lịch sử thi", canvas.width / 2, canvas.height / 2);
    return;
  }

  // Take the 10 most recent tests in chronological order (oldest to newest)
  const recentTests = [...history].reverse().slice(-10);
  const scores = recentTests.map(t => Number(t.score) || 0);
  const dates = recentTests.map(t => {
    const d = new Date(t.created_at);
    return `${d.getDate()}/${d.getMonth() + 1}`;
  });

  // Calculate summary stats
  const totalTests = history.length;
  const avgScore = (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1);
  const maxScore = Math.max(...scores).toFixed(1);

  if (summaryEl) {
    summaryEl.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 14px; margin-bottom: 20px;">
        <div class="stat-card" style="padding: 14px; text-align: center;">
          <div style="font-size: 24px; font-weight: 900; color: #2563eb;">${totalTests}</div>
          <div style="font-size: 12px; color: #64748b; font-weight: 700;">Tổng số bài đã luyện</div>
        </div>
        <div class="stat-card" style="padding: 14px; text-align: center;">
          <div style="font-size: 24px; font-weight: 900; color: #059669;">${avgScore} / 10</div>
          <div style="font-size: 12px; color: #64748b; font-weight: 700;">Điểm số trung bình</div>
        </div>
        <div class="stat-card" style="padding: 14px; text-align: center;">
          <div style="font-size: 24px; font-weight: 900; color: #d97706;">${maxScore} / 10</div>
          <div style="font-size: 12px; color: #64748b; font-weight: 700;">Điểm cao nhất</div>
        </div>
      </div>
    `;
  }

  // Draw Line Chart with HTML5 Canvas
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const padding = { top: 30, right: 30, bottom: 40, left: 45 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Grid lines (0 to 10 scale)
  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#64748b";
  ctx.font = "11px monospace";
  ctx.textAlign = "right";

  for (let s = 0; s <= 10; s += 2) {
    const y = padding.top + chartH - (s / 10) * chartH;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillText(`${s}`, padding.left - 8, y + 4);
  }

  if (scores.length === 1) {
    // Single point
    const x = padding.left + chartW / 2;
    const y = padding.top + chartH - (scores[0] / 10) * chartH;
    ctx.fillStyle = "#2563eb";
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillText(`${scores[0]}`, x, y - 12);
    return;
  }

  // Calculate points coordinates
  const stepX = chartW / (scores.length - 1);
  const points = scores.map((val, i) => ({
    x: padding.left + i * stepX,
    y: padding.top + chartH - (val / 10) * chartH,
    val: val,
    date: dates[i]
  }));

  // Gradient fill under the curve
  const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
  gradient.addColorStop(0, "rgba(37, 99, 235, 0.35)");
  gradient.addColorStop(1, "rgba(37, 99, 235, 0.02)");

  ctx.beginPath();
  ctx.moveTo(points[0].x, height - padding.bottom);
  points.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.lineTo(points[points.length - 1].x, height - padding.bottom);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  // Line stroke
  ctx.beginPath();
  ctx.strokeStyle = "#2563eb";
  ctx.lineWidth = 3;
  ctx.lineJoin = "round";
  points.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.stroke();

  // Draw points and values
  points.forEach(p => {
    // Outer white glow
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(p.x, p.y, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Inner dot
    ctx.fillStyle = (p.val >= 8) ? "#059669" : (p.val >= 5 ? "#2563eb" : "#ef4444");
    ctx.beginPath();
    ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
    ctx.fill();

    // Score label on top
    ctx.fillStyle = "#0f172a";
    ctx.font = "bold 11.5px monospace";
    ctx.textAlign = "center";
    ctx.fillText(`${p.val}`, p.x, p.y - 10);

    // Date label on bottom
    ctx.fillStyle = "#64748b";
    ctx.font = "10.5px sans-serif";
    ctx.fillText(p.date, p.x, height - padding.bottom + 18);
  });
}

// Load Practice Analytics (Mastery & Badges)
async function loadPracticeAnalytics() {
  let analyticsData = null;

  try {
    const res = await fetch(`${API_BASE}/practice/analytics`);
    if (res.ok) {
      const data = await res.json();
      analyticsData = data.analytics;
    }
  } catch (err) {
    console.warn("Could not fetch analytics from server, using local fallback:", err);
  }

  const history = getLocalPracticeHistory();

  // Render Skill & Subject Mastery
  renderSubjectMastery(analyticsData?.subject_mastery || analyticsData?.mastery, history);

  // Render Badges
  const unlockedBadges = analyticsData?.badges || evaluateLocalBadges(history);
  renderBadgesGrid(unlockedBadges);
}

function renderSubjectMastery(serverMastery, history) {
  const container = document.getElementById("skill-mastery-container");
  if (!container) return;

  const subjects = [
    { id: "math", name: "Toán Học", icon: "📐", color: "#2563eb" },
    { id: "vietnamese", name: "Tiếng Việt", icon: "📖", color: "#e11d48" },
    { id: "english", name: "Tiếng Anh", icon: "🇬🇧", color: "#059669" },
    { id: "science", name: "Khoa Học", icon: "🔬", color: "#7c3aed" }
  ];

  container.innerHTML = subjects.map(s => {
    let accuracy = 75; // Default baseline
    let totalAttempts = 0;

    let subStat = null;
    if (Array.isArray(serverMastery)) {
      subStat = serverMastery.find(m => m.subject === s.id);
    } else if (serverMastery && typeof serverMastery === "object") {
      subStat = serverMastery[s.id];
    }

    if (subStat !== null && subStat !== undefined) {
      if (typeof subStat === "number") {
        accuracy = Math.round(subStat);
      } else if (typeof subStat === "object") {
        accuracy = Math.round(subStat.accuracy_rate !== undefined ? subStat.accuracy_rate : (subStat.accuracy || 75));
        totalAttempts = subStat.attempts || 0;
      }
    } else if (history && history.length > 0) {
      const subTests = history.filter(t => t.subject === s.id);
      if (subTests.length > 0) {
        totalAttempts = subTests.length;
        const totalCorrect = subTests.reduce((sum, t) => sum + (t.correct_count || 0), 0);
        const totalQ = subTests.reduce((sum, t) => sum + (t.total_questions || (t.correct_count + t.wrong_count)), 0);
        accuracy = Math.round((totalCorrect / (totalQ || 1)) * 100);
      }
    }

    let statusText = "Đạt yêu cầu";
    let statusBg = "#eff6ff";
    let statusColor = "#1d4ed8";
    if (accuracy >= 85) {
      statusText = "Thành thạo";
      statusBg = "#f0fdf4";
      statusColor = "#15803d";
    } else if (accuracy < 60) {
      statusText = "Cần rèn luyện";
      statusBg = "#fef2f2";
      statusColor = "#b91c1c";
    }

    return `
      <div class="mastery-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 24px;">${s.icon}</span>
            <span style="font-weight: 700; font-size: 15px; color: #1e293b;">${s.name}</span>
          </div>
          <span style="padding: 2px 8px; border-radius: 12px; font-size: 11.5px; font-weight: 700; background: ${statusBg}; color: ${statusColor};">
            ${statusText}
          </span>
        </div>

        <div>
          <div style="display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 6px;">
            <span style="color: #64748b;">Độ chính xác</span>
            <span style="font-weight: 800; color: #0f172a;">${accuracy}%</span>
          </div>
          <div class="progress-bar-track">
            <div class="progress-bar-fill" style="width: ${accuracy}%; background: ${s.color};"></div>
          </div>
        </div>

        <div style="font-size: 12px; color: #64748b; margin-top: -4px;">
          Đã thực hiện: <strong>${totalAttempts} lượt luyện tập</strong>
        </div>
      </div>
    `;
  }).join("");
}

function renderBadgesGrid(unlockedBadgeIds = []) {
  const container = document.getElementById("achievements-badges-container");
  if (!container) return;

  const rawBadges = Array.isArray(unlockedBadgeIds) ? unlockedBadgeIds : [];
  const unlockedSet = new Set(
    rawBadges.map(b => typeof b === 'string' ? b : (b && b.unlocked ? b.id : null)).filter(Boolean)
  );

  container.innerHTML = BADGES_DEFINITIONS.map(b => {
    const isUnlocked = unlockedSet.has(b.id);
    return `
      <div class="badge-card ${isUnlocked ? 'unlocked' : 'locked'}">
        <div class="badge-icon-box">${b.icon}</div>
        <div style="font-weight: 800; font-size: 14.5px; color: #0f172a;">${b.title}</div>
        <p style="font-size: 12px; color: #64748b; line-height: 1.4; margin: 0;">${b.desc}</p>
        <span style="margin-top: auto; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px; ${isUnlocked ? 'background: #fef3c7; color: #b45309;' : 'background: #f1f5f9; color: #94a3b8;'}">
          ${isUnlocked ? '✓ Đã mở khóa' : '🔒 Chưa mở'}
        </span>
      </div>
    `;
  }).join("");
}

function evaluateLocalBadges(history) {
  const unlocked = [];
  if (!history || history.length === 0) return unlocked;

  // 1. First step
  unlocked.push("badge_first_step");

  // 2. Perfect score
  if (history.some(t => Number(t.score) === 10)) {
    unlocked.push("badge_perfect_score");
  }

  // 3. Persistent streak
  if (history.length >= 3) {
    unlocked.push("badge_persistent");
  }

  // 4. Speed racer (<50% duration with score >= 8)
  if (history.some(t => Number(t.score) >= 8 && t.time_spent_seconds <= (t.duration_seconds / 2))) {
    unlocked.push("badge_speed_racer");
  }

  // 5. Math master
  const mathTests = history.filter(t => t.subject === "math");
  if (mathTests.length > 0) {
    const avg = mathTests.reduce((s, t) => s + Number(t.score), 0) / mathTests.length;
    if (avg >= 8.5) unlocked.push("badge_math_master");
  }

  // 6. Scholar
  const vnTests = history.filter(t => t.subject === "vietnamese");
  if (vnTests.length > 0) {
    const avg = vnTests.reduce((s, t) => s + Number(t.score), 0) / vnTests.length;
    if (avg >= 8.5) unlocked.push("badge_scholar");
  }

  // 7. Multilingual
  if (history.some(t => t.subject === "vietnamese") && history.some(t => t.subject === "english")) {
    unlocked.push("badge_multilingual");
  }

  // 8. Top tier
  const excelCount = history.filter(t => t.ranking === "Xuất sắc").length;
  if (excelCount >= 2) {
    unlocked.push("badge_top_tier");
  }

  return unlocked;
}

// ----------------- Practice History Management -----------------

async function loadPracticeHistory() {
  const tbody = document.getElementById("practice-history-tbody");
  if (!tbody) return;

  let records = [];

  try {
    const res = await fetch(`${API_BASE}/practice/history?limit=30`);
    if (res.ok) {
      const data = await res.json();
      records = data.records || data.history || [];
    }
  } catch (err) {
    console.warn("Could not fetch history from server:", err);
  }

  if (!records || records.length === 0) {
    records = getLocalPracticeHistory();
  }

  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 24px;">Chưa có lịch sử làm bài. Bắt đầu luyện tập ngay nhé!</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map((rec, i) => {
    const dateStr = new Date(rec.created_at).toLocaleString("vi-VN");
    const scoreVal = (rec.score !== undefined) ? Number(rec.score).toFixed(1) : "0.0";
    const ranking = rec.ranking || "Khá";
    const timeSpent = `${Math.floor((rec.time_spent_seconds || 0)/60)}p ${(rec.time_spent_seconds || 0)%60}s`;

    let rankClass = "rank-kha";
    if (ranking === "Xuất sắc") rankClass = "rank-xuat-sac";
    else if (ranking === "Giỏi") rankClass = "rank-gioi";
    else if (ranking === "Trung bình") rankClass = "rank-trung-binh";
    else if (ranking === "Cần cố gắng") rankClass = "rank-can-co-gang";

    return `
      <tr>
        <td style="font-size: 12.5px; color: #64748b;">${dateStr}</td>
        <td style="font-weight: 700; color: #1e293b;">${rec.exam_title || 'Bài thi trắc nghiệm'}</td>
        <td><span class="tag-badge" style="background: #eff6ff; color: #1d4ed8;">${getSubjectName(rec.subject)}</span></td>
        <td style="font-size: 13px;">Khối ${rec.grade || 5}</td>
        <td>
          <span style="font-family: var(--font-mono); font-weight: 800; font-size: 14px; color: #047857;">
            ${scoreVal} / 10
          </span>
        </td>
        <td><span class="rank-badge-pill ${rankClass}" style="font-size: 11px; padding: 2px 8px;">${ranking}</span></td>
        <td style="font-size: 12px; color: #64748b;">${timeSpent}</td>
      </tr>
    `;
  }).join("");
}

function savePracticeHistoryLocal(record) {
  try {
    const history = getLocalPracticeHistory();
    history.unshift(record);
    localStorage.setItem("eduquest_practice_history", JSON.stringify(history.slice(0, 50)));
  } catch (e) {
    console.error("Error saving local practice history:", e);
  }
}

function getLocalPracticeHistory() {
  try {
    const raw = localStorage.getItem("eduquest_practice_history");
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function getSubjectName(sub) {
  const map = {
    math: "Toán",
    vietnamese: "Tiếng Việt",
    english: "Tiếng Anh",
    science: "Khoa học"
  };
  return map[sub] || sub || "Toán";
}
