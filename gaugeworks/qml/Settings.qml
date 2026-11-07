// Touch settings menu, titled "GaugeWorks". Everything here is local to the UI;
// trip reset is the only message sent to the core, and nothing reaches the truck.
import QtQuick

Rectangle {
    id: s
    property var theme
    property var gw
    property bool confirmShutdown: false
    signal close()
    color: "#cc000000"

    MouseArea { anchors.fill: parent; onClicked: {} }  // swallow taps behind the panel

    Rectangle {
        id: panel
        anchors.centerIn: parent
        width: 700; height: 520; radius: 16
        color: s.theme.colors.background
        border.color: s.theme.colors.panelBorder; border.width: 2

        Text {
            x: 28; y: 18
            text: "GaugeWorks"
            color: s.theme.colors.accent
            font.family: s.theme.fonts.label; font.pixelSize: 34; font.bold: true
        }
        Btn { theme: s.theme; text: "Close"; x: panel.width - width - 24; y: 18; onClicked: s.close() }

        Column {
            x: 28; y: 96; spacing: 18

            Row {
                spacing: 14
                Text { width: 150; text: "Units"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; text: "Imperial"; active: s.gw.imperial; onClicked: s.gw.setImperial(true) }
                Btn { theme: s.theme; text: "Metric"; active: !s.gw.imperial; onClicked: s.gw.setImperial(false) }
            }
            Row {
                spacing: 14
                Text { width: 150; text: "Theme"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Repeater {
                    model: s.gw.themes
                    Btn { theme: s.theme; text: modelData; active: s.theme.id === modelData; onClicked: s.gw.setTheme(modelData) }
                }
            }
            Row {
                spacing: 14
                visible: s.gw.shift.enabled
                Text { width: 150; text: "Shift at"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; text: "-100"; width: 100; onClicked: s.gw.adjustShift(-100) }
                Text {
                    width: 120; horizontalAlignment: Text.AlignHCenter
                    text: s.gw.shift.rpm.toFixed(0)
                    color: s.theme.colors.text; font.pixelSize: 30; font.bold: true
                    anchors.verticalCenter: parent.verticalCenter
                }
                Btn { theme: s.theme; text: "+100"; width: 100; onClicked: s.gw.adjustShift(100) }
            }
            Row {
                spacing: 14
                Text { width: 150; text: "Trip"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; text: "Reset trip"; width: 200; onClicked: s.gw.tripReset() }
            }
        }

        Row {
            x: 28; y: panel.height - 84; spacing: 14
            Btn {
                theme: s.theme; width: 220
                text: s.confirmShutdown ? "Tap to confirm" : "Shut down Pi"
                fill: s.confirmShutdown ? s.theme.colors.alarm : s.theme.colors.panel
                onClicked: {
                    if (s.confirmShutdown) s.gw.shutdown()
                    else { s.confirmShutdown = true; confirmTimer.restart() }
                }
            }
            Text {
                text: "Wait for the green LED to stop, then unplug."
                color: s.theme.colors.dim; font.pixelSize: 18
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Timer { id: confirmTimer; interval: 4000; onTriggered: s.confirmShutdown = false }
    }
}
