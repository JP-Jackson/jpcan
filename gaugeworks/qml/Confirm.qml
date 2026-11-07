// Simple confirm popup: title, message, Reset / Cancel.
import QtQuick

Rectangle {
    id: c
    property var theme
    property string title: "Are you sure?"
    property string message: ""
    property string okText: "Reset"
    signal accepted()
    signal rejected()
    color: "#cc000000"

    MouseArea { anchors.fill: parent; onClicked: c.rejected() }  // tap outside = cancel

    Rectangle {
        anchors.centerIn: parent
        width: 620; height: 300; radius: 16
        color: c.theme.colors.background
        border.color: c.theme.colors.accent; border.width: 2
        MouseArea { anchors.fill: parent; onClicked: {} }

        Text { x: 28; y: 24; width: 564; text: c.title; color: c.theme.colors.text
               font.pixelSize: 30; font.bold: true; wrapMode: Text.WordWrap }
        Text { x: 28; y: 82; width: 564; text: c.message; color: c.theme.colors.dim
               font.pixelSize: 20; wrapMode: Text.WordWrap }
        Row {
            x: 28; y: 300 - 88; spacing: 16
            Btn { theme: c.theme; width: 220; height: 64; text: c.okText
                  fill: c.theme.colors.alarm; onClicked: c.accepted() }
            Btn { theme: c.theme; width: 200; height: 64; text: "Cancel"; onClicked: c.rejected() }
        }
    }
}
