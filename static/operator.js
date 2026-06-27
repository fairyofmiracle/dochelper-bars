const operatorPin = localStorage.getItem("operator_pin") || "";
let selectedSessionId = null;
let selectedResolved = false;
let queueItems = [];
let resolvedItems = [];

function pinHeaders() {
  const h = {};
  if (operatorPin) h["X-Operator-Pin"] = operatorPin;
  return h;
}

function ensurePin() {
  return operatorPin;
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "docs") loadDocs();
    if (btn.dataset.tab === "stats") loadStats();
    if (btn.dataset.tab === "conversations") loadQueue();
  });
});

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function roleLabel(role) {
  if (role === "user") return "Пользователь";
  if (role === "operator") return "Оператор";
  return "DocHelper";
}

function renderDialogMessage(msg) {
  const role = msg.role === "assistant" ? "bot" : msg.role === "operator" ? "operator" : "user";
  const row = document.createElement("div");
  row.className = "msg-row " + role + (role === "operator" ? " operator" : "");

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "user" ? "П" : role === "operator" ? "Оп" : "AI";

  const body = document.createElement("div");
  body.className = "msg-body";
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble msg " + role;
  bubble.textContent = msg.content;
  body.appendChild(bubble);

  row.appendChild(avatar);
  row.appendChild(body);
  return row;
}

function showDialog(item, isResolved = false) {
  selectedSessionId = item.session_id;
  selectedResolved = isResolved;
  document.getElementById("dialog-empty").classList.add("hidden");
  document.getElementById("dialog-active").classList.remove("hidden");
  document.getElementById("dialog-user").textContent = item.user_label || "Пользователь";
  const statusTag = isResolved ? " · закрыто" : "";
  document.getElementById("dialog-meta").textContent =
    (item.question ? `«${item.question.slice(0, 80)}${item.question.length > 80 ? "…" : ""}» · ` : "") +
    new Date(item.ts * 1000).toLocaleString("ru-RU") +
    statusTag;

  document.querySelectorAll(".session-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.session === item.session_id);
  });

  document.getElementById("resolve-btn").classList.toggle("hidden", isResolved);
  document.getElementById("reply-form").classList.toggle("hidden", isResolved);
  document.getElementById("operator-quick").classList.toggle("hidden", isResolved);

  renderDialogHistory(item.history || []);
}

function renderDialogHistory(history) {
  const box = document.getElementById("dialog-messages");
  box.innerHTML = "";
  if (!history.length) {
    box.innerHTML = '<p class="hint">История пуста</p>';
    return;
  }
  history.forEach((msg) => box.appendChild(renderDialogMessage(msg)));
  box.scrollTop = box.scrollHeight;
}

async function refreshSelectedDialog() {
  if (!selectedSessionId) return;
  try {
    const res = await fetch(`/api/operator/messages/${encodeURIComponent(selectedSessionId)}`, {
      headers: pinHeaders(),
    });
    if (!res.ok) return;
    const data = await res.json();
    renderDialogHistory(data.messages || []);
  } catch {
    /* ignore */
  }
}

async function loadStatus() {
  try {
    const res = await fetch("/api/health");
    const h = await res.json();
    document.getElementById("status-docs").textContent = `Документов: ${h.docs_count ?? 0}`;
    document.getElementById("status-qdrant").textContent = h.qdrant_ok
      ? `Qdrant: ${h.qdrant_points} фрагментов`
      : "Qdrant: пусто — загрузите документы";
    const waiting = queueItems.filter((q) => q.status === "waiting").length;
    document.getElementById("status-queue").textContent = `В очереди: ${waiting}`;
    const tgEl = document.getElementById("status-telegram");
    if (tgEl) {
      if (h.telegram_running) {
        tgEl.textContent = "Telegram: работает";
        tgEl.className = "status-pill status-pill--ok";
      } else if (h.telegram_token_set) {
        tgEl.textContent = "Telegram: не запущен";
        tgEl.className = "status-pill status-pill--warn";
      } else {
        tgEl.textContent = "Telegram: не настроен";
        tgEl.className = "status-pill status-pill--muted";
      }
    }
  } catch {
    document.getElementById("status-online").className = "status-pill status-pill--err";
    document.getElementById("status-online").textContent = "● Офлайн";
  }
}

