#!/usr/bin/env bash
# SOCKS5 через зарубежный сервер → Telegram API для Docker-контейнера app.
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE="${PROJECT_ROOT:-.}/.env.telegram-tunnel"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

FOREIGN_HOST="${FOREIGN_SSH_HOST:-}"
FOREIGN_USER="${FOREIGN_SSH_USER:-root}"
FOREIGN_PORT="${FOREIGN_SSH_PORT:-22}"
SOCKS_PORT="${TELEGRAM_SOCKS_PORT:-1080}"
DOCKER_GW="${DOCKER_GATEWAY:-172.18.0.1}"
SSH_KEY="${FOREIGN_SSH_KEY:-$HOME/.ssh/id_rsa}"

usage() {
  cat <<'EOF'
Использование:
  1) Создайте .env.telegram-tunnel (пример — .env.telegram-tunnel.example)
  2) Добавьте pubkey этого сервера на зарубежный VPS (authorized_keys)
  3) ./scripts/telegram_proxy_tunnel.sh start
  4) ./scripts/telegram_proxy_tunnel.sh apply   # прописать .env + перезапуск app
  5) ./scripts/telegram_proxy_tunnel.sh test    # проверка Telegram через прокси

Команды: start | stop | status | test | apply
EOF
}

if [[ -z "$FOREIGN_HOST" && -f .env.telegram-tunnel ]]; then
  set -a
  source .env.telegram-tunnel
  set +a
fi

FOREIGN_HOST="${FOREIGN_SSH_HOST:-}"
FOREIGN_USER="${FOREIGN_SSH_USER:-root}"

pid_file="/run/telegram-socks-tunnel.pid"
proxy_url="socks5://${DOCKER_GW}:${SOCKS_PORT}"

ssh_target="${FOREIGN_USER}@${FOREIGN_HOST}"

start_tunnel() {
  if [[ -z "$FOREIGN_HOST" ]]; then
    echo "Задайте FOREIGN_SSH_HOST в .env.telegram-tunnel"
    usage
    exit 1
  fi

  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "Туннель уже запущен (pid $(cat "$pid_file"))"
    return 0
  fi

  echo "SSH SOCKS5 → ${ssh_target} (bind ${DOCKER_GW}:${SOCKS_PORT})"
  ssh -f -N \
    -i "$SSH_KEY" \
    -p "$FOREIGN_PORT" \
    -D "${DOCKER_GW}:${SOCKS_PORT}" \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=accept-new \
    "$ssh_target"

  sleep 1
  pid=$(pgrep -f "ssh -f -N.*${DOCKER_GW}:${SOCKS_PORT}" | head -1 || true)
  if [[ -z "$pid" ]]; then
    echo "Не удалось запустить SSH туннель"
    exit 1
  fi
  echo "$pid" > "$pid_file"
  echo "Туннель запущен, pid=$pid"
}

stop_tunnel() {
  if [[ -f "$pid_file" ]]; then
    pid=$(cat "$pid_file")
    kill "$pid" 2>/dev/null || true
    rm -f "$pid_file"
  fi
  pkill -f "ssh -f -N.*${DOCKER_GW}:${SOCKS_PORT}" 2>/dev/null || true
  echo "Туннель остановлен"
}

status_tunnel() {
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "running pid=$(cat "$pid_file") proxy=$proxy_url"
  else
    echo "not running"
  fi
}

test_proxy() {
  echo "Проверка Telegram через $proxy_url ..."
  python3 - "$proxy_url" <<'PY'
import sys, httpx
proxy = sys.argv[1]
try:
    r = httpx.get("https://api.telegram.org", proxy=proxy, timeout=20.0)
    print(f"api.telegram.org → HTTP {r.status_code}")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
PY
}

apply_env() {
  env_path=".env"
  line="TELEGRAM_PROXY_URL=${proxy_url}"
  if grep -q '^TELEGRAM_PROXY_URL=' "$env_path"; then
    sed -i "s|^TELEGRAM_PROXY_URL=.*|${line}|" "$env_path"
  else
    echo "$line" >> "$env_path"
  fi
  echo "Обновлено: $line"
  if docker ps --format '{{.Names}}' | grep -q '^bars_support_bot-app-1$'; then
    echo "Перезапуск app..."
    docker restart bars_support_bot-app-1
    echo "Ждём старт (~60 с) и проверяем health..."
    sleep 55
    curl -s http://localhost:8026/api/health | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('telegram_running:', d.get('telegram_running'))
print('telegram_error:', d.get('telegram_error'))
"
  fi
}

cmd="${1:-}"
case "$cmd" in
  start) start_tunnel ;;
  stop) stop_tunnel ;;
  status) status_tunnel ;;
  test) test_proxy ;;
  apply) apply_env ;;
  "") usage ;;
  *) echo "Неизвестная команда: $cmd"; usage; exit 1 ;;
esac
