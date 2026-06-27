const sessionId = "web-" + Math.random().toString(36).slice(2);
const messages = document.getElementById("messages");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.querySelector("#chat-form button[type=submit]");

const FAQ_CHIPS = [
  "Как работает фильтр документа?",
  "Кто согласовывает БП Командировка?",
  "Что делать в первый рабочий день?",
  "Какие ценности у компании Барс Груп?",
];

let escalated = false;
let pollTimer = null;
let lastOperatorCount = 0;

function setChatBusy(busy) {
  chatInput.disabled = busy;
  sendBtn.disabled = busy;
  document.getElementById("escalate-btn").disabled = busy;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderSourceBlock(snippets) {
  if (!snippets?.length) return null;
  const unique = [];
  const seen = new Set();
  snippets.forEach((s) => {
    if (!seen.has(s.source)) {
      seen.add(s.source);
      unique.push(s);
    }
  });
  const block = document.createElement("div");
  block.className = "source-block source-block--compact";
  block.innerHTML = `<p class="source-title">Источник</p><div class="source-links">${unique
    .map(
      (s) =>
        `<a href="${escapeHtml(s.download_url)}" download class="source-pill" title="Скачать ${escapeHtml(s.source)}">${escapeHtml(s.source)}</a>`
    )
    .join("")}</div>`;
  return block;
}

function addMsg(text, role, meta = "", needsOperator = false, isLoading = false, imageUrls = [], snippets = [], userQuestion = "") {
  const row = document.createElement("div");
  row.className = "msg-row " + role + (isLoading ? " loading" : "");
  if (isLoading) row.dataset.loading = "1";

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  if (role === "user") {
    avatar.textContent = "Вы";
  } else if (role === "operator") {
    avatar.textContent = "Оп";
    row.classList.add("operator");
  } else {
    avatar.textContent = "AI";
  }

  const body = document.createElement("div");
  body.className = "msg-body";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble msg " + role;
  bubble.textContent = text;
  body.appendChild(bubble);

  if (imageUrls?.length) {
    const gallery = document.createElement("div");
    gallery.className = "msg-images";
    imageUrls.forEach((url) => {
      const img = document.createElement("img");
      img.src = url;
      img.alt = "Иллюстрация из документации";
      img.loading = "lazy";
      gallery.appendChild(img);
    });
    body.appendChild(gallery);
  }

  const sourceEl = renderSourceBlock(snippets);
  if (sourceEl) body.appendChild(sourceEl);

  if (meta) {
    const m = document.createElement("div");
    m.className = "msg-meta";
    m.textContent = meta;
    body.appendChild(m);
  }

  row.appendChild(avatar);
  row.appendChild(body);
  messages.appendChild(row);

  if (needsOperator) {
    const actions = document.createElement("div");
    actions.className = "msg-actions";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn inline-escalate";
    btn.textContent = "Переключить на оператора";
    btn.onclick = () => sendChat("оператор", true);
    actions.appendChild(btn);
    messages.appendChild(actions);
  }
  messages.scrollTop = messages.scrollHeight;
  return row;
}

function removeLoadingEl(el) {
  if (el && el.parentNode) el.parentNode.removeChild(el);
}

function applyChatResponse(data, loadingEl, userText) {
  removeLoadingEl(loadingEl);
  const meta = data.sources?.length ? data.sources.join(" · ") : "";
  addMsg(
    data.answer,
    "bot",
    meta,
    data.needs_operator && !data.escalated,
    false,
    data.images || [],
    data.source_snippets || [],
    data.user_question || userText
  );
  if (data.escalated) startOperatorPoll();
}

async function sendChat(text, escalate = false) {
  addMsg(text, "user");
  setChatBusy(true);
  const loadingEl = addMsg("Формирую ответ…", "bot", "", false, true);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
        user_label: "Web UI",
        escalate,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(errText || `HTTP ${res.status}`);
    }

    applyChatResponse(await res.json(), loadingEl, text);
  } catch (err) {
    removeLoadingEl(loadingEl);
    addMsg(
      "Не удалось получить ответ — проверьте, что сервер запущен, или нажмите «Оператор».",
      "bot",
      String(err.message || err),
      true
    );
  } finally {
    setChatBusy(false);
    chatInput.focus();
  }
}

function startOperatorPoll() {
  escalated = true;
  if (pollTimer) return;
  pollTimer = setInterval(pollOperatorMessages, 4000);
}

async function pollOperatorMessages() {
  if (!escalated) return;
  try {
    const res = await fetch(`/api/chat/messages/${encodeURIComponent(sessionId)}`);
    const data = await res.json();
    const ops = (data.messages || []).filter((m) => m.role === "operator");
    if (ops.length <= lastOperatorCount) return;
    for (let i = lastOperatorCount; i < ops.length; i++) {
      addMsg(ops[i].content, "operator", "");
    }
    lastOperatorCount = ops.length;
  } catch {
    /* ignore */
  }
}

