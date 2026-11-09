// Premium theme: big round dial. Chrome bezel, face, ticks and numbers are
// painted once (Canvas); only the light trail and needle move. 240° sweep
// opening at the bottom, where a sub-dial can sit. Key-on needle sweep.
import QtQuick
import QtQuick.Shapes

Item {
    id: d
    property var theme
    property var cfg: ({})
    property real value: 0
    property bool valid: false
    property bool shiftActive: false
    property string hubLabel: ""     // small text above the big hub text
    property string hubText: ""      // big hub text (gear or speed)
    property string hubSub: ""       // small text under it
    property bool hubDim: false
    signal held()

    readonly property var colors: theme ? theme.colors : ({})
    readonly property real minV: cfg.min !== undefined ? cfg.min : 0
    readonly property real maxV: cfg.max !== undefined && cfg.max > minV ? cfg.max : minV + 100
    readonly property real major: cfg.major ? cfg.major : 10
    readonly property int minorN: cfg.minor ? cfg.minor : 5
    readonly property real redAt: (cfg.alarm !== undefined && !isNaN(cfg.alarm)) ? cfg.alarm
                                : (cfg.warn !== undefined && !isNaN(cfg.warn)) ? cfg.warn : NaN
    readonly property real a0: 150
    readonly property real sw: 240
    readonly property real rr: Math.min(width, height) / 2 - 20       // face radius
    readonly property real k: rr / 176                                 // designed at R=176
    readonly property real cx: width / 2
    readonly property real cy: height / 2
    readonly property real hubR: 78 * k

    function frac(v) { return Math.max(0, Math.min(1, (v - minV) / (maxV - minV))) }
    function num(v) {
        var s = v * (cfg.scale ? cfg.scale : 1)
        return Math.abs(s - Math.round(s)) < 1e-6 ? Math.round(s).toString() : s.toFixed(1)
    }

    property real shown: valid ? Math.max(minV, Math.min(maxV, value)) : minV
    Behavior on shown { SmoothedAnimation { velocity: Math.max(1, (d.maxV - d.minV) * 1.5) } }
    property real sweepF: -1                       // key-on sweep position, -1 when done
    readonly property real f: sweepF >= 0 ? sweepF : frac(shown)
    readonly property real ang: a0 + sw * f
    readonly property bool inRed: valid && !isNaN(redAt) && value >= redAt
    property bool flash: false
    Timer { running: d.inRed || d.shiftActive; interval: 350; repeat: true; onTriggered: d.flash = !d.flash
            onRunningChanged: if (!running) d.flash = false }

    SequentialAnimation {
        running: true
        PauseAnimation { duration: typeof splashMs === "number" ? splashMs : 0 }
        NumberAnimation { target: d; property: "sweepF"; from: 0; to: 1; duration: 650; easing.type: Easing.InOutQuad }
        NumberAnimation { target: d; property: "sweepF"; from: 1; to: d.frac(d.shown); duration: 650; easing.type: Easing.InOutQuad }
        ScriptAction { script: d.sweepF = -1 }
    }

    // ---- static art: bezel, face, track, red zone, ticks, numbers
    Canvas {
        id: art
        anchors.fill: parent
        property var deps: [d.cfg, d.width, d.height, d.colors]
        onDepsChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var cx = d.cx, cy = d.cy, R = d.rr, k = d.k
            function rad(a) { return a * Math.PI / 180 }
            function angOf(v) { return d.a0 + d.sw * d.frac(v) }
            function ring(r0, r1, style) {
                c.beginPath(); c.arc(cx, cy, r1, 0, 2 * Math.PI, false); c.arc(cx, cy, r0, 2 * Math.PI, 0, true)
                c.fillStyle = style; c.fill()
            }
            // drop shadow and chrome bezel
            c.beginPath(); c.arc(cx, cy, R + 20, 0, 2 * Math.PI); c.fillStyle = "#000000"; c.fill()
            var g = c.createConicalGradient(cx, cy, rad(80))
            var st = ["#f4f6f9", "#6a737f", "#d3d8df", "#262b33", "#8c95a1", "#f0f3f7", "#353c46", "#b5bcc6", "#1d2229", "#f4f6f9"]
            var pos = [0, .10, .20, .33, .45, .53, .65, .77, .89, 1]
            for (var i = 0; i < st.length; i++) g.addColorStop(pos[i], st[i])
            ring(R + 6, R + 19, g)
            var sh = c.createLinearGradient(0, cy - R - 19, 0, cy + R + 19)
            sh.addColorStop(0, "rgba(255,255,255,0.22)"); sh.addColorStop(0.45, "rgba(0,0,0,0)"); sh.addColorStop(1, "rgba(0,0,0,0.5)")
            ring(R + 6, R + 19, sh)
            // face
            var fg = c.createRadialGradient(cx, cy - R * 0.2, 0, cx, cy, R + 6)
            fg.addColorStop(0, "#0e1826"); fg.addColorStop(0.75, "#070b12"); fg.addColorStop(1, "#03050a")
            c.beginPath(); c.arc(cx, cy, R + 6, 0, 2 * Math.PI); c.fillStyle = fg; c.fill()
            c.lineWidth = 6; c.strokeStyle = "rgba(0,0,0,0.7)"
            c.beginPath(); c.arc(cx, cy, R + 3, 0, 2 * Math.PI); c.stroke()
            c.lineWidth = 2; c.strokeStyle = "rgba(127,184,255,0.22)"
            c.beginPath(); c.arc(cx, cy, R + 1, rad(205), rad(335)); c.stroke()
            // track and red zone
            c.lineCap = "butt"
            c.lineWidth = 9 * k; c.strokeStyle = "#111a26"
            c.beginPath(); c.arc(cx, cy, R - 12 * k, rad(d.a0), rad(d.a0 + d.sw)); c.stroke()
            if (!isNaN(d.redAt) && d.redAt < d.maxV) {
                c.lineWidth = 18 * k; c.strokeStyle = "rgba(255,42,42,0.18)"
                c.beginPath(); c.arc(cx, cy, R - 12 * k, rad(angOf(d.redAt)), rad(d.a0 + d.sw)); c.stroke()
                c.lineWidth = 9 * k; c.strokeStyle = "#c4171c"
                c.beginPath(); c.arc(cx, cy, R - 12 * k, rad(angOf(d.redAt)), rad(d.a0 + d.sw)); c.stroke()
            }
            // ticks and numbers
            var n = Math.round((d.maxV - d.minV) / d.major * d.minorN)
            c.font = Math.round(29 * k) + "px 'Barlow Medium'"
            c.textAlign = "center"; c.textBaseline = "middle"; c.lineCap = "round"
            for (var j = 0; j <= n; j++) {
                var v = d.minV + j * d.major / d.minorN
                var isMaj = j % d.minorN === 0
                var isMid = !isMaj && d.minorN % 2 === 0 && j % (d.minorN / 2) === 0
                var red = !isNaN(d.redAt) && v >= d.redAt - 1e-9
                var a = rad(angOf(v)), r0 = R - 22 * k, r1 = R - (isMaj ? 40 : isMid ? 34 : 28) * k
                c.strokeStyle = red ? (isMaj ? "#ff4040" : "#b02024") : (isMaj ? "#eef3f9" : isMid ? "#aab6c6" : "#56637a")
                c.lineWidth = (isMaj ? 3 : isMid ? 2 : 1.2) * k
                c.beginPath(); c.moveTo(cx + r0 * Math.cos(a), cy + r0 * Math.sin(a))
                c.lineTo(cx + r1 * Math.cos(a), cy + r1 * Math.sin(a)); c.stroke()
                if (isMaj) {
                    c.fillStyle = red ? "#ff5050" : "#e6ecf4"
                    c.fillText(d.num(v), cx + (R - 62 * k) * Math.cos(a), cy + (R - 62 * k) * Math.sin(a))
                }
            }
            // scale label
            c.font = Math.round(11 * k) + "px 'Barlow Semi Condensed SemiBold'"
            c.fillStyle = "#7d8ba0"
            var lab = ((d.cfg.label || "") + (d.cfg.scaleLabel ? "  " + d.cfg.scaleLabel.replace("x", "×") : "")).toUpperCase()
            c.fillText(lab.split("").join(String.fromCharCode(8202)), cx, cy - 112 * k)
        }
    }

    // ---- light trail: annular sector, bright at the needle, fading back to zero
    Shape {
        anchors.fill: parent
        visible: d.f > 0.003
        ShapePath {   // soft halo
            strokeColor: "transparent"
            fillGradient: ConicalGradient {
                centerX: d.cx; centerY: d.cy; angle: -d.ang
                GradientStop { position: 0; color: Qt.rgba(0.45, 0.75, 1, 0.35) }
                GradientStop { position: Math.max(0.002, d.sw * d.f / 360); color: Qt.rgba(0.1, 0.35, 0.9, 0) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathAngleArc { centerX: d.cx; centerY: d.cy; radiusX: d.rr - 2 * d.k; radiusY: radiusX
                           startAngle: d.a0; sweepAngle: d.sw * d.f }
            PathAngleArc { moveToStart: false; centerX: d.cx; centerY: d.cy; radiusX: d.rr - 22 * d.k; radiusY: radiusX
                           startAngle: d.a0 + d.sw * d.f; sweepAngle: -d.sw * d.f }
        }
        ShapePath {   // trail
            strokeColor: "transparent"
            fillGradient: ConicalGradient {
                centerX: d.cx; centerY: d.cy; angle: -d.ang
                GradientStop { position: 0; color: d.inRed && d.flash ? "#ff8080" : "#c8e8ff" }
                GradientStop { position: 0.015; color: d.inRed ? "#ff3b3b" : "#5fb4ff" }
                GradientStop { position: Math.max(0.016, d.sw * d.f / 360); color: Qt.rgba(0.12, 0.3, 0.75, 0.12) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathAngleArc { centerX: d.cx; centerY: d.cy; radiusX: d.rr - 7.5 * d.k; radiusY: radiusX
                           startAngle: d.a0; sweepAngle: d.sw * d.f }
            PathAngleArc { moveToStart: false; centerX: d.cx; centerY: d.cy; radiusX: d.rr - 16.5 * d.k; radiusY: radiusX
                           startAngle: d.a0 + d.sw * d.f; sweepAngle: -d.sw * d.f }
        }
    }

    // ---- needle (pivot at dial centre, starts outside the hub)
    Item {
        id: ndl
        x: d.cx; y: d.cy
        rotation: d.ang
        readonly property real nb: d.hubR + 6 * d.k
        readonly property real nt: d.rr - 16 * d.k
        Shape {
            ShapePath {   // glow
                strokeColor: "transparent"; fillColor: Qt.rgba(1, 0.3, 0.08, 0.28)
                startX: ndl.nb; startY: -8 * d.k
                PathLine { x: ndl.nt + 2; y: -3.5 * d.k }
                PathLine { x: ndl.nt + 9 * d.k; y: 0 }
                PathLine { x: ndl.nt + 2; y: 3.5 * d.k }
                PathLine { x: ndl.nb; y: 8 * d.k }
            }
        }
        Shape {
            ShapePath {
                strokeColor: "transparent"
                fillGradient: LinearGradient {
                    x1: ndl.nb; y1: 0; x2: ndl.nt; y2: 0
                    GradientStop { position: 0; color: Qt.rgba(1, 0.24, 0.07, 0.25) }
                    GradientStop { position: 0.55; color: d.colors.needle || "#ff5a1f" }
                    GradientStop { position: 1; color: "#ffd2b0" }
                }
                startX: ndl.nb; startY: -4.5 * d.k
                PathLine { x: ndl.nt; y: -1.2 * d.k }
                PathLine { x: ndl.nt + 4 * d.k; y: 0 }
                PathLine { x: ndl.nt; y: 1.2 * d.k }
                PathLine { x: ndl.nb; y: 4.5 * d.k }
            }
        }
        Rectangle { x: parent.nb + 30 * d.k; y: -0.4; width: parent.nt - parent.nb - 30 * d.k; height: 0.8
                    color: Qt.rgba(1, 1, 1, 0.7) }
    }

    // ---- hub (over the needle base)
    Canvas {
        anchors.fill: parent
        property var deps: [d.width, d.height]
        onDepsChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var cx = d.cx, cy = d.cy, r = d.hubR
            c.beginPath(); c.arc(cx, cy, r + 9, 0, 2 * Math.PI); c.fillStyle = "rgba(0,0,0,0.6)"; c.fill()
            var g = c.createConicalGradient(cx, cy, Math.PI * 0.4)
            var st = ["#f4f6f9", "#5d6672", "#c9ced6", "#2a3038", "#9aa2ad", "#eef1f5", "#3a414b", "#b8bfc9", "#20252c", "#f4f6f9"]
            for (var i = 0; i < st.length; i++) g.addColorStop(i / (st.length - 1), st[i])
            c.beginPath(); c.arc(cx, cy, r + 6, 0, 2 * Math.PI, false); c.arc(cx, cy, r - 0.5, 2 * Math.PI, 0, true)
            c.fillStyle = g; c.fill()
            var hg = c.createRadialGradient(cx, cy - r * 0.35, 0, cx, cy, r)
            hg.addColorStop(0, "#162233"); hg.addColorStop(1, "#05080d")
            c.beginPath(); c.arc(cx, cy, r, 0, 2 * Math.PI); c.fillStyle = hg; c.fill()
        }
    }
    Rectangle {   // inner accent ring: blue, flashes red in the red zone, yellow to shift
        anchors.centerIn: parent
        width: 2 * (d.hubR - 6 * d.k); height: width; radius: width / 2
        color: "transparent"; border.width: d.inRed || d.shiftActive ? 2 : 1
        border.color: d.shiftActive ? (d.flash ? d.colors.shift : "#5a4a00")
                    : d.inRed ? (d.flash ? d.colors.alarm : "#5a1010") : Qt.rgba(0.29, 0.66, 1, 0.25)
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter; y: d.cy - 36 * d.k
        text: d.shiftActive ? "SHIFT" : d.hubLabel
        color: d.shiftActive ? d.colors.shift : d.colors.dim
        font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: Math.round((d.shiftActive ? 16 : 11) * d.k)
        font.letterSpacing: 2
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter; anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: 6 * d.k
        text: d.hubText
        color: d.hubDim ? d.colors.dim : d.colors.text
        font.family: "Barlow Medium"; font.pixelSize: Math.round((d.hubText.length > 2 ? 64 : 76) * d.k)
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter; y: d.cy + 44 * d.k
        text: d.hubSub
        color: "#9aa7b9"
        font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: Math.round(14 * d.k); font.letterSpacing: 1
    }
    MouseArea {
        anchors.fill: parent
        pressAndHoldInterval: 600
        onPressAndHold: d.held()
        onClicked: if (backend.editMode) d.held()
    }
}
