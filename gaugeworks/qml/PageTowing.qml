// "towing" page (P3): big center gauge (speed, RPM and boost rings, RPM/boost
// window, gear) between eight panels with range bars. Background texture and
// the two accent colors come from Settings. Anything at or over its red line
// blinks at 3 Hz. Every reading except the RPM and boost rings can be changed in edit mode.
// Slots: center, ring, inner, box1, box2, l1-l4, r1-r4 (r4 is usually VGT).
import QtQuick
import QtQuick.Shapes

Item {
    id: p
    property var theme
    property var pg: ({})
    property string gearKey: ""
    signal pick(string slot, string current)
    signal resetAsk(string kind)
    readonly property var sl: pg.slots || ({})
    readonly property color acc: backend.accent
    readonly property color acc2: backend.accent2

    // 3 Hz blink shared by every reading that's over its red line
    property bool blinkOn: true
    Timer { interval: 167; running: true; repeat: true; onTriggered: p.blinkOn = !p.blinkOn }

    // ---- background: texture (setting), darkened a little so numbers stay readable
    Rectangle { anchors.fill: parent; color: "#040506" }
    Image {
        anchors.fill: parent
        visible: backend.backgroundUrl !== ""
        source: backend.backgroundUrl
        fillMode: backend.background === "brushed" ? Image.PreserveAspectCrop : Image.Tile
        smooth: false
    }
    Rectangle { anchors.fill: parent; color: "#000000"
                opacity: backend.background === "carbon" || backend.background === "black" ? 0 : 0.35 }
    Shape {   // accent light spill behind the gauge
        anchors.fill: parent
        ShapePath {
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: 512; centerY: 306; centerRadius: 330; focalX: 512; focalY: 306
                GradientStop { position: 0; color: Qt.rgba(p.acc.r, p.acc.g, p.acc.b, 0.14) }
                GradientStop { position: 1; color: "transparent" }
            }
            startX: 0; startY: 0
            PathLine { x: 1024; y: 0 } PathLine { x: 1024; y: 600 } PathLine { x: 0; y: 600 } PathLine { x: 0; y: 0 }
        }
    }

    TowGauge {
        x: 512 - width / 2; y: 306 - height / 2
        ringCfg: p.sl.ring || ({}); innerCfg: p.sl.inner || ({}); centerCfg: p.sl.center || ({})
        box1Cfg: p.sl.box1 || ({}); box2Cfg: p.sl.box2 || ({}); fuelCfg: p.sl.fuel || ({})
        gearKey: p.gearKey; acc: p.acc; acc2: p.acc2; blinkOn: p.blinkOn
        onHeld: function(slot) { p.pick(slot, (p.sl[slot] || {}).key || "") }
    }

    Repeater {
        model: ["l1", "l2", "l3", "l4", "r1", "r2", "r3", "r4"]
        TowPanel {
            required property string modelData
            required property int index
            readonly property bool isLeft: modelData[0] === "l"
            x: isLeft ? 6 : 1018 - width
            y: 56 + (index % 4) * 135
            visible: !!p.sl[modelData]
            cfg: p.sl[modelData] || ({})
            leftSide: isLeft; acc: p.acc; blinkOn: p.blinkOn
            onHeld: p.pick(modelData, cfg.key || "")
        }
    }
}
