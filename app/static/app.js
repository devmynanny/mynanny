// app/static/app.js
function setToken(token) {
  // Cookie-based auth is primary; keep this as a no-op for legacy callers.
  if (!token) return;
}

function getToken() {
  return null;
}

function clearToken() {
  localStorage.removeItem("token");
  localStorage.removeItem("is_admin");
  sessionStorage.removeItem("impersonation_token");
}

function formatDateTimeZA(value) {
  if (!value) return "-";
  let raw = value;
  if (typeof raw === "string") {
    const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw);
    if (!hasTz) {
      raw = raw.replace(" ", "T");
      // Treat naive timestamps as Africa/Johannesburg local time (UTC+2)
      raw = raw + "+02:00";
    }
  }
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("en-ZA", { timeZone: "Africa/Johannesburg" });
}

window.formatDateTimeZA = formatDateTimeZA;

function toIsoFromZA(dateStr, timeStr) {
  if (!dateStr || !timeStr) return null;
  const parts = dateStr.split("-");
  if (parts.length !== 3) return null;
  const [y, m, d] = parts.map(n => Number(n));
  const [hh, mm] = timeStr.split(":").map(n => Number(n));
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) return null;
  if (!Number.isFinite(hh) || !Number.isFinite(mm)) return null;
  // Africa/Johannesburg is UTC+2 year-round. Convert ZA local to UTC.
  const utcMs = Date.UTC(y, m - 1, d, hh - 2, mm, 0, 0);
  return new Date(utcMs).toISOString();
}

window.toIsoFromZA = toIsoFromZA;

function getImpersonationToken() {
  return sessionStorage.getItem("impersonation_token");
}

function getCookie(name) {
  const key = `${name}=`;
  const parts = document.cookie ? document.cookie.split(";") : [];
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed.startsWith(key)) {
      return decodeURIComponent(trimmed.slice(key.length));
    }
  }
  return null;
}

function getCsrfToken() {
  return getCookie("csrf_token");
}

window.getCsrfToken = getCsrfToken;

async function fetchJson(url, opts = {}) {
  const token = getImpersonationToken();
  const headers = Object.assign(
    { "Content-Type": "application/json" },
    opts.headers || {}
  );

  if (token) headers["Authorization"] = "Bearer " + token;
  const method = String(opts.method || "GET").toUpperCase();
  const isUnsafe = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
  if (isUnsafe && !headers["Authorization"]) {
    const csrfToken = getCsrfToken();
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }
  const fetchOpts = Object.assign({}, opts, { headers, credentials: "same-origin" });
  const res = await fetch(url, fetchOpts);

  let data = null;
  let text = "";
  try {
    data = await res.clone().json();
  } catch {
    text = await res.text().catch(() => "");
    if (text) {
      try { data = JSON.parse(text); } catch { data = text; }
    }
  }

  if (!res.ok) {
    // FastAPI style error
    let msg = "Request failed";
    if (data && typeof data === "object") {
      if (data.detail !== undefined) {
        if (Array.isArray(data.detail)) {
          msg = data.detail.map(d => {
            if (d && typeof d === "object") {
              if (d.msg && d.loc) return `${d.msg} (${d.loc.join(".")})`;
              if (d.msg) return d.msg;
              return JSON.stringify(d);
            }
            return String(d);
          }).join(", ");
        } else if (typeof data.detail === "string") {
          msg = data.detail;
        } else {
          msg = JSON.stringify(data.detail);
        }
      } else {
        msg = JSON.stringify(data);
      }
    } else if (data) {
      msg = String(data);
    }
    throw new Error(msg);
  }

  return data;
}

async function requireMe() {
  const me = await fetchJson("/auth/me").catch(() => null);
  if (!me) {
    location.href = "/static/login.html";
    throw new Error("Not logged in");
  }
  localStorage.setItem("is_admin", String(!!me.is_admin));
  return me;
}

function routeByRole(role) {
  if (role === "parent") window.location.href = "/static/parent_home.html";
  else if (role === "nanny") window.location.href = "/static/nanny_home.html?v=2";
  else window.location.href = "/static/login.html";
}

function logout() {
  clearToken();
  fetch("/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: Object.assign(
      { "Content-Type": "application/json" },
      getCsrfToken() ? { "X-CSRF-Token": getCsrfToken() } : {}
    )
  }).finally(() => {
    window.location.href = "/static/login.html";
  });
}

function renderTopbar(container, me, profileComplete) {
  if (!container) return;
  const firstName = (me?.name || me?.email || "").split(" ")[0];
  const showLogout = container?.dataset?.disableLogout !== "true";

  container.style.display = "flex";
  container.style.justifyContent = "space-between";
  container.style.alignItems = "center";
  container.style.gap = "12px";

  container.innerHTML = `
    <div class="brand">
      <img class="site-logo" src="/static/logo.jpg" alt="My Nanny logo" />
    </div>
    <div class="topbar-right">
      <div class="topbar-actions">
        <div style="color:#666;">
          Logged in as: ${firstName}
          ${profileComplete ? '<span class="check">✓</span>' : ''}
        </div>
        ${showLogout ? '<button class="btn secondary logout-btn" id="logoutBtn" style="width:auto;">Log out</button>' : ''}
      </div>
    </div>
  `;

  if (showLogout) {
    const btn = document.getElementById("logoutBtn");
    if (btn) btn.onclick = logout;
  }
}

