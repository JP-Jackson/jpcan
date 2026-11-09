// Touch settings menu, titled "GaugeWorks". Display prefs are local; trip reset
// and fill-ups go to the core over MQTT. Nothing here reaches the truck.
import QtQuick

Rectangle {
    id: s
    property var theme
    property var gw
    property bool confirmShutdown: false
    property string confirmSource: ""   // "truck" / "sim" while waiting for the second tap
    signal close()
    signal openFillup()
    signal openHistory()
    signal openExport()
    signal openColors()
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

        Flickable {  // rows scroll when they don't fit; the bottom buttons stay put
            id: rows
            x: 28; y: 84; width: panel.width - 40; height: panel.height - 84 - 96
            clip: true
            contentHeight: col.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
        Column {
            id: col
            spacing: 10

            Row {
                spacing: 12
                Text { width: 150; text: "Units"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; text: "Imperial"; active: s.gw.imperial; onClicked: s.gw.setImperial(true) }
                Btn { theme: s.theme; text: "Metric"; active: !s.gw.imperial; onClicked: s.gw.setImperial(false) }
            }
            Row {
                spacing: 12
                Text { width: 150; text: "Theme"; color: s.theme.colors.dim; font.pixelSize: 22 }
                Flow {
                    width: 540; spacing: 8
                    Repeater {
                        model: s.gw.themes
                        Btn { theme: s.theme; width: 172; height: 48; text: modelData.name
                              active: s.theme.id === modelData.id; onClicked: s.gw.setTheme(modelData.id) }
                    }
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
                id: sourceRow
                spacing: 12
                property bool isSim: s.gw.sourceMode === "sim"
                Text { width: 150; text: "Data from"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Repeater {
                    model: [["truck", "Truck"], ["sim", "Simulator"]]
                    Btn {
                        theme: s.theme; width: 170
                        property bool current: (modelData[0] === "sim") === sourceRow.isSim
                        text: s.confirmSource === modelData[0] ? "Tap to confirm" : modelData[1]
                        active: current
                        fill: s.confirmSource === modelData[0] ? s.theme.colors.alarm : (current ? s.theme.colors.accent : s.theme.colors.panel)
                        onClicked: {
                            if (current) return
                            if (s.confirmSource === modelData[0]) { s.confirmSource = ""; s.gw.setSource(modelData[0]) }
                            else { s.confirmSource = modelData[0]; sourceTimer.restart() }
                        }
                    }
                }
            }
            Row {
                spacing: 12
                visible: s.gw.sourceMode === "sim"
                Text { width: 150; text: "Sim drive"; color: s.theme.colors.dim; font.pixelSize: 22 }
                Flow {
                    width: 560; spacing: 8
                    Repeater {
                        model: s.gw.simScenarios
                        Btn { theme: s.theme; width: 176; height: 48; text: modelData.label
                              active: s.gw.simScenario === modelData.key
                              fill: active ? s.theme.colors.accent : (modelData.problem ? "#3a1a1e" : s.theme.colors.panel)
                              onClicked: s.gw.setSimScenario(modelData.key) }
                    }
                }
            }
            Row {
                spacing: 12
                Text { width: 150; text: "Background"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Flow {
                    width: 560; spacing: 8
                    Repeater {
                        model: [["carbon", "Carbon"], ["expanded", "Expanded"], ["diamond", "Diamond"], ["brushed", "Brushed"], ["honeycomb", "Honeycomb"], ["black", "Black"]]
                        Btn { theme: s.theme; width: 176; height: 48; text: modelData[1]
                              active: backend.background === modelData[0]; onClicked: backend.setBackground(modelData[0]) }
                    }
                }
            }
            Row {
                spacing: 12
                Text { width: 150; text: "Colors"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Rectangle { width: 44; height: 44; radius: 22; color: backend.accent; border.color: "#ffffff"; border.width: 2; anchors.verticalCenter: parent.verticalCenter }
                Rectangle { width: 44; height: 44; radius: 22; color: backend.accent2; border.color: "#ffffff"; border.width: 2; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; width: 170; text: "Change"; onClicked: s.openColors() }
            }
            Row {
                spacing: 12
                Text { width: 150; text: "Fuel"; color: s.theme.colors.dim; font.pixelSize: 22; anchors.verticalCenter: parent.verticalCenter }
                Btn { theme: s.theme; text: "Fill-up"; width: 150; onClicked: s.openFillup() }
                Btn { theme: s.theme; text: "History"; width: 150; onClicked: s.openHistory() }
                Btn { theme: s.theme; text: "Reset trip"; width: 170; onClicked: s.gw.tripReset() }
            }
        }

        }
        Rectangle {  // scroll hint: a thin bar on the right when there's more below/above
            visible: rows.contentHeight > rows.height
            x: panel.width - 10; width: 4; radius: 2
            color: s.theme.colors.dim; opacity: 0.6
            height: rows.height * rows.height / rows.contentHeight
            y: rows.y + (rows.height - height) * (rows.contentY / Math.max(1, rows.contentHeight - rows.height))
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
            Btn { theme: s.theme; width: 190; text: "Edit page"; active: true
                  onClicked: { backend.setEditMode(true); s.close() } }
            Text {
                text: "Unplug after the\ngreen LED stops."
                color: s.theme.colors.dim; font.pixelSize: 16
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Timer { id: confirmTimer; interval: 4000; onTriggered: s.confirmShutdown = false }
        Timer { id: sourceTimer; interval: 4000; onTriggered: s.confirmSource = "" }
    }
}
