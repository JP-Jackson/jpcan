// Premium theme: one row of the centre card. Label, value, thin bar with a red
// zone. Dual entries (VGT) show actual with a white marker at desired + diff.
import QtQuick

Item {
    id: b
    property var theme
    property var cfg: ({})
    signal held()
    readonly property var colors: theme ? theme.colors : ({})
    readonly property bool dual: cfg.dual === true
    function v(k) { var x = backend.values[k]; return x === undefined ? 0 : x }
    function ok(k) { return k !== undefined && k !== "" && backend.fresh[k] === true }
    readonly property bool valid: dual ? ok(cfg.actual) : ok(cfg.key)
    readonly property real value: dual ? v(cfg.actual) : v(cfg.key)
    readonly property real minV: dual ? 0 : (cfg.min !== undefined ? cfg.min : 0)
    readonly property real maxV: dual ? 100 : (cfg.max !== undefined && cfg.max > minV ? cfg.max : minV + 100)
    readonly property real redAt: dual ? NaN : (cfg.warn !== undefined && !isNaN(cfg.warn)) ? cfg.warn
                                : (cfg.alarm !== undefined && !isNaN(cfg.alarm)) ? cfg.alarm : NaN
    function frac(x) { return Math.max(0, Math.min(1, (x - minV) / (maxV - minV))) }
    readonly property bool bad: valid && !isNaN(redAt) && value >= redAt
    readonly property real diff: dual && ok(cfg.desired) ? value - v(cfg.desired) : NaN
    height: 30

    Text {
        y: 0; text: ((b.cfg.label || b.cfg.key || "") + (b.cfg.verified === false ? "?" : "")).toUpperCase()
        color: b.colors.dim; font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 11; font.letterSpacing: 1.5
    }
    Row {
        anchors.right: parent.right; y: -5; spacing: 4
        Text {
            visible: !isNaN(b.diff); anchors.baseline: val.baseline
            text: "Δ" + (b.diff >= 0 ? "+" : "") + b.diff.toFixed(0)
            color: Math.abs(b.diff) >= 10 ? b.colors.warn : b.colors.dim
            font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 12
        }
        Text {
            id: val
            text: !b.valid ? "--" : b.value.toFixed(b.dual ? 0 : (b.cfg.decimals || 0))
            color: b.bad ? b.colors.alarm : b.colors.text
            font.family: "Barlow Medium"; font.pixelSize: 17
        }
        Text {
            anchors.baseline: val.baseline
            text: b.dual ? "%" : (b.cfg.units || ""); color: b.colors.dim
            font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 11
        }
    }
    Rectangle { id: track; y: 18; width: parent.width; height: 4; radius: 2; color: "#152131" }
    Rectangle {
        visible: !isNaN(b.redAt); y: 18; height: 4; radius: 2; color: "#4a1518"
        x: track.width * b.frac(b.redAt); width: track.width - x
    }
    Rectangle {
        y: 18; height: 4; radius: 2; color: b.bad ? b.colors.alarm : b.colors.accent
        width: b.valid ? track.width * b.frac(b.value) : 0
        Behavior on width { SmoothedAnimation { velocity: 300 } }
    }
    Rectangle {
        visible: b.valid; y: 16; width: 8; height: 8; radius: 4; color: "#dff0ff"
        x: track.width * b.frac(b.value) - 4
        Behavior on x { SmoothedAnimation { velocity: 300 } }
    }
    Rectangle {   // desired marker (dual)
        visible: b.dual && b.ok(b.cfg.desired); y: 14; width: 2; height: 12; color: "#ffffff"
        x: track.width * b.frac(b.v(b.cfg.desired)) - 1
    }
    MouseArea { anchors.fill: parent; anchors.margins: -4; pressAndHoldInterval: 600; onPressAndHold: b.held() }
}
