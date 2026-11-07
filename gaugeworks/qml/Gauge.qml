// Round gauge with two styles, chosen by the theme (theme.style.gauge):
//   "needle": face image -> ticks/arcs -> numbers -> needle image -> hub/readout
//   "arc":    face -> track arc -> glowing value arc (GPU Shapes) -> big digital readout
// States: "" (normal), warn, alarm (flashing glow), shift (full yellow face + SHIFT).
// `fx` adds a theme effect in the hub ("turbo" snail, "flame") driven by the value.
import QtQuick
import QtQuick.Shapes

Item {
    id: g
    property var theme
    property var cfg: ({})
    property real value: 0
    property bool valid: false
    property bool shiftActive: false
    property string sub: ""           // small text under readout
    property string bigText: ""       // big text (gear)
    property bool bigDim: false       // e.g. no gear right now
    property string fx: ""            // theme effect: "turbo", "flame" or ""

    readonly property var tstyle: theme && theme.style ? theme.style : ({})
    readonly property string gstyle: tstyle.gauge || "needle"
    readonly property real minValue: cfg.min !== undefined ? cfg.min : 0
    readonly property real maxValue: cfg.max !== undefined ? cfg.max : 100
    readonly property real majorStep: cfg.major ? cfg.major : 10
    readonly property int minorTicks: cfg.minor ? cfg.minor : 5
    readonly property real warnAt: cfg.warn !== undefined ? cfg.warn : NaN
    readonly property real alarmAt: cfg.alarm !== undefined ? cfg.alarm : NaN
    readonly property real numScale: cfg.scale ? cfg.scale : 1
    readonly property int decimals: cfg.decimals !== undefined ? cfg.decimals : 0
    readonly property var colors: theme ? theme.colors : ({})
    readonly property string labelText: (cfg.label || "") + (cfg.scaleLabel ? " " + cfg.scaleLabel : "")

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
    readonly property color stateColor: inAlarm ? colors.alarm : inWarn ? colors.warn : colors.accent
    property bool flash: false
    Timer { running: g.inAlarm; interval: 400; repeat: true; onTriggered: g.flash = !g.flash }

    // animated value shared by both styles (smooth needle / arc)
    property real shown: valid ? Math.max(minValue, Math.min(maxValue, value)) : minValue
    Behavior on shown { SmoothedAnimation { velocity: Math.max(1, (g.maxValue - g.minValue) * 2) } }

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

    // ===== needle style =====================================================
    Canvas {
        id: ticks
        visible: g.gstyle === "needle"
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
    Repeater {
        model: g.gstyle === "needle" && g.maxValue > g.minValue ? Math.round((g.maxValue - g.minValue) / g.majorStep) + 1 : 0
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

    // ===== arc style ========================================================
    Shape {
        id: arcs
        visible: g.gstyle === "arc"
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        readonly property real r: g.size * 0.40
        readonly property real w: g.size * 0.075
        ShapePath {  // track
            strokeColor: g.colors.ring || "#333"; strokeWidth: arcs.w; fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: g.cx; centerY: g.cy; radiusX: arcs.r; radiusY: arcs.r
                           startAngle: 135; sweepAngle: g.sweep }
        }
        ShapePath {  // warn band (thin, outside the track)
            strokeColor: isNaN(g.warnAt) ? "transparent" : g.colors.warn; strokeWidth: g.size * 0.012
            fillColor: "transparent"
            PathAngleArc { centerX: g.cx; centerY: g.cy; radiusX: arcs.r + arcs.w * 0.75; radiusY: radiusX
                           startAngle: 135 + g.sweep * g.frac(g.warnAt)
                           sweepAngle: isNaN(g.warnAt) ? 0 : g.sweep * (g.frac(isNaN(g.alarmAt) ? g.maxValue : g.alarmAt) - g.frac(g.warnAt)) }
        }
        ShapePath {  // alarm band
            strokeColor: isNaN(g.alarmAt) ? "transparent" : g.colors.alarm; strokeWidth: g.size * 0.012
            fillColor: "transparent"
            PathAngleArc { centerX: g.cx; centerY: g.cy; radiusX: arcs.r + arcs.w * 0.75; radiusY: radiusX
                           startAngle: 135 + g.sweep * g.frac(g.alarmAt)
                           sweepAngle: isNaN(g.alarmAt) ? 0 : g.sweep * (1 - g.frac(g.alarmAt)) }
        }
        ShapePath {  // glow under the value arc
            strokeColor: g.tstyle.glow ? Qt.rgba(g.stateColor.r, g.stateColor.g, g.stateColor.b, 0.28) : "transparent"
            strokeWidth: arcs.w * 1.9; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: g.cx; centerY: g.cy; radiusX: arcs.r; radiusY: arcs.r
                           startAngle: 135; sweepAngle: Math.max(0.5, g.sweep * g.frac(g.shown)) }
        }
        ShapePath {  // value
            strokeColor: g.valid ? g.stateColor : "transparent"; strokeWidth: arcs.w; fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: g.cx; centerY: g.cy; radiusX: arcs.r; radiusY: arcs.r
                           startAngle: 135; sweepAngle: Math.max(0.5, g.sweep * g.frac(g.shown)) }
        }
    }
    Text {  // arc: min / max at the ends
        visible: g.gstyle === "arc"
        x: g.cx - g.size * 0.30 - width / 2; y: g.cy + g.size * 0.33
        text: g.fmtNum(g.minValue); color: g.colors.dim || "gray"; font.pixelSize: g.size * 0.05
    }
    Text {
        visible: g.gstyle === "arc"
        x: g.cx + g.size * 0.30 - width / 2; y: g.cy + g.size * 0.33
        text: g.fmtNum(g.maxValue); color: g.colors.dim || "gray"; font.pixelSize: g.size * 0.05
    }

    // ===== shared text ======================================================
    Text {  // big gear numeral
        visible: g.bigText !== ""
        anchors.horizontalCenter: parent.horizontalCenter
        y: g.gstyle === "arc" ? g.cy - g.size * 0.36 : g.cy - g.size * 0.05 - height
        text: g.bigText
        color: g.bigDim ? (g.colors.minorTick || "gray") : (g.colors.text || "white")
        font.family: g.theme ? g.theme.fonts.digits : ""
        font.pixelSize: g.size * (g.gstyle === "arc" ? 0.15 : 0.27)
        font.bold: true
    }
    Text {  // label
        visible: g.bigText === "" || g.gstyle === "arc"
        anchors.horizontalCenter: parent.horizontalCenter
        y: g.gstyle === "arc" ? g.cy + g.size * 0.22 : g.cy - g.size * 0.17
        text: g.labelText
        color: g.colors.dim || "gray"
        font.family: g.theme ? g.theme.fonts.label : ""
        font.pixelSize: g.size * 0.052
    }

    // needle + hub (drawn above labels)
    Image {
        id: needle
        visible: g.gstyle === "needle"
        width: g.size * 0.05; height: g.size * 0.42
        x: g.cx - width / 2; y: g.cy - height
        source: g.theme ? g.theme.needle : ""
        sourceSize: Qt.size(width, height)
        smooth: true
        transformOrigin: Item.Bottom
        rotation: g.angleFor(g.shown)
        opacity: g.valid ? 1 : 0.35
    }
    Rectangle {
        visible: g.gstyle === "needle" && g.fx === ""
        anchors.centerIn: parent
        width: g.size * 0.11; height: width; radius: width / 2
        color: g.colors.hub || "#222"
        border.color: g.colors.ring || "#444"; border.width: 2
    }

    // theme effects in the hub
    Image {  // turbo snail: shell spins faster with boost
        id: snail
        visible: g.fx === "turbo" && !!(g.theme && g.theme.assets && g.theme.assets.snail)
        anchors.centerIn: parent
        width: g.size * 0.24; height: width
        source: visible ? g.theme.assets.snail : ""
        sourceSize: Qt.size(width, height)
        RotationAnimator on rotation {
            from: 0; to: 360; loops: Animation.Infinite
            running: snail.visible && g.valid && g.frac(g.value) > 0.02
            duration: Math.max(140, 2400 * (1 - g.frac(g.value)))
        }
    }
    Image {  // rev flame: grows with rpm, flickers near redline
        id: flame
        visible: g.fx === "flame" && !!(g.theme && g.theme.assets && g.theme.assets.flame)
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.verticalCenter; anchors.bottomMargin: -g.size * 0.05
        width: g.size * 0.2; height: g.size * (0.08 + 0.22 * g.frac(g.shown))
        source: visible ? g.theme.assets.flame : ""
        sourceSize: Qt.size(width * 2, width * 3)
        opacity: g.valid ? (g.inWarn || g.inAlarm ? (g.flash ? 1 : 0.7) : 0.85) : 0.2
    }

    // digital readout
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: g.gstyle === "arc" ? g.cy - height / 2 + g.size * 0.02 : g.cy + g.size * 0.12
        spacing: 0
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: g.valid ? g.value.toFixed(g.decimals) : "--"
            color: g.inAlarm ? g.colors.alarm : g.inWarn ? g.colors.warn : (g.colors.text || "white")
            font.family: g.theme ? g.theme.fonts.digits : ""
            font.pixelSize: g.size * (g.gstyle === "arc" ? 0.21 : 0.115)
            font.bold: true
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: text !== ""
            text: g.sub !== "" ? g.sub
                  : g.gstyle === "arc" ? (g.cfg.units || "")
                  : g.bigText !== "" ? g.labelText
                  : (g.cfg.units || "")
            color: g.colors.dim || "gray"
            font.family: g.theme ? g.theme.fonts.label : ""
            font.pixelSize: g.size * 0.055
        }
    }

    // SHIFT state: whole gauge goes yellow
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