function renderSessionButtons(items, container, isResolved) {
  if (!items.length) {
    container.innerHTML = isResolved
      ? "<p class='hint'>Пока нет закрытых обращений</p>"
      : "<p class='hint'>Очередь пуста — все пользователи получили ответ.</p>";
    return;
  }
  container.innerHTML = items
    .map(
      (item) =>
        `<button type="button" class="session-item${isResolved ? " session-item--resolved" : ""}${item.session_id === selectedSessionId ? " active" : ""}" data-session="${escapeHtml(item.session_id)}" data-resolved="${isResolved ? "1" : "0"}">
          <span class="session-item-user">${escapeHtml(item.user_label || "Пользователь")}${isResolved ? ' <span class="session-tag">✓</span>' : ""}</span>
          <span class="session-item-q">${escapeHtml((item.question || "Без текста").slice(0, 90))}</span>
          <span class="session-item-time">${new Date(item.ts * 1000).toLocaleString("ru-RU")}</span>
        </button>`
    )
    .join("");

  container.querySelectorAll(".session-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pool = btn.dataset.resolved === "1" ? resolvedItems : queueItems;
      const item = pool.find((q) => q.session_id === btn.dataset.session);
      if (item) showDialog(item, btn.dataset.resolved === "1");
    });
  });
}

async function loadQueue() {
  ensurePin();
  const list = document.getElementById("session-list");
  const resolvedList = document.getElementById("resolved-list");
  try {
    const res = await fetch("/api/operator/queue", { headers: pinHeaders() });
    if (res.status === 401) {
      const pin = prompt("Введите PIN оператора:", "");
      if (pin) {
        localStorage.setItem("operator_pin", pin);
        location.reload();
        return;
      }
      list.innerHTML = "<p class='hint'>Нужен PIN оператора — обновите страницу и введите его</p>";
      return;
    }
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    queueItems = data.queue || [];
    resolvedItems = data.resolved || [];
    const waiting = queueItems.length;
    document.getElementById("queue-badge").textContent = String(waiting);
    document.getElementById("resolved-badge").textContent = String(resolvedItems.length);
    loadStatus();

    renderSessionButtons(queueItems, list, false);
    renderSessionButtons(resolvedItems, resolvedList, true);

    if (selectedSessionId) {
      const current =
        queueItems.find((q) => q.session_id === selectedSessionId) ||
        resolvedItems.find((q) => q.session_id === selectedSessionId);
      if (current) showDialog(current, selectedResolved);
    } else if (queueItems.length === 1) {
      showDialog(queueItems[0], false);
    } else if (!queueItems.length && resolvedItems.length) {
      showDialog(resolvedItems[0], true);
    } else if (!queueItems.length && !resolvedItems.length) {
      selectedSessionId = null;
      document.getElementById("dialog-empty").classList.remove("hidden");
      document.getElementById("dialog-active").classList.add("hidden");
    }
  } catch (err) {
    list.innerHTML = `<p class="hint">Не удалось загрузить очередь: ${escapeHtml(String(err.message || err))}</p>`;
  }
}

document.getElementById("reply-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!selectedSessionId) return;
  const input = document.getElementById("reply-input");
  const message = input.value.trim();
  if (!message) return;

  const res = await fetch("/api/operator/reply", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...pinHeaders() },
    body: JSON.stringify({ session_id: selectedSessionId, message, resolve: false }),
  });
  if (!res.ok) {
    alert("Ошибка: " + (await res.text()));
    return;
  }
  input.value = "";
  await refreshSelectedDialog();
});

