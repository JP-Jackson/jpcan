#!/usr/bin/env bash
# Install/refresh JpCAN on the Pi: mosquitto, core service, 3.5" status screen,
# GaugeWorks on the 7" HDMI screen.
# Idempotent: safe to re-run after every 'git pull'.
# Usage: sudo ~/jpcan/scripts/install-services.sh
set -euo pipefail

[ "$EUID" -eq 0 ] || { echo "Run with sudo."; exit 1; }
REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-jp}"
VENV="$REPO/.venv"
FONT=/usr/share/consolefonts/Lat15-TerminusBold32x16.psf.gz
CONFIG=/boot/firmware/config.txt
CMDLINE=/boot/firmware/cmdline.txt

echo "== packages (first run downloads Qt, ~100 MB; give it a few minutes)"
apt-get install -y -q mosquitto mosquitto-clients \
    libegl1 libgles2 libgbm1 libdrm2 libinput10 libmtdev1 libxkbcommon0 \
    libfontconfig1 fonts-dejavu-core >/dev/null
systemctl enable --now mosquitto >/dev/null
sudo -u "$USER_NAME" "$VENV/bin/pip" install -q -e "$REPO[ui]"

echo "== permissions"
# GaugeWorks' Shut Down button: allow exactly 'systemctl poweroff', nothing else.
SUDOERS=/etc/sudoers.d/jpcan-poweroff
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff" > "$SUDOERS.tmp"
chmod 0440 "$SUDOERS.tmp"
visudo -cf "$SUDOERS.tmp" >/dev/null && mv "$SUDOERS.tmp" "$SUDOERS"
for grp in video render input dialout; do usermod -aG "$grp" "$USER_NAME"; done

echo "== 3.5in screen + console"
grep -q '^dtoverlay=piscreen' "$CONFIG" || echo "dtoverlay=piscreen,speed=24000000,rotate=270" >> "$CONFIG"
grep -q 'consoleblank=0' "$CMDLINE" || sed -i '1 s/$/ consoleblank=0/' "$CMDLINE"

[ -f /etc/default/jpcan ] || cat > /etc/default/jpcan <<'EOF'
# Extra arguments for the core service ('jpcan run').
# Bench demo without the truck: JPCAN_ARGS="--sim"
JPCAN_ARGS=""
EOF

echo "== services"
cat > /etc/systemd/system/jpcan-core.service <<EOF
[Unit]
Description=JpCAN core (adapter, guard, logger, MQTT)
After=mosquitto.service
Wants=mosquitto.service

[Service]
User=$USER_NAME
WorkingDirectory=$REPO
EnvironmentFile=-/etc/default/jpcan
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV/bin/jpcan run \$JPCAN_ARGS
Restart=always
RestartSec=3
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/jpcan-status.service <<EOF
[Unit]
Description=JpCAN status screen (tty1, reads MQTT)
After=systemd-user-sessions.service getty@tty1.service jpcan-core.service
Conflicts=getty@tty1.service

[Service]
User=$USER_NAME
WorkingDirectory=$REPO
Environment=TERM=linux LANG=C.UTF-8
ExecStartPre=+/usr/bin/setfont -C /dev/tty1 $FONT
ExecStart=$VENV/bin/jpcan live --bus
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

cat > /etc/systemd/system/gaugeworks.service <<UNIT
[Unit]
Description=GaugeWorks (7in HDMI gauges, reads MQTT)
After=jpcan-core.service systemd-user-sessions.service

[Service]
User=$USER_NAME
WorkingDirectory=$REPO
Environment=PYTHONUNBUFFERED=1
Environment=XDG_RUNTIME_DIR=/tmp
ExecStart=$REPO/scripts/gaugeworks-launch.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl disable getty@tty1.service >/dev/null 2>&1 || true
systemctl enable jpcan-core.service jpcan-status.service gaugeworks.service >/dev/null
systemctl restart jpcan-core.service jpcan-status.service gaugeworks.service
echo "Done. Logs: journalctl -u jpcan-core -f  /  journalctl -u gaugeworks -f   Drives: ~/jpcan-logs"
