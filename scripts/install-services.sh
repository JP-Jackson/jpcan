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
# Qt for GaugeWorks (D29). Default "system": Raspberry Pi OS's PySide6 from apt,
# whose Qt has the EGLFS KMS/GBM GPU path (the pip wheel lacks
# libQt6EglFsKmsGbmSupport, so it could only draw with the CPU).
# GW_QT=pip goes back to the pip wheel.
GW_QT="${GW_QT:-system}"
CFG="$VENV/pyvenv.cfg"
if [ "$GW_QT" = "system" ]; then
    echo "== Qt: Raspberry Pi OS PySide6 (GPU)"
    for p in python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtqml python3-pyside6.qtquick \
             qml6-module-qtquick qml6-module-qtquick-shapes qml6-module-qtquick-window \
             qml6-module-qtqml-workerscript qml6-module-qtqml-models qt6-qpa-plugins libqt6gui6 \
             qt6-svg-plugins; do
        echo "   apt: $p"
        apt-get install -y -q --no-install-recommends "$p" >/dev/null 2>&1 || echo "WARNING: apt couldn't install $p"
    done
    sed -i 's/^include-system-site-packages = .*/include-system-site-packages = true/' "$CFG"
    sudo -u "$USER_NAME" "$VENV/bin/pip" uninstall -y -q PySide6 PySide6-Essentials PySide6-Addons shiboken6 \
        >/dev/null 2>&1 || true
    sudo -u "$USER_NAME" "$VENV/bin/pip" install -q -e "$REPO"
else
    echo "== Qt: pip wheel (CPU drawing only)"
    sed -i 's/^include-system-site-packages = .*/include-system-site-packages = false/' "$CFG"
    sudo -u "$USER_NAME" "$VENV/bin/pip" install -q -e "$REPO[ui]"
fi
# Fail loudly if the pieces GaugeWorks loads are missing (it would crash-loop or
# fall back to the CPU): EGLFS + KMS integration (GPU), linuxfb (fallback),
# evdevtouch (touch). X11/Wayland are irrelevant.
QTINFO="$(sudo -u "$USER_NAME" "$VENV/bin/python" -c "import PySide6
from PySide6.QtCore import QLibraryInfo as L
print(PySide6.__version__, L.path(L.LibraryPath.PluginsPath))" 2>/dev/null)" \
    || { echo "WARNING: PySide6 import failed"; QTINFO=""; }
if [ -n "$QTINFO" ]; then
    PLUG="${QTINFO#* }"
    echo "   PySide6 ${QTINFO%% *}, plugins in $PLUG"
    for f in platforms/libqeglfs.so egldeviceintegrations/libqeglfs-kms-integration.so \
             platforms/libqlinuxfb.so generic/libqevdevtouchplugin.so imageformats/libqsvg.so; do
        if [ ! -e "$PLUG/$f" ]; then echo "WARNING: missing Qt plugin $f"; continue; fi
        MISSING="$(ldd "$PLUG/$f" 2>/dev/null | grep 'not found' | sort -u || true)"
        if [ -n "$MISSING" ]; then echo "WARNING: $f is missing libraries:"; echo "$MISSING"; fi
    done
    # End to end: render the Premium theme offscreen; QML errors make it exit non-zero.
    if sudo -u "$USER_NAME" env QT_QPA_PLATFORM=offscreen timeout 90 "$VENV/bin/gaugeworks" \
            --demo cruise --theme oem --screenshot /tmp/gaugeworks-check.png >/tmp/gaugeworks-check.log 2>&1; then
        echo "   GaugeWorks render check OK"
    else
        echo "WARNING: GaugeWorks render check failed:"; tail -5 /tmp/gaugeworks-check.log | sed 's/^/   /'
    fi
fi

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

echo "== HDMI mode for the GaugeWorks screen (D28)"
# Lock HDMI0 to the panel's native mode, even if the screen is plugged in after
# boot. Otherwise the Pi falls back to 1024x768 and the 600-tall layout lands
# 84 px low with the bottom cut off. Change GW_MODE for a different screen.
GW_MODE="${GW_MODE:-1024x600@60}"
if grep -q 'video=HDMI-A-1:' "$CMDLINE"; then
    sed -i "1 s/video=HDMI-A-1:[^ ]*/video=HDMI-A-1:${GW_MODE}D/" "$CMDLINE"
else
    sed -i "1 s/\$/ video=HDMI-A-1:${GW_MODE}D/" "$CMDLINE"
fi
grep -o 'video=HDMI-A-1:[^ ]*' "$CMDLINE" | sed 's/^/   /'
echo "   (takes effect after a reboot)"

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
