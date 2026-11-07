// Small value tile: label, big value, units. "mil" shows OK/ON.
import QtQuick

Rectangle {
    id: t
    property var theme
    property var cfg: ({})
    property real value: 0
    property bool valid: false
    readonly property var colors: theme ? theme.colors : ({})
    readonly property bool isMil: cfg.key === "mil"
    readonly property bool milOn: isMil && valid && value >= 1

    color: colors.panel || "#111"
    border.color: milOn ? colors.warn : (colors.panelBorder || "#333")
    border.width: milOn ? 3 : 1
    radius: 10

    Text {
        x: 10; y: 6
        text: (t.cfg.label || "") + (t.cfg.verified === false ? "?" : "")
        color: t.colors.dim || "gray"
        font.family: t.theme ? t.theme.fonts.label : ""
        font.pixelSize: 15
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: 8
        text: !t.valid ? "--" : t.isMil ? (t.milOn ? "ON" : "OK") : t.value.toFixed(t.cfg.decimals || 0)
        color: t.isMil && t.valid ? (t.milOn ? t.colors.warn : t.colors.ok) : (t.colors.text || "white")
        font.family: t.theme ? t.theme.fonts.digits : ""
        font.pixelSize: 30
        font.bold: true
    }
    Text {
        anchors.right: parent.right; anchors.rightMargin: 8
        anchors.bottom: parent.bottom; anchors.bottomMargin: 4
        text: t.isMil ? "" : (t.cfg.units || "")
        color: t.colors.dim || "gray"
        font.family: t.theme ? t.theme.fonts.label : ""
        font.pixelSize: 14
    }
}
