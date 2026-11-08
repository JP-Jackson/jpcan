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
apt-get install -y -q mosquitto mosquitto-clients fbset \
    libegl1 libgles2 libgl1 libopengl0 libgbm1 libdrm2 libinput10 libmtdev1 \
    libxkbcommon0 libfontconfig1 fonts-dejavu-core >/dev/null
# GLib was renamed for the 64-bit time_t transition (Trixie); accept either name.
apt-get install -y -q libglib2.0-0t64 >/dev/null 2>&1 || apt-get install -y -q libglib2.0-0 >/dev/null
systemctl enable --now mosquitto >/dev/null
sudo -u "$USER_NAME" "$VENV/bin/pip" install -q -e "$REPO[ui]"
# Fail loudly if Qt is missing a system library (GaugeWorks would crash-loop).
# Only the pieces GaugeWorks loads (EGLFS, no desktop); X11/Wayland libs are irrelevant.
QT="$(echo "$VENV"/lib/python3*/site-packages/PySide6/Qt)"
MISSING="$(ldd "$QT"/lib/libQt6Core.so.6 "$QT"/lib/libQt6Gui.so.6 "$QT"/lib/libQt6Qml.so.6 \
    "$QT"/lib/libQt6Quick.so.6 "$QT"/lib/libQt6EglFSDeviceIntegration.so.6 \
    "$QT"/plugins/platforms/libqeglfs.so "$QT"/plugins/platforms/libqlinuxfb.so \
    "$QT"/plugins/egldeviceintegrations/libqeglfs-kms-integration.so \
    2>/dev/null | grep 'not found' | sort -u)"
if [ -n "$MISSING" ]; then echo "WARNING: Qt is missing system libraries:"; echo "$MISSING"; fi
sudo -u "$USER_NAME" "$VENV/bin/python" -c "from PySide6.QtGui import QGuiApplication" \
    && echo "Qt import OK" || echo "WARNING: PySide6 import failed; see above"

echo "== permissions"
# GaugeWorks' Shut Down button: allow exactly 'systemctl poweroff', nothing else.
SUDOERS=/etc/sudoers.d/jpcan-poweroff
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff" > "$SUDOERS.tmp"
chmod 0440 "$SUDOERS.tmp"
visudo -cf "$SUDOERS.tmp" >/dev/null && mv "$SUDOERS.tmp" "$SUDOERS"
# USB export: root-owned helper (NOT the user-editable repo copy) + a rule for exactly it.
install -o root -g root -m 0755 "$REPO/scripts/jpcan-usb" /usr/local/sbin/jpcan-usb
sed -i "s/__JPCAN_USER__/$USER_NAME/" /usr/local/sbin/jpcan-usb
SUDOERS_USB=/etc/sudoers.d/jpcan-usb
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/local/sbin/jpcan-usb" > "$SUDOERS_USB.tmp"
chmod 0440 "$SUDOERS_USB.tmp"
visudo -cf "$SUDOERS_USB.tmp" >/dev/null && mv "$SUDOERS_USB.tmp" "$SUDOERS_USB"
mkdir -p /media/jpcan-usb
# Truck/Simulator switch in Settings: same pattern, a root-owned helper and one rule.
install -o root -g root -m 0755 "$REPO/scripts/jpcan-mode" /usr/local/sbin/jpcan-mode
SUDOERS_MODE=/etc/sudoers.d/jpcan-mode
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/local/sbin/jpcan-mode truck, /usr/local/sbin/jpcan-mode sim, /usr/local/sbin/jpcan-mode status" > "$SUDOERS_MODE.tmp"
chmod 0440 "$SUDOERS_MODE.tmp"
visudo -cf "$SUDOERS_MODE.tmp" >/dev/null && mv "$SUDOERS_MODE.tmp" "$SUDOERS_MODE"
for grp in video render input dialout systemd-journal; do usermod -aG "$grp" "$USER_NAME" 2>/dev/null || true; done

echo "== persistent journal (service logs survive a reboot, capped at 64 MB)"
mkdir -p /var/log/journal /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=persistent\nSystemMaxUse=64M\n' > /etc/systemd/journald.conf.d/jpcan.conf
systemd-tmpfiles --create --prefix /var/log/journal >/dev/null 2>&1 || true
systemctl restart systemd-journald

echo "== 3.5in screen + console"
grep -q '^dtoverlay=piscreen' "$CONFIG" || echo "dtoverlay=piscreen,speed=24000000,rotate=270" >> "$CONFIG"
grep -q 'consoleblank=0' "$CMDLINE" || sed -i '1 s/$/ consoleblank=0/' "$CMDLINE"

[ -f /etc/default/jpcan ] || cat > /etc/default/jpcan <<'EOF'
# Extra arguments for the core service ('jpcan run').
# Truck vs simulator is the Settings switch now (/etc/default/jpcan-mode).
JPCAN_ARGS=""
EOF
[ -f /etc/default/jpcan-mode ] || printf 'JPCAN_MODE_ARGS=""\n' > /etc/default/jpcan-mode
if grep -q '^JPCAN_ARGS=.*--sim' /etc/default/jpcan; then
    echo "NOTE: /etc/default/jpcan still has --sim, so the Settings switch can't pick Truck. Remove it there."
fi

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
EnvironmentFile=-/etc/default/jpcan-mode
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV/bin/jpcan run \$JPCAN_ARGS \$JPCAN_MODE_ARGS
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
ExecStartPre=+$REPO/scripts/console-to-spi.sh
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
