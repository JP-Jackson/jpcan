// Fill-up entry (new) and fill-up editing (edit) on a big touch keypad.
// New: gallons + $/gal; miles come from the truck's odometer in the core.
// Edit: gallons, $/gal, odometer and date of one history line. The core
// recalculates miles and MPG for this and the following fill-up.
import QtQuick

Rectangle {
    id: f
    property var theme
    property var gw
    property string mode: "new"         // "new" | "edit"
    property int rowId: -1
    property string gallons: ""
    property string price: ""
    property string odo: ""
    property string date: ""            // YYYYMMDD while typing
    property string field: "gallons"
    signal close()
    signal deleteRow(int id)
    color: "#ee000000"

    readonly property var fields: mode === "edit"
        ? [["gallons", "Gallons"], ["price", "$ per gallon"], ["odo", "Odometer (mi)"], ["date", "Date (YYYYMMDD)"]]
        : [["gallons", "Gallons"], ["price", "$ per gallon"]]

    function openNew() { mode = "new"; rowId = -1; gallons = ""; price = ""; odo = ""; date = ""; field = "gallons"; visible = true }
    function openEdit(r) {
        mode = "edit"; rowId = r.id
        gallons = r.gallons !== null && r.gallons !== undefined ? String(r.gallons) : ""
        price = r.price ? String(r.price) : ""
        odo = r.odo_mi ? String(Math.round(r.odo_mi)) : ""
        date = Qt.formatDate(new Date(r.ts * 1000), "yyyyMMdd")
        field = "gallons"; visible = true
    }
    function get(k) { return k === "gallons" ? gallons : k === "price" ? price : k === "odo" ? odo : date }
    function put(k, v) { if (k === "gallons") gallons = v; else if (k === "price") price = v; else if (k === "odo") odo = v; else date = v }
    function shown(k) {
        var v = get(k)
        if (k === "date" && v.length === 8) return v.slice(0, 4) + "-" + v.slice(4, 6) + "-" + v.slice(6)
        return v || "-"
    }
    function press(k) {
        var cur = get(field)
        var decimals = field === "gallons" || field === "price"
        var maxLen = field === "date" ? 8 : field === "odo" ? 7 : 6
        if (k === "⌫") cur = cur.slice(0, -1)
        else if (k === ".") { if (decimals && cur.indexOf(".") < 0) cur = (cur === "" ? "0" : cur) + "." }
        else if (cur.length < maxLen) cur = cur + k
        put(field, cur)
    }
    function num(s) { var v = parseFloat(s); return isNaN(v) ? 0 : v }
    function save() {
        if (mode === "new") {
            f.gw.fillup(num(gallons), num(price))
            if (num(gallons) >= 0.5) f.close()
            return
        }
        var d = date.length === 8 ? date.slice(0, 4) + "-" + date.slice(4, 6) + "-" + date.slice(6) : ""
        f.gw.fuelEdit(rowId, num(gallons), num(price), num(odo), d)
        f.close()
    }

    MouseArea { anchors.fill: parent; onClicked: {} }

    Rectangle {
        anchors.centerIn: parent
        width: 760; height: 580; radius: 16
        color: f.theme.colors.background
        border.color: f.theme.colors.panelBorder; border.width: 2

        Text {
            x: 28; y: 18; text: f.mode === "edit" ? "Edit fill-up" : "Fill-up"
            color: f.theme.colors.accent; font.pixelSize: 34; font.bold: true
        }
        Text {
            x: 28; y: 62
            text: f.mode === "edit" ? "Miles and MPG are recalculated from the odometer."
                                    : "Filled to full. Miles come from the truck's odometer."
            color: f.theme.colors.dim; font.pixelSize: 17
        }

        Column {
            x: 28; y: 100; spacing: f.mode === "edit" ? 8 : 14
            Repeater {
                model: f.fields
                Rectangle {
                    width: 330; height: f.mode === "edit" ? 74 : 84; radius: 10
                    color: f.theme.colors.panel
                    border.color: f.field === modelData[0] ? f.theme.colors.accent : f.theme.colors.panelBorder
                    border.width: f.field === modelData[0] ? 3 : 1
                    Text { x: 14; y: 6; text: modelData[1]; color: f.theme.colors.dim; font.pixelSize: 16 }
                    Text {
                        anchors.right: parent.right; anchors.rightMargin: 16
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 6
                        text: f.shown(modelData[0])
                        color: f.theme.colors.text
                        font.family: f.theme.fonts.digits; font.pixelSize: 36; font.bold: true
                    }
                    MouseArea { anchors.fill: parent; onClicked: f.field = modelData[0] }
                }
            }
            Text {
                width: 330
                visible: f.gallons !== "" && f.price !== ""
                text: "Total  $" + (f.num(f.gallons) * f.num(f.price)).toFixed(2)
                color: f.theme.colors.text; font.pixelSize: 22; font.bold: true
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
            Btn { theme: f.theme; width: 180; text: "Save"; active: f.gallons !== ""; onClicked: f.save() }
            Btn {
                theme: f.theme; width: 200; text: "Delete line"
                visible: f.mode === "edit"
                fill: f.theme.colors.alarm
                onClicked: f.deleteRow(f.rowId)
            }
            Btn { theme: f.theme; width: 160; text: "Cancel"; onClicked: f.close() }
        }
    }
}
