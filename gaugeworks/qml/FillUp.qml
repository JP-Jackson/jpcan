// Fill-up entry: gallons (required) and $/gal (optional) on a big touch keypad.
// Miles come from the truck's odometer in the core; JP always fills to full.
import QtQuick

Rectangle {
    id: f
    property var theme
    property var gw
    property string gallons: ""
    property string price: ""
    property string field: "gallons"
    signal close()
    color: "#ee000000"

    function reset() { gallons = ""; price = ""; field = "gallons" }
    function press(k) {
        var cur = field === "gallons" ? gallons : price
        if (k === "⌫") cur = cur.slice(0, -1)
        else if (k === ".") { if (cur.indexOf(".") < 0) cur = (cur === "" ? "0" : cur) + "." }
        else if (cur.length < 6) cur = cur + k
        if (field === "gallons") gallons = cur; else price = cur
    }
    onVisibleChanged: if (visible) reset()

    MouseArea { anchors.fill: parent; onClicked: {} }

    Rectangle {
        anchors.centerIn: parent
        width: 760; height: 580; radius: 16
        color: f.theme.colors.background
        border.color: f.theme.colors.panelBorder; border.width: 2

        Text {
            x: 28; y: 18; text: "Fill-up"
            color: f.theme.colors.accent; font.pixelSize: 34; font.bold: true
        }
        Text {
            x: 28; y: 62
            text: "Filled to full. Miles come from the truck's odometer."
            color: f.theme.colors.dim; font.pixelSize: 17
        }

        Column {
            x: 28; y: 110; spacing: 14
            Repeater {
                model: [["gallons", "Gallons"], ["price", "$ per gallon"]]
                Rectangle {
                    width: 330; height: 84; radius: 10
                    color: f.theme.colors.panel
                    border.color: f.field === modelData[0] ? f.theme.colors.accent : f.theme.colors.panelBorder
                    border.width: f.field === modelData[0] ? 3 : 1
                    Text { x: 14; y: 8; text: modelData[1]; color: f.theme.colors.dim; font.pixelSize: 17 }
                    Text {
                        anchors.right: parent.right; anchors.rightMargin: 16
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 8
                        text: (modelData[0] === "gallons" ? f.gallons : f.price) || "-"
                        color: f.theme.colors.text
                        font.family: f.theme.fonts.digits; font.pixelSize: 40; font.bold: true
                    }
                    MouseArea { anchors.fill: parent; onClicked: f.field = modelData[0] }
                }
            }
            Text {
                width: 330
                visible: f.gallons !== "" && f.price !== ""
                text: "Total  $" + (parseFloat(f.gallons) * parseFloat(f.price)).toFixed(2)
                color: f.theme.colors.text; font.pixelSize: 24; font.bold: true
            }
        }

        Grid {
            x: 390; y: 100; columns: 3; spacing: 10
            Repeater {
                model: ["7", "8", "9", "4", "5", "6", "1", "2", "3", ".", "0", "⌫"]
                Btn { theme: f.theme; width: 106; height: 76; text: modelData; onClicked: f.press(modelData) }
            }
        }

        Row {
            x: 28; y: 580 - 84; spacing: 14
            Btn {
                theme: f.theme; width: 200; text: "Save"
                active: f.gallons !== ""
                onClicked: {
                    var g = parseFloat(f.gallons)
                    var p = f.price === "" ? 0 : parseFloat(f.price)
                    f.gw.fillup(isNaN(g) ? 0 : g, isNaN(p) ? 0 : p)
                    if (g >= 0.5) f.close()
                }
            }
            Btn { theme: f.theme; width: 160; text: "Cancel"; onClicked: f.close() }
        }
    }
}
