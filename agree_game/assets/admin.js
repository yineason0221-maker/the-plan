const elements = {
  flashList: document.getElementById("flash-list"),
  loginPanel: document.getElementById("login-panel"),
  dashboard: document.getElementById("dashboard"),
  summaryGrid: document.getElementById("summary-grid"),
  questionGrid: document.getElementById("question-grid"),
  recentWrap: document.getElementById("recent-wrap"),
  loginForm: document.getElementById("login-form"),
  password: document.getElementById("password"),
  passwordForm: document.getElementById("password-form"),
  currentPassword: document.getElementById("current-password"),
  newPassword: document.getElementById("new-password"),
  confirmPassword: document.getElementById("confirm-password"),
  clearRecordsButton: document.getElementById("clear-records-button"),
  logoutButton: document.getElementById("logout-button"),
  status: document.getElementById("status"),
};

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setStatus(message, kind = "neutral") {
  elements.status.textContent = message;
  elements.status.dataset.kind = kind;
}

function showFlash(message, kind = "success") {
  elements.flashList.innerHTML = `
    <div class="flash flash--${kind}">${escapeHTML(message)}</div>
  `;
}

function clearFlash() {
  elements.flashList.innerHTML = "";
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    const error = new Error(data.error || "發生錯誤。");
    error.status = response.status;
    throw error;
  }

  return data;
}

function renderSummary(data) {
  const cards = [
    ["總票數", data.total_votes],
    ["題目數", data.question_count],
    ["啟用題目", data.active_count],
    ["最近回應", data.recent_votes.length],
  ];

  elements.summaryGrid.innerHTML = cards.map(([label, value]) => `
    <section class="panel stat">
      <div class="panel__muted">${escapeHTML(label)}</div>
      <div class="stat__value">${escapeHTML(value)}</div>
    </section>
  `).join("");
}

function renderQuestions(data) {
  elements.questionGrid.innerHTML = data.questions.length
    ? data.questions.map((question) => `
        <article class="panel">
          <div class="admin-top">
            <div>
              <h3>${escapeHTML(question.prompt)}</h3>
              ${question.description ? `<p class="panel__muted">${escapeHTML(question.description)}</p>` : ""}
            </div>
            <span class="badge ${question.active ? "badge--active" : "badge--inactive"}">
              ${question.active ? "active" : "inactive"}
            </span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:.75rem;margin-bottom:1rem;color:var(--muted);">
            <span class="pill">題目 ID：${escapeHTML(question.id)}</span>
            <span class="pill">總票數：${escapeHTML(question.total)}</span>
          </div>
          <ul class="choice-list">
            ${question.choices.map((choice) => `
              <li class="choice-row">
                <span>${escapeHTML(choice.label)}</span>
                <strong>${escapeHTML(choice.count)}</strong>
              </li>
            `).join("")}
          </ul>
        </article>
      `).join("")
    : `<p class="empty-state">目前沒有題目資料，請先確認 <code>data/questions.json</code>。</p>`;
}

function renderRecentVotes(data) {
  if (!data.recent_votes.length) {
    elements.recentWrap.innerHTML = '<p class="empty-state">目前還沒有任何回應。</p>';
    return;
  }

  elements.recentWrap.innerHTML = `
    <table class="table">
      <thead>
        <tr>
          <th>時間</th>
          <th>題目</th>
          <th>選擇</th>
          <th>值</th>
        </tr>
      </thead>
      <tbody>
        ${data.recent_votes.map((vote) => `
          <tr>
            <td>${escapeHTML(vote.created_at)}</td>
            <td>${escapeHTML(vote.question_prompt)}</td>
            <td>${escapeHTML(vote.choice_label)}</td>
            <td>${escapeHTML(vote.choice_value)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderDashboard(data) {
  renderSummary(data);
  renderQuestions(data);
  renderRecentVotes(data);
}

function showDashboard() {
  elements.loginPanel.hidden = true;
  elements.dashboard.hidden = false;
  elements.logoutButton.hidden = false;
  setStatus("", "neutral");
}

function showLogin() {
  elements.loginPanel.hidden = false;
  elements.dashboard.hidden = true;
  elements.logoutButton.hidden = true;
  setStatus("", "neutral");
}

async function refreshDashboard() {
  try {
    const data = await requestJson("/api/admin/stats", { method: "GET" });
    clearFlash();
    showDashboard();
    renderDashboard(data);
  } catch (error) {
    if (error.status === 401) {
      showLogin();
      clearFlash();
      return;
    }

    showLogin();
    showFlash(error.message || "讀取失敗。", "error");
    setStatus(error.message || "讀取失敗。", "error");
  }
}

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await requestJson("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({
        password: elements.password.value,
      }),
    });
    elements.password.value = "";
    clearFlash();
    showDashboard();
    renderDashboard(data);
  } catch (error) {
    showFlash(error.message || "登入失敗。", "error");
    setStatus("", "neutral");
  }
});

elements.passwordForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const currentPassword = elements.currentPassword.value;
  const newPassword = elements.newPassword.value;
  const confirmPassword = elements.confirmPassword.value;

  if (newPassword !== confirmPassword) {
    showFlash("兩次新密碼不一致。", "error");
    return;
  }

  try {
    const data = await requestJson("/api/admin/password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    });

    elements.currentPassword.value = "";
    elements.newPassword.value = "";
    elements.confirmPassword.value = "";
    showFlash(data.message || "密碼已更新。", "success");
  } catch (error) {
    showFlash(error.message || "密碼更新失敗。", "error");
  }
});

elements.clearRecordsButton.addEventListener("click", async () => {
  const confirmed = window.confirm("確定要清空所有投票紀錄嗎？這個動作無法復原。");
  if (!confirmed) {
    return;
  }

  try {
    const data = await requestJson("/api/admin/clear-records", { method: "POST" });
    renderDashboard(data);
    showFlash(data.message || "已清空紀錄。", "success");
  } catch (error) {
    showFlash(error.message || "清空失敗。", "error");
  }
});

elements.logoutButton.addEventListener("click", async () => {
  try {
    await requestJson("/api/admin/logout", { method: "POST" });
    clearFlash();
    showLogin();
  } catch (error) {
    showFlash(error.message || "登出失敗。", "error");
    setStatus("", "neutral");
  }
});

document.addEventListener("DOMContentLoaded", refreshDashboard);
