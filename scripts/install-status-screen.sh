#!/usr/bin/env bash
# Install the JpCAN status screen as a boot service on tty1 (3.5" SPI screen).
# Idempotent: safe to re-run. Usage: sudo scripts/install-status-screen.sh
set -euo pipefail

[ "$EUID" -eq 0 ] || { echo "Run with sudo."; exit 1; }
REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-jp}"
FONT=/usr/share/consolefonts/Lat15-TerminusBold32x16.psf.gz
CONFIG=/boot/firmware/config.txt
CMDLINE=/boot/firmware/cmdline.txt

# 3.5" screen driver (stock overlay), power cable at top
grep -q '^dtoverlay=piscreen' "$CONFIG" || echo "dtoverlay=piscreen,speed=24000000,rotate=270" >> "$CONFIG"
# never blank the console
grep -q 'consoleblank=0' "$CMDLINE" || sed -i '1 s/$/ consoleblank=0/' "$CMDLINE"

[ -f /etc/default/jpcan ] || cat > /etc/default/jpcan <<'EOF'
# Extra arguments for 'jpcan live' at boot.
# Bench demo without the truck: JPCAN_ARGS="--sim"
JPCAN_ARGS=""
EOF

cat > /etc/systemd/system/jpcan-status.service <<EOF
[Unit]
Description=JpCAN status screen (tty1)
After=systemd-user-sessions.service getty@tty1.service
Conflicts=getty@tty1.service

[Service]
User=$USER_NAME
WorkingDirectory=$REPO
EnvironmentFile=-/etc/default/jpcan
Environment=TERM=linux LANG=C.UTF-8
ExecStartPre=+/usr/bin/setfont -C /dev/tty1 $FONT
ExecStart=$REPO/.venv/bin/jpcan live \$JPCAN_ARGS
StandardInput=tty
StandardOutput=tty
StandardError=journal
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl disable getty@tty1.service >/dev/null 2>&1 || true
systemctl enable --now jpcan-status.service
echo "Installed jpcan-status.service. Args: /etc/default/jpcan. Logs: journalctl -u jpcan-status"
