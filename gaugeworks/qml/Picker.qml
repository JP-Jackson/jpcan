// Choose what a slot or tile shows. Saved per vehicle and page.
import QtQuick

Rectangle {
    id: pk
    property var theme
    property var channels: []
    property string pageName: ""
    property string slotName: ""
    property string current: ""
    signal close()
    color: "#ee000000"
    // red line for the reading in this slot (press and hold -> set red line)
    property var li: ({})
    function refresh() { li = (visible && current) ? backend.limitFor(current) : ({}) }
    onVisibleChanged: refresh()
    onCurrentChanged: refresh()
    function num(x) { var st = li.step || 1; return st < 1 ? x.toFixed(1) : Math.round(x).toLocaleString(Qt.locale("en_US"), "f", 0) }

    MouseArea { anchors.fill: parent; onClicked: {} }

    Rectangle {
        anchors.centerIn: parent
        width: 1000; height: 580; radius: 16
        color: pk.theme.colors.background
        border.color: pk.theme.colors.panelBorder; border.width: 2

        Text { x: 28; y: 20; text: "Show on " + pk.pageName; color: pk.theme.colors.accent; font.pixelSize: 30; font.bold: true }
        Btn { theme: pk.theme; text: "Cancel"; x: 1000 - width - 24; y: 16; onClicked: pk.close() }
        Btn { theme: pk.theme; text: "Reset page"; width: 170; x: 1000 - 150 - 24 - 180; y: 16
              onClicked: { backend.resetPage(pk.pageName); pk.close() } }

        Flickable {
            x: 24; y: 84; width: 952; height: pk.li.key ? 396 : 480
            clip: true
            contentHeight: grid.height
            Grid {
                id: grid
                columns: 5; spacing: 10
                Repeater {
                    model: pk.channels
                    Btn {
                        theme: pk.theme; width: 182; height: 58
                        text: modelData.label + (modelData.verified ? "" : "?")
                        active: modelData.key === pk.current
                        onClicked: { backend.setSlot(pk.pageName, pk.slotName, modelData.key); pk.close() }
                    }
                }
            }
        }

        // ---- red line for this reading: at or over it, the reading turns red and blinks
        Rectangle {
            visible: !!pk.li.key
            x: 24; y: 492; width: 952; height: 72; radius: 12
            color: "#111c29"; border.color: "#22364d"
            Text { x: 18; anchors.verticalCenter: parent.verticalCenter
                   text: "Red line  ·  " + (pk.li.label || "").toUpperCase()
                   color: pk.theme.colors.text; font.pixelSize: 24; font.bold: true }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                spacing: 12
                Btn { theme: pk.theme; width: 70; height: 54; text: "−"; visible: pk.li.value !== null && pk.li.value !== undefined
                      onClicked: { backend.setLimit(pk.li.key, Math.max(pk.li.min, pk.li.value - pk.li.step)); pk.refresh() } }
                Text { width: 170; horizontalAlignment: Text.AlignHCenter; anchors.verticalCenter: parent.verticalCenter
                       text: pk.li.value === null || pk.li.value === undefined ? "Off" : pk.num(pk.li.value) + " " + (pk.li.units || "")
                       color: "#ff5a5a"; font.pixelSize: 34; font.bold: true }
                Btn { theme: pk.theme; width: 70; height: 54; text: "+"; visible: pk.li.value !== null && pk.li.value !== undefined
                      onClicked: { backend.setLimit(pk.li.key, Math.min(pk.li.max, pk.li.value + pk.li.step)); pk.refresh() } }
                Btn { theme: pk.theme; width: 110; height: 54; text: "Set"; visible: pk.li.value === null || pk.li.value === undefined
                      onClicked: { backend.setLimit(pk.li.key, pk.li.min + (pk.li.max - pk.li.min) * 0.8); pk.refresh() } }
                Btn { theme: pk.theme; width: 130; height: 54; text: "Default"; visible: !!pk.li.custom
                      onClicked: { backend.resetLimit(pk.li.key); pk.refresh() } }
            }
        }
    }
}
