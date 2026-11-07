// Layered round gauge: face image -> ticks/arcs -> numbers -> needle image -> hub/readout.
// States: "" (normal), warn, alarm (flashing glow), shift (full yellow face + SHIFT).
import QtQuick

Item {
    id: g
    property var theme
    property var cfg: ({})            // from backend.config.gauges.<name>
    property real value: 0
    property bool valid: false
    property bool shiftActive: false
    property string sub: ""           // small text under readout (e.g. gear)

    readonly property real minValue: cfg.min !== undefined ? cfg.min : 0
    readonly property real maxValue: cfg.max !== undefined ? cfg.max : 100
    readonly property real majorStep: cfg.major ? cfg.major : 10
    readonly property int minorTicks: cfg.minor ? cfg.minor : 5
    readonly property real warnAt: cfg.warn !== undefined ? cfg.warn : NaN
    readonly property real alarmAt: cfg.alarm !== undefined ? cfg.alarm : NaN
    readonly property real numScale: cfg.scale ? cfg.scale : 1
    readonly property int decimals: cfg.decimals !== undefined ? cfg.decimals : 0
    readonly property var colors: theme ? theme.colors : ({})

    readonly property real startAngle: -135
    readonly property real sweep: 270
    readonly property real size: Math.min(width, height)
    readonly property real cx: width / 2
    readonly property real cy: height / 2

    function frac(v) { return Math.max(0, Math.min(1, (v - minValue) / (maxValue - minValue))) }
    function angleFor(v) { return startAngle + sweep * frac(v) }
    function fmtNum(v) {
        var s = v * numScale
        return Math.abs(s - Math.round(s)) < 1e-6 ? Math.round(s).toString() : s.toFixed(1)
    }

    readonly property bool inAlarm: valid && !isNaN(alarmAt) && value >= alarmAt
    readonly property bool inWarn: valid && !isNaN(warnAt) && value >= warnAt && !inAlarm
    property bool flash: false
    Timer { running: g.inAlarm; interval: 400; repeat: true; onTriggered: g.flash = !g.flash }

    state: shiftActive ? "shift" : inAlarm ? "alarm" : inWarn ? "warn" : ""
    states: [
        State { name: "warn" },
        State { name: "alarm" },
        State { name: "shift"; PropertyChanges { target: shiftFace; opacity: 1 } }
    ]
    transitions: Transition { NumberAnimation { property: "opacity"; duration: 120 } }

    // 1. face
    Image {
        anchors.centerIn: parent
        width: g.size; height: g.size
        source: g.theme ? g.theme.face : ""
        sourceSize: Qt.size(width, height)
        smooth: true
    }
    Rectangle {  // alarm glow
        anchors.centerIn: parent
        width: g.size * 0.93; height: width; radius: width / 2
        color: g.colors.alarm || "red"
        opacity: g.inAlarm ? (g.flash ? 0.38 : 0.14) : 0
    }
    Rectangle {  // state ring
        anchors.centerIn: parent
        width: g.size * 0.955; height: width; radius: width / 2
        color: "transparent"
        border.width: Math.max(2, g.size * 0.018)
        border.color: g.inAlarm ? g.colors.alarm : g.inWarn ? g.colors.warn : (g.colors.ring || "#333")
    }

    // 2. ticks + warn/alarm arcs
    Canvas {
        id: ticks
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            if (!g.colors.tick || g.maxValue <= g.minValue) return
            var r = g.size * 0.43
            function rad(v) { return (g.angleFor(v) - 90) * Math.PI / 180 }
            function band(from, to, color) {
                if (isNaN(from)) return
                ctx.beginPath()
                ctx.lineWidth = g.size * 0.03
                ctx.strokeStyle = color
                ctx.arc(g.cx, g.cy, r - g.size * 0.015, rad(from), rad(to), false)
                ctx.stroke()
            }
            band(g.warnAt, isNaN(g.alarmAt) ? g.maxValue : g.alarmAt, g.colors.warn)
            band(g.alarmAt, g.maxValue, g.colors.alarm)
            var n = Math.round((g.maxValue - g.minValue) / g.majorStep)
            for (var i = 0; i <= n; i++) {
                for (var j = 0; j < g.minorTicks; j++) {
                    if (i === n && j > 0) break
                    var v = g.minValue + (i + j / g.minorTicks) * g.majorStep
                    var a = rad(v)
                    var major = j === 0
                    var len = g.size * (major ? 0.075 : 0.035)
                    ctx.beginPath()
                    ctx.lineWidth = major ? g.size * 0.012 : g.size * 0.005
                    ctx.strokeStyle = major ? g.colors.tick : g.colors.minorTick
                    ctx.moveTo(g.cx + Math.cos(a) * r, g.cy + Math.sin(a) * r)
                    ctx.lineTo(g.cx + Math.cos(a) * (r - len), g.cy + Math.sin(a) * (r - len))
                    ctx.stroke()
                }
            }
        }
        Connections {
            target: g
            function onCfgChanged() { ticks.requestPaint() }
            function onThemeChanged() { ticks.requestPaint() }
            function onWidthChanged() { ticks.requestPaint() }
            function onHeightChanged() { ticks.requestPaint() }
        }
    }

    // 3. numbers + labels
    Repeater {
        model: g.maxValue > g.minValue ? Math.round((g.maxValue - g.minValue) / g.majorStep) + 1 : 0
        Text {
            readonly property real v: g.minValue + index * g.majorStep
            readonly property real a: (g.angleFor(v) - 90) * Math.PI / 180
            readonly property real r: g.size * 0.335
            x: g.cx + Math.cos(a) * r - width / 2
            y: g.cy + Math.sin(a) * r - height / 2
            text: g.fmtNum(v)
            color: g.colors.text || "white"
            font.family: g.theme ? g.theme.fonts.label : ""
            font.pixelSize: g.size * 0.068
            font.bold: true
        }
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        y: g.cy - g.size * 0.17
        text: (g.cfg.label || "") + (g.cfg.scaleLabel ? " " + g.cfg.scaleLabel : "")
        color: g.colors.dim || "gray"
        font.family: g.theme ? g.theme.fonts.label : ""
        font.pixelSize: g.size * 0.052
    }

    // 4. needle (image, pivots at its bottom centre)
    Image {
        id: needle
        width: g.size * 0.05; height: g.size * 0.42
        x: g.cx - width / 2; y: g.cy - height
        source: g.theme ? g.theme.needle : ""
        sourceSize: Qt.size(width, height)
        smooth: true
        transformOrigin: Item.Bottom
        rotation: g.valid ? g.angleFor(g.value) : g.startAngle
        opacity: g.valid ? 1 : 0.35
        Behavior on rotation { SmoothedAnimation { velocity: 540 } }
    }
    Rectangle {
        anchors.centerIn: parent
        width: g.size * 0.11; height: width; radius: width / 2
        color: g.colors.hub || "#222"
        border.color: g.colors.ring || "#444"; border.width: 2
    }

    // 5. digital readout
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: g.cy + g.size * 0.12
        spacing: 0
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: g.valid ? g.value.toFixed(g.decimals) : "--"
            color: g.inAlarm ? g.colors.alarm : g.inWarn ? g.colors.warn : (g.colors.text || "white")
            font.family: g.theme ? g.theme.fonts.digits : ""
            font.pixelSize: g.size * 0.115
            font.bold: true
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: g.sub !== "" ? g.sub : (g.cfg.units || "")
            color: g.colors.dim || "gray"
            font.family: g.theme ? g.theme.fonts.label : ""
            font.pixelSize: g.size * 0.055
        }
    }

    // 6. SHIFT state: whole gauge goes yellow
    Rectangle {
        id: shiftFace
        anchors.centerIn: parent
        width: g.size * 0.96; height: width; radius: width / 2
        color: g.colors.shift || "yellow"
        opacity: 0
        visible: opacity > 0
        Text {
            anchors.centerIn: parent
            text: "SHIFT"
            color: g.colors.shiftText || "black"
            font.family: g.theme ? g.theme.fonts.label : ""
            font.pixelSize: g.size * 0.22
            font.bold: true
        }
    }
}
