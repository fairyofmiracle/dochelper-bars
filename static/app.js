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

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "admin") loadDocs();
    if (btn.dataset.tab === "stats") loadStats();
    if (btn.dataset.tab === "chat") chatInput.focus();
  });
});

function setChatBusy(busy) {
  chatInput.disabled = busy;
  sendBtn.disabled = busy;
  document.getElementById("escalate-btn").disabled = busy;
}

function addMsg(text, role, meta = "", needsOperator = false, isLoading = false) {
  const row = document.createElement("div");
  row.className = "msg-row " + role + (isLoading ? " loading" : "");
  if (isLoading) row.dataset.loading = "1";

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "user" ? "Вы" : "AI";

  const body = document.createElement("div");
  body.className = "msg-body";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble msg " + role;
  bubble.textContent = text;
  body.appendChild(bubble);

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
    removeLoadingEl(loadingEl);

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(errText || `HTTP ${res.status}`);
    }

    const data = await res.json();
    const meta =
      `confidence: ${(data.confidence * 100).toFixed(0)}%` +
      (data.sources?.length ? ` · ${data.sources.join(", ")}` : "");
    addMsg(data.answer, "bot", meta, data.needs_operator && !data.escalated);
  } catch (err) {
    removeLoadingEl(loadingEl);
    addMsg(
      "Не удалось получить ответ — проверьте, что сервер запущен (порт 8026), или нажмите «Оператор».",
      "bot",
      String(err.message || err),
      true
    );
  } finally {
    setChatBusy(false);
    chatInput.focus();
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
  b.onclick = () => sendChat(q);
  chips.appendChild(b);
});

