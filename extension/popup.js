// EduQuest Pro - Popup Controller v1.3.15
document.addEventListener("DOMContentLoaded", () => {
  const dot = document.getElementById("status-dot");
  const text = document.getElementById("status-text");
  const scanBtn = document.getElementById("btn-scan-tab");
  const harvestBtn = document.getElementById("btn-harvest-all-tab");
  const questionsCountEl = document.getElementById("popup-questions-count");
  const logsCountEl = document.getElementById("popup-logs-count");
  const questionsListEl = document.getElementById("popup-scanned-list");
  const terminalListEl = document.getElementById("popup-terminal-list");

  // Question tab actions
  const saveAllBtn = document.getElementById("btn-save-all-popup");
  const clearQuestionsBtn = document.getElementById("btn-clear-scanned-popup");

  // Log tab actions
  const copyLogsBtn = document.getElementById("btn-copy-logs-popup");
  const clearLogsBtn = document.getElementById("btn-clear-logs-popup");
  const refreshLogsBtn = document.getElementById("btn-refresh-logs-popup");
  const searchInput = document.getElementById("popup-log-search-input");
  const clearSearchBtn = document.getElementById("btn-clear-search");

  // State
  let localCaptured = [];
  let localLogs = [];
  let currentActiveTab = "tab-questions";
  let activeLogFilter = "all";
  let logSearchQuery = "";

  function escapeHtml(str) {
    if (typeof str !== "string") str = String(str || "");
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // 1. Check Server Connection
  function checkServerConnection() {
    fetch("http://localhost:8000/api/stats")
      .then(res => res.json())
      .then(data => {
        dot.className = "dot connected";
        text.innerText = `Đã kết nối (${data.total_questions || 0} câu hỏi trong CSDL)`;
        text.style.color = "#4ade80";
      })
      .catch(() => {
        dot.className = "dot";
        text.innerText = "Chưa kết nối EduQuest (Port 8000)";
        text.style.color = "#f87171";
      });
  }

  // 2. Tab Switcher
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      currentActiveTab = targetId;
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");

      if (targetId === "tab-logs") {
        renderTerminalLogs();
      } else {
        renderQuestionsList();
      }
    });
  });

  // 3. Load Storage Data
  function loadStorageData() {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(["eduquest_captured_questions", "eduquest_ext_logs"], (res) => {
        if (res) {
          localCaptured = Array.isArray(res.eduquest_captured_questions) ? res.eduquest_captured_questions : [];
          localLogs = Array.isArray(res.eduquest_ext_logs) ? res.eduquest_ext_logs : [];
        } else {
          localCaptured = [];
          localLogs = [];
        }

        if (questionsCountEl) questionsCountEl.innerText = localCaptured.length;
        if (logsCountEl) logsCountEl.innerText = localLogs.length;

        updateLogFilterPillCounts();
        renderQuestionsList();
        renderTerminalLogs();
      });
    }
  }

  // 4. Render Questions List
  function renderQuestionsList() {
    if (!questionsListEl) return;
    if (localCaptured.length === 0) {
      questionsListEl.innerHTML = `
        <div style="color: #64748b; font-size: 11.5px; text-align: center; padding: 25px 10px; line-height: 1.5;">
          <div style="font-size: 24px; margin-bottom: 6px;">🔍</div>
          Chưa có câu hỏi nào được bắt trong phiên.<br/>
          Mở bài tập trên VioEdu, Trạng Nguyên, Hành Trang Số... để thu thập tự động.
        </div>
      `;
      return;
    }

    questionsListEl.innerHTML = localCaptured.map((q, idx) => {
      const isSaved = q.saved_to_db;
      const statusHtml = isSaved
        ? `<span style="background: #052e16; color: #4ade80; border: 1px solid #14532d; padding: 1px 6px; border-radius: 8px; font-size: 10px; font-weight: 700;">✓ Đã lưu</span>`
        : `<span style="background: #451a03; color: #fde68a; border: 1px solid #78350f; padding: 1px 6px; border-radius: 8px; font-size: 10px; font-weight: 700;">⏳ Chờ lưu</span>`;

      const snippet = escapeHtml((q.content_text || "").substring(0, 110)) + ((q.content_text || "").length > 110 ? "..." : "");
      const platform = escapeHtml((q.source_platform || "ONLINE").toUpperCase());

      return `
        <div class="scanned-item" data-id="${q.id}">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <strong style="color: #38bdf8;">Câu #${idx + 1} (${platform})</strong>
            <div style="display: flex; align-items: center; gap: 6px;">
              ${statusHtml}
              <button class="btn-del-single-popup" data-id="${q.id}" title="Xóa câu hỏi này">✕</button>
            </div>
          </div>
          <div style="color: #cbd5e1; line-height: 1.35; font-size: 11px;">${snippet}</div>
        </div>
      `;
    }).join("");

    // Attach single item delete handlers
    document.querySelectorAll(".btn-del-single-popup").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const qid = btn.getAttribute("data-id");
        if (!qid) return;
        localCaptured = localCaptured.filter(item => item.id !== qid);
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          chrome.storage.local.set({ eduquest_captured_questions: localCaptured });
        }
        if (questionsCountEl) questionsCountEl.innerText = localCaptured.length;
        renderQuestionsList();
      });
    });
  }

  // 5. Update Log Filter Pill Counts
  function updateLogFilterPillCounts() {
    let successCount = 0, skipCount = 0, netCount = 0, errorCount = 0;
    localLogs.forEach(l => {
      if (l.type === "success") successCount++;
      else if (l.type === "skip" || l.type === "warn") skipCount++;
      else if (l.type === "net") netCount++;
      else if (l.type === "error") errorCount++;
    });

    const elAll = document.getElementById("count-log-all");
    const elSuccess = document.getElementById("count-log-success");
    const elSkip = document.getElementById("count-log-skip");
    const elNet = document.getElementById("count-log-net");
    const elError = document.getElementById("count-log-error");

    if (elAll) elAll.innerText = localLogs.length;
    if (elSuccess) elSuccess.innerText = successCount;
    if (elSkip) elSkip.innerText = skipCount;
    if (elNet) elNet.innerText = netCount;
    if (elError) elError.innerText = errorCount;
  }

  // 6. Render Terminal Logs
  function renderTerminalLogs() {
    if (!terminalListEl) return;

    let filtered = localLogs;
    if (activeLogFilter !== "all") {
      filtered = filtered.filter(l => {
        if (activeLogFilter === "skip") return l.type === "skip" || l.type === "warn";
        return l.type === activeLogFilter;
      });
    }

    if (logSearchQuery) {
      const q = logSearchQuery.toLowerCase();
      filtered = filtered.filter(l => (l.msg && l.msg.toLowerCase().includes(q)) || (l.time && l.time.includes(q)));
    }

    if (filtered.length === 0) {
      terminalListEl.innerHTML = `
        <div style="color: #64748b; font-size: 11px; text-align: center; padding: 25px 10px; line-height: 1.5;">
          ${logSearchQuery ? "Không có log nào khớp với từ khóa tìm kiếm." : "Chưa có log ghi nhận. Mở trang học để bắt đầu theo dõi."}
        </div>
      `;
      return;
    }

    terminalListEl.innerHTML = filtered.map(l => {
      let badgeClass = "badge-info";
      let tagText = "INFO";
      let msgColor = "#38bdf8";

      if (l.type === "error") {
        badgeClass = "badge-error";
        tagText = "LỖI";
        msgColor = "#f87171";
      } else if (l.type === "success") {
        badgeClass = "badge-success";
        tagText = "OK";
        msgColor = "#4ade80";
      } else if (l.type === "skip" || l.type === "warn") {
        badgeClass = "badge-skip";
        tagText = "BỎ QUA";
        msgColor = "#fbbf24";
      } else if (l.type === "net") {
        badgeClass = "badge-net";
        tagText = "MẠNG";
        msgColor = "#c084fc";
      }

      const src = l.source || "online";
      return `
        <div class="terminal-row" title="Click để sao chép dòng log này" data-log-msg="[${escapeHtml(l.time)}] [${escapeHtml(src)}] [${tagText}] ${escapeHtml(l.msg)}">
          <span class="terminal-time">[${escapeHtml(l.time)}]</span>
          <span class="terminal-badge" style="background: rgba(14, 165, 233, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); font-weight: 600; font-size: 9.5px; padding: 1px 5px; border-radius: 3px;">[${escapeHtml(src)}]</span>
          <span class="terminal-badge ${badgeClass}">[${tagText}]</span>
          <span style="color: ${msgColor}; word-break: break-word;">${escapeHtml(l.msg)}</span>
        </div>
      `;
    }).join("");

    // Add click-to-copy for individual rows
    terminalListEl.querySelectorAll(".terminal-row").forEach(row => {
      row.addEventListener("click", () => {
        const textToCopy = row.getAttribute("data-log-msg");
        if (textToCopy) {
          navigator.clipboard.writeText(textToCopy).then(() => {
            const originalBorder = row.style.borderColor;
            row.style.background = "rgba(56, 189, 248, 0.15)";
            setTimeout(() => {
              row.style.background = "";
            }, 300);
          });
        }
      });
    });
  }

  // 7. Filter Pills Event Listeners
  document.querySelectorAll(".log-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".log-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeLogFilter = pill.getAttribute("data-filter") || "all";
      renderTerminalLogs();
    });
  });

  // 8. Search Input Event Listener
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      logSearchQuery = e.target.value.trim();
      if (clearSearchBtn) {
        clearSearchBtn.style.display = logSearchQuery ? "block" : "none";
      }
      renderTerminalLogs();
    });
  }

  if (clearSearchBtn) {
    clearSearchBtn.addEventListener("click", () => {
      searchInput.value = "";
      logSearchQuery = "";
      clearSearchBtn.style.display = "none";
      renderTerminalLogs();
    });
  }

  // 9. Log Tab Action Buttons
  if (copyLogsBtn) {
    copyLogsBtn.addEventListener("click", () => {
      let filtered = localLogs;
      if (activeLogFilter !== "all") {
        filtered = filtered.filter(l => {
          if (activeLogFilter === "skip") return l.type === "skip" || l.type === "warn";
          return l.type === activeLogFilter;
        });
      }
      if (filtered.length === 0) {
        alert("Không có log nào để sao chép!");
        return;
      }
      const text = filtered.map(l => `[${l.time}] [${l.source || 'online'}] [${l.type.toUpperCase()}] ${l.msg}`).join("\n");
      navigator.clipboard.writeText(text).then(() => {
        const orig = copyLogsBtn.innerText;
        copyLogsBtn.innerText = "✓ Đã chép";
        setTimeout(() => { copyLogsBtn.innerText = orig; }, 1500);
      });
    });
  }

  if (clearLogsBtn) {
    clearLogsBtn.addEventListener("click", () => {
      if (confirm("Bạn có chắc muốn xóa toàn bộ nhật ký debug?")) {
        localLogs = [];
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          chrome.storage.local.set({ eduquest_ext_logs: [] });
        }
        if (logsCountEl) logsCountEl.innerText = "0";
        updateLogFilterPillCounts();
        renderTerminalLogs();
      }
    });
  }

  if (refreshLogsBtn) {
    refreshLogsBtn.addEventListener("click", () => {
      loadStorageData();
      checkServerConnection();
    });
  }

  // 10. Question Tab Action Buttons
  if (saveAllBtn) {
    saveAllBtn.addEventListener("click", () => {
      if (localCaptured.length === 0) {
        alert("Danh sách câu hỏi đang trống!");
        return;
      }
      saveAllBtn.innerText = "Đang lưu...";
      chrome.runtime.sendMessage({ action: "save_questions", questions: localCaptured }, (res) => {
        saveAllBtn.innerText = "💾 Lưu tất cả";
        if (res && res.success) {
          localCaptured.forEach(q => { q.saved_to_db = true; });
          if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ eduquest_captured_questions: localCaptured });
          }
          renderQuestionsList();
          alert(`Đã lưu thành công ${localCaptured.length} câu hỏi vào CSDL!`);
        } else {
          alert("Lỗi lưu CSDL: " + (res?.error || "Không kết nối được server port 8000"));
        }
      });
    });
  }

  if (clearQuestionsBtn) {
    clearQuestionsBtn.addEventListener("click", () => {
      if (confirm("Bạn có chắc muốn xóa danh sách câu hỏi đã quét tạm thời này?")) {
        localCaptured = [];
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          chrome.storage.local.set({ eduquest_captured_questions: [] });
        }
        if (questionsCountEl) questionsCountEl.innerText = "0";
        renderQuestionsList();

        // Notify active tab to clear its anti-duplicate sets and immediately re-scan
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          if (tabs && tabs[0]) {
            chrome.tabs.sendMessage(tabs[0].id, { action: "clear_and_rescan" }).catch(() => {});
          }
        });
      }
    });
  }

  // 11. Relay Action Buttons (Harvest All, Quick Scan)
  if (harvestBtn) {
    harvestBtn.addEventListener("click", () => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          chrome.scripting.executeScript({
            target: { tabId: tabs[0].id },
            func: () => {
              const btn = document.getElementById("eduquest-harvest-all-btn") || document.getElementById("eduquest-scan-btn");
              if (btn) btn.click();
              else alert("Vui lòng mở trang web học tập (VioEdu, Hành Trang Số, Trạng Nguyên...) để cào câu hỏi.");
            }
          });
        }
      });
    });
  }

  if (scanBtn) {
    scanBtn.addEventListener("click", () => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, { action: "force_scan" }, (res) => {
            if (chrome.runtime.lastError || !res) {
              chrome.scripting.executeScript({
                target: { tabId: tabs[0].id },
                func: () => {
                  const btn = document.getElementById("eduquest-scan-btn");
                  if (btn) btn.click();
                  else alert("Vui lòng mở trang web học tập (VioEdu, Hành Trang Số, Trạng Nguyên...) để quét.");
                }
              }).catch(() => {});
            }
          });
        }
      });
    });
  }

  // 12. Storage Live Watcher
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
    chrome.storage.onChanged.addListener((changes, areaName) => {
      if (areaName === "local") {
        if (changes.eduquest_captured_questions) {
          localCaptured = changes.eduquest_captured_questions.newValue || [];
          if (questionsCountEl) questionsCountEl.innerText = localCaptured.length;
          if (currentActiveTab === "tab-questions") renderQuestionsList();
        }
        if (changes.eduquest_ext_logs) {
          localLogs = changes.eduquest_ext_logs.newValue || [];
          if (logsCountEl) logsCountEl.innerText = localLogs.length;
          updateLogFilterPillCounts();
          if (currentActiveTab === "tab-logs") renderTerminalLogs();
        }
      }
    });
  }

  // Initial Boot
  checkServerConnection();
  loadStorageData();
});