document.getElementById("resolve-btn")?.addEventListener("click", async () => {
  if (!selectedSessionId) return;
  const res = await fetch("/api/operator/reply", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...pinHeaders() },
    body: JSON.stringify({ session_id: selectedSessionId, message: "Обращение закрыто оператором.", resolve: true }),
  });
  if (res.ok) {
    selectedSessionId = null;
    document.getElementById("dialog-empty").classList.remove("hidden");
    document.getElementById("dialog-active").classList.add("hidden");
    loadQueue();
  }
});

async function loadDocs() {
  const alert = document.getElementById("docs-alert");
  const status = document.getElementById("upload-status");
  try {
    const [docsRes, healthRes] = await Promise.all([fetch("/api/admin/documents"), fetch("/api/health")]);
    const data = await docsRes.json();
    const health = await healthRes.json();

    if (!health.docs_count) {
      alert.classList.remove("hidden");
      alert.className = "docs-alert docs-alert--warn";
      alert.textContent =
        "База пуста — бот пока не находит ответы. Загрузите docx кейса (Functionalnie, Komandirovka, newbiePage, ReestrMebeli) или свои файлы.";
    } else if (!health.qdrant_ok || !health.qdrant_points) {
      alert.classList.remove("hidden");
      alert.className = "docs-alert docs-alert--warn";
      alert.textContent = "Документы есть, но индекс пуст — нажмите «Переиндексировать всё».";
    } else {
      alert.classList.add("hidden");
    }

    status.textContent = health.qdrant_ok
      ? `В индексе ${health.qdrant_points} фрагментов из ${health.docs_count} файлов`
      : "Индекс не создан";

    const ul = document.getElementById("doc-list");
    ul.innerHTML = "";
    const docs = data.documents || [];
    if (!docs.length) {
      ul.innerHTML = "<li class='hint'>Файлов пока нет</li>";
      return;
    }
    docs.forEach((d) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${escapeHtml(d.name)} <small>(${escapeHtml(d.folder)}, ${Math.round(d.size_bytes / 1024)} KB)</small></span>`;
      const del = document.createElement("button");
      del.textContent = "Удалить";
      del.className = "btn btn-outline btn-sm";
      del.onclick = async () => {
        if (!confirm(`Удалить ${d.name}?`)) return;
        await fetch(`/api/admin/documents/${encodeURIComponent(d.name)}`, { method: "DELETE" });
        loadDocs();
        loadStatus();
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

  const btn = document.getElementById("upload-btn");
  const status = document.getElementById("upload-status");
  btn.disabled = true;
  status.textContent = "Загрузка и индексация…";

  try {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/admin/upload", { method: "POST", body: fd });
    const raw = await res.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      throw new Error(raw.slice(0, 200) || `HTTP ${res.status}`);
    }
    if (!res.ok) throw new Error(data.detail || raw.slice(0, 200) || `HTTP ${res.status}`);
    const chunks = data.index?.chunks ?? "?";
    status.textContent = `Готово: ${file.name} — ${chunks} фрагментов в индексе`;
    document.getElementById("file-input").value = "";
    document.getElementById("file-name").textContent = "Файл не выбран";
    loadDocs();
    loadStatus();
  } catch (err) {
    status.textContent = "Ошибка: " + (err.message || err);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("reindex-btn")?.addEventListener("click", async () => {
  const status = document.getElementById("upload-status");
  status.textContent = "Переиндексация…";
  try {
    const res = await fetch("/api/admin/reindex?clear=true", { method: "POST" });
    const raw = await res.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      throw new Error(raw.slice(0, 200) || `HTTP ${res.status}`);
    }
    if (!res.ok) throw new Error(data.detail || raw.slice(0, 200));
    const s = data.stats || {};
    status.textContent = `Готово: ${s.files || 0} файлов, ${s.chunks || 0} фрагментов`;
    if (s.errors?.length) status.textContent += " · " + s.errors.join("; ");
    loadDocs();
    loadStatus();
  } catch (err) {
    status.textContent = "Ошибка переиндексации";
  }
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
loadStatus();
setInterval(loadQueue, 12000);
setInterval(refreshSelectedDialog, 5000);
