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
    property int pointerStyle: 2   // 0 cone, 1 bar, 2 blade (JP's pick), 3 line + arrowhead, 4 laser line, 5 rim wedge
    property int scaleStyle: 2     // JP's pick. 0 static, 1 lit as passed, 2 color as passed, 3 contrast as passed, 4 focus number
    // light trail: dark gap behind the needle (degrees), strength at its peak, and how much it fades toward the center
    property real gapDeg: 4          // JP's pick: T3
    property real trailPeak: 1.0
    property real trailFade: 0.45
    // peak hold ("ghost"): 0 off, 1 line, 2 ghost needle, 3 rim marker, 4 line + value
    property int ghostStyle: 2        // 1 thin line, 2 needle copy (JP: same as the dial, orange), 3 rim marker, 4 line + value
    property color ghostColor: "#ff6a00"   // JP's pick: O3 deep orange
    property real ghostAlpha: 0.9
    property bool ghostTrail: true
    property real pkTrailDeg: 32       // peak needle's glow trail: length (degrees) and strength
    property real pkTrailA: 0.75   // JP's pick: K4
    property color scaleRed: "#9e1f2a"   // red-zone ticks and numbers on the scales
    property int ringStyle: 0         // 0 current; 1 chrome bevel + soft backlight; 2 chrome + strong backlight; 3 wide turned chrome + backlight;
                                      // 4-6 round chrome tube (like a hoop earring) + backlight: 4 slim, 5 thick, 6 thick polished;
                                      // 7-10 high-quality ring, glow from behind: 7 polished chrome, 8 satin, 9 gunmetal, 10 polished + inner bevel
    property real haloA: 0.55        // backlight spilling onto the background behind the gauge
    property int holdMs: 3500         // hold the peak this long, then ease back to the needle in about 2.5 s
    property real demoRPeak: NaN      // screenshots only
    property real demoIPeak: NaN
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
    function quant(c, x) { var st = (c.major || 1) / Math.max(1, c.minor || 5); return Math.floor(x / st + 1e-6) * st }
    readonly property real rPass: scaleStyle ? quant(ringCfg, rShown) : 0
    readonly property real iPass: scaleStyle ? quant(innerCfg, iShown) : 0
    // ---- peak hold: jumps up with the reading, holds, then falls back toward it
    property real rHold: rShown
    property real iHold: iShown
    property double rHoldT: 0
    property double iHoldT: 0
    onRShownChanged: if (rShown >= rHold) { rHold = rShown; rHoldT = Date.now() }
    onIShownChanged: if (iShown >= iHold) { iHold = iShown; iHoldT = Date.now() }
    Timer {
        interval: 50; repeat: true; running: g.ghostStyle > 0
        onTriggered: {
            var now = Date.now()
            // ease back: close ~8% of the gap every 50 ms (about 2.5 s to reach the needle), with a small floor
            if (g.rHold > g.rShown && now - g.rHoldT > g.holdMs)
                g.rHold = Math.max(g.rShown, g.rHold - Math.max((g.rHold - g.rShown) * 0.08, ((g.ringCfg.max || 100) - (g.ringCfg.min || 0)) * 0.001))
            if (g.iHold > g.iShown && now - g.iHoldT > g.holdMs)
                g.iHold = Math.max(g.iShown, g.iHold - Math.max((g.iHold - g.iShown) * 0.08, ((g.innerCfg.max || 100) - (g.innerCfg.min || 0)) * 0.001))
        }
    }
    readonly property real rPeak: isNaN(demoRPeak) ? rHold : demoRPeak
    readonly property real iPeak: isNaN(demoIPeak) ? iHold : demoIPeak
    readonly property real rAng: ang(ringCfg, rShown)
    readonly property real iAng: ang(innerCfg, iShown)

    // ---- chrome ring with accent backlight (styles 1-3), painted once
    Canvas {
        visible: g.ringStyle > 0
        x: -60; y: -60; width: g.width + 120; height: g.height + 120
        property var deps: [g.acc, g.width, g.ringStyle]
        onDepsChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            if (g.ringStyle === 0) return
            var cx = g.cx + 60, cy = g.cy + 60, R = g.rd, st = g.ringStyle
            var W = st === 3 ? 20 : st === 4 ? 16 : st >= 5 ? 22 : 15
            var glowA = st === 2 || st === 6 ? 0.75 : 0.5, glowW = st === 2 || st === 6 ? 52 : 40
            var tube = st >= 4
            var A = g.acc
            function ann(r0, r1, style) { c.beginPath(); c.arc(cx, cy, r1, 0, 2 * Math.PI, false); c.arc(cx, cy, r0, 2 * Math.PI, 0, true); c.fillStyle = style; c.fill() }
            function acc(a) { return Qt.rgba(A.r, A.g, A.b, a) }
            if (st >= 7) {
                W = 18
                // backlight: light from behind the gauge spilling onto the background, strongest at the edge
                var hl = c.createRadialGradient(cx, cy, R + W - 2, cx, cy, R + W + 70)
                hl.addColorStop(0, acc(g.haloA)); hl.addColorStop(0.12, acc(g.haloA * 0.75)); hl.addColorStop(0.4, acc(g.haloA * 0.28)); hl.addColorStop(1, acc(0))
                ann(R + W - 2, R + W + 70, hl)
                // contact shadow the ring throws onto the face (heavier below)
                ann(R - 16, R, (function() { var sg = c.createRadialGradient(cx, cy + 4, R - 16, cx, cy + 4, R)
                    sg.addColorStop(0, "rgba(0,0,0,0)"); sg.addColorStop(1, "rgba(0,0,0,0.9)"); return sg })())
                var r0 = R
                if (st === 10) {   // thin stepped bevel between face and tube
                    var bv2 = c.createRadialGradient(cx, cy, R, cx, cy, R + 5)
                    bv2.addColorStop(0, "#0b0d10"); bv2.addColorStop(0.5, "#8d96a2"); bv2.addColorStop(1, "#1a1e23")
                    ann(R, R + 5, bv2); r0 = R + 5; W = 17
                }
                // cross-section profile: what the tube reflects from its inner edge (0) to its outer edge (1)
                var prof = st === 8
                    ? [[0, "#121519"], [0.12, "#4b525b"], [0.35, "#b9c0c8"], [0.5, "#d9dee3"], [0.62, "#b0b7bf"], [0.85, "#4e555e"], [1, "#101317"]]
                    : st === 9
                    ? [[0, "#040506"], [0.14, "#262b31"], [0.3, "#8f98a3"], [0.38, "#c4cbd3"], [0.46, "#3a4048"], [0.5, "#16191d"], [0.68, "#2e343b"], [0.86, "#6b737d"], [1, "#040506"]]
                    : [[0, "#0b0d10"], [0.06, "#3a4048"], [0.15, "#c7ced6"], [0.3, "#ffffff"], [0.42, "#e3e8ee"], [0.47, "#5a616b"], [0.5, "#23282e"],
                       [0.62, "#6f7782"], [0.78, "#bcc4cd"], [0.88, "#f4f7fa"], [0.95, "#5b626c"], [1, "#0b0d10"]]
                var tg = c.createRadialGradient(cx, cy, r0, cx, cy, r0 + W)
                for (var q = 0; q < prof.length; q++) tg.addColorStop(prof[q][0], prof[q][1])
                ann(r0, r0 + W, tg)
                // environment: brighter where it faces up toward the light, darker facing down
                var env = c.createLinearGradient(0, cy - r0 - W, 0, cy + r0 + W)
                env.addColorStop(0, "rgba(255,255,255,0.16)"); env.addColorStop(0.45, "rgba(255,255,255,0)")
                env.addColorStop(0.6, "rgba(0,0,0,0.12)"); env.addColorStop(1, "rgba(0,0,0,0.45)")
                ann(r0, r0 + W, env)
                // cool tint in the reflections
                ann(r0, r0 + W, "rgba(120,160,210,0.06)")
                // crisp specular highlights on the bright band, upper left (and a softer one upper right)
                var spA = st === 8 ? 0.45 : st === 9 ? 0.6 : 0.95
                c.lineCap = "round"
                c.lineWidth = st === 8 ? 4 : 2.2; c.strokeStyle = "rgba(255,255,255," + spA + ")"
                c.beginPath(); c.arc(cx, cy, r0 + W * 0.27, Math.PI * 1.12, Math.PI * 1.38); c.stroke()
                c.lineWidth = st === 8 ? 3 : 1.4; c.strokeStyle = "rgba(255,255,255," + (spA * 0.6) + ")"
                c.beginPath(); c.arc(cx, cy, r0 + W * 0.27, Math.PI * 1.6, Math.PI * 1.75); c.stroke()
                // hairline edges so it reads crisp
                c.lineWidth = 1; c.strokeStyle = "rgba(0,0,0,0.9)"
                c.beginPath(); c.arc(cx, cy, r0 + W - 0.5, 0, 2 * Math.PI); c.stroke()
                c.beginPath(); c.arc(cx, cy, r0 + 0.5, 0, 2 * Math.PI); c.stroke()
                c.strokeStyle = "rgba(255,255,255,0.35)"
                c.beginPath(); c.arc(cx, cy, r0 + W - 2, Math.PI * 1.1, Math.PI * 1.9); c.stroke()
                return
            }
            // backlight bleeding out around the ring
            var bl = c.createRadialGradient(cx, cy, R + W - 4, cx, cy, R + W + glowW)
            bl.addColorStop(0, acc(glowA)); bl.addColorStop(0.35, acc(glowA * 0.35)); bl.addColorStop(1, acc(0))
            ann(R + W - 4, R + W + glowW, bl)
            // shadow the ring casts on the face
            ann(R - 10, R, (function() { var sg = c.createRadialGradient(cx, cy, R - 10, cx, cy, R); sg.addColorStop(0, "rgba(0,0,0,0)"); sg.addColorStop(1, "rgba(0,0,0,0.85)"); return sg })())
            if (tube) {
                // round tube: cast shadow, then a cross-section that's dark at both edges and bright at the crest,
                // lit from the upper left, with a sharp shine and a faint reflected light underneath
                ann(R - 2, R + W + 4, (function() { var sh = c.createRadialGradient(cx + 3, cy + 6, R - 2, cx + 3, cy + 6, R + W + 4)
                    sh.addColorStop(0, "rgba(0,0,0,0)"); sh.addColorStop(0.3, "rgba(0,0,0,0.6)"); sh.addColorStop(0.7, "rgba(0,0,0,0.6)"); sh.addColorStop(1, "rgba(0,0,0,0)"); return sh })())
                var tb = c.createRadialGradient(cx, cy, R, cx, cy, R + W)
                tb.addColorStop(0, "#1a1d22"); tb.addColorStop(0.18, "#6b737e"); tb.addColorStop(0.42, "#e8ecf1")
                tb.addColorStop(0.5, "#ffffff"); tb.addColorStop(0.6, "#c9cfd7"); tb.addColorStop(0.85, "#4a515b"); tb.addColorStop(1, "#14171b")
                ann(R, R + W, tb)
                var lt = c.createConicalGradient(cx, cy, Math.PI * 0.75)   // brighter toward the upper left, darker lower right
                lt.addColorStop(0, "rgba(255,255,255,0.22)"); lt.addColorStop(0.25, "rgba(0,0,0,0)"); lt.addColorStop(0.5, "rgba(0,0,0,0.42)")
                lt.addColorStop(0.75, "rgba(0,0,0,0)"); lt.addColorStop(1, "rgba(255,255,255,0.22)")
                ann(R, R + W, lt)
                var sp = st === 6 ? 0.95 : 0.7
                c.lineCap = "round"; c.lineWidth = st === 4 ? 2.5 : 3.5
                c.strokeStyle = "rgba(255,255,255," + sp + ")"
                c.beginPath(); c.arc(cx, cy, R + W * 0.44, Math.PI * 1.08, Math.PI * 1.42); c.stroke()
                c.lineWidth = 1.5; c.strokeStyle = "rgba(255,255,255," + (sp * 0.55) + ")"
                c.beginPath(); c.arc(cx, cy, R + W * 0.44, Math.PI * 1.55, Math.PI * 1.7); c.stroke()
                c.lineWidth = 2; c.strokeStyle = acc(0.5)   // accent light reflected on the lower edge of the tube
                c.beginPath(); c.arc(cx, cy, R + W * 0.82, Math.PI * 0.15, Math.PI * 0.85); c.stroke()
                c.lineWidth = 2.5; c.strokeStyle = acc(0.9); c.beginPath(); c.arc(cx, cy, R + W + 1.5, 0, 2 * Math.PI); c.stroke()
                return
            }
            // chrome
            var gr = c.createConicalGradient(cx, cy, Math.PI * 0.44)
            var cs = ["#ffffff", "#7d8692", "#eef1f4", "#3c434c", "#d3d8df", "#ffffff", "#4a515b", "#c1c7cf", "#262b33", "#ffffff"]
            for (var j = 0; j < cs.length; j++) gr.addColorStop(j / (cs.length - 1), cs[j])
            ann(R, R + W, gr)
            // bevel: lit from above, dark below
            var bv = c.createLinearGradient(0, cy - R - W, 0, cy + R + W)
            bv.addColorStop(0, "rgba(255,255,255,0.35)"); bv.addColorStop(0.5, "rgba(0,0,0,0)"); bv.addColorStop(1, "rgba(0,0,0,0.5)")
            ann(R, R + W, bv)
            // rounded profile: dark inner lip, bright crest, dark outer edge
            var pr = c.createRadialGradient(cx, cy, R, cx, cy, R + W)
            pr.addColorStop(0, "rgba(0,0,0,0.75)"); pr.addColorStop(0.18, "rgba(0,0,0,0)")
            pr.addColorStop(0.5, "rgba(255,255,255,0.18)"); pr.addColorStop(0.82, "rgba(0,0,0,0)"); pr.addColorStop(1, "rgba(0,0,0,0.65)")
            ann(R, R + W, pr)
            if (st === 3) {   // turned grooves
                for (var k = 1; k < 4; k++) { c.lineWidth = 1; c.strokeStyle = "rgba(0,0,0,0.3)"; c.beginPath(); c.arc(cx, cy, R + W * k / 4, 0, 2 * Math.PI); c.stroke()
                                              c.strokeStyle = "rgba(255,255,255,0.22)"; c.beginPath(); c.arc(cx, cy, R + W * k / 4 + 1, 0, 2 * Math.PI); c.stroke() }
            }
            // backlit edges: thin accent line outside the chrome and a faint one where it meets the face
            c.lineWidth = 2.5; c.strokeStyle = acc(0.95); c.beginPath(); c.arc(cx, cy, R + W + 1.5, 0, 2 * Math.PI); c.stroke()
            c.lineWidth = 1.5; c.strokeStyle = acc(0.55); c.beginPath(); c.arc(cx, cy, R - 0.5, 0, 2 * Math.PI); c.stroke()
        }
    }
    // ---- bezel, face and glow (painted once)
    Canvas {
        anchors.fill: parent
        property var deps: [g.acc, g.width, g.ringStyle]
        onDepsChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var cx = g.cx, cy = g.cy, R = g.rd
            function ring(r0, r1, style) { c.beginPath(); c.arc(cx, cy, r1, 0, 2 * Math.PI, false); c.arc(cx, cy, r0, 2 * Math.PI, 0, true); c.fillStyle = style; c.fill() }
            if (g.ringStyle > 0) {   // face only; the chrome ring canvas draws the bezel
                var f2 = c.createRadialGradient(cx, cy - R * 0.4, 0, cx, cy, R)
                f2.addColorStop(0, "#111d2c"); f2.addColorStop(0.7, "#070b12"); f2.addColorStop(1, "#03050a")
                c.beginPath(); c.arc(cx, cy, R, 0, 2 * Math.PI); c.fillStyle = f2; c.fill(); return
            }
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
                GradientStop { position: 0; color: Qt.rgba(tr.col.r, tr.col.g, tr.col.b, 0) }
                GradientStop { position: Math.min(g.gapDeg / 360 * 0.35, tr.swp / 360 * 0.15); color: Qt.rgba(tr.col.r, tr.col.g, tr.col.b, tr.peak * 0.08) }
                GradientStop { position: Math.min(g.gapDeg / 360, tr.swp / 360 * 0.35); color: Qt.rgba(tr.col.r, tr.col.g, tr.col.b, tr.peak) }
                GradientStop { position: Math.max(g.gapDeg / 360 + 0.001, tr.swp / 360 * 0.55); color: Qt.rgba(tr.col.r, tr.col.g, tr.col.b, tr.peak * 0.45) }
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
                GradientStop { position: 0; color: Qt.rgba(0.027, 0.043, 0.07, g.trailFade) }
                GradientStop { position: 0.55; color: Qt.rgba(0.027, 0.043, 0.07, g.trailFade / 3) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathAngleArc { centerX: g.cx; centerY: g.cy; radiusX: tr.r1; radiusY: tr.r1; startAngle: g.a0; sweepAngle: tr.swp }
            PathAngleArc { moveToStart: false; centerX: g.cx; centerY: g.cy; radiusX: tr.r0; radiusY: tr.r0
                           startAngle: tr.endAng; sweepAngle: -tr.swp }
        }
    }
    Trail { r0: 176; r1: g.rd - 12; endAng: g.rAng; col: g.rHot ? "#ff3b3b" : g.acc
            peak: g.rHot ? (g.blinkOn ? 0.95 : 0.12) : g.trailPeak }
    Trail { r0: 100; r1: 160; endAng: g.iAng; col: g.iHot ? "#ff3b3b" : g.acc2
            peak: g.iHot ? (g.blinkOn ? 0.95 : 0.12) : g.trailPeak }

    // ---- scales, red lines and limit markers (painted when the config changes)
    Canvas {
        anchors.fill: parent
        property var deps: [g.ringCfg, g.innerCfg, g.acc, g.acc2, g.scaleRed, g.scaleStyle, g.rPass, g.iPass]
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
            function scale(cf, R, inner, col, pass, now) {
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
                    c.lineWidth = inner ? 4 : 5; c.strokeStyle = Qt.rgba(g.scaleRed.r, g.scaleRed.g, g.scaleRed.b, 0.5)
                    c.beginPath(); c.arc(cx, cy, inner ? R + 4 : R + 9, rad(g.ang(cf, red)), rad(g.a0 + g.sw)); c.stroke()
                }
                // ticks: every minor step below the split; above it, minor if roomy enough, else major
                var hiStep = (g.sw * 0.125 * mnr / (mx - sp) >= 3.5) ? mnr : maj
                var ticks = []
                for (var x = mn; x <= sp + 1e-9; x += mnr) ticks.push(x)
                for (var y = sp + hiStep; y <= mx + 1e-9; y += hiStep) ticks.push(y)
                var labStep = Math.max(maj, (mx - sp) / 2)
                c.font = (inner ? 19 : 24) + "px 'Barlow Semi Condensed SemiBold'"; c.textAlign = "center"; c.textBaseline = "middle"
                // nearest labelled number to the needle (style 4)
                var near = NaN, best = 1e9
                for (var k = 0; k < ticks.length; k++) { var tk = ticks[k]
                    if (Math.abs(tk / maj - Math.round(tk / maj)) < 1e-6 && Math.abs(tk - now) < best) { best = Math.abs(tk - now); near = tk } }
                var st = g.scaleStyle
                for (var i = 0; i < ticks.length; i++) {
                    var t = ticks[i], a = g.ang(cf, t), isMaj = Math.abs(t / maj - Math.round(t / maj)) < 1e-6
                    var isRed = !isNaN(red) && t >= red - 1e-9, passed = t <= pass + 1e-9
                    var base = inner ? col.toString() : "#e9f1f8"
                    var tc = isRed ? g.scaleRed.toString() : base
                    if (st === 1) tc = isRed ? (passed ? "#ff6b78" : "#7a3a40") : (passed ? (inner ? Qt.lighter(col, 1.3).toString() : "#ffffff") : "#56627a")
                    else if (st === 2 && passed && !isRed) tc = "#ffffff"
                    else if (st === 3 && passed) tc = "#05080c"
                    else if (st === 4) tc = isRed ? g.scaleRed.toString() : (t === near ? base : (inner ? Qt.darker(col, 1.8).toString() : "#7d8aa0"))
                    if (st === 1 && passed && isMaj) {   // glow behind lit major ticks
                        var gp = P(R + 11, a), gq = P(R - 11, a); c.strokeStyle = Qt.rgba(1, 1, 1, 0.22); c.lineWidth = 10
                        c.beginPath(); c.moveTo(gp[0], gp[1]); c.lineTo(gq[0], gq[1]); c.stroke() }
                    if (inner) line(R + 6, R - (isMaj ? 9 : 3), a, tc, isMaj ? 3 : 1.4)
                    else line(R + 11, R - (isMaj ? 11 : 2), a, tc, isMaj ? 4 : 2)
                    var labelled = t <= sp + 1e-9 ? isMaj : Math.abs((t - sp) / labStep - Math.round((t - sp) / labStep)) < 1e-6
                    if (labelled) {
                        var p = P(inner ? R - 24 : R - 22, a)
                        var fs = t > sp + 1e-9 ? (inner ? 16 : 19) : (inner ? 19 : 24)
                        if (st === 4 && t === near) fs = Math.round(fs * 1.5)
                        c.font = fs + "px 'Barlow Semi Condensed SemiBold'"
                        c.fillStyle = st ? tc : (isRed ? g.scaleRed.toString() : (inner ? col.toString() : "#eef3f8"))
                        c.fillText(num(cf, t), p[0], p[1])
                    }
                }
                if (!isNaN(red) && red < mx) marker(inner ? R + 3 : R + 12, g.ang(cf, red), inner ? 9 : 13)
            }
            scale(g.ringCfg, g.ro, false, g.acc, g.rPass, g.rShown)
            scale(g.innerCfg, g.ri, true, g.acc2, g.iPass, g.iShown)
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
        readonly property int st: g.pointerStyle
        // ---- 1: straight bar, same width end to end, rounded ends
        Item {
            visible: pt.st === 1
            Rectangle { x: pt.r0 + 3; y: -1; width: pt.r1 - pt.r0; height: 7; radius: 3.5; color: "#000000"; opacity: 0.5 }
            Rectangle { x: pt.r0 - 3; y: -6; width: pt.r1 - pt.r0 + 6; height: 12; radius: 6; color: Qt.rgba(pt.col.r, pt.col.g, pt.col.b, 0.3) }
            Rectangle { x: pt.r0; y: -3.5; width: pt.r1 - pt.r0; height: 7; radius: 3.5
                gradient: Gradient { GradientStop { position: 0; color: pt.col } GradientStop { position: 0.35; color: pt.lite }
                                     GradientStop { position: 0.6; color: Qt.darker(pt.lite, 1.1) } GradientStop { position: 1; color: Qt.darker(pt.col, 2.2) } } }
        }
        // ---- 2: thin blade, straight sides, sharp point
        Shape {   // blade shadow (two soft layers)
            visible: pt.st === 2; x: 3; y: 5
            ShapePath { strokeColor: "transparent"; fillColor: Qt.rgba(0, 0, 0, 0.35)
                startX: pt.r0 - 2; startY: -6
                PathLine { x: pt.r1 - 12; y: -6 } PathLine { x: pt.r1 + 4; y: 0 } PathLine { x: pt.r1 - 12; y: 6 } PathLine { x: pt.r0 - 2; y: 6 } PathLine { x: pt.r0 - 2; y: -6 } }
            ShapePath { strokeColor: "transparent"; fillColor: Qt.rgba(0, 0, 0, 0.55)
                startX: pt.r0; startY: -3.5
                PathLine { x: pt.r1 - 12; y: -3.5 } PathLine { x: pt.r1; y: 0 } PathLine { x: pt.r1 - 12; y: 3.5 } PathLine { x: pt.r0; y: 3.5 } PathLine { x: pt.r0; y: -3.5 } }
        }
        Shape {
            visible: pt.st === 2
            ShapePath { strokeColor: "transparent"; fillColor: Qt.rgba(pt.col.r, pt.col.g, pt.col.b, 0.3)
                startX: pt.r0 - 2; startY: -5.5
                PathLine { x: pt.r1 - 14; y: -5.5 } PathLine { x: pt.r1 + 4; y: 0 } PathLine { x: pt.r1 - 14; y: 5.5 } PathLine { x: pt.r0 - 2; y: 5.5 } PathLine { x: pt.r0 - 2; y: -5.5 } }
            ShapePath { strokeColor: "transparent"
                fillGradient: LinearGradient { x1: 0; y1: -3; x2: 0; y2: 3
                    GradientStop { position: 0; color: pt.lite } GradientStop { position: 0.5; color: pt.lite } GradientStop { position: 0.51; color: Qt.darker(pt.lite, 1.35) } GradientStop { position: 1; color: Qt.darker(pt.col, 1.6) } }
                startX: pt.r0; startY: -3
                PathLine { x: pt.r1 - 12; y: -3 } PathLine { x: pt.r1; y: 0 } PathLine { x: pt.r1 - 12; y: 3 } PathLine { x: pt.r0; y: 3 } PathLine { x: pt.r0; y: -3 } }
        }
        // ---- 3: thin line with an arrowhead at the rim
        Item {
            visible: pt.st === 3
            Rectangle { x: pt.r0; y: -1.5; width: pt.r1 - pt.r0 - 14; height: 3; radius: 1.5; color: pt.lite }
            Shape {
                ShapePath { strokeColor: Qt.rgba(0, 0, 0, 0.7); strokeWidth: 1; fillColor: pt.lite
                    startX: pt.r1 - 18; startY: -8
                    PathLine { x: pt.r1 + 2; y: 0 } PathLine { x: pt.r1 - 18; y: 8 } PathLine { x: pt.r1 - 18; y: -8 } }
                ShapePath { strokeColor: "transparent"; fillColor: pt.col
                    startX: pt.r1 - 18; startY: 0
                    PathLine { x: pt.r1 + 2; y: 0 } PathLine { x: pt.r1 - 18; y: 8 } PathLine { x: pt.r1 - 18; y: 0 } }
            }
        }
        // ---- 4: glowing laser line, no body
        Item {
            visible: pt.st === 4
            Rectangle { x: pt.r0 - 2; y: -7; width: pt.r1 - pt.r0 + 4; height: 14; radius: 7; color: Qt.rgba(pt.col.r, pt.col.g, pt.col.b, 0.18) }
            Rectangle { x: pt.r0 - 1; y: -3.5; width: pt.r1 - pt.r0 + 2; height: 7; radius: 3.5; color: Qt.rgba(pt.col.r, pt.col.g, pt.col.b, 0.4) }
            Rectangle { x: pt.r0; y: -1; width: pt.r1 - pt.r0; height: 2; radius: 1; color: "#ffffff" }
        }
        // ---- 5: white wedge at the rim pointing out, like the side-panel pointers
        Shape {
            visible: pt.st === 5
            ShapePath { strokeColor: Qt.rgba(0, 0, 0, 0.8); strokeWidth: 1.2; joinStyle: ShapePath.MiterJoin; fillColor: pt.lite
                startX: pt.r1 - 30; startY: -6
                PathLine { x: pt.r1 + 4; y: 0 } PathLine { x: pt.r1 - 30; y: 6 } PathLine { x: pt.r1 - 30; y: -6 } }
        }
        // ---- 0: rounded cone (below)
        Item { visible: pt.st === 0
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
                    GradientStop { position: 0.3; color: pt.lite }
                    GradientStop { position: 0.55; color: Qt.darker(pt.lite, 1.12) }
                    GradientStop { position: 1; color: Qt.darker(pt.col, 2.5) }
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
    }
    component Ghost: Item {
        id: gh
        property real r0
        property real r1
        property real angle
        property real peak
        property var cfg
        property color col
        property bool show: true
        // opacity, not visible: the Pi's GPU renderer skips Shapes that start hidden
        opacity: show && g.ghostStyle > 0 && Math.abs(angle - g.a0) > 0.5 ? 1 : 0
        x: g.cx; y: g.cy
        rotation: angle
        Shape {   // soft light trail fading back from the peak
            id: gtr
            opacity: g.ghostStyle === 1 || g.ghostStyle === 4 || (g.ghostStyle === 2 && g.ghostTrail) ? 1 : 0
            readonly property color tc: g.ghostStyle === 2 ? g.ghostColor : "#ffffff"
            ShapePath { strokeColor: "transparent"
                fillGradient: ConicalGradient { centerX: 0; centerY: 0; angle: 0
                    GradientStop { position: 0; color: Qt.rgba(gtr.tc.r, gtr.tc.g, gtr.tc.b, g.pkTrailA) }
                    GradientStop { position: g.pkTrailDeg / 360 * 0.5; color: Qt.rgba(gtr.tc.r, gtr.tc.g, gtr.tc.b, g.pkTrailA * 0.4) }
                    GradientStop { position: g.pkTrailDeg / 360; color: Qt.rgba(gtr.tc.r, gtr.tc.g, gtr.tc.b, 0) }
                    GradientStop { position: 1; color: "transparent" } }
                PathAngleArc { centerX: 0; centerY: 0; radiusX: gh.r1; radiusY: gh.r1; startAngle: -g.pkTrailDeg; sweepAngle: g.pkTrailDeg }
                PathAngleArc { moveToStart: false; centerX: 0; centerY: 0; radiusX: gh.r0; radiusY: gh.r0; startAngle: 0; sweepAngle: -g.pkTrailDeg } }
        }
        Rectangle {   // shadow
            visible: g.ghostStyle === 1 || g.ghostStyle === 4
            x: gh.r0 + 2; y: 0; width: gh.r1 - gh.r0; height: 5; radius: 2.5; color: "#000000"; opacity: 0.55 }
        Rectangle {   // glow
            visible: g.ghostStyle === 1 || g.ghostStyle === 4
            x: gh.r0 - 2; y: -5.5; width: gh.r1 - gh.r0 + 4; height: 11; radius: 5.5; color: Qt.rgba(1, 1, 1, 0.16) }
        Rectangle {   // the line: 5 px, shaded like a rounded bar
            visible: g.ghostStyle === 1 || g.ghostStyle === 4
            x: gh.r0; y: -2.5; width: gh.r1 - gh.r0; height: 5; radius: 2.5
            gradient: Gradient {
                GradientStop { position: 0; color: "#9aa3ad" }
                GradientStop { position: 0.35; color: "#ffffff" }
                GradientStop { position: 0.6; color: "#dfe5eb" }
                GradientStop { position: 1; color: "#5a626d" }
            }
        }
        Shape {       // 3: small white marker on the rim, pointing in
            visible: g.ghostStyle === 3
            ShapePath { strokeColor: Qt.rgba(0, 0, 0, 0.8); strokeWidth: 1; fillColor: "#ffffff"
                startX: gh.r1 + 16; startY: -7
                PathLine { x: gh.r1 + 2; y: 0 } PathLine { x: gh.r1 + 16; y: 7 } PathLine { x: gh.r1 + 16; y: -7 } }
        }
    }
    Ghost { r0: 176; r1: g.ro + 12; angle: g.ang(g.ringCfg, g.rPeak); peak: g.rPeak; cfg: g.ringCfg; col: g.acc
            show: g.rOk && g.rPeak > g.rShown + 1e-6 }
    Ghost { r0: 100; r1: g.ri + 8; angle: g.ang(g.innerCfg, g.iPeak); peak: g.iPeak; cfg: g.innerCfg; col: g.acc2
            show: g.iOk && g.iPeak > g.iShown + 1e-6 }
    // 2: ghost needle, a faint copy of the needle at the peak
    Pointer { r0: 176; r1: g.ro + 12; halfDeg: 1.35; angle: g.ang(g.ringCfg, g.rPeak); col: g.ghostColor; lite: Qt.lighter(g.ghostColor, 1.6)
              dim: g.ghostStyle === 2 && g.rOk && g.rPeak > g.rShown + 1e-6 ? g.ghostAlpha : 0 }
    Pointer { r0: 100; r1: g.ri + 8; halfDeg: 2.1; angle: g.ang(g.innerCfg, g.iPeak); col: g.ghostColor; lite: Qt.lighter(g.ghostColor, 1.6)
              dim: g.ghostStyle === 2 && g.iOk && g.iPeak > g.iShown + 1e-6 ? g.ghostAlpha : 0 }
    // 4: the peak value next to the rim
    Text {
        visible: g.ghostStyle === 4 && g.rOk && g.rPeak > g.rShown + 1e-6
        readonly property real a: g.ang(g.ringCfg, g.rPeak) * Math.PI / 180
        x: g.cx + (g.ro - 52) * Math.cos(a) - width / 2; y: g.cy + (g.ro - 52) * Math.sin(a) - height / 2
        text: Math.round(g.rPeak).toLocaleString(Qt.locale("en_US"), "f", 0)
        color: "#ffffff"; font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 17
        style: Text.Outline; styleColor: "#000000"
    }
    Text {
        visible: g.ghostStyle === 4 && g.iOk && g.iPeak > g.iShown + 1e-6
        readonly property real a: g.ang(g.innerCfg, g.iPeak) * Math.PI / 180
        x: g.cx + (g.ri - 52) * Math.cos(a) - width / 2; y: g.cy + (g.ri - 52) * Math.sin(a) - height / 2
        text: g.iPeak.toFixed(1)
        color: "#ffffff"; font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 16
        style: Text.Outline; styleColor: "#000000"
    }
    Pointer { r0: 176; r1: g.ro + 12; halfDeg: 1.35; angle: g.rAng
              col: g.rHot ? "#ff3b3b" : g.acc; lite: g.rHot ? "#ffd0d4" : "#ffffff"
              dim: !g.rOk ? 0 : (g.rHot && !g.blinkOn ? 0.3 : 1) }
    Pointer { r0: 100; r1: g.ri + 8; halfDeg: 2.1; angle: g.iAng
              col: g.iHot ? "#ff3b3b" : g.acc2; lite: g.iHot ? "#ffd0d4" : "#ffffff"
              dim: !g.iOk ? 0 : (g.iHot && !g.blinkOn ? 0.3 : 1) }

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
        x: g.cx - 100; y: g.cy + 54; width: 200; height: 118
        Text { x: 12; y: 10; text: (g.box1Cfg.label || "").toUpperCase(); color: "#8796a8"
               font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 18 }
        Text { anchors.right: parent.right; anchors.rightMargin: 12; y: -4
               text: g.ok(g.box1Cfg.key) ? g.fmtBox(g.box1Cfg, g.v(g.box1Cfg.key)) : "--"
               color: g.b1Hot ? (g.blinkOn ? "#ff3b3b" : "#5a1a20") : "#eef3f8"
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 52 }
        Rectangle { x: 12; y: 62; width: parent.width - 24; height: 1; color: "#22364d" }
        Text { x: 12; y: 72; text: (g.box2Cfg.label || "").toUpperCase(); color: g.acc2
               font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 18 }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 12; y: 60; spacing: 4
            readonly property color c: g.b2Hot ? (g.blinkOn ? "#ff3b3b" : "#5a1a20") : g.acc2
            Text { id: b2v; text: g.ok(g.box2Cfg.key) ? g.fmtBox(g.box2Cfg, g.v(g.box2Cfg.key)) : "--"; color: parent.c
                   font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 44 }
            Text { anchors.baseline: b2v.baseline; text: g.box2Cfg.units || ""; color: parent.c; opacity: 0.8
                   font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 18 }
        }
    }
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
