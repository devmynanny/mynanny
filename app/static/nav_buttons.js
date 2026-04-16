(() => {
  const path = window.location.pathname || "";

  function getDashboardHref() {
    if (path.includes("/static/admin")) return "/static/admin_dashboard.html";
    if (path.includes("/static/nanny")) return "/static/nanny_home.html";
    if (path.includes("/static/parent")) return "/static/parent_home.html";
    return null;
  }

  const dashboardHref = getDashboardHref();
  if (!dashboardHref) return;

  const style = document.createElement("style");
  style.textContent = `
    .global-nav-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin: 16px auto 12px;
      width: min(1100px, calc(100% - 32px));
      position: sticky;
      top: 12px;
      z-index: 1000;
    }
    .global-nav-actions .global-nav-btn {
      padding: 10px 14px;
      border-radius: 10px;
      border: 1px solid #d1d5db;
      background: rgba(255, 255, 255, 0.96);
      color: #111827;
      cursor: pointer;
      font: inherit;
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
      backdrop-filter: blur(6px);
    }
    .global-nav-actions .global-nav-btn:hover {
      background: #ffffff;
    }
    @media (max-width: 640px) {
      .global-nav-actions {
        width: calc(100% - 24px);
        margin: 12px auto 10px;
      }
      .global-nav-actions .global-nav-btn {
        flex: 1 1 0;
      }
    }
  `;
  document.head.appendChild(style);

  const wrapper = document.createElement("div");
  wrapper.className = "global-nav-actions";

  const backBtn = document.createElement("button");
  backBtn.type = "button";
  backBtn.className = "global-nav-btn";
  backBtn.textContent = "Back";
  backBtn.addEventListener("click", () => {
    if (window.history.length > 1) {
      window.history.back();
      return;
    }
    window.location.href = dashboardHref;
  });

  const dashboardBtn = document.createElement("button");
  dashboardBtn.type = "button";
  dashboardBtn.className = "global-nav-btn";
  dashboardBtn.textContent = "My dashboard";
  dashboardBtn.addEventListener("click", () => {
    window.location.href = dashboardHref;
  });

  wrapper.append(backBtn, dashboardBtn);
  document.body.prepend(wrapper);

  const duplicateSelectors = [
    "#backBtn",
    "#backBottomBtn",
    "#backToOpsBtn",
    ".back-btn",
  ];

  const duplicateLabels = new Set([
    "back to dashboard",
    "back to home",
    "back to operations",
    "back",
  ]);

  const seen = new Set();
  duplicateSelectors.forEach((selector) => {
    document.querySelectorAll(selector).forEach((el) => {
      if (!el || el.closest(".global-nav-actions")) return;
      seen.add(el);
    });
  });

  document.querySelectorAll("button").forEach((btn) => {
    if (!btn || btn.closest(".global-nav-actions")) return;
    const label = (btn.textContent || "").trim().toLowerCase();
    if (duplicateLabels.has(label)) {
      seen.add(btn);
    }
  });

  seen.forEach((el) => {
    el.remove();
  });
})();
