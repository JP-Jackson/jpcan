// Touch settings menu, titled "GaugeWorks". Display prefs are local; trip reset
// and fill-ups go to the core over MQTT. Nothing here reaches the truck.
import QtQuick

Rectangle {
    id: s
    property var theme
    property var gw
    property bool confirmShutdown: false
    signal close()
    signal openFillup()
    signal openHistory()
    signal openExport()
    color: "#cc000000"

    MouseArea { anchors.fill: parent; onClicked: {} }  // swallow taps behind the panel

    Rectangle {
        id: panel
        anchors.centerIn: parent
        width: 760; height: 580; radius: 16
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
            x: 28; y: 90; spacing: 14

            Row {
                spacing: 12
                Text { width: 150; text: "Units"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; text: "Imperial"; active: s.gw.imperial; onClicked: s.gw.setImperial(true) }
                Btn { theme: s.theme; text: "Metric"; active: !s.gw.imperial; onClicked: s.gw.setImperial(false) }
            }
            Row {
                spacing: 12
                Text { width: 150; text: "Theme"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Repeater {
                    model: s.gw.themes
                    Btn { theme: s.theme; text: modelData; active: s.theme.id === modelData; onClicked: s.gw.setTheme(modelData) }
                }
            }
            Row {
                spacing: 12
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
                spacing: 12
                Text { width: 150; text: "MPG shown"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; text: "Raw"; width: 120; active: !s.gw.econCorrected; onClicked: s.gw.setEconCorrected(false) }
                Btn { theme: s.theme; text: "Corrected"; width: 150; active: s.gw.econCorrected; onClicked: s.gw.setEconCorrected(true) }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: s.gw.econFactor > 0
                          ? "x" + s.gw.econFactor.toFixed(2) + " from " + s.gw.fuel.factor_tanks + " tank" + (s.gw.fuel.factor_tanks === 1 ? "" : "s")
                          : "needs 2 fill-ups"
                    color: s.theme.colors.dim; font.pixelSize: 18
                }
            }
            Row {
                spacing: 12
                Text { width: 150; text: "Last N avg"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Repeater {
                    model: [5, 10, 25, 50]
                    Btn { theme: s.theme; width: 90; text: modelData + " mi"; active: s.gw.econWindow === modelData
                          onClicked: s.gw.setEconWindow(modelData) }
                }
            }
            Row {
                spacing: 12
                Text { width: 150; text: "Fuel"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; text: "Fill-up"; width: 150; onClicked: s.openFillup() }
                Btn { theme: s.theme; text: "History"; width: 150; onClicked: s.openHistory() }
                Btn { theme: s.theme; text: "Reset trip"; width: 170; onClicked: s.gw.tripReset() }
            }
        }

        Row {
            x: 28; y: panel.height - 80; spacing: 14
            Btn {
                theme: s.theme; width: 220
                text: s.confirmShutdown ? "Tap to confirm" : "Shut down Pi"
                fill: s.confirmShutdown ? s.theme.colors.alarm : s.theme.colors.panel
                onClicked: {
                    if (s.confirmShutdown) s.gw.shutdown()
                    else { s.confirmShutdown = true; confirmTimer.restart() }
                }
            }
            Btn { theme: s.theme; width: 190; text: "USB export"; onClicked: s.openExport() }
            Text {
                text: "Unplug after the\ngreen LED stops."
                color: s.theme.colors.dim; font.pixelSize: 16
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Timer { id: confirmTimer; interval: 4000; onTriggered: s.confirmShutdown = false }
    }
}
