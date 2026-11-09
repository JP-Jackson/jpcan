// One configurable slot: round gauge, dual bar (VGT) or a "choose" placeholder.
// Press and hold to pick what it shows (hold, not tap, so bumps don't trigger it).
import QtQuick

Item {
    id: sv
    property var theme
    property var cfg: ({})
    property string slotName: ""
    property string gearKey: ""
    signal pick(string slot, string current)

    function val(k) { var v = backend.values[k]; return v === undefined ? 0 : v }
    function ok(k) { return k !== undefined && k !== "" && backend.fresh[k] === true }

    readonly property bool isRpm: cfg.key === "rpm"
    readonly property bool hasGear: isRpm && gearKey !== ""

    Gauge {
        anchors.fill: parent
        visible: !sv.cfg.dual && !sv.cfg.missing && sv.cfg.key !== undefined
        theme: sv.theme; cfg: sv.cfg
        value: sv.val(sv.cfg.key); valid: sv.ok(sv.cfg.key)
        shiftActive: sv.isRpm && backend.shift.enabled && valid && value >= backend.shift.rpm
        bigText: sv.hasGear ? (sv.ok(sv.gearKey) ? sv.val(sv.gearKey).toFixed(0) : "–") : ""
        bigDim: sv.hasGear && !sv.ok(sv.gearKey)
        fx: !(sv.theme && sv.theme.style && sv.theme.style.fx) ? ""
            : (["boost", "map", "map_wide"].indexOf(sv.cfg.key) >= 0 ? "turbo" : sv.cfg.key === "rpm" ? "flame" : "")
    }
    DualBar {
        anchors.fill: parent
        visible: sv.cfg.dual === true
        theme: sv.theme; label: sv.cfg.label || ""
        desired: sv.val(sv.cfg.desired); desiredValid: sv.ok(sv.cfg.desired)
        actual: sv.val(sv.cfg.actual); actualValid: sv.ok(sv.cfg.actual)
    }
    Rectangle {
        anchors.fill: parent
        visible: sv.cfg.missing === true
        radius: 10; color: sv.theme.colors.panel; border.color: sv.theme.colors.panelBorder
        Text { anchors.centerIn: parent; text: "Hold to choose"; color: sv.theme.colors.dim; font.pixelSize: 18 }
    }
    MouseArea {
        anchors.fill: parent
        pressAndHoldInterval: 600
        onPressAndHold: sv.pick(sv.slotName, sv.cfg.key || "")
        onClicked: if (backend.editMode) sv.pick(sv.slotName, sv.cfg.key || "")
    }
}
