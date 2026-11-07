// Two values on one bar: actual = fill, desired = marker. Used for VGT vanes.
import QtQuick

Rectangle {
    id: d
    property var theme
    property string label: "VGT"
    property real desired: 0
    property real actual: 0
    property bool desiredValid: false
    property bool actualValid: false
    readonly property var colors: theme ? theme.colors : ({})
    function pct(v) { return Math.max(0, Math.min(100, v)) / 100 }

    color: colors.panel || "#111"
    border.color: colors.panelBorder || "#333"
    radius: 10

    Text {
        x: 14; y: 10
        text: d.label + " %"
        color: d.colors.dim || "gray"
        font.family: d.theme ? d.theme.fonts.label : ""
        font.pixelSize: 18
    }
    Rectangle {
        id: track
        x: 14; y: 44; width: d.width - 28; height: 34; radius: 6
        color: "#0a0d11"; border.color: d.colors.panelBorder || "#333"
        Rectangle {
            width: d.actualValid ? parent.width * d.pct(d.actual) : 0
            height: parent.height; radius: 6
            color: d.colors.accent || "orange"
            Behavior on width { SmoothedAnimation { velocity: 600 } }
        }
        Rectangle {  // desired marker
            visible: d.desiredValid
            x: parent.width * d.pct(d.desired) - width / 2
            y: -6; width: 5; height: parent.height + 12; radius: 2
            color: d.colors.text || "white"
            Behavior on x { SmoothedAnimation { velocity: 600 } }
        }
    }
    Text {  // % difference, actual - desired
        anchors.right: parent.right; anchors.rightMargin: 14; y: 10
        text: d.desiredValid && d.actualValid
              ? "DIFF " + (d.actual - d.desired >= 0 ? "+" : "") + (d.actual - d.desired).toFixed(0) + "%"
              : "DIFF --"
        color: d.colors.text || "white"
        font.family: d.theme ? d.theme.fonts.digits : ""
        font.pixelSize: 20; font.bold: true
    }
    Row {
        x: 14; y: 88; spacing: 24
        Text {
            text: "DES " + (d.desiredValid ? d.desired.toFixed(0) : "--")
            color: d.colors.text || "white"
            font.family: d.theme ? d.theme.fonts.digits : ""; font.pixelSize: 22; font.bold: true
        }
        Text {
            text: "ACT " + (d.actualValid ? d.actual.toFixed(0) : "--")
            color: d.colors.accent || "orange"
            font.family: d.theme ? d.theme.fonts.digits : ""; font.pixelSize: 22; font.bold: true
        }
    }
}
