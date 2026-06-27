#!/usr/bin/env bash
# SSH SOCKS5 в foreground — для systemd (автоперезапуск).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env.telegram-tunnel ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.telegram-tunnel
  set +a
fi

: "${FOREIGN_SSH_HOST:?FOREIGN_SSH_HOST не задан в .env.telegram-tunnel}"
FOREIGN_SSH_USER="${FOREIGN_SSH_USER:-root}"
FOREIGN_SSH_PORT="${FOREIGN_SSH_PORT:-22}"
DOCKER_GW="${DOCKER_GATEWAY:-172.18.0.1}"
SOCKS_PORT="${TELEGRAM_SOCKS_PORT:-1080}"
SSH_KEY="${FOREIGN_SSH_KEY:-/root/.ssh/id_rsa}"

exec ssh -N \
  -i "$SSH_KEY" \
  -p "$FOREIGN_SSH_PORT" \
  -D "${DOCKER_GW}:${SOCKS_PORT}" \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=accept-new \
  "${FOREIGN_SSH_USER}@${FOREIGN_SSH_HOST}"
