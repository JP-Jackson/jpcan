// Dash telltale lamp: turn arrows and headlights. Lit from a channel when the
// vehicle profile provides one (e.g. a body-module Mode 22 DID); otherwise it
// stays dim. Turn signals blink here if the channel only reports "on".
import QtQuick
import QtQuick.Shapes

Item {
    id: tl
    property string kind: "left"        // left | right | low | high
    property string key: ""
    property color onColor: "#2fd36b"
    readonly property bool on: key !== "" && backend.fresh[key] === true && backend.values[key] >= 1
    readonly property bool blinks: kind === "left" || kind === "right"
    property bool phase: true
    Timer { running: tl.on && tl.blinks; interval: 330; repeat: true; onTriggered: tl.phase = !tl.phase
            onRunningChanged: tl.phase = true }
    readonly property bool lit: on && phase
    width: 28; height: 20
    Shape {
        anchors.fill: parent
        visible: tl.blinks
        transform: Scale { origin.x: 14; xScale: tl.kind === "right" ? -1 : 1 }
        ShapePath {
            strokeColor: tl.lit ? tl.onColor : Qt.rgba(0.18, 0.83, 0.42, 0.28); strokeWidth: 1.6
            fillColor: tl.lit ? tl.onColor : "transparent"; joinStyle: ShapePath.RoundJoin
            startX: 1; startY: 10
            PathLine { x: 13; y: 1 } PathLine { x: 13; y: 6 } PathLine { x: 27; y: 6 }
            PathLine { x: 27; y: 14 } PathLine { x: 13; y: 14 } PathLine { x: 13; y: 19 } PathLine { x: 1; y: 10 }
        }
    }
    Shape {
        anchors.fill: parent
        id: lamp
        visible: !tl.blinks
        readonly property real dy: tl.kind === "low" ? 3 : 0
        readonly property color c: tl.lit ? tl.onColor : Qt.rgba(tl.onColor.r, tl.onColor.g, tl.onColor.b, 0.28)
        ShapePath {   // lamp
            strokeColor: lamp.c; strokeWidth: 1.6; fillColor: tl.lit ? tl.onColor : "transparent"
            startX: 15; startY: 2
            PathCubic { x: 15; y: 18; control1X: 28; control1Y: 2; control2X: 28; control2Y: 18 }
            PathLine { x: 15; y: 2 }
        }
        ShapePath {   // beams: angled down for low, straight for high
            strokeColor: lamp.c; strokeWidth: 1.8; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: 11; startY: 5;  PathLine { x: 2; y: 5 + lamp.dy }
            PathMove { x: 11; y: 10 } PathLine { x: 2; y: 10 + lamp.dy }
            PathMove { x: 11; y: 15 } PathLine { x: 2; y: 15 + lamp.dy }
        }
    }
}
