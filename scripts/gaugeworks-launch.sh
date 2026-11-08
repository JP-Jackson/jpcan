#!/usr/bin/env bash
# Start GaugeWorks fullscreen on the HDMI screen (no desktop).
# - waits for a connected HDMI output and picks its DRM card (Pi 5 has several)
# - uses only the HDMI screen's USB touch, not the 3.5" ADS7846
# - tries EGLFS (GPU); falls back to linuxfb + software rendering if EGLFS fails fast
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
GW="$REPO/.venv/bin/gaugeworks"
RUNDIR="${XDG_RUNTIME_DIR:-/tmp}"

hdmi_connector() {
    for st in /sys/class/drm/card*-HDMI-A-*/status; do
        [ -e "$st" ] && [ "$(cat "$st")" = "connected" ] && { basename "$(dirname "$st")"; return 0; }
    done
    return 1
}

until CONN="$(hdmi_connector)"; do
    echo "GaugeWorks: waiting for an HDMI screen..."; sleep 5
done
CARD="/dev/dri/${CONN%%-*}"          # card1-HDMI-A-1 -> /dev/dri/card1
OUTPUT="${CONN#*-}"                  # -> HDMI-A-1
echo "GaugeWorks: $OUTPUT on $CARD"

find_touch() {
    for ev in /dev/input/event*; do
        name="$(cat "/sys/class/input/$(basename "$ev")/device/name" 2>/dev/null)"
        case "$name" in *ADS7846*) continue ;; esac
        if udevadm info -q property -n "$ev" 2>/dev/null | grep -q '^ID_INPUT_TOUCHSCREEN=1'; then
            echo "$ev ($name)"; return 0
        fi
    done
    return 1
}

# The HDMI screen's USB touch can enumerate after the HDMI output; give it ~20 s.
TOUCH=""; TOUCH_NAME=""
for _ in $(seq 1 10); do
    if T="$(find_touch)"; then
        TOUCH="${T%% *}"; TOUCH_NAME="${T#* (}"; TOUCH_NAME="${TOUCH_NAME%)}"
        echo "GaugeWorks: touch $T"; break
    fi
    echo "GaugeWorks: waiting for a USB touchscreen..."; sleep 2
done
[ -z "$TOUCH" ] && echo "GaugeWorks: no USB touchscreen found; Qt will auto-detect input"

cat > "$RUNDIR/gaugeworks-kms.json" <<EOF
{ "device": "$CARD", "hwcursor": false,
  "outputs": [ { "name": "$OUTPUT", "mode": "current" } ] }
EOF

export QT_QPA_EGLFS_KMS_CONFIG="$RUNDIR/gaugeworks-kms.json"
export QT_QPA_EGLFS_ALWAYS_SET_MODE=1
export QT_QPA_EGLFS_HIDECURSOR=1
# Input: turn OFF Qt's built-in handlers (mouse, keyboard, touch, libinput) and
# load exactly one evdev touch handler on the HDMI screen's touch device.
# Never point a handler at /dev/null to "disable" it: it reads EOF forever and
# Qt spins at 100% CPU logging "evdevmouse: Got EOF" (the touch lockups, D27).
unset QT_QPA_EVDEV_MOUSE_PARAMETERS QT_QPA_EVDEV_KEYBOARD_PARAMETERS QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS
if [ -n "$TOUCH" ]; then
    export QT_QPA_EGLFS_DISABLE_INPUT=1
    export QT_QPA_FB_DISABLE_INPUT=1         # same for the linuxfb fallback
    export QT_QPA_GENERIC_PLUGINS="evdevtouch:${TOUCH}"
    export GAUGEWORKS_TOUCH="${TOUCH}"       # touch watchdog (restarts us if touch dies)
    export GAUGEWORKS_TOUCH_NAME="${TOUCH_NAME}"   # ...and follows it by name if it re-enumerates
else
    # No USB touch: let Qt find whatever input there is.
    unset QT_QPA_EGLFS_DISABLE_INPUT QT_QPA_FB_DISABLE_INPUT QT_QPA_GENERIC_PLUGINS GAUGEWORKS_TOUCH GAUGEWORKS_TOUCH_NAME
fi

start=$(date +%s)
QT_QPA_PLATFORM=eglfs "$GW" "$@"
rc=$?
# rc 3 = touch watchdog restart, not an EGLFS failure: let systemd restart us.
if [ $rc -ne 0 ] && [ $rc -ne 3 ] && [ $(( $(date +%s) - start )) -lt 15 ]; then
    echo "GaugeWorks: EGLFS failed (rc=$rc); falling back to linuxfb + software rendering"
    FB="$(grep -l . /sys/class/graphics/fb*/name 2>/dev/null | while read -r n; do
          d=$(dirname "$n"); grep -qv fb_ili9486 "$n" && echo "/dev/$(basename "$d")"; done | head -1)"
    QT_QPA_PLATFORM="linuxfb:fb=${FB:-/dev/fb1}" QT_QUICK_BACKEND=software exec "$GW" "$@"
fi
exit $rc
