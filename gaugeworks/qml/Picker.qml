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
            x: 24; y: 84; width: 952; height: 480
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
    }
}
