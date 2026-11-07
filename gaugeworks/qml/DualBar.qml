// Two values that should track each other (VGT desired vs actual).
// Fill = actual, white marker = desired, shaded band between them = deviation,
// coloured by size. The panel only goes warn/alarm when the deviation is
// SUSTAINED for holdMs (vanes lag briefly during normal transients).
import QtQuick

Rectangle {
    id: d
    property var theme
    property var cfg: ({})
    property string label: cfg.label || "VGT"
    property real desired: 0
    property real actual: 0
    property bool desiredValid: false
    property bool actualValid: false

    readonly property var colors: theme ? theme.colors : ({})
    readonly property real devWarn: cfg.dev_warn !== undefined ? cfg.dev_warn : 10
    readonly property real devAlarm: cfg.dev_alarm !== undefined ? cfg.dev_alarm : 20
    readonly property int holdMs: cfg.dev_hold !== undefined ? cfg.dev_hold * 1000 : 1500
    readonly property bool bothValid: desiredValid && actualValid
    readonly property real dev: bothValid ? actual - desired : 0
    readonly property real absDev: Math.abs(dev)
    readonly property int level: !bothValid ? 0 : absDev >= devAlarm ? 2 : absDev >= devWarn ? 1 : 0
    property int held: 0              // level that has persisted >= holdMs
    property bool flash: false

    function pct(v) { return Math.max(0, Math.min(100, v)) / 100 }
    function levelColor(l) { return l === 2 ? colors.alarm : l === 1 ? colors.warn : colors.dim }

    onLevelChanged: {
        if (level < held) held = level      // clear immediately when it recovers
        if (level > held) holdTimer.restart()
        else holdTimer.stop()
    }
    Timer { id: holdTimer; interval: d.holdMs; onTriggered: d.held = d.level }
    Timer { running: d.held === 2; interval: 400; repeat: true; onTriggered: d.flash = !d.flash }

    color: held === 2 && flash ? Qt.darker(colors.alarm, 2.2) : (colors.panel || "#111")
    border.color: held > 0 ? levelColor(held) : (colors.panelBorder || "#333")
    border.width: held > 0 ? 3 : 1
    radius: 10

    Text {
        x: 14; y: 8
        text: d.label + "  vanes %"
        color: d.colors.dim || "gray"
        font.family: d.theme ? d.theme.fonts.label : ""
        font.pixelSize: 18
    }
    Text {  // live deviation readout, top-right
        anchors.right: parent.right; anchors.rightMargin: 14; y: 6
        text: d.bothValid ? "Δ " + (d.dev >= 0 ? "+" : "") + d.dev.toFixed(0) : "Δ --"
        color: d.bothValid ? d.levelColor(d.level) : (d.colors.dim || "gray")
        font.family: d.theme ? d.theme.fonts.digits : ""
        font.pixelSize: 22; font.bold: true
    }
    Rectangle {
        id: track
        x: 14; y: 42; width: d.width - 28; height: 34; radius: 6
        color: "#0a0d11"; border.color: d.colors.panelBorder || "#333"
        Rectangle {  // actual = fill
            width: d.actualValid ? parent.width * d.pct(d.actual) : 0
            height: parent.height; radius: 6
            color: d.colors.accent || "orange"
            opacity: 0.85
            Behavior on width { SmoothedAnimation { velocity: 600 } }
        }
        Rectangle {  // deviation band between desired and actual
            visible: d.bothValid && d.absDev >= 1
            x: parent.width * d.pct(Math.min(d.desired, d.actual))
            width: parent.width * Math.abs(d.pct(d.actual) - d.pct(d.desired))
            y: parent.height * 0.25; height: parent.height * 0.5
            color: d.levelColor(d.level)
            opacity: d.level === 0 ? 0.5 : 0.95
            Behavior on x { SmoothedAnimation { velocity: 600 } }
            Behavior on width { SmoothedAnimation { velocity: 600 } }
        }
        Rectangle {  // desired = marker
            visible: d.desiredValid
            x: parent.width * d.pct(d.desired) - width / 2
            y: -6; width: 5; height: parent.height + 12; radius: 2
            color: d.colors.text || "white"
            Behavior on x { SmoothedAnimation { velocity: 600 } }
        }
    }
    Row {
        x: 14; y: 86; spacing: 18
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
    Text {
        x: 14; y: 122; width: d.width - 28
        visible: d.held > 0
        text: d.held === 2 ? "VANES NOT TRACKING" : "VANE MISMATCH"
        color: d.levelColor(d.held)
        font.family: d.theme ? d.theme.fonts.label : ""
        font.pixelSize: 16; font.bold: true
        fontSizeMode: Text.HorizontalFit; minimumPixelSize: 11; elide: Text.ElideRight
    }
}
