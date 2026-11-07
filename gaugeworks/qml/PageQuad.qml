// "quad" template (towing): four large gauges, a big gear readout, six tiles.
import QtQuick

Item {
    id: p
    property var theme
    property var pg: ({})
    property string gearKey: ""
    signal pick(string slot, string current)
    readonly property var sl: pg.slots || ({})
    function val(k) { var v = backend.values[k]; return v === undefined ? 0 : v }
    function ok(k) { return k !== undefined && k !== "" && backend.fresh[k] === true }

    Row {
        x: 8; y: 52; spacing: 8
        Repeater {
            model: ["g1", "g2", "g3", "g4"]
            SlotView { width: 246; height: 246; theme: p.theme; cfg: p.sl[modelData] || ({}); slotName: modelData
                       visible: !!p.sl[modelData]; gearKey: p.gearKey; onPick: (s, c) => p.pick(s, c) }
        }
    }
    Rectangle {  // big gear
        x: 8; y: 312; width: 220; height: 280; radius: 12
        visible: p.gearKey !== ""
        color: p.theme.colors.panel; border.color: p.theme.colors.panelBorder
        Text { x: 14; y: 10; text: "GEAR"; color: p.theme.colors.dim; font.pixelSize: 20 }
        Text {
            anchors.centerIn: parent; anchors.verticalCenterOffset: 12
            text: p.ok(p.gearKey) ? p.val(p.gearKey).toFixed(0) : "–"
            color: p.ok(p.gearKey) ? p.theme.colors.text : p.theme.colors.minorTick
            font.family: p.theme.fonts.digits; font.pixelSize: 190; font.bold: true
        }
    }
    Grid {
        x: p.gearKey !== "" ? 240 : 8; y: 312; columns: 3; spacing: 10
        Repeater {
            model: p.pg.tiles || []
            TileSlot { width: p.gearKey !== "" ? 252 : 328; height: 135; theme: p.theme; cfg: modelData
                       index: model.index; onPick: (s, c) => p.pick(s, c) }
        }
    }
}
