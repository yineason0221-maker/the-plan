const QUESTION_ID = "agree-me";
const API_BASE_URL = "https://the-plan.onrender.com"; // 
let VOTE_KEY = `agree_game_vote_${QUESTION_ID}_v1`;

const form = document.getElementById("vote-form");
const statusEl = document.getElementById("status");
const buttons = Array.from(document.querySelectorAll("[data-choice]"));

function setStatus(message, kind = "neutral") {
  if (!statusEl) {
    return;
  }

  statusEl.textContent = message;
  statusEl.dataset.kind = kind;
}

async function requestJson(url, options = {}) {
  const fullUrl = url.startsWith("http") ? url : `${API_BASE_URL}${url}`;
  const response = await fetch(fullUrl, {
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

function setVoteKey(version) {
  const safeVersion = Number.isFinite(version) && version > 0 ? Math.floor(version) : 1;
  VOTE_KEY = `agree_game_vote_${QUESTION_ID}_v${safeVersion}`;
}

function disableButtons(disabled) {
  buttons.forEach((button) => {
    button.disabled = disabled;
  });
}

function applyStoredVote() {
  const storedVote = localStorage.getItem(VOTE_KEY);
  if (!storedVote) {
    setStatus("選一個答案，結果會直接送到後台。");
    return;
  }

  disableButtons(true);
  setStatus(`你這台裝置已經選過：${storedVote}`, "success");
}

async function submitVote(choiceValue, choiceLabel, button) {
  disableButtons(true);
  button.classList.add("is-selected");
  setStatus("正在記錄你的選擇...", "working");

  try {
    const result = await requestJson("/api/vote", {
      method: "POST",
      body: JSON.stringify({
        question_id: QUESTION_ID,
        choice: choiceValue,
      }),
    });

    localStorage.setItem(VOTE_KEY, choiceLabel);
    button.classList.add("is-confirmed");
    setStatus(result.message, "success");
  } catch (error) {
    disableButtons(false);
    button.classList.remove("is-selected");
    setStatus(error.message || "送出失敗。", "error");
  }
}

async function bootstrap() {
  if (!form || !statusEl || buttons.length === 0) {
    return;
  }

  try {
    const data = await requestJson("/api/current-question", { method: "GET" });
    setVoteKey(Number(data.vote_version || 1));
  } catch {
    setVoteKey(1);
  }

  applyStoredVote();

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) {
        return;
      }

      submitVote(button.dataset.choice, button.textContent.trim(), button);
    });
  });
}

document.addEventListener("DOMContentLoaded", bootstrap);
