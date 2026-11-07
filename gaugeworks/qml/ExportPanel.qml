// USB export: copies drive logs, fuel history, scans and diagnostics to a stick.
import QtQuick

Rectangle {
    id: e
    property var theme
    property var gw
    readonly property var usb: gw ? gw.usb : ({})
    signal close()
    color: "#ee000000"

    MouseArea { anchors.fill: parent; onClicked: {} }

    Rectangle {
        anchors.centerIn: parent
        width: 760; height: 460; radius: 16
        color: e.theme.colors.background
        border.color: e.theme.colors.panelBorder; border.width: 2

        Text { x: 28; y: 18; text: "USB export"; color: e.theme.colors.accent; font.pixelSize: 34; font.bold: true }
        Btn { theme: e.theme; text: "Close"; x: 760 - width - 24; y: 18; onClicked: e.close()
              visible: e.usb.state !== "exporting" }

        Column {
            x: 28; y: 92; width: 704; spacing: 14
            Text {
                text: e.usb.present ? "Drive: " + e.usb.name : "Plug in a USB drive (FAT32, exFAT or NTFS)"
                color: e.theme.colors.text; font.pixelSize: 24; font.bold: true
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                text: "Copies drive logs (with CSV), fuel history, scan files and a diagnostics report " +
                      "to JpCAN_export/<date> on the drive. Nothing is deleted from the Pi."
                color: e.theme.colors.dim; font.pixelSize: 19
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                visible: text !== ""
                text: e.usb.state === "exporting" ? e.usb.progress : (e.usb.result || "")
                color: e.usb.state === "error" ? e.theme.colors.alarm
                     : e.usb.state === "done" ? e.theme.colors.ok : e.theme.colors.text
                font.pixelSize: 24; font.bold: true
            }
        }
        Row {
            x: 28; y: 460 - 84; spacing: 14
            Btn {
                theme: e.theme; width: 280; height: 60
                text: e.usb.state === "exporting" ? "Exporting..." : "Export everything"
                active: e.usb.present && e.usb.state !== "exporting"
                onClicked: if (e.usb.present && e.usb.state !== "exporting") e.gw.exportUsb()
            }
            Btn {
                theme: e.theme; width: 200; height: 60; text: "Eject"
                visible: e.usb.present && e.usb.state !== "exporting"
                onClicked: e.gw.ejectUsb()
            }
        }
    }
}
