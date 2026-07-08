"""Write presentation SVGs with UTF-8 Russian labels."""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "static" / "presentation"

ARCH = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 230" fill="none">
  <rect x="10" y="10" width="700" height="210" rx="18" fill="rgba(16,185,129,0.06)" stroke="rgba(16,185,129,0.5)" stroke-width="2" stroke-dasharray="8 4"/>
  <text x="360" y="38" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="14" font-weight="700" fill="#10b981">Закрытый контур — данные не уходят наружу</text>
  <rect x="24" y="58" width="100" height="58" rx="12" fill="#0f172a" stroke="#0084ff" stroke-width="1.5"/>
  <text x="74" y="82" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="11" font-weight="600" fill="#e2e8f0">Telegram</text>
  <text x="74" y="98" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#94a3b8">Web-чат</text>
  <rect x="148" y="58" width="108" height="58" rx="12" fill="#0f172a" stroke="#8b5cf6" stroke-width="1.5"/>
  <text x="202" y="82" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="11" font-weight="600" fill="#c4b5fd">Orchestrator</text>
  <text x="202" y="98" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#94a3b8">FastAPI · 6 агентов</text>
  <rect x="280" y="58" width="100" height="58" rx="12" fill="#0f172a" stroke="#00c2ff" stroke-width="1.5"/>
  <text x="330" y="82" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="11" font-weight="600" fill="#e2e8f0">Qdrant</text>
  <text x="330" y="98" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#94a3b8">e5 embeddings</text>
  <rect x="404" y="58" width="88" height="58" rx="12" fill="#0f172a" stroke="#10b981" stroke-width="1.5"/>
  <text x="448" y="82" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="11" font-weight="600" fill="#10b981">LLM</text>
  <text x="448" y="98" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#94a3b8">Ollama / GigaChat</text>
  <rect x="516" y="52" width="108" height="70" rx="12" fill="rgba(16,185,129,0.18)" stroke="#10b981" stroke-width="2"/>
  <text x="570" y="78" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="12" font-weight="700" fill="#10b981">Ответ</text>
  <text x="570" y="96" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#94a3b8">+ источник</text>
  <text x="570" y="112" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">пользователю</text>
  <path d="M124 87h16M256 87h16M380 87h16M492 87h16" stroke="#64748b" stroke-width="2.5" marker-end="url(#arr)"/>
  <text x="360" y="148" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#64748b">Внутри orchestrator</text>
  <rect x="24" y="162" width="115" height="50" rx="10" fill="#0f172a" stroke="#f59e0b"/>
  <text x="81" y="184" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#fbbf24">Speech</text>
  <text x="81" y="200" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">Whisper · голос</text>
  <rect x="155" y="162" width="115" height="50" rx="10" fill="#0f172a" stroke="#f59e0b"/>
  <text x="212" y="184" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#fbbf24">Evaluator</text>
  <text x="212" y="200" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">confidence</text>
  <rect x="286" y="162" width="115" height="50" rx="10" fill="#0f172a" stroke="#ef4444"/>
  <text x="343" y="184" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#fca5a5">Escalation</text>
  <text x="343" y="200" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">оператор · тикет</text>
  <rect x="417" y="162" width="115" height="50" rx="10" fill="#0f172a" stroke="#ec4899"/>
  <text x="474" y="184" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#f472b6">Analytics</text>
  <text x="474" y="200" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">weak spots</text>
  <rect x="548" y="162" width="148" height="50" rx="10" fill="#0f172a" stroke="#64748b"/>
  <text x="622" y="184" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#94a3b8">Redis</text>
  <text x="622" y="200" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">сессии · лимиты</text>
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8 Z" fill="#64748b"/>
    </marker>
  </defs>
