// EduQuest Collector - Background Service Worker v1.3.18
// Hỗ trợ URL server động — dùng chrome.storage.sync

// URL server chung — tất cả dữ liệu cào được gửi về đây
const DEFAULT_SERVER = "https://otter-scrawny-squall.ngrok-free.dev";

// ngrok free hiển thị trang cảnh báo HTML cho request từ trình duyệt nếu thiếu header này
const COMMON_HEADERS = { "ngrok-skip-browser-warning": "true" };

/** Lấy URL server hiện tại từ storage (mặc định localhost:8000) */
function getServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER }, (result) => {
      let url = (result.serverUrl || DEFAULT_SERVER).trim().replace(/\/$/, "");
      resolve(url);
    });
  });
}

/** Chuyển lỗi fetch thô thành thông báo dễ hiểu (kèm URL server) */
function describeFetchError(err, baseUrl) {
  const msg = (err && err.message) || "";
  if (/failed to fetch|networkerror|load failed/i.test(msg)) {
    return `Không kết nối được server ${baseUrl} (server/tunnel đang tắt hoặc sai URL)`;
  }
  return msg || `Không thể kết nối đến ${baseUrl}`;
}

/** Diễn giải lỗi HTTP (đặc biệt ngrok offline trả 404) */
function describeHttpError(res, data, baseUrl) {
  if (data && data.detail) return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
  if (res.status === 404 && /ngrok/i.test(baseUrl)) {
    return `Tunnel ngrok ${baseUrl} đang offline (HTTP 404). Hãy bật lại server hoặc đổi URL trong popup`;
  }
  return `Lỗi máy chủ HTTP ${res.status} (${baseUrl})`;
}

/** POST JSON đến API EduQuest và trả kết quả chuẩn hóa qua sendResponse */
function postJson(path, body, sendResponse) {
  getServerUrl().then((baseUrl) => {
    fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...COMMON_HEADERS },
      body: JSON.stringify(body)
    })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          sendResponse({ success: false, error: describeHttpError(res, data, baseUrl), serverUrl: baseUrl });
        } else {
          sendResponse({ success: true, data: data, serverUrl: baseUrl });
        }
      })
      .catch((err) => {
        sendResponse({ success: false, error: describeFetchError(err, baseUrl), serverUrl: baseUrl });
      });
  });
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("EduQuest Collector Extension v1.3.18 installed.");
  chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER }, (r) => {
    if (!r.serverUrl) chrome.storage.sync.set({ serverUrl: DEFAULT_SERVER });
  });
});

// Relay message từ content script hoặc popup đến EduQuest API
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "save_questions") {
    postJson("/api/questions/bulk", { questions: request.questions }, sendResponse);
    return true;
  }

  // Cập nhật khối lớp cho các câu hỏi ĐÃ lưu trong CSDL (bulk insert bỏ qua câu trùng nên không tự cập nhật)
  if (request.action === "update_grade") {
    postJson("/api/questions/bulk-update-grade", { question_ids: request.question_ids || [], grade: request.grade }, sendResponse);
    return true;
  }

  if (request.action === "sync_log" && request.log) {
    // Relay fire-and-forget tu content script (tranh CORS khi fetch truc tiep tu trang VioEdu)
    postJson("/api/collect/logs/sync", request.log, () => {});
    return false;
  }

  if (request.action === "check_server") {
    getServerUrl().then((baseUrl) => {
      fetch(`${baseUrl}/api/stats`, { headers: COMMON_HEADERS })
        .then(async (res) => {
          if (!res.ok) throw new Error(describeHttpError(res, null, baseUrl));
          const data = await res.json();
          sendResponse({ connected: true, data: data, serverUrl: baseUrl });
        })
        .catch((err) => sendResponse({ connected: false, error: describeFetchError(err, baseUrl), serverUrl: baseUrl }));
    });
    return true;
  }

  if (request.action === "get_server_url") {
    getServerUrl().then((url) => sendResponse({ serverUrl: url }));
    return true;
  }

  if (request.action === "set_server_url") {
    const newUrl = (request.serverUrl || DEFAULT_SERVER).trim().replace(/\/$/, "");
    chrome.storage.sync.set({ serverUrl: newUrl }, () => {
      sendResponse({ success: true, serverUrl: newUrl });
    });
    return true;
  }
});
