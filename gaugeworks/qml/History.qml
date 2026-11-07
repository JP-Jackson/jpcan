// Fill-up history: actual MPG (pump) vs the truck's estimate, price, lifetime.
import QtQuick

Rectangle {
    id: h
    property var theme
    property var gw
    readonly property var fuel: gw ? gw.fuel : ({})
    readonly property var life: fuel.lifetime || ({})
    signal close()
    signal editRow(var row)
    signal deleteAll()
    color: "#ee000000"

    function n(v, d) { return (v === null || v === undefined) ? "--" : Number(v).toFixed(d) }
    function day(ts) { return Qt.formatDate(new Date(ts * 1000), "MMM d") }

    MouseArea { anchors.fill: parent; onClicked: {} }

    Rectangle {
        anchors.centerIn: parent
        width: 1000; height: 580; radius: 16
        color: h.theme.colors.background
        border.color: h.theme.colors.panelBorder; border.width: 2

        Text { x: 28; y: 18; text: "Fuel history"; color: h.theme.colors.accent; font.pixelSize: 34; font.bold: true }
        Btn { theme: h.theme; text: "Close"; x: 1000 - width - 24; y: 18; onClicked: h.close() }
        Btn { theme: h.theme; text: "Delete all"; width: 170; x: 1000 - 150 - 24 - 180; y: 18
              fill: h.theme.colors.alarm; visible: (h.fuel.rows || []).length > 0; onClicked: h.deleteAll() }

        Row {  // lifetime summary
            x: 28; y: 80; spacing: 34
            Repeater {
                model: [
                    ["Lifetime MPG", h.n(h.life.mpg, 1)],
                    ["Miles", h.n(h.life.miles, 0)],
                    ["Gallons", h.n(h.life.gallons, 1)],
                    ["Cost", h.life.cost ? "$" + h.n(h.life.cost, 0) : "--"],
                    ["$/mile", h.life.cost_per_mile ? "$" + h.n(h.life.cost_per_mile, 3) : "--"],
                    ["Correction", h.fuel.factor ? "x" + h.n(h.fuel.factor, 2) : "--"]
                ]
                Column {
                    Text { text: modelData[0]; color: h.theme.colors.dim; font.pixelSize: 16 }
                    Text { text: modelData[1]; color: h.theme.colors.text; font.family: h.theme.fonts.digits; font.pixelSize: 28; font.bold: true }
                }
            }
        }

        Row {  // column headers
            id: hdr
            x: 28; y: 160
            Repeater {
                model: [["Date", 110], ["Odometer", 140], ["Miles", 110], ["Gallons", 110], ["MPG", 110], ["Truck est", 120], ["$/gal", 110], ["Total", 110]]
                Text { width: modelData[1]; text: modelData[0]; color: h.theme.colors.dim; font.pixelSize: 17 }
            }
        }
        ListView {
            x: 28; y: 192; width: 944; height: 360
            clip: true
            model: h.fuel.rows || []
            delegate: Item {
                id: rowItem
                width: 944; height: 40
                readonly property var r: modelData
                Rectangle { anchors.fill: parent; color: h.theme.colors.accent; opacity: tap.pressed ? 0.18 : 0 }
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    Text { width: 110; text: h.day(rowItem.r.ts); color: h.theme.colors.text; font.pixelSize: 20 }
                    Text { width: 140; text: h.n(rowItem.r.odo_mi, 0); color: h.theme.colors.text; font.family: h.theme.fonts.digits; font.pixelSize: 20 }
                    Text { width: 110; text: rowItem.r.miles_src === "baseline" ? "start"
                                             : h.n(rowItem.r.miles, 0) + (rowItem.r.miles_src === "estimate" ? "*" : "")
                           color: h.theme.colors.text; font.family: h.theme.fonts.digits; font.pixelSize: 20 }
                    Text { width: 110; text: h.n(rowItem.r.gallons, 1); color: h.theme.colors.text; font.family: h.theme.fonts.digits; font.pixelSize: 20 }
                    Text { width: 110; text: h.n(rowItem.r.mpg, 1); color: h.theme.colors.accent; font.family: h.theme.fonts.digits; font.pixelSize: 22; font.bold: true }
                    Text { width: 120; text: h.n(rowItem.r.est_mpg, 1); color: h.theme.colors.dim; font.family: h.theme.fonts.digits; font.pixelSize: 20 }
                    Text { width: 110; text: rowItem.r.price ? "$" + h.n(rowItem.r.price, 3) : "--"; color: h.theme.colors.text; font.family: h.theme.fonts.digits; font.pixelSize: 20 }
                    Text { width: 110; text: rowItem.r.total ? "$" + h.n(rowItem.r.total, 2) : "--"; color: h.theme.colors.text; font.family: h.theme.fonts.digits; font.pixelSize: 20 }
                }
                MouseArea { id: tap; anchors.fill: parent; onClicked: h.editRow(rowItem.r) }  // tap = edit
            }
            Text {
                visible: (h.fuel.rows || []).length === 0
                text: "No fill-ups yet. Log one from GaugeWorks > Fill-up."
                color: h.theme.colors.dim; font.pixelSize: 20
            }
        }
        Text {
            x: 28; y: 556
            text: "Tap a row to edit or delete it.  * miles estimated (no odometer).  Truck est = fuel-rate average for that tank."
            color: h.theme.colors.dim; font.pixelSize: 14
        }
    }
}
