/* EduQuest Pro — Account auth (login/register/change-password + admin approval).
 * Token stored in localStorage; every authed fetch goes through authHeaders().
 * Pure helpers (AuthStore) are unit-testable via node harness.
 */
(function () {
  "use strict";

  var TOKEN_KEY = "eduquest_auth_token";
  var USER_KEY = "eduquest_auth_user";

  var AuthStore = {
    save: function (token, user) {
      try {
        localStorage.setItem(TOKEN_KEY, token || "");
        localStorage.setItem(USER_KEY, JSON.stringify(user || null));
      } catch (e) { /* private mode */ }
    },
    clear: function () {
      try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      } catch (e) { /* ignore */ }
    },
    token: function () {
      try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
    },
    user: function () {
      try {
        var raw = localStorage.getItem(USER_KEY);
        return raw ? JSON.parse(raw) : null;
      } catch (e) { return null; }
    }
  };

  function apiBase() {
    if (typeof API_BASE !== "undefined" && API_BASE) return API_BASE;
    return (typeof window !== "undefined" && window.location && window.location.origin) || "";
  }

  function authHeaders() {
    var t = AuthStore.token();
    return t ? { "Authorization": "Bearer " + t } : {};
  }

  async function callAuth(path, body) {
    var res = await fetch(apiBase() + path, {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json" }, authHeaders()),
      body: JSON.stringify(body || {})
    });
    var data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) throw new Error((data && data.detail) || ("HTTP " + res.status));
    return data || {};
  }

  async function refreshBadge() {
    var badge = document.getElementById("auth-user-badge");
    var btnLogin = document.getElementById("btn-open-auth-modal");
    var btnAdmin = document.getElementById("btn-open-admin-users");
    var me = AuthStore.user();
    // Validate token against server (cheap) — drop it if expired.
    if (me && AuthStore.token()) {
      try {
        var res = await fetch(apiBase() + "/api/auth/me", { headers: authHeaders() });
        if (!res.ok) { AuthStore.clear(); me = null; }
      } catch (e) { /* offline: keep local state */ }
    }
    if (badge) {
      if (me && me.username) {
        badge.style.display = "inline-flex";
        badge.textContent = (me.role === "admin" ? "👑 " : "👤 ") + me.username;
        badge.title = me.role === "admin" ? "Tài khoản admin" : "Tài khoản đã đăng nhập";
      } else {
        badge.style.display = "none";
      }
    }
    if (btnLogin) btnLogin.style.display = (me && me.username) ? "none" : "";
    if (btnAdmin) btnAdmin.style.display = (me && me.role === "admin") ? "" : "none";
    var adminPanel = document.getElementById("admin-users-panel");
    if (adminPanel && !(me && me.role === "admin")) adminPanel.style.display = "none";
  }

  function openAuthModal() { var m = document.getElementById("modal-auth"); if (m) m.style.display = "flex"; }
  function closeAuthModal() { var m = document.getElementById("modal-auth"); if (m) m.style.display = "none"; }

  async function doLogin() {
    var u = (document.getElementById("auth-login-user") || {}).value || "";
    var p = (document.getElementById("auth-login-pass") || {}).value || "";
    try {
      var data = await callAuth("/api/auth/login", { username: u.trim(), password: p });
      AuthStore.save(data.token, { username: data.username, role: data.role });
      toast("Đăng nhập thành công. Xin chào " + data.username + "!", "success");
      closeAuthModal();
      refreshBadge();
    } catch (e) { toast(e.message, "error"); }
  }

  async function doRegister() {
    var u = (document.getElementById("auth-reg-user") || {}).value || "";
    var p = (document.getElementById("auth-reg-pass") || {}).value || "";
    try {
      var data = await callAuth("/api/auth/register", { username: u.trim(), password: p });
      toast(data.message || "Đăng ký thành công! Chờ admin phê duyệt.", "success");
    } catch (e) { toast(e.message, "error"); }
  }

  async function doLogout() {
    try { await callAuth("/api/auth/logout", {}); } catch (e) { /* ignore */ }
    AuthStore.clear();
    toast("Đã đăng xuất.", "success");
    refreshBadge();
  }

  async function doChangePassword() {
    var o = (document.getElementById("auth-old-pass") || {}).value || "";
    var n = (document.getElementById("auth-new-pass") || {}).value || "";
    try {
      var data = await callAuth("/api/auth/change-password", { old_password: o, new_password: n });
      toast((data.message || "Đổi mật khẩu xong.") + " Vui lòng đăng nhập lại.", "success");
      AuthStore.clear();
      refreshBadge();
    } catch (e) { toast(e.message, "error"); }
  }

  async function loadAdminUsers() {
    var box = document.getElementById("admin-users-list");
    if (!box) return;
    box.innerHTML = "<div style='color:#64748b;font-size:13px;'>Đang tải...</div>";
    try {
      var res = await fetch(apiBase() + "/api/auth/users", { headers: authHeaders() });
      var data = await res.json();
      if (!res.ok) throw new Error(data.detail || ("HTTP " + res.status));
      var users = data.users || [];
      if (!users.length) { box.innerHTML = "<div style='color:#64748b;font-size:13px;'>Chưa có tài khoản.</div>"; return; }
      box.innerHTML = users.map(function (x) {
        var pill = x.status === "active"
          ? "<span style='background:#dcfce7;color:#166534;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;'>active</span>"
          : x.status === "pending"
            ? "<span style='background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;'>pending</span>"
            : "<span style='background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;'>banned</span>";
        var role = x.role === "admin" ? " 👑admin" : "";
        var btns = x.role === "admin" ? "" :
          "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.approve('" + x.username + "','active')\">✔ Duyệt</button> " +
          "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.approve('" + x.username + "','banned')\">⛔ Khóa</button>";
        return "<div style='display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px;'>" +
          "<div><b>" + x.username + "</b>" + role + " " + pill +
          "<div style='color:#94a3b8;font-size:11px;'>tạo: " + (x.created_at || "?") + "</div></div>" +
          "<div style='display:flex;gap:6px;'>" + btns + "</div></div>";
      }).join("");
    } catch (e) { box.innerHTML = "<div style='color:#dc2626;font-size:13px;'>" + e.message + "</div>"; }
  }

  async function approve(username, status) {
    try {
      var data = await callAuth("/api/auth/approve", { username: username, status: status });
      toast(data.message, "success");
      loadAdminUsers();
    } catch (e) { toast(e.message, "error"); }
  }

  function toast(msg, type) {
    if (typeof showToast === "function") showToast(msg, type);
    else if (typeof window !== "undefined" && window.alert) window.alert(msg);
  }

  window.EduAuth = {
    AuthStore: AuthStore,
    authHeaders: authHeaders,
    openAuthModal: openAuthModal,
    closeAuthModal: closeAuthModal,
    doLogin: doLogin,
    doRegister: doRegister,
    doLogout: doLogout,
    doChangePassword: doChangePassword,
    loadAdminUsers: loadAdminUsers,
    approve: approve,
    refreshBadge: refreshBadge
  };

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", function () { refreshBadge(); });
  }
})();
