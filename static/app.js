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

function renderSourceBlock(snippets, userQuestion) {
  if (!snippets?.length) return null;
  const block = document.createElement("div");
  block.className = "source-block";
  const q = userQuestion ? `<p class="source-question"><span>Ваш вопрос:</span> ${escapeHtml(userQuestion)}</p>` : "";
  const cards = snippets
    .map((s) => {
      const page = s.chunk_index >= 0 ? ` · фрагмент ${s.chunk_index + 1}` : "";
      return `<article class="source-card">
        <header>
          <strong>${escapeHtml(s.source)}</strong>${page}
          <a href="${escapeHtml(s.download_url)}" download class="source-dl">Скачать документ</a>
        </header>
        <p class="source-excerpt">${escapeHtml(s.excerpt)}</p>
      </article>`;
    })
    .join("");
  block.innerHTML = `${q}<p class="source-title">Фрагмент из документации</p>${cards}`;
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

  const sourceEl = renderSourceBlock(snippets, userQuestion);
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
  const meta =
    `уверенность: ${(data.confidence * 100).toFixed(0)}%` +
    (data.sources?.length ? ` · ${data.sources.join(", ")}` : "");
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

async function sendChatImage(file, caption = "") {
  addMsg(caption || "[скриншот]", "user");
  setChatBusy(true);
  const loadingEl = addMsg("Анализирую изображение…", "bot", "", false, true);

  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("message", caption || "Что на скриншоте? Подскажите по документации.");
    fd.append("session_id", sessionId);
    fd.append("user_label", "Web UI");

    const res = await fetch("/api/chat/image", { method: "POST", body: fd });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(errText || `HTTP ${res.status}`);
    }
    applyChatResponse(await res.json(), loadingEl, caption);
  } catch (err) {
    removeLoadingEl(loadingEl);
    addMsg("Не удалось обработать изображение.", "bot", String(err.message || err), true);
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
      addMsg(ops[i].content, "operator", "Ответ оператора");
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

document.getElementById("chat-image").addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  e.target.value = "";
  if (!file) return;
  const caption = chatInput.value.trim();
  chatInput.value = "";
  sendChatImage(file, caption);
});

const chips = document.getElementById("faq-chips");
FAQ_CHIPS.forEach((q) => {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "chip";
  b.textContent = q;
  b.onclick = () => sendChat(q);
  chips.appendChild(b);
});

addMsg(
  "Привет! Я DocHelper Барс.\n\n" +
    "Я изучил документацию БАРС-Офис и корпоративных сервисов и готов ответить на ваши вопросы.\n\n" +
    "Выберите тему ниже или напишите свой вопрос. Если понадобится живой человек — нажмите «Оператор».\n\n" +
    "Чем могу помочь?",
  "bot"
);

chatInput.focus();
