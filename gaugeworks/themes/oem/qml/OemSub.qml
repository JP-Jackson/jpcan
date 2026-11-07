// Premium theme: small chrome sub-dial nested in a big dial (coolant, fuel...).
import QtQuick
import QtQuick.Shapes

Item {
    id: s
    property var theme
    property var cfg: ({})
    property real value: 0
    property bool valid: false
    signal held()

    readonly property var colors: theme ? theme.colors : ({})
    readonly property real minV: cfg.min !== undefined ? cfg.min : 0
    readonly property real maxV: cfg.max !== undefined && cfg.max > minV ? cfg.max : minV + 100
    readonly property bool isFuel: cfg.key === "fuel_level"
    readonly property bool isTemp: (cfg.units || "").indexOf("°") === 0
    readonly property real redAt: (cfg.alarm !== undefined && !isNaN(cfg.alarm)) ? cfg.alarm
                                : (cfg.warn !== undefined && !isNaN(cfg.warn)) ? cfg.warn : NaN
    readonly property real a0: 140
    readonly property real sw: 260
    readonly property real r: Math.min(width, height) / 2 - 6
    readonly property real k: r / 42
    readonly property real cx: width / 2
    readonly property real cy: height / 2
    function frac(v) { return Math.max(0, Math.min(1, (v - minV) / (maxV - minV))) }
    property real shown: valid ? value : minV
    Behavior on shown { SmoothedAnimation { velocity: Math.max(1, (s.maxV - s.minV)) } }
    readonly property real ang: a0 + sw * frac(shown)
    readonly property bool bad: valid && (isFuel ? value <= minV + 0.12 * (maxV - minV) : (!isNaN(redAt) && value >= redAt))

    Canvas {
        anchors.fill: parent
        property var deps: [s.cfg, s.width, s.height]
        onDepsChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var cx = s.cx, cy = s.cy, r = s.r, k = s.k
            function rad(a) { return a * Math.PI / 180 }
            c.beginPath(); c.arc(cx, cy, r + 6, 0, 2 * Math.PI); c.fillStyle = "rgba(0,0,0,0.8)"; c.fill()
            var g = c.createConicalGradient(cx, cy, Math.PI * 0.45)
            var st = ["#f4f6f9", "#5d6672", "#c9ced6", "#2a3038", "#9aa2ad", "#eef1f5", "#3a414b", "#b8bfc9", "#20252c", "#f4f6f9"]
            for (var i = 0; i < st.length; i++) g.addColorStop(i / (st.length - 1), st[i])
            c.beginPath(); c.arc(cx, cy, r + 6, 0, 2 * Math.PI, false); c.arc(cx, cy, r - 0.5, 2 * Math.PI, 0, true)
            c.fillStyle = g; c.fill()
            var fg = c.createRadialGradient(cx, cy - r * 0.3, 0, cx, cy, r)
            fg.addColorStop(0, "#0e1826"); fg.addColorStop(1, "#03050a")
            c.beginPath(); c.arc(cx, cy, r, 0, 2 * Math.PI); c.fillStyle = fg; c.fill()
            c.lineWidth = 3 * k; c.lineCap = "butt"
            c.strokeStyle = "#1a2635"; c.beginPath(); c.arc(cx, cy, r - 6 * k, rad(s.a0), rad(s.a0 + s.sw)); c.stroke()
            c.strokeStyle = "#d01e22"; c.beginPath()
            if (s.isFuel) c.arc(cx, cy, r - 6 * k, rad(s.a0), rad(s.a0 + s.sw * 0.12))
            else if (!isNaN(s.redAt)) c.arc(cx, cy, r - 6 * k, rad(s.a0 + s.sw * s.frac(s.redAt)), rad(s.a0 + s.sw))
            c.stroke()
            for (var j = 0; j <= 8; j++) {
                var a = rad(s.a0 + s.sw * j / 8), big = j % 4 === 0
                c.strokeStyle = big ? "#dfe6ef" : "#6b788c"; c.lineWidth = (big ? 1.6 : 1) * k
                c.beginPath(); c.moveTo(cx + (r - 10 * k) * Math.cos(a), cy + (r - 10 * k) * Math.sin(a))
                c.lineTo(cx + (r - (big ? 16 : 13) * k) * Math.cos(a), cy + (r - (big ? 16 : 13) * k) * Math.sin(a)); c.stroke()
            }
            var lo = s.isFuel ? "E" : s.isTemp ? "C" : Math.round(s.minV).toString()
            var hi = s.isFuel ? "F" : s.isTemp ? "H" : Math.round(s.maxV).toString()
            c.font = Math.round(9 * k) + "px 'Barlow Semi Condensed SemiBold'"; c.fillStyle = "#9aa7b9"
            c.textAlign = "center"; c.textBaseline = "middle"
            var la = rad(s.a0 + 4), ha = rad(s.a0 + s.sw - 4)
            c.fillText(lo, cx + (r - 22 * k) * Math.cos(la), cy + (r - 22 * k) * Math.sin(la))
            c.fillText(hi, cx + (r - 22 * k) * Math.cos(ha), cy + (r - 22 * k) * Math.sin(ha))
        }
    }
    Shape {   // value arc
        anchors.fill: parent
        visible: s.valid
        ShapePath {
            strokeColor: s.bad ? s.colors.alarm : s.colors.accent; strokeWidth: 3 * s.k
            fillColor: "transparent"; capStyle: ShapePath.FlatCap
            PathAngleArc { centerX: s.cx; centerY: s.cy; radiusX: s.r - 6 * s.k; radiusY: radiusX
                           startAngle: s.a0; sweepAngle: s.ang - s.a0 }
        }
    }
    Item {   // needle
        id: sn
        x: s.cx; y: s.cy; rotation: s.ang
        visible: s.valid
        Shape {
            ShapePath {
                strokeColor: "transparent"; fillColor: s.colors.needle || "#ff5a1f"
                startX: 4 * s.k; startY: -1.6 * s.k
                PathLine { x: (s.r - 12 * s.k); y: -0.6 * s.k }
                PathLine { x: (s.r - 10 * s.k); y: 0 }
                PathLine { x: (s.r - 12 * s.k); y: 0.6 * s.k }
                PathLine { x: 4 * s.k; y: 1.6 * s.k }
            }
        }
    }
    Rectangle { x: s.cx - width / 2; y: s.cy - height / 2; width: 6 * s.k; height: width; radius: width / 2
                color: "#1b2330"; border.color: "#8c96a3" }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter; y: s.cy + 12 * s.k
        text: !s.valid ? "--" : s.value.toFixed(0) + (s.isFuel ? "%" : (s.cfg.units || ""))
        color: s.bad ? s.colors.alarm : s.colors.text
        font.family: "Barlow SemiBold"; font.pixelSize: Math.round(13 * s.k)
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter; y: s.cy + 27 * s.k
        text: (s.cfg.label || "") + (s.cfg.verified === false ? "?" : "")
        color: s.colors.dim
        font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: Math.round(8 * s.k); font.letterSpacing: 1.5
    }
    MouseArea { anchors.fill: parent; pressAndHoldInterval: 600; onPressAndHold: s.held() }
}
