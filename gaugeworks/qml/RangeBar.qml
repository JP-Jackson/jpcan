// Premium vertical bar (towing page panels): outline frame on the outer side,
// red zone fading down from the top, fill fading down from a bright top edge,
// pointer at the current value, scale min/max, and this drive's min-max as a
// bracket outside the frame. Frame and scale are painted once; the fill and
// pointer are plain items so they move on the GPU.
import QtQuick
import QtQuick.Shapes

Item {
    id: b
    property real minV: 0
    property real maxV: 100
    property real red: NaN          // red line (NaN = none)
    property real value: 0
    property bool valid: false
    property real lo: NaN           // this drive's min / max
    property real hi: NaN
    property real cmd: NaN          // optional second marker (VGT commanded)
    property bool leftSide: true        // frame on the left (left-hand panels)
    property bool showScale: true
    property color acc: "#29c4ff"
    property bool blinkOn: true
    property string fmtMin: ""
    property string fmtMax: ""
    width: 24; height: 100

    readonly property bool hot: valid && !isNaN(red) && value >= red
    readonly property color col: hot ? "#ff3b3b" : acc
    function yOf(v) { return height - height * Math.max(0, Math.min(1, (v - minV) / Math.max(1e-9, maxV - minV))) }
    property real shown: valid ? value : minV
    Behavior on shown { SmoothedAnimation { velocity: Math.max(1, (b.maxV - b.minV) * 1.2) } }

    // bar body
    Rectangle { anchors.fill: parent; color: "#05080c" }
    Rectangle {   // red zone, fading down
        visible: !isNaN(b.red) && b.red < b.maxV
        width: b.width; y: 0; height: Math.min(b.height, b.yOf(b.red) + 18)
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.rgba(1, 0.23, 0.36, 0.85) }
            GradientStop { position: 1; color: Qt.rgba(1, 0.23, 0.36, 0) }
        }
    }
    Rectangle {
        visible: !isNaN(b.red) && b.red < b.maxV
        x: b.leftSide ? b.width - 2 : 0; width: 2.5; height: b.yOf(b.red); color: "#ff4d6a"
    }
    Rectangle {   // fill
        visible: b.valid
        width: b.width; y: b.yOf(b.shown); height: b.height - y
        opacity: b.hot && !b.blinkOn ? 0.2 : 1
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.lighter(b.col, 1.35) }
            GradientStop { position: 0.12; color: b.col }
            GradientStop { position: 0.6; color: Qt.darker(b.col, 1.9) }
            GradientStop { position: 1; color: Qt.darker(b.col, 3.6) }
        }
    }
    Repeater {   // faint dividers
        model: 3
        Rectangle { y: b.height * (index + 1) / 4; width: b.width; height: 1; color: Qt.rgba(1, 1, 1, 0.12) }
    }
    Rectangle {   // tube shading across the bar
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(0, 0, 0, 0.55) }
            GradientStop { position: 0.32; color: Qt.rgba(1, 1, 1, 0.16) }
            GradientStop { position: 0.45; color: Qt.rgba(1, 1, 1, 0.03) }
            GradientStop { position: 1; color: Qt.rgba(0, 0, 0, 0.5) }
        }
    }
    Rectangle {   // commanded marker (dashed look: two short dashes)
        visible: !isNaN(b.cmd)
        x: -3; y: b.yOf(b.cmd) - 1.5; width: b.width + 6; height: 3; color: "transparent"
        Row { spacing: 3; Repeater { model: 5; Rectangle { width: 4; height: 3; color: "#ffffff" } } }
    }

    // frame (outer side), scale numbers and the drive bracket: painted once
    Canvas {
        x: -40; y: -10; width: b.width + 80; height: b.height + 20
        property var deps: [b.leftSide, b.minV, b.maxV, b.showScale, b.fmtMin, b.fmtMax]
        onDepsChanged: requestPaint()
        onPaint: {
            var c = getContext("2d"); c.reset()
            var ox = 40, oy = 10, w = b.width, h = b.height
            var fx = b.leftSide ? ox - 5 : ox + w + 5, cap = b.leftSide ? ox + w + 6 : ox - 6, dir = b.leftSide ? 8 : -8
            c.strokeStyle = "#e9f1f8"; c.lineWidth = 2.5; c.lineCap = "round"
            c.beginPath(); c.moveTo(cap, oy - 5); c.lineTo(fx + dir, oy - 5)
            c.quadraticCurveTo(fx, oy - 5, fx, oy + 3); c.lineTo(fx, oy + h - 3)
            c.quadraticCurveTo(fx, oy + h + 5, fx + dir, oy + h + 5); c.lineTo(cap, oy + h + 5); c.stroke()
            if (b.showScale) {
                c.fillStyle = "#dbe7f2"; c.font = "17px 'Barlow Semi Condensed Medium'"
                c.textAlign = b.leftSide ? "left" : "right"; c.textBaseline = "middle"
                var lx = b.leftSide ? ox + w + 14 : ox - 14
                c.fillText(b.fmtMax, lx, oy + 2); c.fillText(b.fmtMin, lx, oy + h - 2)
            }
        }
    }
    Item {   // this drive's min-max bracket
        visible: b.valid && !isNaN(b.lo) && !isNaN(b.hi)
        readonly property real yh: b.yOf(b.hi)
        readonly property real yl: b.yOf(b.lo)
        x: b.leftSide ? -18 : b.width + 13; y: yh; width: 6; height: Math.max(2, yl - yh)
        Rectangle { x: b.leftSide ? 0 : 3.5; width: 2.5; height: parent.height; color: Qt.lighter(b.acc, 1.5) }
        Rectangle { width: 6; height: 2.5; color: Qt.lighter(b.acc, 1.5) }
        Rectangle { y: parent.height - 2.5; width: 6; height: 2.5; color: Qt.lighter(b.acc, 1.5) }
    }
    Shape {   // pointer wedge toward the scale numbers
        visible: b.valid
        x: b.leftSide ? 2 : b.width - 2; y: b.yOf(b.shown)
        opacity: b.hot && !b.blinkOn ? 0.25 : 1
        ShapePath {
            strokeColor: "transparent"; fillColor: b.hot ? "#ff8a8a" : Qt.lighter(b.acc, 1.5)
            startX: 0; startY: -5
            PathLine { x: b.leftSide ? b.width + 10 : -(b.width + 10); y: 0 }
            PathLine { x: 0; y: 5 }
            PathLine { x: 0; y: -5 }
        }
    }
}
