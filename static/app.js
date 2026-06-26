const sessionId = "web-" + Math.random().toString(36).slice(2);
const messages = document.getElementById("messages");

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "admin") loadDocs();
    if (btn.dataset.tab === "stats") loadStats();
  });
});

function addMsg(text, role, meta = "") {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  messages.appendChild(div);
  if (meta) {
    const m = document.createElement("div");
    m.className = "msg meta";
    m.textContent = meta;
    messages.appendChild(m);
  }
  messages.scrollTop = messages.scrollHeight;
}

async function sendChat(text, escalate = false) {
  addMsg(text, "user");
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, session_id: sessionId, escalate }),
  });
  const data = await res.json();
  const meta = `confidence: ${(data.confidence * 100).toFixed(0)}%` +
    (data.sources?.length ? ` · ${data.sources.join(", ")}` : "");
  addMsg(data.answer, "bot", meta);
}

document.getElementById("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const v = input.value.trim();
  if (!v) return;
  input.value = "";
  sendChat(v);
});

document.getElementById("escalate-btn").addEventListener("click", () => sendChat("оператор", true));

async function loadDocs() {
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
}

document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = document.getElementById("file-input").files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  await fetch("/api/admin/upload", { method: "POST", body: fd });
  document.getElementById("file-input").value = "";
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
  const res = await fetch("/api/analytics");
  const s = await res.json();
  document.getElementById("stats-box").innerHTML = `
    <p><strong>Всего запросов:</strong> ${s.total_queries}</p>
    <p><strong>Автоответов:</strong> ${s.auto_answered} (${s.auto_rate_percent}%)</p>
    <p><strong>Эскалаций:</strong> ${s.escalated}</p>
  `;
}

addMsg("Привет! Я DocHelper Барс. Задайте вопрос по документации.", "bot");
