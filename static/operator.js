const sessionId = "op-" + Math.random().toString(36).slice(2);
const operatorPin = localStorage.getItem("operator_pin") || "";

const FAQ_CHIPS = [
  "Как работает фильтр документа?",
  "Кто согласовывает БП Командировка?",
  "Что делать в первый рабочий день?",
  "Какие ценности у компании Барс Груп?",
];

function pinHeaders() {
  const h = {};
  if (operatorPin) h["X-Operator-Pin"] = operatorPin;
  return h;
}

function ensurePin() {
  if (operatorPin) return operatorPin;
  const pin = prompt("PIN оператора (если задан в .env):", "");
  if (pin) localStorage.setItem("operator_pin", pin);
  return pin || "";
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "admin") loadDocs();
    if (btn.dataset.tab === "stats") loadStats();
    if (btn.dataset.tab === "queue") loadQueue();
  });
});

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function loadQueue() {
  ensurePin();
  const box = document.getElementById("queue-box");
  try {
    const res = await fetch("/api/operator/queue", { headers: pinHeaders() });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const items = data.queue || [];
    if (!items.length) {
      box.innerHTML = "<p class='hint'>Очередь пуста — все пользователи получили ответ.</p>";
      return;
    }
    box.innerHTML = items
      .map((item) => {
        const hist = (item.history || [])
          .slice(-6)
          .map((m) => {
            const who = m.role === "user" ? "Пользователь" : m.role === "operator" ? "Оператор" : "Бот";
            return `<li><strong>${who}:</strong> ${escapeHtml(m.content.slice(0, 200))}</li>`;
          })
          .join("");
        return `<article class="queue-card" data-session="${escapeHtml(item.session_id)}">
          <header>
            <strong>${escapeHtml(item.user_label || "Пользователь")}</strong>
            <span class="hint">${new Date(item.ts * 1000).toLocaleString("ru-RU")}</span>
          </header>
          <p class="queue-question">${escapeHtml(item.question || "—")}</p>
          <ul class="queue-history">${hist}</ul>
          <form class="reply-form">
            <input type="text" placeholder="Ответ пользователю…" required />
            <button type="submit" class="btn btn-primary">Отправить</button>
            <label class="resolve-check"><input type="checkbox" /> Закрыть обращение</label>
          </form>
        </article>`;
      })
      .join("");

    box.querySelectorAll(".reply-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const card = form.closest(".queue-card");
        const sid = card.dataset.session;
        const input = form.querySelector("input[type=text]");
        const resolve = form.querySelector("input[type=checkbox]").checked;
        const res = await fetch("/api/operator/reply", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...pinHeaders() },
          body: JSON.stringify({ session_id: sid, message: input.value.trim(), resolve }),
        });
        if (res.ok) {
          input.value = "";
          loadQueue();
        } else {
          alert("Ошибка: " + (await res.text()));
        }
      });
    });
  } catch (err) {
    box.innerHTML = `<p>Не удалось загрузить очередь: ${escapeHtml(String(err.message || err))}</p>`;
  }
}

const messages = document.getElementById("messages");
const chatInput = document.getElementById("chat-input");

function addMsg(text, role) {
  const row = document.createElement("div");
  row.className = "msg-row " + role;
  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "user" ? "Вы" : "AI";
  const body = document.createElement("div");
  body.className = "msg-body";
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble msg " + role;
  bubble.textContent = text;
  body.appendChild(bubble);
  row.appendChild(avatar);
  row.appendChild(body);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;
}

async function sendChat(text) {
  addMsg(text, "user");
  const loading = addMsg("Формирую ответ…", "bot");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId, user_label: "Operator test" }),
    });
    const data = await res.json();
    loading.remove();
    addMsg(data.answer, "bot");
  } catch {
    loading.remove();
    addMsg("Ошибка запроса", "bot");
  }
}

document.getElementById("chat-form")?.addEventListener("submit", (e) => {
  e.preventDefault();
  const v = chatInput.value.trim();
  if (!v) return;
  chatInput.value = "";
  sendChat(v);
});

const chips = document.getElementById("faq-chips");
FAQ_CHIPS.forEach((q) => {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "chip";
  b.textContent = q;
  b.onclick = () => sendChat(q);
  chips?.appendChild(b);
});

async function loadDocs() {
  try {
    const res = await fetch("/api/admin/documents");
    const data = await res.json();
    const ul = document.getElementById("doc-list");
    ul.innerHTML = "";
    (data.documents || []).forEach((d) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${escapeHtml(d.name)} <small>(${escapeHtml(d.folder)}, ${Math.round(d.size_bytes / 1024)} KB)</small></span>`;
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
    document.getElementById("doc-list").innerHTML = "<li>Не удалось загрузить список</li>";
  }
}

document.getElementById("file-input")?.addEventListener("change", (e) => {
  const nameEl = document.getElementById("file-name");
  const file = e.target.files?.[0];
  if (nameEl) nameEl.textContent = file ? file.name : "Файл не выбран";
});

document.getElementById("upload-form")?.addEventListener("submit", async (e) => {
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

document.getElementById("reindex-btn")?.addEventListener("click", async () => {
  const res = await fetch("/api/admin/reindex?clear=true", { method: "POST" });
  const data = await res.json();
  alert("Готово: " + JSON.stringify(data.stats));
  loadDocs();
});

function renderBars(items, labelKey, valueKey, fillClass = "") {
  if (!items.length) return '<p class="hint">Нет данных</p>';
  const max = Math.max(...items.map((i) => i[valueKey]), 1);
  return items
    .map((item) => {
      const pct = (item[valueKey] / max) * 100;
      const label = escapeHtml(String(item[labelKey]));
      return `<div class="bar-row"><span class="bar-label">${label}</span><div class="bar-track"><div class="bar-fill ${fillClass}" style="width:${pct}%"></div></div><span class="bar-val">${item[valueKey]}</span></div>`;
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
      return `<div class="bar-row"><span class="bar-label">${i.label}</span><div class="bar-track"><div class="bar-fill ${i.cls}" style="width:${pct}%"></div></div><span class="bar-val">${val}</span></div>`;
    })
    .join("");
}

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
        <td>${r.auto ? "авто" : "эскалация"}</td>
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
    <div class="progress-wrap"><div class="progress-bar" style="width:${Math.min(s.auto_rate_percent, 100)}%"></div></div>
    <div class="charts-row">
      <div class="chart-card"><h3>Авто vs эскалация</h3><div class="donut-wrap"><div class="donut" style="${donutStyle}" data-label="${s.auto_rate_percent}%"></div></div></div>
      <div class="chart-card"><h3>Уверенность</h3>${renderConfBars(s.confidence_buckets || {})}</div>
    </div>
    <div class="charts-row">
      <div class="chart-card"><h3>Топ вопросов</h3>${renderBars(s.top_questions || [], "question", "count")}</div>
      <div class="chart-card"><h3>Источники</h3>${renderBars(s.top_sources || [], "source", "count", "src")}</div>
    </div>
    <h3 class="stats-section-title">Последние запросы</h3>
    <table class="recent-table"><thead><tr><th>Время</th><th>Вопрос</th><th>Conf.</th><th>Итог</th><th>Источник</th></tr></thead><tbody>${recentRows || "<tr><td colspan='5'>Нет данных</td></tr>"}</tbody></table>`;
  } catch {
    document.getElementById("stats-box").innerHTML = "<p>Не удалось загрузить аналитику.</p>";
  }
}

loadQueue();
setInterval(loadQueue, 15000);
