// Pick the two accent colors: drag around the hue ring for any color, set the
// brightness, or tap a quick pick. Main accent: frames, RPM pointer, bars and
// glow. Second accent: boost pointer and scale. Red, amber and green keep their
// meaning (danger, warning, OK) and aren't affected.
import QtQuick

Rectangle {
    id: cp
    property var theme
    signal close()
    color: "#ee000000"
    property int which: 0                 // 0 = main accent, 1 = second accent
    property real hue: 0.55
    property real light: 0.58
    readonly property color picked: Qt.hsla(hue, 0.95, light, 1)
    function load() {
        var c = Qt.color(which ? backend.accent2 : backend.accent)
        hue = c.hslHue < 0 ? 0 : c.hslHue
        light = Math.max(0.25, Math.min(0.85, c.hslLightness))
    }
    onVisibleChanged: if (visible) load()
    onWhichChanged: load()
    function hex(c) { function h(x) { var s = Math.round(x * 255).toString(16); return s.length < 2 ? "0" + s : s }
                      return "#" + h(c.r) + h(c.g) + h(c.b) }
    function apply() { backend.setAccent(cp.which, cp.hex(cp.picked)) }

    MouseArea { anchors.fill: parent; onClicked: {} }

    Rectangle {
        id: panel
        anchors.centerIn: parent
        width: 880; height: 520; radius: 18
        color: "#0b131d"; border.color: cp.picked; border.width: 2

        Text { x: 32; y: 26; text: "Colors"; color: "#eef3f8"; font.pixelSize: 32; font.bold: true }

        Column {
            x: 32; y: 84; spacing: 14
            Repeater {
                model: [["Main accent", backend.accent], ["Second accent", backend.accent2]]
                Rectangle {
                    width: 250; height: 70; radius: 12
                    color: index === cp.which ? "#134a74" : "#111c29"
                    border.color: index === cp.which ? cp.picked : "#22364d"; border.width: index === cp.which ? 3 : 1.5
                    Rectangle { x: 18; anchors.verticalCenter: parent.verticalCenter; width: 36; height: 36; radius: 18
                                color: index === cp.which ? cp.picked : modelData[1]; border.color: "#ffffff"; border.width: 2 }
                    Text { x: 68; anchors.verticalCenter: parent.verticalCenter; text: modelData[0]
                           color: "#eef3f8"; font.pixelSize: 24; font.bold: true }
                    MouseArea { anchors.fill: parent; onClicked: { cp.apply(); cp.which = index } }
                }
            }
            Text { width: 250; wrapMode: Text.WordWrap; color: "#8796a8"; font.pixelSize: 18
                   text: "Main: frames, RPM pointer, bars, glow.\nSecond: boost pointer and scale.\n\nRed, amber and green stay fixed: they mean danger, warning, OK." }
        }

        // hue ring
        Item {
            id: ring
            x: 330; y: 80; width: 330; height: 330
            readonly property real r: 150
            Canvas {
                anchors.fill: parent
                onPaint: {
                    var c = getContext("2d"); c.reset()
                    var cx = width / 2, cy = height / 2
                    for (var a = 0; a < 360; a += 2) {
                        c.beginPath(); c.lineWidth = 40
                        c.strokeStyle = Qt.hsla(a / 360, 0.95, 0.58, 1)
                        c.arc(cx, cy, ring.r, (a - 90) * Math.PI / 180, (a - 87.5) * Math.PI / 180); c.stroke()
                    }
                }
            }
            Rectangle {   // preview swatch with the hex value
                anchors.centerIn: parent; width: 196; height: 196; radius: 98; color: cp.picked
                Text { anchors.centerIn: parent; text: cp.hex(cp.picked).toUpperCase()
                       color: cp.light > 0.6 ? "#000000" : "#ffffff"; font.pixelSize: 28; font.bold: true }
            }
            Rectangle {   // knob
                readonly property real a: (cp.hue * 360 - 90) * Math.PI / 180
                x: ring.width / 2 + ring.r * Math.cos(a) - width / 2; y: ring.height / 2 + ring.r * Math.sin(a) - height / 2
                width: 52; height: 52; radius: 26; color: Qt.hsla(cp.hue, 0.95, 0.58, 1); border.color: "#ffffff"; border.width: 5
            }
            MouseArea {
                anchors.fill: parent
                function setFrom(m) {
                    var dx = m.x - width / 2, dy = m.y - height / 2
                    if (Math.sqrt(dx * dx + dy * dy) < 90) return
                    var deg = Math.atan2(dy, dx) * 180 / Math.PI + 90
                    cp.hue = ((deg % 360) + 360) % 360 / 360
                }
                onPressed: function(m) { setFrom(m) }
                onPositionChanged: function(m) { setFrom(m) }
            }
        }
        Text { x: ring.x; width: ring.width; y: 420; horizontalAlignment: Text.AlignHCenter
               text: "Drag around the ring for any color"; color: "#8796a8"; font.pixelSize: 18 }

        // brightness
        Text { x: 690; y: 72; text: "Brightness"; color: "#8796a8"; font.pixelSize: 18 }
        Rectangle {
            id: bright
            x: 700; y: 100; width: 48; height: 300; radius: 12; border.color: "#22364d"; border.width: 2
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.hsla(cp.hue, 0.95, 0.85, 1) }
                GradientStop { position: 0.5; color: Qt.hsla(cp.hue, 0.95, 0.55, 1) }
                GradientStop { position: 1; color: Qt.hsla(cp.hue, 0.95, 0.25, 1) }
            }
            Rectangle { x: -8; width: 64; height: 16; radius: 6; color: "#ffffff"; border.color: "#000000"; border.width: 2
                        y: (0.85 - cp.light) / 0.6 * bright.height - 8 }
            MouseArea {
                anchors.fill: parent; anchors.margins: -12
                function setFrom(m) { cp.light = Math.max(0.25, Math.min(0.85, 0.85 - (m.y - 12) / bright.height * 0.6)) }
                onPressed: function(m) { setFrom(m) }
                onPositionChanged: function(m) { setFrom(m) }
            }
        }

        // quick picks
        Grid {
            x: 776; y: 100; columns: 2; spacing: 12
            Repeater {
                model: [[0.54, 0.58], [0.6, 0.6], [0.4, 0.55], [0.08, 0.56], [0.75, 0.62], [0.88, 0.6], [0, 0.92], [0.14, 0.55]]
                Rectangle {
                    width: 40; height: 40; radius: 20
                    color: Qt.hsla(modelData[0], modelData[1] > 0.9 ? 0.2 : 0.95, modelData[1], 1)
                    border.color: "#22364d"; border.width: 2
                    MouseArea { anchors.fill: parent; anchors.margins: -4
                                onClicked: { cp.hue = modelData[0]; cp.light = Math.min(0.85, modelData[1]) } }
                }
            }
        }
        Text { x: 776; y: 324; text: "Quick picks"; color: "#8796a8"; font.pixelSize: 18 }

        Btn { theme: cp.theme; x: 32; y: 446; width: 230; height: 56; text: "Reset to default"
              onClicked: { backend.resetColors(); cp.load() } }
        Btn { theme: cp.theme; x: 560; y: 446; width: 130; height: 56; text: "Cancel"; onClicked: cp.close() }
        Rectangle {
            x: 706; y: 446; width: 150; height: 56; radius: 12; color: cp.picked
            Text { anchors.centerIn: parent; text: "Done"; color: cp.light > 0.6 ? "#000000" : "#ffffff"; font.pixelSize: 26; font.bold: true }
            MouseArea { anchors.fill: parent; onClicked: { cp.apply(); cp.close() } }
        }
    }
}
