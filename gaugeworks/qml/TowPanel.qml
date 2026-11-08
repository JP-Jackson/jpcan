// Towing page side panel: beveled pentagon (arrow side toward the center),
// label, big value, units with this drive's min-max, and a RangeBar on the
// straight side. A dual slot (VGT) shows CMD, ACT and DIFF instead.
// Press and hold to change what it shows.
import QtQuick
import QtQuick.Shapes

Item {
    id: tp
    property var cfg: ({})
    property bool leftSide: true
    property color acc: "#29c4ff"
    property bool blinkOn: true
    signal held()
    width: 228; height: 126

    readonly property string key: cfg.key || ""
    readonly property bool dual: cfg.dual === true
    function v(k) { var x = backend.values[k]; return x === undefined ? 0 : x }
    function ok(k) { return !!k && backend.fresh[k] === true }
    readonly property real scale_: cfg.scale ? cfg.scale : 1
    readonly property int dec: scale_ !== 1 ? 1 : (cfg.decimals !== undefined ? cfg.decimals : 0)
    function fmt(x) { return (x * scale_).toFixed(dec) }
    function fmtScale(x) { var s = x * scale_; return Math.abs(s - Math.round(s)) < 1e-6 ? Math.round(s).toString() : s.toFixed(1) }
    readonly property string unitText: {
        var u = cfg.units || ""
        if (scale_ === 0.001 && u.indexOf("psi") === 0) return "KPSI"
        return (cfg.scaleLabel ? cfg.scaleLabel.replace("x", "×") + " " : "") + u.toUpperCase()
    }
    readonly property bool valid: dual ? ok(cfg.actual) : ok(key)
    readonly property real value: v(key)
    readonly property bool hot: !dual && valid && !isNaN(cfg.alarm) && value >= cfg.alarm
    readonly property real lo: backend.lo[key] === undefined ? NaN : backend.lo[key]
    readonly property real hi: backend.hi[key] === undefined ? NaN : backend.hi[key]

    // pentagon outline (arrow side toward the center)
    readonly property var pts: leftSide ? [[0, 0], [width - 24, 0], [width, height / 2], [width - 24, height], [0, height]]
                                    : [[24, 0], [width, 0], [width, height], [24, height], [0, height / 2]]
    component Poly: ShapePath {
        property real dx: 0
        property real dy: 0
        property real k: 1
        readonly property real mx: tp.width / 2
        readonly property real my: tp.height / 2
        function px(i) { return mx + (tp.pts[i][0] - mx) * k + dx }
        function py(i) { return my + (tp.pts[i][1] - my) * k + dy }
        startX: px(0); startY: py(0)
        PathLine { x: px(1); y: py(1) }
        PathLine { x: px(2); y: py(2) }
        PathLine { x: px(3); y: py(3) }
        PathLine { x: px(4); y: py(4) }
        PathLine { x: px(0); y: py(0) }
    }
    Shape {   // soft drop shadow, panel body, gloss, accent edge, inner bevel
        anchors.fill: parent
        Poly { dy: 9; strokeColor: "transparent"; fillColor: Qt.rgba(0, 0, 0, 0.35) }
        Poly { dy: 5; strokeColor: "transparent"; fillColor: Qt.rgba(0, 0, 0, 0.45) }
        Poly {
            strokeColor: "transparent"
            fillGradient: LinearGradient {
                x1: 0; y1: 0; x2: 0; y2: tp.height
                GradientStop { position: 0; color: "#18222e" }
                GradientStop { position: 0.55; color: "#0a0f15" }
                GradientStop { position: 1; color: "#04070a" }
            }
        }
        Poly {
            strokeColor: "transparent"
            fillGradient: LinearGradient {
                x1: 0; y1: 0; x2: 0; y2: tp.height
                GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0.13) }
                GradientStop { position: 0.48; color: Qt.rgba(1, 1, 1, 0.025) }
                GradientStop { position: 0.5; color: "transparent" }
            }
        }
        Poly { strokeColor: tp.acc; strokeWidth: 2.5; fillColor: "transparent" }
        Poly { k: 0.95; strokeColor: Qt.rgba(1, 1, 1, 0.22); strokeWidth: 1.2; fillColor: "transparent" }
    }

    readonly property real bx: leftSide ? 20 : width - 44
    readonly property real cx: leftSide ? width / 2 + 28 : width / 2 - 28

    component Skew: Item {   // big italic-style digits with a raised shadow
        property alias text: t.text
        property alias color: t.color
        property int size: 62
        width: t.implicitWidth; height: t.implicitHeight
        transform: Matrix4x4 { matrix: Qt.matrix4x4(1, -0.158, 0, 0.158 * t.height * 0.8, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1) }
        Text { x: 0; y: 3; text: t.text; color: "#000000"; opacity: 0.8; font: t.font }
        Text { id: t; font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: parent.size }
    }

    // ---- single reading
    Item {
        visible: !tp.dual
        anchors.fill: parent
        Text {
            x: tp.cx - width / 2; y: 12
            text: (tp.cfg.label || tp.key || "--").toUpperCase()
            color: "#dbe7f2"; font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 24; font.letterSpacing: 2
        }
        Skew {
            x: tp.cx - width / 2; y: 36; size: 62
            text: tp.valid ? tp.fmt(tp.value) : "--"
            color: tp.hot ? (tp.blinkOn ? "#ff3b3b" : "#5a1a20") : "#eef3f8"
        }
        Text {
            x: tp.cx - width / 2; y: 102
            text: tp.unitText + (!isNaN(tp.lo) && !isNaN(tp.hi) ? "  ·  " + tp.fmt(tp.lo) + "–" + tp.fmt(tp.hi) : "")
            color: "#8796a8"; font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 17
        }
        RangeBar {
            x: tp.bx; y: 14; width: 24; height: tp.height - 28
            visible: !!tp.cfg.max
            leftSide: tp.leftSide; acc: tp.acc; blinkOn: tp.blinkOn
            minV: tp.cfg.min || 0; maxV: tp.cfg.max || 100; red: tp.cfg.alarm === undefined ? NaN : tp.cfg.alarm
            value: tp.value; valid: tp.valid; lo: tp.lo; hi: tp.hi
            fmtMin: tp.fmtScale(tp.cfg.min || 0); fmtMax: tp.fmtScale(tp.cfg.max || 100)
        }
    }

    // ---- dual (VGT): commanded, actual and the difference
    Item {
        visible: tp.dual
        anchors.fill: parent
        readonly property real cmd: tp.v(tp.cfg.desired)
        readonly property real act: tp.v(tp.cfg.actual)
        readonly property real diff: act - cmd
        readonly property color dc: Math.abs(diff) >= 10 ? "#ff3b3b" : Math.abs(diff) >= 5 ? "#ffb340" : "#38d97a"
        Text { x: (tp.leftSide ? 46 : 22) + 78 - width / 2; y: 12; text: (tp.cfg.label || "VGT") + " VANE"
               color: "#dbe7f2"; font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 22; font.letterSpacing: 2 }
        Row {
            x: tp.leftSide ? 48 : 28; y: 42; spacing: 5
            Text { anchors.baseline: c1.baseline; text: "CMD"; color: "#8796a8"; font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 17 }
            Text { id: c1; text: tp.ok(tp.cfg.desired) ? parent.parent.cmd.toFixed(0) : "--"; color: "#eef3f8"
                   font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 30 }
            Item { width: 2; height: 1 }
            Text { anchors.baseline: c1.baseline; text: "ACT"; color: "#8796a8"; font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 17 }
            Text { text: tp.ok(tp.cfg.actual) ? parent.parent.act.toFixed(0) : "--"; color: "#eef3f8"
                   font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 30 }
        }
        Rectangle { x: tp.leftSide ? 50 : 30; y: 82; width: 140; height: 1; color: "#22364d" }
        Text { x: tp.leftSide ? 50 : 30; y: 96; text: "DIFF"; color: "#8796a8"; font.family: "Barlow Semi Condensed Medium"; font.pixelSize: 17 }
        Skew {
            x: (tp.leftSide ? 50 : 30) + 140 - width; y: 76; size: 44
            readonly property real d: parent.diff
            text: tp.valid && tp.ok(tp.cfg.desired) ? (d > 0 ? "+" : "") + d.toFixed(0) + "%" : "--"
            color: parent.dc
        }
        RangeBar {
            x: tp.bx; y: 14; width: 24; height: tp.height - 28
            leftSide: tp.leftSide; acc: tp.acc; blinkOn: tp.blinkOn; showScale: false
            minV: 0; maxV: 100; value: parent.act; valid: tp.valid
            cmd: tp.ok(tp.cfg.desired) ? parent.cmd : NaN
        }
    }

    MouseArea { anchors.fill: parent; pressAndHoldInterval: 600; onPressAndHold: tp.held() }
}
