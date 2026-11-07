import QtQuick

Rectangle {
    id: b
    property var theme
    property string text: ""
    property bool active: false
    property color fill: active ? (theme ? theme.colors.accent : "orange") : (theme ? theme.colors.panel : "#222")
    signal clicked()
    width: 150; height: 56; radius: 10
    color: area.pressed ? Qt.lighter(fill, 1.3) : fill
    border.color: theme ? theme.colors.panelBorder : "#444"
    Text {
        anchors.centerIn: parent
        text: b.text
        color: theme ? theme.colors.text : "white"
        font.family: theme ? theme.fonts.label : ""
        font.pixelSize: 20
        font.bold: true
    }
    MouseArea { id: area; anchors.fill: parent; onClicked: b.clicked() }
}