function ensureSiteLogo() {
  if (document.querySelector(".site-logo")) return;
  const logoHtml = '<img class="site-logo" src="/static/logo.jpg" alt="My Nanny logo" />';
  const topbar = document.querySelector(".topbar");
  if (topbar) {
    const brand = document.createElement("div");
    brand.className = "brand";
    brand.innerHTML = logoHtml;
    const firstChild = topbar.firstElementChild;
    if (firstChild && firstChild.tagName === "DIV") {
      firstChild.prepend(brand);
    } else {
      topbar.prepend(brand);
    }
    return;
  }

  const bar = document.createElement("div");
  bar.className = "logo-bar";
  bar.innerHTML = logoHtml;
  if (document.body) {
    document.body.prepend(bar);
  }
}

async function loadParentContext() {
  let me = null;
  try {
    me = await fetchJson("/auth/me");
  } catch {
    return null;
  }

  if (!me || me.role !== "parent") {
    return { user: me, profileComplete: false };
  }

  let profileComplete = false;
  try {
    const status = await fetchJson("/parents/me/profile-status");
    profileComplete = !!status?.is_profile_complete;
  } catch {
    profileComplete = false;
  }

  return { user: me, profileComplete };
}

window.loadParentContext = loadParentContext;

(function ensureCheckStyle(){
  if (document.getElementById("checkStyle")) return;
  const style = document.createElement("style");
  style.id = "checkStyle";
  style.textContent = ".check{color:#22c55e;margin-left:6px;font-weight:700;}.location-actions{display:flex;gap:12px;}.btn-secondary{min-width:120px;height:44px;border-radius:10px;border:1px solid #ccc;background:#fff;cursor:pointer;}";
  document.head.appendChild(style);
})();

(async function setupLogout(){
  const topbar = document.getElementById("topbar");
  const path = window.location.pathname || "";

  if (!topbar) return;
  const disableLogout = topbar.dataset && topbar.dataset.disableLogout === "true";
  if (path.endsWith("/login.html") || path.endsWith("/signup.html")) return;

  let me = null;
  try {
    me = await fetchJson("/auth/me");
  } catch {
    return;
  }

  let profileComplete = false;
  if (me && me.role === "parent") {
    try {
      const status = await fetchJson("/parents/me/profile-status");
      profileComplete = !!status?.is_profile_complete;
    } catch {
      profileComplete = false;
    }
  }

  renderTopbar(topbar, me, profileComplete);
})();

function ensureImpersonationBanner() {
  const token = getImpersonationToken();
  if (!token) return;
  if (!document.body) {
    window.addEventListener("DOMContentLoaded", ensureImpersonationBanner, { once: true });
    return;
  }
  if (document.getElementById("impersonationBanner")) return;

  if (!document.getElementById("impersonationBannerStyle")) {
    const style = document.createElement("style");
    style.id = "impersonationBannerStyle";
    style.textContent = "html.has-impersonation-banner body{padding-top:52px;} .impersonation-banner{position:fixed;top:0;left:0;right:0;z-index:9999;background:#111827;color:#fff;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 16px;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,0.2);} .impersonation-banner button{background:#fff;color:#111827;border:1px solid #e5e7eb;border-radius:8px;padding:6px 10px;cursor:pointer;}";
    document.head.appendChild(style);
  }

  document.documentElement.classList.add("has-impersonation-banner");
  const banner = document.createElement("div");
  banner.id = "impersonationBanner";
  banner.className = "impersonation-banner";
  banner.innerHTML = "<div>Admin editing as <span id=\"impersonationEmail\">user</span></div><button id=\"exitImpersonationBtn\" type=\"button\">Exit admin mode</button>";
  document.body.appendChild(banner);

  const exitBtn = document.getElementById("exitImpersonationBtn");
  if (exitBtn) {
    exitBtn.addEventListener("click", () => {
      sessionStorage.removeItem("impersonation_token");
      window.location.href = "/static/admin_dashboard.html";
    });
  }

  fetchJson("/auth/me")
    .then((me) => {
      const emailEl = document.getElementById("impersonationEmail");
      if (emailEl && me?.email) emailEl.textContent = me.email;
    })
    .catch(() => {
      const emailEl = document.getElementById("impersonationEmail");
      if (emailEl) emailEl.textContent = "user";
    });
}

ensureImpersonationBanner();

function moveBackButtons() {
  const backButtons = Array.from(document.querySelectorAll(".back-btn"));
  if (!backButtons.length) return;
  const topbar = document.querySelector(".topbar");
  if (!topbar) return;

  let topbarRight = topbar.querySelector(".topbar-right");
  if (!topbarRight) {
    topbarRight = document.createElement("div");
    topbarRight.className = "topbar-right";
    const logoutBtn = topbar.querySelector("#logoutBtn");
    if (logoutBtn) {
      const actions = document.createElement("div");
      actions.className = "topbar-actions";
      actions.appendChild(logoutBtn);
      topbarRight.appendChild(actions);
    }
    topbar.appendChild(topbarRight);
  }

  backButtons.forEach((btn) => {
    if (btn.parentElement !== topbarRight) {
      topbarRight.appendChild(btn);
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    ensureSiteLogo();
    moveBackButtons();
  });
} else {
  ensureSiteLogo();
  moveBackButtons();
}
