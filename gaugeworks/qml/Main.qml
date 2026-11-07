// GaugeWorks main screen: swipeable pages built from profile templates,
// designed at 1024x600 and scaled to the window.
import QtQuick

Rectangle {
    id: root
    readonly property var theme: backend.theme
    readonly property var cfg: backend.config
    readonly property var pages: cfg.pages || []
    readonly property var colors: theme.colors
    color: colors.background

    function openPicker(pageName, slot, current) {
        picker.pageName = pageName; picker.slotName = slot; picker.current = current
        picker.visible = true
    }

    Item {
        id: stage
        width: 1024; height: 600
        anchors.centerIn: parent
        scale: Math.min(root.width / width, root.height / height)

        // ---- pages (swipe left/right)
        ListView {
            id: pagesView
            anchors.fill: parent
            orientation: ListView.Horizontal
            snapMode: ListView.SnapOneItem
            highlightRangeMode: ListView.StrictlyEnforceRange
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 250
            model: root.pages
            interactive: !settings.visible && !picker.visible && !fillup.visible && !history.visible
                         && !exportPanel.visible
            onMovementEnded: backend.setPage(currentIndex)
            onCountChanged: positionViewAtIndex(Math.min(backend.currentPage, Math.max(0, count - 1)), ListView.Beginning)
            Component.onCompleted: positionViewAtIndex(backend.currentPage, ListView.Beginning)
            delegate: Item {
                id: pageItem
                width: 1024; height: 600
                required property var modelData
                required property int index
                Loader {
                    id: loader
                    anchors.fill: parent
                    source: {
                        var t = pageItem.modelData.template
                        return t === "quad" ? "PageQuad.qml" : t === "economy" ? "PageEconomy.qml"
                             : t === "list" ? "PageList.qml" : "PageDash.qml"
                    }
                    onLoaded: {
                        item.theme = Qt.binding(function() { return root.theme })
                        item.pg = Qt.binding(function() { return pageItem.modelData })
                        item.gearKey = Qt.binding(function() { return root.cfg.gear || "" })
                        if (item.diag !== undefined) item.diag = Qt.binding(function() { return root.cfg.diag || [] })
                        item.pick.connect(function(slot, current) { root.openPicker(pageItem.modelData.name, slot, current) })
                        if (item.openFillup) item.openFillup.connect(function() { fillup.visible = true })
                        if (item.openHistory) item.openHistory.connect(function() { history.visible = true })
                    }
                }
            }
        }

        // ---- top bar
        Item {
            id: topBar
            width: parent.width; height: 44
            Row {
                x: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                Text {
                    text: root.pages.length ? root.pages[Math.max(0, pagesView.currentIndex)].name : "JpCAN"
                    color: colors.text; font.family: theme.fonts.label; font.pixelSize: 20; font.bold: true
                }
                Row {
                    spacing: 7; anchors.verticalCenter: parent.verticalCenter
                    visible: root.pages.length > 1
                    Repeater {
                        model: root.pages.length
                        Rectangle {
                            width: 11; height: 11; radius: 6
                            color: index === pagesView.currentIndex ? colors.accent : colors.panelBorder
                            MouseArea { anchors.fill: parent; anchors.margins: -8
                                        onClicked: { pagesView.currentIndex = index; backend.setPage(index) } }
                        }
                    }
                }
            }
            Row {
                anchors.centerIn: parent; spacing: 10
                Rectangle {
                    width: 12; height: 12; radius: 6; anchors.verticalCenter: parent.verticalCenter
                    color: backend.status.state === "running" ? colors.ok
                         : backend.status.state === "offline" ? colors.alarm : colors.warn
                }
                Text {
                    text: (backend.status.state === "running" ? backend.status.mode + "  " : "") + backend.status.text
                    color: backend.status.state === "running" ? colors.dim : colors.warn
                    font.family: theme.fonts.label; font.pixelSize: 18
                }
            }
            Text {
                id: clock
                anchors.right: gearIcon.left; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter
                color: colors.text; font.family: theme.fonts.digits; font.pixelSize: 20
                Timer { interval: 1000; running: true; repeat: true; triggeredOnStart: true
                        onTriggered: clock.text = Qt.formatTime(new Date(), "h:mm AP") }
            }
            Text {
                id: gearIcon
                anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                text: "⚙"
                color: colors.text; font.pixelSize: 32
                MouseArea { anchors.fill: parent; anchors.margins: -12; onClicked: settings.visible = true }
            }
        }

        // ---- check engine banner: only when the light is ON, over every page but Diagnostic
        Rectangle {
            id: celBanner
            readonly property bool active: backend.fresh["mil"] === true && backend.values["mil"] >= 1
            readonly property int diagIndex: {
                for (var i = 0; i < root.pages.length; i++) if (root.pages[i].template === "list") return i
                return -1
            }
            readonly property bool onDiag: diagIndex >= 0 && pagesView.currentIndex === diagIndex
            readonly property bool hasCount: backend.fresh["dtc_count"] === true
            visible: active && !onDiag
            anchors.horizontalCenter: parent.horizontalCenter
            y: 48; width: 520; height: 56; radius: 12
            color: colors.warn
            border.color: "#000000"; border.width: 2
            Row {
                anchors.centerIn: parent; spacing: 14
                Text { text: "\u26a0"; color: "#111111"; font.pixelSize: 30; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "CHECK ENGINE" + (celBanner.hasCount
                          ? "  \u2022  " + backend.values["dtc_count"].toFixed(0) + " code" + (backend.values["dtc_count"] === 1 ? "" : "s")
                          : "")
                    color: "#111111"; font.family: theme.fonts.label; font.pixelSize: 26; font.bold: true
                }
            }
            MouseArea {  // tap: jump to the Diagnostic page
                anchors.fill: parent
                onClicked: if (celBanner.diagIndex >= 0) { pagesView.currentIndex = celBanner.diagIndex; backend.setPage(celBanner.diagIndex) }
            }
        }

        // ---- USB drive prompt (bottom centre)
        Rectangle {
            id: usbPrompt
            visible: backend.usb.present === true && backend.usb.state === "idle" && !backend.usb.dismissed
                     && !exportPanel.visible
            anchors.horizontalCenter: parent.horizontalCenter
            y: 600 - height - 10; width: 640; height: 70; radius: 12
            color: colors.panel; border.color: colors.accent; border.width: 2
            Text {
                x: 18; anchors.verticalCenter: parent.verticalCenter
                text: "USB drive found: " + (backend.usb.name || "")
                color: colors.text; font.pixelSize: 21; font.bold: true
                width: 330; elide: Text.ElideRight
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Btn { theme: root.theme; width: 130; height: 50; text: "Export"; active: true
                      onClicked: { exportPanel.visible = true; backend.exportUsb() } }
                Btn { theme: root.theme; width: 130; height: 50; text: "Not now"; onClicked: backend.dismissUsb() }
            }
        }

        // ---- overlays
        Settings {
            id: settings
            objectName: "settingsPanel"
            anchors.fill: parent
            visible: false
            theme: root.theme; gw: backend
            onClose: visible = false
            onOpenFillup: { visible = false; fillup.visible = true }
            onOpenHistory: { visible = false; history.visible = true }
            onOpenExport: { visible = false; exportPanel.visible = true }
        }
        ExportPanel {
            id: exportPanel
            objectName: "exportPanel"
            anchors.fill: parent
            visible: false
            theme: root.theme; gw: backend
            onClose: visible = false
        }
        FillUp {
            id: fillup
            objectName: "fillupPanel"
            anchors.fill: parent
            visible: false
            theme: root.theme; gw: backend
            onClose: visible = false
        }
        History {
            id: history
            objectName: "historyPanel"
            anchors.fill: parent
            visible: false
            theme: root.theme; gw: backend
            onClose: visible = false
        }
        Picker {
            id: picker
            objectName: "pickerPanel"
            anchors.fill: parent
            visible: false
            theme: root.theme
            channels: root.cfg.channels || []
            onClose: visible = false
        }

        // ---- toast for fill-up results and other messages
        Rectangle {
            id: toast
            property string text: ""
            anchors.horizontalCenter: parent.horizontalCenter
            y: 52
            width: toastText.implicitWidth + 40; height: 52; radius: 12
            color: colors.panel; border.color: colors.accent; border.width: 2
            opacity: 0; visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 250 } }
            Text { id: toastText; anchors.centerIn: parent; text: toast.text; color: colors.text; font.pixelSize: 22; font.bold: true }
            Timer { id: toastTimer; interval: 6000; onTriggered: toast.opacity = 0 }
            Connections {
                target: backend
                function onMessage(msg) { toast.text = msg; toast.opacity = 1; toastTimer.restart() }
            }
        }

        // ---- splash (placeholder logo until JP's SVG)
        Rectangle {
            id: splash
            anchors.fill: parent
            color: "black"
            opacity: 1
            visible: opacity > 0
            Image {
                anchors.centerIn: parent
                width: 600; height: 260
                source: backend.splash
                sourceSize: Qt.size(width, height)
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height - 90
                text: "JpCAN reads it. GaugeWorks shows it."
                color: "#8a929c"; font.pixelSize: 22
            }
            Timer { interval: splashMs; running: true; onTriggered: splash.opacity = 0 }
            Behavior on opacity { NumberAnimation { duration: 600 } }
        }
    }
}