</svg>
"""

METRICS = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 220" fill="none">
  <rect x="8" y="8" width="284" height="204" rx="16" fill="#0f172a" stroke="rgba(16,185,129,0.35)" stroke-width="1.5"/>
  <text x="150" y="32" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="11" font-weight="700" fill="#94a3b8">Тесты брифа · 17 кейсов</text>
  <circle cx="95" cy="118" r="58" stroke="#1e293b" stroke-width="12"/>
  <circle cx="95" cy="118" r="58" stroke="url(#donut)" stroke-width="12" stroke-dasharray="327 364" stroke-linecap="round" transform="rotate(-90 95 118)"/>
  <text x="95" y="114" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="26" font-weight="800" fill="#10b981">94%</text>
  <text x="95" y="134" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">авто</text>
  <rect x="175" y="58" width="110" height="36" rx="10" fill="rgba(0,132,255,0.12)" stroke="#0084FF"/>
  <text x="185" y="74" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">Всего</text>
  <text x="185" y="88" font-family="Manrope,system-ui,sans-serif" font-size="14" font-weight="700" fill="#e2e8f0">17</text>
  <rect x="175" y="102" width="110" height="36" rx="10" fill="rgba(16,185,129,0.12)" stroke="#10b981"/>
  <text x="185" y="118" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">Авто</text>
  <text x="185" y="132" font-family="Manrope,system-ui,sans-serif" font-size="14" font-weight="700" fill="#10b981">16</text>
  <rect x="175" y="146" width="110" height="36" rx="10" fill="rgba(239,68,68,0.1)" stroke="#ef4444"/>
  <text x="185" y="162" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">Эскалация</text>
  <text x="185" y="176" font-family="Manrope,system-ui,sans-serif" font-size="14" font-weight="700" fill="#fca5a5">1</text>
  <rect x="24" y="188" width="252" height="8" rx="4" fill="#1e293b"/>
  <rect x="24" y="188" width="236" height="8" rx="4" fill="url(#bar)"/>
  <text x="150" y="206" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">~1,6 сек · цель ≥ 40%</text>
  <defs>
    <linearGradient id="donut" x1="37" y1="60" x2="153" y2="176" gradientUnits="userSpaceOnUse">
      <stop stop-color="#10b981"/><stop offset="1" stop-color="#0084FF"/>
    </linearGradient>
    <linearGradient id="bar" x1="24" y1="192" x2="276" y2="192" gradientUnits="userSpaceOnUse">
      <stop stop-color="#10b981"/><stop offset="1" stop-color="#0084FF"/>
    </linearGradient>
  </defs>
</svg>
"""

SOLUTION = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 240" fill="none">
  <rect x="16" y="24" width="288" height="192" rx="18" fill="#0f172a" stroke="rgba(0,132,255,0.45)" stroke-width="2"/>
  <rect x="16" y="24" width="288" height="36" rx="18" fill="rgba(0,132,255,0.12)"/>
  <rect x="16" y="42" width="288" height="18" fill="rgba(0,132,255,0.12)"/>
  <circle cx="40" cy="42" r="6" fill="#ef4444" opacity="0.7"/>
  <circle cx="58" cy="42" r="6" fill="#f59e0b" opacity="0.7"/>
  <circle cx="76" cy="42" r="6" fill="#10b981" opacity="0.7"/>
  <text x="160" y="47" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="11" font-weight="700" fill="#e2e8f0">DocHelper</text>
  <circle cx="52" cy="88" r="22" fill="url(#botGrad)"/>
  <text x="52" y="93" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="11" font-weight="800" fill="#fff">AI</text>
  <rect x="82" y="68" width="196" height="44" rx="12" fill="#1e293b" stroke="#334155"/>
  <text x="96" y="88" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#cbd5e1">Как работает фильтр</text>
  <text x="96" y="102" font-family="Manrope,system-ui,sans-serif" font-size="10" fill="#cbd5e1">документа?</text>
  <circle cx="52" cy="148" r="22" fill="url(#botGrad)" opacity="0.9"/>
  <text x="52" y="153" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="11" font-weight="800" fill="#fff">AI</text>
  <rect x="82" y="124" width="210" height="72" rx="12" fill="rgba(16,185,129,0.1)" stroke="rgba(16,185,129,0.45)" stroke-width="1.5"/>
  <text x="96" y="144" font-family="Manrope,system-ui,sans-serif" font-size="9.5" font-weight="600" fill="#10b981">Ответ из docx</text>
  <text x="96" y="160" font-family="Manrope,system-ui,sans-serif" font-size="8.5" fill="#94a3b8">Functionalnie.docx — фрагмент</text>
  <rect x="96" y="168" width="72" height="18" rx="6" fill="rgba(0,132,255,0.2)" stroke="rgba(0,132,255,0.5)"/>
  <text x="132" y="180" text-anchor="middle" font-family="Manrope,system-ui,sans-serif" font-size="8" font-weight="600" fill="#00c2ff">Скачать</text>
  <rect x="32" y="204" width="256" height="28" rx="14" fill="#1e293b" stroke="#334155"/>
  <text x="48" y="222" font-family="Manrope,system-ui,sans-serif" font-size="9" fill="#64748b">Задайте вопрос...</text>
  <circle cx="272" cy="218" r="10" fill="url(#botGrad)"/>
  <path d="M266 218h6l-3 3v-3z" fill="#fff"/>
  <defs>
    <linearGradient id="botGrad" x1="30" y1="66" x2="74" y2="110" gradientUnits="userSpaceOnUse">
      <stop stop-color="#0084FF"/><stop offset="1" stop-color="#00C2FF"/>
    </linearGradient>
  </defs>
</svg>
"""

(OUT / "ill-arch.svg").write_text(ARCH, encoding="utf-8")
(OUT / "ill-metrics.svg").write_text(METRICS, encoding="utf-8")
(OUT / "ill-solution.svg").write_text(SOLUTION, encoding="utf-8")
print("ok")
