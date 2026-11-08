// Towing page center gauge: chrome bezel and sunken face; outer scale (RPM)
// and inner scale (boost), each with a light trail, a slim rounded pointer and
// a red-line marker; big speed in the middle; a recessed RPM/boost window and
// a gear window at the bottom. Scales with a `split` put min..split on 7/8 of
// the sweep and squeeze split..max into the last 1/8. At or over the red line,
// that reading's whole trail, pointer and digits turn red and blink.
// Static art is painted once; trails and pointers move on the GPU.
import QtQuick
import QtQuick.Shapes

Item {
    id: g
    property var ringCfg: ({})
    property var innerCfg: ({})
    property var centerCfg: ({})
    property var box1Cfg: ({})
    property var box2Cfg: ({})
    property string gearKey: ""
    property color acc: "#29c4ff"
    property color acc2: "#ffb340"
    property bool blinkOn: true
    signal held(string slot)
    width: 524; height: 524

    readonly property real cx: width / 2
    readonly property real cy: height / 2
    readonly property real rd: 246
    readonly property real ro: 220
    readonly property real ri: 166
    readonly property real a0: 140
    readonly property real sw: 260

    function v(k) { var x = backend.values[k]; return x === undefined ? 0 : x }
    function ok(k) { return !!k && backend.fresh[k] === true }
    function lim(c) { return c && c.alarm !== undefined && !isNaN(c.alarm) ? c.alarm : NaN }
    // value -> 0..1 along the sweep, honoring the split
    function frac(c, x) {
        var mn = c.min || 0, mx = c.max > mn ? c.max : mn + 1, sp = c.split
        x = Math.max(mn, Math.min(mx, x))
        if (sp === undefined || isNaN(sp) || sp <= mn || sp >= mx) return (x - mn) / (mx - mn)
        return x <= sp ? 0.875 * (x - mn) / (sp - mn) : 0.875 + 0.125 * (x - sp) / (mx - sp)
    }
    function ang(c, x) { return a0 + sw * frac(c, x) }
    function fmtBox(c, x) {
        if (c.key === "rpm") return Math.round(x).toLocaleString(Qt.locale("en_US"), "f", 0)
        var d = c.decimals !== undefined ? c.decimals : 0
        return x.toFixed(d)
    }

    readonly property bool rOk: ok(ringCfg.key)
    readonly property bool iOk: ok(innerCfg.key)
    property real rShown: rOk ? v(ringCfg.key) : (ringCfg.min || 0)
    property real iShown: iOk ? v(innerCfg.key) : (innerCfg.min || 0)
    Behavior on rShown { SmoothedAnimation { velocity: Math.max(1, ((g.ringCfg.max || 100) - (g.ringCfg.min || 0)) * 1.5) } }
    Behavior on iShown { SmoothedAnimation { velocity: Math.max(1, ((g.innerCfg.max || 100) - (g.innerCfg.min || 0)) * 1.5) } }
    readonly property bool rHot: rOk && v(ringCfg.key) >= lim(ringCfg)
    readonly property bool iHot: iOk && v(innerCfg.key) >= lim(innerCfg)
    readonly property real rAng: ang(ringCfg, rShown)
    readonly property real iAng: ang(innerCfg, iShown)

    // ---- bezel, face and glow (painted once)
    Canvas {
        anchors.fill: parent
        property var deps: [g.acc, g.width]
        onDepsChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var cx = g.cx, cy = g.cy, R = g.rd
            function ring(r0, r1, style) { c.beginPath(); c.arc(cx, cy, r1, 0, 2 * Math.PI, false); c.arc(cx, cy, r0, 2 * Math.PI, 0, true); c.fillStyle = style; c.fill() }
            for (var i = 0; i < 4; i++) {   // soft accent glow outside the bezel
                c.lineWidth = 3 + i * 4; c.strokeStyle = Qt.rgba(g.acc.r, g.acc.g, g.acc.b, 0.12 - i * 0.025)
                c.beginPath(); c.arc(cx, cy, R + 14, 0, 2 * Math.PI); c.stroke()
            }
            c.beginPath(); c.arc(cx, cy + 6, R + 12, 0, 2 * Math.PI); c.fillStyle = "rgba(0,0,0,0.55)"; c.fill()
            var gr = c.createConicalGradient(cx, cy, Math.PI * 0.44)
            var st = ["#f7f9fb", "#7d8692", "#e3e7ec", "#3c434c", "#c9ced6", "#f4f6f9", "#4a515b", "#b5bcc6", "#262b33", "#f7f9fb"]
            for (var j = 0; j < st.length; j++) gr.addColorStop(j / (st.length - 1), st[j])
            ring(R, R + 12, gr)
            var sh = c.createLinearGradient(0, cy - R - 12, 0, cy + R + 12)
            sh.addColorStop(0, "rgba(255,255,255,0.25)"); sh.addColorStop(0.45, "rgba(0,0,0,0)"); sh.addColorStop(1, "rgba(0,0,0,0.45)")
            ring(R, R + 12, sh)
            c.lineWidth = 2; c.strokeStyle = g.acc
            c.beginPath(); c.arc(cx, cy, R + 13, 0, 2 * Math.PI); c.stroke()
            var fg = c.createRadialGradient(cx, cy - R * 0.4, 0, cx, cy, R)
            fg.addColorStop(0, "#111d2c"); fg.addColorStop(0.7, "#070b12"); fg.addColorStop(1, "#03050a")
            c.beginPath(); c.arc(cx, cy, R, 0, 2 * Math.PI); c.fillStyle = fg; c.fill()
            var inn = c.createRadialGradient(cx, cy, R * 0.72, cx, cy, R)
            inn.addColorStop(0, "rgba(0,0,0,0)"); inn.addColorStop(1, "rgba(0,0,0,0.85)")
            c.beginPath(); c.arc(cx, cy, R, 0, 2 * Math.PI); c.fillStyle = inn; c.fill()
            c.lineWidth = 3; c.strokeStyle = "rgba(0,0,0,0.85)"
            c.beginPath(); c.arc(cx, cy, R - 1.5, 0, 2 * Math.PI); c.stroke()
        }
    }

    // ---- light trails (behind the scales)
    component Trail: Shape {
        id: tr
        property real r0
        property real r1
        property real endAng
        property color col
        property real peak: 0.75
        anchors.fill: parent
        visible: endAng - g.a0 > 0.5
        readonly property real swp: endAng - g.a0
        ShapePath {
            strokeColor: "transparent"
            fillGradient: ConicalGradient {
                centerX: g.cx; centerY: g.cy; angle: -tr.endAng
                GradientStop { position: 0; color: Qt.rgba(tr.col.r, tr.col.g, tr.col.b, tr.peak) }
                GradientStop { position: Math.max(0.002, tr.swp / 360 * 0.4); color: Qt.rgba(tr.col.r, tr.col.g, tr.col.b, tr.peak * 0.35) }
                GradientStop { position: Math.max(0.003, tr.swp / 360); color: Qt.rgba(tr.col.r, tr.col.g, tr.col.b, 0) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathAngleArc { centerX: g.cx; centerY: g.cy; radiusX: tr.r1; radiusY: tr.r1; startAngle: g.a0; sweepAngle: tr.swp }
            PathAngleArc { moveToStart: false; centerX: g.cx; centerY: g.cy; radiusX: tr.r0; radiusY: tr.r0
                           startAngle: tr.endAng; sweepAngle: -tr.swp }
        }
        ShapePath {   // fade toward the center, so it glows brightest at the rim
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: g.cx; centerY: g.cy; centerRadius: tr.r1; focalX: g.cx; focalY: g.cy; focalRadius: tr.r0
                GradientStop { position: 0; color: Qt.rgba(0.027, 0.043, 0.07, 0.9) }
                GradientStop { position: 0.55; color: Qt.rgba(0.027, 0.043, 0.07, 0.3) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathAngleArc { centerX: g.cx; centerY: g.cy; radiusX: tr.r1; radiusY: tr.r1; startAngle: g.a0; sweepAngle: tr.swp }
            PathAngleArc { moveToStart: false; centerX: g.cx; centerY: g.cy; radiusX: tr.r0; radiusY: tr.r0
                           startAngle: tr.endAng; sweepAngle: -tr.swp }
        }
    }
    Trail { r0: 176; r1: g.rd - 12; endAng: g.rAng; col: g.rHot ? "#ff3b3b" : g.acc
            peak: g.rHot ? (g.blinkOn ? 0.95 : 0.12) : 0.75 }
    Trail { r0: 100; r1: 160; endAng: g.iAng; col: g.iHot ? "#ff3b3b" : g.acc2
            peak: g.iHot ? (g.blinkOn ? 0.95 : 0.12) : 0.7 }

    // ---- scales, red lines and limit markers (painted when the config changes)
    Canvas {
        anchors.fill: parent
        property var deps: [g.ringCfg, g.innerCfg, g.acc, g.acc2]
        onDepsChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var cx = g.cx, cy = g.cy
            function rad(a) { return a * Math.PI / 180 }
            function P(r, a) { return [cx + r * Math.cos(rad(a)), cy + r * Math.sin(rad(a))] }
            function line(r0, r1, a, col, w) { var p = P(r0, a), q = P(r1, a); c.strokeStyle = col; c.lineWidth = w
                c.beginPath(); c.moveTo(p[0], p[1]); c.lineTo(q[0], q[1]); c.stroke() }
            function marker(r, a, sz) {   // small red triangle outside the scale, pointing in
                var t = P(r + 4, a), b1 = P(r + sz, a - 1.5 * sz / 13), b2 = P(r + sz, a + 1.5 * sz / 13)
                c.beginPath(); c.moveTo(t[0], t[1]); c.lineTo(b1[0], b1[1]); c.lineTo(b2[0], b2[1]); c.closePath()
                c.fillStyle = "#ff3b3b"; c.fill(); c.lineWidth = 1; c.strokeStyle = "#ffffff"; c.stroke()
            }
            function num(cf, x) { var s = x * (cf.scale || 1); return Math.abs(s - Math.round(s)) < 1e-6 ? Math.round(s).toString() : s.toFixed(1) }
            function scale(cf, R, inner, col) {
                if (!cf || cf.max === undefined) return
                var mn = cf.min || 0, mx = cf.max, maj = cf.major || (mx - mn) / 5, mnr = maj / Math.max(1, cf.minor || 5)
                var sp = (cf.split !== undefined && !isNaN(cf.split) && cf.split > mn && cf.split < mx) ? cf.split : mx
                var red = g.lim(cf)
                c.lineCap = "butt"
                if (!inner) { c.lineWidth = 2; c.strokeStyle = Qt.rgba(g.acc.r, g.acc.g, g.acc.b, 0.35)
                              c.beginPath(); c.arc(cx, cy, R + 10, rad(g.a0), rad(g.a0 + g.sw)); c.stroke() }
                else { c.lineWidth = 12; c.strokeStyle = Qt.rgba(col.r, col.g, col.b, 0.13)
                       c.beginPath(); c.arc(cx, cy, R, rad(g.a0), rad(g.a0 + g.sw)); c.stroke() }
                if (!isNaN(red) && red < mx) {
                    c.lineWidth = inner ? 4 : 5; c.strokeStyle = "rgba(255,59,59,0.45)"
                    c.beginPath(); c.arc(cx, cy, inner ? R + 4 : R + 9, rad(g.ang(cf, red)), rad(g.a0 + g.sw)); c.stroke()
                }
                // ticks: every minor step below the split; above it, minor if roomy enough, else major
                var hiStep = (g.sw * 0.125 * mnr / (mx - sp) >= 3.5) ? mnr : maj
                var ticks = []
                for (var x = mn; x <= sp + 1e-9; x += mnr) ticks.push(x)
                for (var y = sp + hiStep; y <= mx + 1e-9; y += hiStep) ticks.push(y)
                var labStep = Math.max(maj, (mx - sp) / 2)
                c.font = (inner ? 19 : 24) + "px 'Barlow Semi Condensed SemiBold'"; c.textAlign = "center"; c.textBaseline = "middle"
                for (var i = 0; i < ticks.length; i++) {
                    var t = ticks[i], a = g.ang(cf, t), isMaj = Math.abs(t / maj - Math.round(t / maj)) < 1e-6
                    var isRed = !isNaN(red) && t >= red - 1e-9
                    var tc = isRed ? "#ff8a94" : (inner ? col.toString() : "#e9f1f8")
                    if (inner) line(R + 6, R - (isMaj ? 9 : 3), a, tc, isMaj ? 3 : 1.4)
                    else line(R + 11, R - (isMaj ? 11 : 2), a, tc, isMaj ? 4 : 2)
                    var labelled = t <= sp + 1e-9 ? isMaj : Math.abs((t - sp) / labStep - Math.round((t - sp) / labStep)) < 1e-6
                    if (labelled) {
                        var p = P(inner ? R - 24 : R - 22, a)
                        if (t > sp + 1e-9) c.font = (inner ? 16 : 19) + "px 'Barlow Semi Condensed SemiBold'"
                        c.fillStyle = isRed ? "#ff8a94" : (inner ? col.toString() : "#eef3f8")
                        c.fillText(num(cf, t), p[0], p[1])
                    }
                }
                if (!isNaN(red) && red < mx) marker(inner ? R + 3 : R + 12, g.ang(cf, red), inner ? 9 : 13)
            }
            scale(g.ringCfg, g.ro, false, g.acc)
            scale(g.innerCfg, g.ri, true, g.acc2)
        }
    }

    // ---- pointers: slim, rounded and shaded, across each light trail
    component Pointer: Item {
        id: pt
        property real r0
        property real r1
        property real halfDeg: 1.35
        property color col
        property color lite
        property real angle
        property real dim: 1
        x: g.cx; y: g.cy
        rotation: angle
        opacity: dim
        readonly property real hw: r0 * Math.sin(halfDeg * Math.PI / 180)
        Shape {   // shadow
            x: 3; y: 4; opacity: 0.6
            ShapePath { strokeColor: "transparent"; fillColor: "#000000"
                startX: pt.r0; startY: -pt.hw
                PathQuad { controlX: (pt.r0 + pt.r1) / 2; controlY: -pt.hw * 0.62; x: pt.r1; y: 0 }
                PathQuad { controlX: (pt.r0 + pt.r1) / 2; controlY: pt.hw * 0.62; x: pt.r0; y: pt.hw }
                PathQuad { controlX: pt.r0 - 5; controlY: 0; x: pt.r0; y: -pt.hw } }
        }
        Shape {   // glow
            ShapePath { strokeColor: "transparent"; fillColor: Qt.rgba(pt.col.r, pt.col.g, pt.col.b, 0.35)
                startX: pt.r0 - 4; startY: -pt.hw * 2.2
                PathQuad { controlX: (pt.r0 + pt.r1) / 2; controlY: -pt.hw * 1.6; x: pt.r1 + 6; y: 0 }
                PathQuad { controlX: (pt.r0 + pt.r1) / 2; controlY: pt.hw * 1.6; x: pt.r0 - 4; y: pt.hw * 2.2 }
                PathLine { x: pt.r0 - 4; y: -pt.hw * 2.2 } }
        }
        Shape {   // body, shaded across its width like a polished needle
            ShapePath { strokeColor: "transparent"
                fillGradient: LinearGradient {
                    x1: 0; y1: -pt.hw; x2: 0; y2: pt.hw
                    GradientStop { position: 0; color: pt.col }
                    GradientStop { position: 0.38; color: pt.lite }
                    GradientStop { position: 0.55; color: pt.col }
                    GradientStop { position: 1; color: Qt.darker(pt.col, 3) }
                }
                startX: pt.r0; startY: -pt.hw
                PathQuad { controlX: (pt.r0 + pt.r1) / 2; controlY: -pt.hw * 0.62; x: pt.r1; y: 0 }
                PathQuad { controlX: (pt.r0 + pt.r1) / 2; controlY: pt.hw * 0.62; x: pt.r0; y: pt.hw }
                PathQuad { controlX: pt.r0 - 5; controlY: 0; x: pt.r0; y: -pt.hw } }
        }
        Rectangle { x: pt.r0 + 3; y: -pt.hw * 0.25 - 0.55; width: pt.r1 - pt.r0 - 9; height: 1.1; color: Qt.rgba(1, 1, 1, 0.75) }
        Rectangle {   // metal cap at the base
            x: pt.r0 - 5 - width / 2; y: -height / 2; width: pt.hw * 1.8; height: width; radius: width / 2
            gradient: Gradient { GradientStop { position: 0; color: "#9aa2ad" } GradientStop { position: 1; color: "#08090a" } }
        }
    }
    Pointer { r0: 176; r1: g.ro + 12; halfDeg: 1.35; angle: g.rAng
              col: g.rHot ? "#ff3b3b" : g.acc; lite: g.rHot ? "#ffd0d4" : Qt.lighter(g.acc, 1.5)
              dim: g.rHot && !g.blinkOn ? 0.3 : 1; visible: g.rOk }
    Pointer { r0: 100; r1: g.ri + 8; halfDeg: 2.1; angle: g.iAng
              col: g.iHot ? "#ff3b3b" : g.acc2; lite: g.iHot ? "#ffd0d4" : Qt.lighter(g.acc2, 1.4)
              dim: g.iHot && !g.blinkOn ? 0.3 : 1; visible: g.iOk }

    // ---- big center reading (speed)
    readonly property bool cOk: ok(centerCfg.key)
    Item {
        anchors.horizontalCenter: parent.horizontalCenter; y: g.cy - 128
        width: spd.implicitWidth; height: spd.implicitHeight
        transform: Matrix4x4 { matrix: Qt.matrix4x4(1, -0.158, 0, 0.158 * spd.height * 0.8, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1) }
        Text { y: 4; text: spd.text; color: "#000000"; opacity: 0.8; font: spd.font }
        Text { id: spd; text: g.cOk ? g.v(g.centerCfg.key).toFixed(g.centerCfg.decimals || 0) : "--"
               color: "#eef3f8"; font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 156 }
    }
    Text { anchors.horizontalCenter: parent.horizontalCenter; y: g.cy + 30
           text: (g.centerCfg.units || "").toUpperCase(); color: "#8796a8"
           font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 22; font.letterSpacing: 4 }

    // ---- recessed windows: RPM / boost, and gear
    component Recess: Item {
        Rectangle { anchors.fill: parent; radius: 10
                    gradient: Gradient { GradientStop { position: 0; color: "#03060a" } GradientStop { position: 1; color: "#0e1824" } } }
        Rectangle { anchors.fill: parent; radius: 10
                    gradient: Gradient { GradientStop { position: 0; color: Qt.rgba(0, 0, 0, 0.85) } GradientStop { position: 0.22; color: "transparent" } } }
        Rectangle { anchors.fill: parent; radius: 10; color: "transparent"; border.width: 1.5; border.color: Qt.rgba(1, 1, 1, 0.18) }
        Rectangle { x: 6; width: parent.width - 12; height: 2; color: Qt.rgba(0, 0, 0, 0.9) }
    }
    readonly property bool b1Hot: ok(box1Cfg.key) && v(box1Cfg.key) >= lim(box1Cfg)
    readonly property bool b2Hot: ok(box2Cfg.key) && v(box2Cfg.key) >= lim(box2Cfg)
    Recess {
        id: box
        x: g.cx - 96; y: g.cy + 60; width: 192; height: 88
        Text { x: 12; y: 8; text: (g.box1Cfg.label || "").toUpperCase(); color: "#8796a8"
               font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 17 }
        Text { anchors.right: parent.right; anchors.rightMargin: 12; y: -2
               text: g.ok(g.box1Cfg.key) ? g.fmtBox(g.box1Cfg, g.v(g.box1Cfg.key)) : "--"
               color: g.b1Hot ? (g.blinkOn ? "#ff3b3b" : "#5a1a20") : "#eef3f8"
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 38 }
        Rectangle { x: 12; y: 46; width: parent.width - 24; height: 1; color: "#22364d" }
        Text { x: 12; y: 56; text: (g.box2Cfg.label || "").toUpperCase(); color: g.acc2
               font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 17 }
        Text { anchors.right: parent.right; anchors.rightMargin: 12; y: 48
               text: g.ok(g.box2Cfg.key) ? g.fmtBox(g.box2Cfg, g.v(g.box2Cfg.key)) + " " + (g.box2Cfg.units || "") : "--"
               color: g.b2Hot ? (g.blinkOn ? "#ff3b3b" : "#5a1a20") : g.acc2
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 30 }
    }
    Text { anchors.horizontalCenter: parent.horizontalCenter; y: g.cy + 154
           text: (g.ringCfg.label || "") + (g.ringCfg.scaleLabel ? " " + g.ringCfg.scaleLabel.replace("x", "×") : "")
                 + "  ·  " + (g.innerCfg.label || "") + " " + (g.innerCfg.units || "")
           color: "#8796a8"; font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 16 }
    Recess {
        x: g.cx - 62; y: g.cy + 182; width: 124; height: 60
        visible: g.gearKey !== ""
        Text { x: 14; anchors.verticalCenter: parent.verticalCenter; text: "GEAR"; color: "#8796a8"
               font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 18; font.letterSpacing: 2 }
        Text { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
               text: g.ok(g.gearKey) ? g.v(g.gearKey).toFixed(0) : "–"; color: "#eef3f8"
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 48 }
    }

    // press and hold: center number, inner scale, outer scale, or a box row
    MouseArea {
        anchors.fill: parent
        pressAndHoldInterval: 600
        onPressAndHold: function(m) {
            if (m.x >= box.x && m.x <= box.x + box.width && m.y >= box.y && m.y <= box.y + box.height) {
                g.held(m.y < box.y + box.height / 2 ? "box1" : "box2"); return
            }
            var d = Math.sqrt((m.x - g.cx) * (m.x - g.cx) + (m.y - g.cy) * (m.y - g.cy))
            if (d > g.rd + 14) return
            g.held(d < 96 ? "center" : d < 172 ? "inner" : "ring")
        }
    }
}
