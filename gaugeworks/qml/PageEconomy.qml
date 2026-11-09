// "economy" template: big MPG numbers, fuel gauge, last fill-up, pump buttons.
import QtQuick

Item {
    id: p
    property var theme
    property var pg: ({})
    property string gearKey: ""
    signal pick(string slot, string current)
    signal resetAsk(string kind)
    signal openFillup()
    signal openHistory()
    readonly property var sl: pg.slots || ({})
    readonly property var fuel: backend.fuel || ({})
    readonly property var last: (fuel.rows && fuel.rows.length) ? fuel.rows[0] : null
    function val(k) { var v = backend.values[k]; return v === undefined ? 0 : v }
    function ok(k) { return k !== undefined && k !== "" && backend.fresh[k] === true }
    function n(v, d) { return (v === null || v === undefined) ? "--" : Number(v).toFixed(d) }

    Grid {
        x: 8; y: 52; columns: 2; spacing: 10
        Repeater {
            model: p.pg.tiles || []
            Rectangle {
                width: 300; height: 262; radius: 14
                readonly property var c: modelData
                color: p.theme.colors.panel; border.color: p.theme.colors.panelBorder
                Text { x: 18; y: 12; text: c.label + (c.econ && backend.econCorrected && backend.econFactor > 0 ? "  corr" : "")
                       color: p.theme.colors.dim; font.pixelSize: 24 }
                Text {
                    anchors.centerIn: parent; anchors.verticalCenterOffset: 10
                    text: p.ok(c.key) ? p.val(c.key).toFixed(1) : "--"
                    color: p.theme.colors.text; font.family: p.theme.fonts.digits
                    font.pixelSize: 104; font.bold: true
                }
                Text { anchors.right: parent.right; anchors.rightMargin: 16; anchors.bottom: parent.bottom
                       anchors.bottomMargin: 10; text: c.units; color: p.theme.colors.dim; font.pixelSize: 22 }
                MouseArea { anchors.fill: parent; pressAndHoldInterval: 600
                            onPressAndHold: p.pick("tile" + index, c.key)
                            onClicked: if (backend.editMode) p.pick("tile" + index, c.key)
                                       else if (c.key === "econ_trip" || c.key === "econ_last")
                                           p.resetAsk(c.key === "econ_trip" ? "trip" : "roll") }
            }
        }
    }
    SlotView { x: 640; y: 52; width: 240; height: 240; theme: p.theme; cfg: p.sl.gauge || ({}); slotName: "gauge"
               visible: !!p.sl.gauge; onPick: (s, c) => p.pick(s, c) }
    Rectangle {
        x: 630; y: 302; width: 386; height: 210; radius: 14
        color: p.theme.colors.panel; border.color: p.theme.colors.panelBorder
        Column {
            x: 18; y: 12; spacing: 6
            Text { text: "Last fill-up"; color: p.theme.colors.dim; font.pixelSize: 20 }
            Text {
                text: p.last ? (p.last.mpg ? p.n(p.last.mpg, 1) + " mpg" : "baseline") : "none yet"
                color: p.theme.colors.accent; font.family: p.theme.fonts.digits; font.pixelSize: 40; font.bold: true
            }
            Text {
                text: p.last ? (p.n(p.last.miles, 0) + " mi  " + p.n(p.last.gallons, 1) + " gal" +
                                (p.last.total ? "  $" + p.n(p.last.total, 2) : "")) : ""
                color: p.theme.colors.text; font.pixelSize: 20
            }
            Text {
                text: "Lifetime " + p.n((p.fuel.lifetime || {}).mpg, 1) + " mpg" +
                      ((p.fuel.lifetime || {}).cost_per_mile ? "   $" + p.n(p.fuel.lifetime.cost_per_mile, 3) + "/mi" : "")
                color: p.theme.colors.dim; font.pixelSize: 20
            }
        }
    }
    Row {
        x: 630; y: 524; spacing: 10
        Btn { theme: p.theme; width: 188; height: 64; text: "Fill-up"; active: true; onClicked: p.openFillup() }
        Btn { theme: p.theme; width: 188; height: 64; text: "History"; onClicked: p.openHistory() }
    }
}
