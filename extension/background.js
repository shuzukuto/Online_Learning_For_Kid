// EduQuest Collector - Background Service Worker v1.3.16
// Hỗ trợ URL server động — dùng chrome.storage.sync

// URL server chung — tất cả dữ liệu cào được gửi về đây
const DEFAULT_SERVER = "https://otter-scrawny-squall.ngrok-free.dev";

/** Lấy URL server hiện tại từ storage (mặc định localhost:8000) */
function getServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER }, (result) => {
      let url = (result.serverUrl || DEFAULT_SERVER).trim().replace(/\/$/, "");
      resolve(url);
    });
  });
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("EduQuest Collector Extension v1.3.16 installed.");
  chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER }, (r) => {
    if (!r.serverUrl) chrome.storage.sync.set({ serverUrl: DEFAULT_SERVER });
  });
});

// Relay message từ content script hoặc popup đến EduQuest API
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "save_questions") {
    getServerUrl().then((baseUrl) => {
      fetch(`${baseUrl}/api/questions/bulk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions: request.questions })
      })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          sendResponse({ success: false, error: data.detail || `Lỗi máy chủ HTTP ${res.status}` });
        } else {
          sendResponse({ success: true, data: data });
        }
      })
      .catch((err) => {
        sendResponse({ success: false, error: err.message || `Không thể kết nối đến ${baseUrl}` });
      });
    });
    return true;
  }

  if (request.action === "check_server") {
    getServerUrl().then((baseUrl) => {
      fetch(`${baseUrl}/api/stats`)
        .then(async (res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          sendResponse({ connected: true, data: data, serverUrl: baseUrl });
        })
        .catch((err) => sendResponse({ connected: false, error: err.message, serverUrl: baseUrl }));
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


