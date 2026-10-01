// EduQuest Collector - Background Service Worker v1.3.12

chrome.runtime.onInstalled.addListener(() => {
  console.log("EduQuest Collector Extension v1.3.12 installed successfully.");
});

// Relay message from content script or popup to local EduQuest API
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "save_questions") {
    fetch("http://localhost:8000/api/questions/bulk", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
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
      sendResponse({ success: false, error: err.message || "Không thể kết nối đến máy chủ EduQuest (Port 8000)" });
    });
    return true; // Keep sendResponse open for async
  }
  
  if (request.action === "check_server") {
    fetch("http://localhost:8000/api/stats")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        sendResponse({ connected: true, data: data });
      })
      .catch((err) => sendResponse({ connected: false, error: err.message }));
    return true;
  }
});

