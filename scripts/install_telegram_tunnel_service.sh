#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT=/etc/systemd/system/bars-telegram-tunnel.service

cat > "$UNIT" <<EOF
[Unit]
Description=Bars DocHelper — SSH SOCKS5 for Telegram
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${ROOT}
ExecStart=${ROOT}/scripts/telegram_tunnel_foreground.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

chmod +x "${ROOT}/scripts/telegram_tunnel_foreground.sh"
systemctl daemon-reload
systemctl enable bars-telegram-tunnel.service
echo "OK: bars-telegram-tunnel.service"
echo "Добавьте SSH-ключ на ${ROOT}/.env.telegram-tunnel → FOREIGN_SSH_HOST"
echo "  cat /root/.ssh/id_rsa.pub  # на прокси-сервере в authorized_keys"
echo "  systemctl start bars-telegram-tunnel"
echo "  cd ${ROOT} && ./scripts/telegram_proxy_tunnel.sh apply"
