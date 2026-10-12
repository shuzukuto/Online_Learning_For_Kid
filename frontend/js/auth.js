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
    // API_BASE (app.js) already ends with "/api" while every auth call site
    // passes a full "/api/auth/..." path — strip the duplicate suffix once
    // here so login/register/me/users/approve never hit /api/api/... (405).
    var b = (typeof API_BASE !== "undefined" && API_BASE) ? API_BASE :
      ((typeof window !== "undefined" && window.location && window.location.origin) || "");
    return String(b).replace(/\/api$/, "");
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
    var btnSwitch = document.getElementById("btn-switch-account");
    var btnLogout = document.getElementById("btn-logout");
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
    var logged = !!((me && me.username));
    if (btnSwitch) btnSwitch.style.display = logged ? "" : "none";
    if (btnLogout) btnLogout.style.display = logged ? "" : "none";
    if (btnAdmin) btnAdmin.style.display = (me && me.role === "admin") ? "" : "none";
    var adminPanel = document.getElementById("admin-users-panel");
    if (adminPanel && !(me && me.role === "admin")) adminPanel.style.display = "none";
    // Ẩn/hiện mục Quản trị trong sidebar theo quyền admin
    try {
      var navAdmin = document.querySelector('.nav-item[data-view="admin-users"]');
      if (navAdmin) navAdmin.style.display = (me && me.role === "admin") ? "" : "none";
    } catch (e) { /* ignore */ }
    // Có phiên hợp lệ → hạ tường login (trường hợp mở lại tab khi còn login)
    if (me && me.username) { try { hideLoginWall(); } catch (e) {} }
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
      hideLoginWall();
      refreshBadge();
      try {
        if (typeof switchView === "function") switchView("dashboard");
        if (typeof loadDashboardStats === "function") loadDashboardStats();
      } catch (e) { /* ignore */ }
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

  async function doForgotPassword() {
    var u = (document.getElementById("auth-forgot-user") || {}).value || "";
    if (!u.trim()) { toast("Nhập tên đăng nhập cần lấy lại mật khẩu.", "error"); return; }
    try {
      var data = await callAuth("/api/auth/forgot", { username: u.trim() });
      toast(data.message || "Đã gửi yêu cầu. Admin duyệt sẽ cấp mật khẩu tạm.", "success");
    } catch (e) { toast(e.message, "error"); }
  }

  async function adminResetPassword(username) {
    try {
      if (typeof window !== "undefined" && window.confirm &&
          !window.confirm("Cấp mật khẩu TẠM mới cho '" + username + "'? Mật khẩu cũ mất hiệu lực ngay.")) return;
    } catch (e) { /* headless: tiếp tục */ }
    try {
      var data = await callAuth("/api/auth/reset", { username: username });
      var msg = data.message || "Đã cấp mật khẩu tạm.";
      toast(msg, "success");
      try {
        if (typeof window !== "undefined" && window.prompt)
          window.prompt("Báo mật khẩu tạm này cho user (họ đăng nhập rồi đổi ngay):", msg);
      } catch (e) { /* ignore */ }
      loadAdminUsers();
    } catch (e) { toast(e.message, "error"); }
  }

  async function doLogout() {
    try { await callAuth("/api/auth/logout", {}); } catch (e) { /* ignore */ }
    AuthStore.clear();
    toast("Đã đăng xuất.", "success");
    refreshBadge();
    showLoginWall();
  }

  async function switchAccount() {
    // Đổi tài khoản: đăng xuất phiên hiện tại rồi mở ngay form đăng nhập
    // (trên tường login) để nhập tài khoản khác — không cần tải lại trang.
    try { await callAuth("/api/auth/logout", {}); } catch (e) { /* ignore */ }
    AuthStore.clear();
    try { refreshBadge(); } catch (e) {}
    showLoginWall();
    openAuthModal();
    try {
      if (typeof switchAuthTab === "function") switchAuthTab("login");
    } catch (e) { /* modal tab mặc định đã là login */ }
    toast("Mời đăng nhập tài khoản khác.", "success");
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
    var boxes = [];
    ["admin-users-list", "admin-users-view-list"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) boxes.push(el);
    });
    if (!boxes.length) return;
    boxes.forEach(function (box) {
      box.innerHTML = "<div style='color:#64748b;font-size:13px;'>Đang tải...</div>";
    });
    try {
      var res = await fetch(apiBase() + "/api/auth/users", { headers: authHeaders() });
      var data = await res.json();
      if (!res.ok) throw new Error(data.detail || ("HTTP " + res.status));
      var users = data.users || [];
      var me = AuthStore.user() || {};
      if (!users.length) {
        boxes.forEach(function (box) {
          box.innerHTML = "<div style='color:#64748b;font-size:13px;'>Chưa có tài khoản.</div>";
        });
        return;
      }
      var html = "<div style='display:flex;gap:8px;margin-bottom:10px;font-size:12px;color:#64748b;'>"
        + "<span>🟢 active: dùng được</span><span>🟡 pending: chờ duyệt</span>"
        + "<span>🔴 banned: bị khóa</span><span>👑 admin</span></div>"
        + users.map(function (x) {
        var pill = x.status === "active"
          ? "<span style='background:#dcfce7;color:#166534;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;'>active</span>"
          : x.status === "pending"
            ? "<span style='background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;'>pending</span>"
            : "<span style='background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;'>banned</span>";
        var role = x.role === "admin" ? " 👑admin" : "";
        var isSelf = (x.username || "") === (me.username || "");
        var btns = "";
        if (!isSelf) {
          if (x.status === "pending")
            btns += "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.approve('" + x.username + "','active')\">✔ Duyệt</button> ";
          if (x.status === "active")
            btns += "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.approve('" + x.username + "','banned')\">⛔ Khóa</button> ";
          if (x.status === "banned")
            btns += "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.approve('" + x.username + "','active')\">🔓 Mở khóa</button> ";
          btns += (x.role === "admin"
            ? "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.setRole('" + x.username + "','user')\" title='Hạ xuống user'>⬇ user</button> "
            : "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.setRole('" + x.username + "','admin')\" title='Nâng lên admin'>⬆ admin</button> ");
          btns += "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.deleteUser('" + x.username + "')\" style='color:#b91c1c;border-color:#fecaca;' title='Xóa vĩnh viễn'>🗑 Xóa</button>"; 
          btns += "<button class='btn btn-secondary btn-sm' onclick=\"EduAuth.adminResetPassword('" + x.username + "')\" title='Cấp mật khẩu tạm mới (mật khẩu cũ mất hiệu lực ngay)'>🔑 Đặt lại MK</button>";
        } else {
          btns = "<span style='font-size:11px;color:#94a3b8;'>(bạn)</span>";
        }
        return "<div style='display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:13px;flex-wrap:wrap;'>"
          + "<div><b>" + x.username + "</b>" + role + " " + pill
          + "<div style='color:#94a3b8;font-size:11px;'>tạo: " + (x.created_at || "?")
          + (x.approved_by ? " • duyệt bởi: " + x.approved_by : "") + "</div></div>"
          + "<div style='display:flex;gap:6px;flex-wrap:wrap;'>" + btns + "</div></div>";
      }).join("");
      boxes.forEach(function (box) { box.innerHTML = html; });
    } catch (e) {
      boxes.forEach(function (box) {
        box.innerHTML = "<div style='color:#dc2626;font-size:13px;'>" + e.message + "</div>";
      });
    }
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

  // Login wall: khi API trả 401 (chưa login / hết phiên), mở tường login
  // toàn màn hình thay vì để dashboard trống + lỗi rải rác từng fetch.
  function showLoginWall() {
    try {
      var w = document.getElementById("login-wall");
      if (w) { w.style.display = "flex"; return; }
      w = document.createElement("div");
      w.id = "login-wall";
      w.setAttribute("style", "position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(15,23,42,0.72);backdrop-filter:blur(3px);");
      w.innerHTML = "<div style='background:#fff;border-radius:16px;max-width:420px;width:92%;padding:28px;text-align:center;box-shadow:0 25px 50px -12px rgba(0,0,0,.4);'>"
        + "<div style='font-size:44px;'>🔐</div>"
        + "<h2 style='margin:10px 0 6px;font-size:19px;color:#0f172a;'>EduQuest Pro cần đăng nhập</h2>"
        + "<p style='margin:0 0 18px;font-size:13.5px;color:#64748b;'>Ai có link đều mở được trang — nhưng phải đăng nhập mới dùng được dữ liệu. Chưa có tài khoản thì đăng ký, chờ admin duyệt.</p>"
        + "<button id='login-wall-btn' class='btn btn-primary' style='width:100%;font-weight:700;padding:10px;'>🔑 Đăng nhập / Đăng ký</button></div>";
      document.body.appendChild(w);
      var b = document.getElementById("login-wall-btn");
      if (b) b.addEventListener("click", function () { openAuthModal(); });
    } catch (e) { /* ignore */ }
  }

  function hideLoginWall() {
    try {
      var w = document.getElementById("login-wall");
      if (w) w.style.display = "none";
    } catch (e) { /* ignore */ }
  }

  // Fetch wrapper: tự gắn Bearer + mở tường login khi 401 + báo 403 rõ ràng.
  // Các module khác gọi EduAuth.apiFetch thay vì fetch trần cho /api/*.
  async function apiFetch(path, options) {
    var opts = options || {};
    opts.headers = Object.assign({}, authHeaders(), opts.headers || {});
    var res = await fetch(apiBase() + path, opts);
    if (res && res.status === 401) {
      AuthStore.clear();
      try { refreshBadge(); } catch (e) {}
      showLoginWall();
      var d401 = null;
      try { d401 = await res.clone().json(); } catch (e) { d401 = null; }
      throw new Error((d401 && d401.detail) || "Chưa đăng nhập hoặc phiên đã hết hạn.");
    }
    if (res && res.status === 403) {
      var d403 = null;
      try { d403 = await res.clone().json(); } catch (e) { d403 = null; }
      throw new Error((d403 && d403.detail) || "Tài khoản không đủ quyền.");
    }
    return res;
  }

  // Kiểm tra phiên lúc mở trang: không login → hiện tường ngay (không chờ
  // fetch đầu tiên fail). Trả true khi đã login.
  async function requireLogin() {
    var me = AuthStore.user();
    if (!me || !AuthStore.token()) { showLoginWall(); return false; }
    try {
      // /api/auth/me là route GET — phải fetch GET kèm Bearer (callAuth
      // POST-only sẽ 405, xóa oan token, đá user ra sau reload — bug
      // E2E 2026-10-12).
      var res = await fetch(apiBase() + "/api/auth/me", { headers: authHeaders() });
      if (!res.ok) throw new Error("HTTP " + res.status);
      hideLoginWall();
      return true;
    } catch (e) {
      AuthStore.clear();
      try { refreshBadge(); } catch (err) {}
      showLoginWall();
      return false;
    }
  }

  // Quản trị: điều hướng sang view riêng trong sidebar (chỉ admin).
  function openAdminView() {
    try {
      var me = AuthStore.user();
      if (!me || me.role !== "admin") { toast("Chỉ admin mới vào trang Quản trị.", "error"); return; }
      if (typeof switchView === "function") switchView("admin-users");
      loadAdminUsers();
    } catch (e) { toast("Không mở được trang Quản trị.", "error"); }
  }

  async function setRole(username, role) {
    try {
      var data = await callAuth("/api/auth/role", { username: username, role: role });
      toast(data.message, "success");
      loadAdminUsers();
    } catch (e) { toast(e.message, "error"); }
  }

  async function deleteUser(username) {
    var me = AuthStore.user() || {};
    if ((username || "") === (me.username || "")) { toast("Không thể tự xóa chính mình.", "error"); return; }
    try {
      if (typeof window !== "undefined" && window.confirm &&
          !window.confirm("Xóa vĩnh viễn tài khoản '" + username + "'?")) return;
    } catch (e) { /* headless: tiếp tục */ }
    try {
      var data = await callAuth("/api/auth/delete", { username: username });
      toast(data.message, "success");
      loadAdminUsers();
    } catch (e) { toast(e.message, "error"); }
  }

  window.EduAuth = {
    AuthStore: AuthStore,
    authHeaders: authHeaders,
    apiFetch: apiFetch,
    requireLogin: requireLogin,
    showLoginWall: showLoginWall,
    hideLoginWall: hideLoginWall,
    openAdminView: openAdminView,
    setRole: setRole,
    deleteUser: deleteUser,
    openAuthModal: openAuthModal,
    closeAuthModal: closeAuthModal,
    doLogin: doLogin,
    doRegister: doRegister,
    doLogout: doLogout,
    switchAccount: switchAccount,
    doChangePassword: doChangePassword,
    doForgotPassword: doForgotPassword,
    adminResetPassword: adminResetPassword,
    loadAdminUsers: loadAdminUsers,
    approve: approve,
    refreshBadge: refreshBadge
  };

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", function () { refreshBadge(); });
  }
})();