async function loadDocs() {
  try {
    const res = await fetch("/api/admin/documents");
    const data = await res.json();
    const ul = document.getElementById("doc-list");
    ul.innerHTML = "";
    (data.documents || []).forEach((d) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${d.name} <small>(${d.folder}, ${Math.round(d.size_bytes / 1024)} KB)</small></span>`;
      const del = document.createElement("button");
      del.textContent = "Удалить";
      del.onclick = async () => {
        await fetch(`/api/admin/documents/${encodeURIComponent(d.name)}`, { method: "DELETE" });
        loadDocs();
      };
      li.appendChild(del);
      ul.appendChild(li);
    });
  } catch {
    document.getElementById("doc-list").innerHTML = "<li>Не удалось загрузить список документов</li>";
  }
}

document.getElementById("file-input").addEventListener("change", (e) => {
  const nameEl = document.getElementById("file-name");
  const file = e.target.files?.[0];
  if (nameEl) nameEl.textContent = file ? file.name : "Файл не выбран";
});

document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = document.getElementById("file-input").files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  await fetch("/api/admin/upload", { method: "POST", body: fd });
  document.getElementById("file-input").value = "";
  document.getElementById("file-name").textContent = "Файл не выбран";
  loadDocs();
  alert("Файл загружен и проиндексирован");
});

document.getElementById("reindex-btn").addEventListener("click", async () => {
  const res = await fetch("/api/admin/reindex?clear=true", { method: "POST" });
  const data = await res.json();
  alert("Готово: " + JSON.stringify(data.stats));
  loadDocs();
});

async function loadStats() {
  try {
    const res = await fetch("/api/analytics");
    const s = await res.json();
    const recentRows = (s.recent || [])
      .slice(0, 15)
      .map(
        (r) => `<tr>
        <td>${new Date(r.ts).toLocaleString("ru-RU")}</td>
        <td>${escapeHtml(r.question)}</td>
        <td>${(r.confidence * 100).toFixed(0)}%</td>
        <td>${r.auto ? "✅ авто" : "🆘 эскалация"}</td>
        <td>${escapeHtml(r.source || "—")}</td>
      </tr>`
      )
      .join("");

    const autoPct = s.total_queries ? (s.auto_answered / s.total_queries) * 100 : 0;
    const escPct = 100 - autoPct;
    const donutStyle = `background: conic-gradient(#10b981 0 ${autoPct}%, #ef4444 ${autoPct}% 100%)`;

    document.getElementById("stats-box").innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><span class="stat-num">${s.total_queries}</span><span class="stat-label">Всего запросов</span></div>
      <div class="stat-card"><span class="stat-num">${s.auto_answered}</span><span class="stat-label">Автоответов</span></div>
      <div class="stat-card"><span class="stat-num">${s.escalated}</span><span class="stat-label">Эскалаций</span></div>
      <div class="stat-card"><span class="stat-num">${s.auto_rate_percent}%</span><span class="stat-label">Доля авто · цель 40%</span></div>
    </div>
    <div class="progress-wrap">
      <div class="progress-bar" style="width:${Math.min(s.auto_rate_percent, 100)}%"></div>
    </div>

    <div class="charts-row">
      <div class="chart-card">
        <h3>Авто vs эскалация</h3>
        <div class="donut-wrap">
          <div class="donut" style="${donutStyle}" data-label="${s.auto_rate_percent}%"></div>
          <ul class="legend">
            <li><span class="legend-dot" style="background:#10b981"></span>Авто: ${s.auto_answered} (${autoPct.toFixed(0)}%)</li>
            <li><span class="legend-dot" style="background:#ef4444"></span>Эскалация: ${s.escalated} (${escPct.toFixed(0)}%)</li>
          </ul>
        </div>
      </div>
      <div class="chart-card">
        <h3>Уверенность ответов</h3>
        ${renderConfBars(s.confidence_buckets || {})}
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-card">
        <h3>Топ частых вопросов</h3>
        ${renderBars(s.top_questions || [], "question", "count")}
      </div>
      <div class="chart-card">
        <h3>Источники в документации</h3>
        ${renderBars(s.top_sources || [], "source", "count", "src")}
      </div>
    </div>

    <h3 class="stats-section-title">Последние запросы</h3>
    <table class="recent-table">
      <thead><tr><th>Время</th><th>Вопрос</th><th>Conf.</th><th>Итог</th><th>Источник</th></tr></thead>
      <tbody>${recentRows || "<tr><td colspan='5'>Пока нет данных — задайте вопросы в чате</td></tr>"}</tbody>
    </table>
    <p class="hint" style="margin-top:0.75rem">Хранилище: ${s.storage || "—"} · обновляется после каждого запроса</p>
  `;
  } catch {
    document.getElementById("stats-box").innerHTML = "<p>Не удалось загрузить аналитику. Проверьте, что сервер запущен.</p>";
  }
}

function renderBars(items, labelKey, valueKey, fillClass = "") {
  if (!items.length) return '<p class="hint">Нет данных — задайте несколько вопросов в чате</p>';
  const max = Math.max(...items.map((i) => i[valueKey]), 1);
  return items
    .map((item) => {
      const pct = (item[valueKey] / max) * 100;
      const label = escapeHtml(String(item[labelKey]));
      return `<div class="bar-row" title="${label}">
        <span class="bar-label">${label}</span>
        <div class="bar-track"><div class="bar-fill ${fillClass}" style="width:${pct}%"></div></div>
        <span class="bar-val">${item[valueKey]}</span>
      </div>`;
    })
    .join("");
}

function renderConfBars(buckets) {
  const items = [
    { label: "Высокая ≥70%", key: "high", cls: "conf-high" },
    { label: "Средняя 45–70%", key: "medium", cls: "conf-med" },
    { label: "Низкая <45%", key: "low", cls: "conf-low" },
  ];
  const max = Math.max(...items.map((i) => buckets[i.key] || 0), 1);
  return items
    .map((i) => {
      const val = buckets[i.key] || 0;
      const pct = (val / max) * 100;
      return `<div class="bar-row">
        <span class="bar-label">${i.label}</span>
        <div class="bar-track"><div class="bar-fill ${i.cls}" style="width:${pct}%"></div></div>
        <span class="bar-val">${val}</span>
      </div>`;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

addMsg(
  "Здравствуйте! Я DocHelper — виртуальный помощник по документации АО «БАРС Груп».\n\n" +
    "Задайте вопрос или выберите тему ниже. Ответ придёт с указанием источника. Если информации нет — нажмите «Оператор».",
  "bot"
);

chatInput.focus();