document.getElementById("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = chatInput.value.trim();
  if (!v) return;
  chatInput.value = "";
  sendChat(v);
});

document.getElementById("escalate-btn").addEventListener("click", () => sendChat("оператор", true));

const chips = document.getElementById("faq-chips");
FAQ_CHIPS.forEach((q) => {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "chip";
  b.textContent = q;
  b.disabled = true;
  b.onclick = () => sendChat(q);
  chips.appendChild(b);
});

function setChatEnabled(enabled) {
  chatInput.disabled = !enabled;
  sendBtn.disabled = !enabled;
  document.getElementById("escalate-btn").disabled = !enabled;
  chips.querySelectorAll(".chip").forEach((chip) => {
    chip.disabled = !enabled;
  });
}

function showWelcomeMessage(text) {
  addMsg(text || chatWelcomeText, "bot");
  chatInput.focus();
}

let chatWelcomeText =
  "Привет! Я DocHelper Барс.\n\n" +
  "Я изучил документацию БАРС-Офис и готов ответить на ваши вопросы.\n\n" +
  "Чем могу помочь?";

function renderWelcomeIntro(intro, telegramUrl, telegramLabel) {
  const tag = document.getElementById("welcome-tag");
  const title = document.getElementById("welcome-title");
  const lead = document.getElementById("welcome-lead");
  const features = document.getElementById("welcome-features");
  const hint = document.getElementById("welcome-hint");
  const startBtn = document.getElementById("welcome-start");

  if (tag) tag.textContent = intro.tag || "";
  if (title) {
    title.innerHTML =
      escapeHtml(intro.title || "") +
      ' <span class="hero-accent">' +
      escapeHtml(intro.title_accent || "") +
      "</span>";
  }
  if (lead) lead.textContent = intro.lead || "";
  if (hint) hint.textContent = intro.hint || "";
  if (startBtn) startBtn.textContent = intro.button || "Начать диалог";
  if (intro.chat_welcome) chatWelcomeText = intro.chat_welcome;

  if (features) {
    features.innerHTML = "";
    (intro.features || []).forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line;
      features.appendChild(li);
    });
    if (intro.telegram_prefix) {
      const li = document.createElement("li");
      li.appendChild(document.createTextNode(intro.telegram_prefix + " "));
      const a = document.createElement("a");
      a.id = "welcome-telegram";
      a.href = telegramUrl || "https://t.me/SUP_BARS_BOT";
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = telegramLabel || "Telegram";
      li.appendChild(a);
      features.appendChild(li);
    }
  }
}

function closeWelcome() {
  const overlay = document.getElementById("welcome-overlay");
  const page = document.getElementById("page-content");
  if (!overlay) return;

  overlay.classList.add("is-closing");
  document.body.classList.remove("welcome-open");
  page?.removeAttribute("aria-hidden");

  overlay.addEventListener(
    "animationend",
    () => {
      overlay.hidden = true;
    },
    { once: true }
  );

  setChatEnabled(true);
  if (!messages.children.length) showWelcomeMessage();
  else chatInput.focus();
}

setChatEnabled(false);

document.getElementById("welcome-start")?.addEventListener("click", closeWelcome);

(async function initPage() {
  let intro = {};
  let links = {};
  try {
    [intro, links] = await Promise.all([
      fetch("/api/web-welcome").then((r) => r.json()),
      fetch("/api/demo-links").then((r) => r.json()),
    ]);
  } catch {
    intro = {
      tag: "Королева Кода · АО «Барс Груп»",
      title: "DocHelper",
      title_accent: "Барс",
      lead: "AI-агент первой линии поддержки — отвечает по корпоративной документации и показывает источник ответа.",
      features: [
        "Поиск по базе знаний БАРС-Офис и внутренним регламентам",
        "Структурированный ответ со ссылкой на документ-источник",
        "Если нужен человек — переключение на оператора в один клик",
      ],
      telegram_prefix: "Тот же помощник доступен в",
      hint: "Задайте вопрос текстом или выберите тему из подсказок — попробуйте прямо сейчас.",
      button: "Начать диалог",
    };
  }

  const telegramUrl = links.telegram || "https://t.me/SUP_BARS_BOT";
  const telegramUser = telegramUrl.replace(/^https:\/\/t\.me\//, "@");

  renderWelcomeIntro(intro, telegramUrl, telegramUser || "Telegram");

  const footerLink = document.getElementById("link-telegram");
  if (footerLink && links.telegram) {
    footerLink.href = links.telegram;
    footerLink.textContent = "Telegram " + telegramUser;
  }
})();
