// GaugeWorks main screen: swipeable pages built from profile templates,
// designed at 1024x600 and scaled to the window.
import QtQuick

Rectangle {
    id: root
    readonly property var theme: backend.theme
    readonly property var cfg: backend.config
    readonly property var pages: cfg.pages || []
    readonly property var colors: theme.colors
    readonly property bool oemBar: !!(theme.style && theme.style.topBar === "oem")
    color: colors.background

    function askConfirm(title, message, okText, action) {
        confirm.title = title; confirm.message = message; confirm.okText = okText
        confirm.action = action
        confirm.visible = true
    }

    function askReset(kind) {
        askConfirm(kind === "roll" ? "Reset Last " + backend.econWindow + " average?" : "Reset trip average?",
                   kind === "roll"
                   ? "The rolling average starts over and shows -- until you've driven " + backend.econWindow + " miles."
                   : "Trip miles, fuel used and the trip average start over.\nTank average and fill-up history are not affected.",
                   "Reset", function() { backend.resetEcon(kind) })
    }

    function askDeleteAll() {
        var n = (backend.fuel.rows || []).length
        askConfirm("Delete all fill-ups?",
                   "Deletes the fuel history for " + (backend.status.profile || "this vehicle") +
                   " only. A backup is saved first.", "Delete all",
                   function() {
                       askConfirm("Are you sure?",
                                  "This removes " + n + " fill-up" + (n === 1 ? "" : "s") +
                                  " from the screen and the MPG history.", "Yes, delete",
                                  function() { backend.fuelClear() })
                   })
    }

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
            objectName: "pagesView"
            anchors.fill: parent
            orientation: ListView.Horizontal
            cacheBuffer: 1024 * 4   // keep pages alive (skins keep short histories)
            snapMode: ListView.SnapOneItem
            highlightRangeMode: ListView.StrictlyEnforceRange
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 250
            model: root.pages
            interactive: !settings.visible && !picker.visible && !fillup.visible && !history.visible && !colorPicker.visible
                         && !exportPanel.visible && !confirm.visible
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
                    source: {  // theme "skin" page if the theme ships one, else the standard page
                        var t = pageItem.modelData.template
                        var src = (root.theme.pages || {})[t]
                        return src ? src : (t === "quad" ? "PageQuad.qml" : t === "towing" ? "PageTowing.qml" : t === "economy" ? "PageEconomy.qml"
                                            : t === "list" ? "PageList.qml" : "PageDash.qml")
                    }
                    onLoaded: {
                        item.theme = Qt.binding(function() { return root.theme })
                        item.pg = Qt.binding(function() { return pageItem.modelData })
                        item.gearKey = Qt.binding(function() { return root.cfg.gear || "" })
                        if (item.diag !== undefined) item.diag = Qt.binding(function() { return root.cfg.diag || [] })
                        item.pick.connect(function(slot, current) { root.openPicker(pageItem.modelData.name, slot, current) })
                        item.resetAsk.connect(function(kind) { root.askReset(kind) })
                        if (item.openFillup) item.openFillup.connect(function() { fillup.openNew() })
                        if (item.openHistory) item.openHistory.connect(function() { history.visible = true })
                    }
                }
            }
        }

        // ---- shift-light bar (themes with style.shiftBar): fills toward redline
        Row {
            id: shiftBar
            readonly property var rc: root.cfg.rpm || ({})
            readonly property bool enabled_: !!(root.theme.style && root.theme.style.shiftBar) && rc.max !== undefined
            readonly property real rpm: backend.values["rpm"] === undefined ? 0 : backend.values["rpm"]
            readonly property bool rpmOk: backend.fresh["rpm"] === true
            readonly property real rpmTop: backend.shift.enabled ? backend.shift.rpm
                                       : (!isNaN(rc.alarm) ? rc.alarm : rc.max * 0.85)
            readonly property real rpmBottom: rpmTop * 0.55
            readonly property int lit: rpmOk ? Math.max(0, Math.min(15, Math.round(15 * (rpm - rpmBottom) / (rpmTop - rpmBottom)))) : 0
            property bool blink: false
            Timer { running: shiftBar.lit >= 15; interval: 110; repeat: true; onTriggered: shiftBar.blink = !shiftBar.blink }
            visible: enabled_
            z: 5
            anchors.horizontalCenter: parent.horizontalCenter
            y: 46; spacing: 6
            Repeater {
                model: 15
                Rectangle {
                    width: 26; height: 14; radius: 7
                    readonly property color on: index < 5 ? colors.ok : index < 10 ? colors.warn : colors.alarm
                    color: shiftBar.lit >= 15 ? (shiftBar.blink ? colors.shift : "#111111")
                         : index < shiftBar.lit ? on : "#161616"
                    border.color: "#000000"
                }
            }
        }

        // ---- top bar
        Item {
            id: topBar
            width: parent.width; height: 44
            Row {
                x: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 10
                visible: !root.oemBar
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
            Text {  // Turbo Snail quips replace the status for a few seconds
                id: quip
                anchors.centerIn: parent
                visible: text !== "" && !root.oemBar
                color: colors.accent; font.pixelSize: 20; font.bold: true
                property real lastAt: 0
                property real idleSince: 0
                function v(k) { return backend.fresh[k] === true ? backend.values[k] : NaN }
                function say(list) {
                    var now = Date.now()
                    if (now - lastAt < 25000) return
                    lastAt = now
                    text = list[Math.floor(Math.random() * list.length)]
                    quipHide.restart()
                }
                Timer { id: quipHide; interval: 5000; onTriggered: quip.text = "" }
                Timer {
                    running: !!(root.theme.style && root.theme.style.quips); interval: 1000; repeat: true
                    onTriggered: {
                        var boost = quip.v("boost"), rpm = quip.v("rpm"), mpg = quip.v("econ_inst"), spd = quip.v("speed")
                        var rc = root.cfg.rpm || ({})
                        if (spd === 0 && rpm > 0) { if (!quip.idleSince) quip.idleSince = Date.now() } else quip.idleSince = 0
                        if (boost >= 25) quip.say(["SPOOL GOES BRRRR", "Snail is AWAKE", "Turbo snail at full gallop"])
                        else if (!isNaN(rc.warn) && rpm >= rc.warn) quip.say(["Easy, cowboy", "Those are a lot of RPMs", "Shift happens"])
                        else if (mpg >= 25) quip.say(["Hypermiler mode", "Leaf is thriving", "Sipping, not gulping"])
                        else if (spd >= 80) quip.say(["Warp speed engaged", "Speedy snail"])
                        else if (quip.idleSince && Date.now() - quip.idleSince > 120000) quip.say(["Zzz... still idling", "The snail is napping"])
                    }
                }
            }
            Row {
                anchors.centerIn: parent; spacing: 10
                visible: quip.text === "" && !root.oemBar
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
                visible: !root.oemBar
                anchors.right: gearIcon.left; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter
                color: colors.text; font.family: theme.fonts.digits; font.pixelSize: 42; font.bold: true
                Timer { interval: 1000; running: true; repeat: true; triggeredOnStart: true
                        onTriggered: clock.text = Qt.formatTime(new Date(), "h:mm AP") }
            }
            // ---- OEM-style bar (Premium theme): long date + time, telltales, outside temp
            Row {
                visible: root.oemBar
                x: 16; y: -3; spacing: 14
                Text {
                    id: oemTime
                    color: colors.text; font.family: theme.fonts.digits; font.pixelSize: 44
                    Timer { interval: 1000; running: root.oemBar; repeat: true; triggeredOnStart: true
                            onTriggered: { var n = new Date(); oemTime.text = Qt.formatTime(n, "h:mm AP")
                                           oemDate.text = Qt.formatDate(n, "dddd, MMMM d, yyyy") } }
                }
                Text { id: oemDate; anchors.baseline: oemTime.baseline; color: colors.dim
                       font.family: theme.fonts.label; font.pixelSize: 20; font.letterSpacing: 0.5 }
                Text {  // only when the core isn't running normally
                    anchors.baseline: oemTime.baseline
                    visible: backend.status.state !== "running"
                    text: "● " + backend.status.text
                    color: backend.status.state === "offline" ? colors.alarm : colors.warn
                    font.family: theme.fonts.label; font.pixelSize: 15
                }
            }
            Row {
                visible: root.oemBar
                anchors.horizontalCenter: parent.horizontalCenter; y: 15; spacing: 22
                Telltale { kind: "left"; key: "turn_left" }
                Telltale { kind: "low"; key: "headlights" }
                Telltale { kind: "high"; key: "high_beam"; onColor: "#3b82ff" }
                Telltale { kind: "right"; key: "turn_right" }
            }
            Row {
                visible: root.oemBar && backend.values["ambient"] !== undefined
                anchors.right: gearIcon.left; anchors.rightMargin: 22; y: 4; spacing: 8
                Text { anchors.baseline: outT.baseline; text: "OUTSIDE"; color: colors.dim
                       font.family: theme.fonts.label; font.pixelSize: 14; font.letterSpacing: 1.5 }
                Text { id: outT; color: colors.text; font.family: theme.fonts.digits; font.pixelSize: 32
                       text: backend.fresh["ambient"] === true ? backend.values["ambient"].toFixed(0) + "°" : "--" }
            }
            Text {
                id: gearIcon
                anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                text: "⚙"
                color: colors.text; font.pixelSize: root.oemBar ? 42 : 32
                MouseArea { anchors.fill: parent; anchors.margins: -12; onClicked: settings.visible = true }
            }
        }

        // ---- page dots for the OEM-style bar (bottom centre)
        Row {
            visible: root.oemBar && root.pages.length > 1 && !settings.visible && !picker.visible && !colorPicker.visible
                     && !fillup.visible && !history.visible && !exportPanel.visible && !confirm.visible
            anchors.horizontalCenter: parent.horizontalCenter; y: 566; spacing: 9; z: 4
            Repeater {
                model: root.pages.length
                Rectangle {
                    width: index === pagesView.currentIndex ? 22 : 8; height: 8; radius: 4
                    color: index === pagesView.currentIndex ? colors.accent : colors.panelBorder
                    Behavior on width { NumberAnimation { duration: 200 } }
                    MouseArea { anchors.fill: parent; anchors.margins: -10
                                onClicked: { pagesView.currentIndex = index; backend.setPage(index) } }
                }
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
            y: shiftBar.visible ? 68 : 48; width: 520; height: 56; radius: 12
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
            onOpenFillup: { visible = false; fillup.openNew() }
            onOpenHistory: { visible = false; history.visible = true }
            onOpenExport: { visible = false; exportPanel.visible = true }
            onOpenColors: { visible = false; colorPicker.visible = true }
        }
        ExportPanel {
            id: exportPanel
            objectName: "exportPanel"
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
            onEditRow: (row) => fillup.openEdit(row)
            onDeleteAll: root.askDeleteAll()
        }
        FillUp {
            id: fillup
            objectName: "fillupPanel"
            anchors.fill: parent
            visible: false
            theme: root.theme; gw: backend
            onClose: visible = false
            onDeleteRow: (id) => root.askConfirm("Delete this fill-up?",
                "Miles and MPG for the next fill-up are recalculated.", "Delete",
                function() { backend.fuelDelete(id); fillup.visible = false })
        }
        ColorPicker {
            id: colorPicker
            objectName: "colorsPanel"
            anchors.fill: parent
            visible: false
            theme: root.theme
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

        Confirm {
            id: confirm
            objectName: "confirmPanel"
            property var action: null
            anchors.fill: parent
            visible: false
            theme: root.theme
            onAccepted: { visible = false; var a = action; action = null; if (a) a() }
            onRejected: { visible = false; action = null }
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

        // ---- edit mode bar: tap any reading to change it
        Rectangle {
            visible: backend.editMode && !picker.visible
            z: 60
            width: parent.width; height: 56
            color: "#0d141c"; border.color: colors.accent; border.width: 2
            Text { x: 20; anchors.verticalCenter: parent.verticalCenter
                   text: "EDIT  ·  Tap a reading to change it"; color: colors.text
                   font.pixelSize: 26; font.bold: true }
            Btn { theme: root.theme; anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                  width: 150; height: 44; text: "Done"; active: true; onClicked: backend.setEditMode(false) }
        }

        // ---- simulator badge: always on top in sim mode, so fake numbers can't pass as real
        Rectangle {
            visible: backend.sourceMode === "sim" && !demoMode
            z: 50
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10
            width: simText.implicitWidth + 28; height: 36; radius: 18
            color: "#e0a000"; border.color: "#000000"; border.width: 2
            Text { id: simText; anchors.centerIn: parent; text: "SIMULATOR"; color: "#000000"
                   font.pixelSize: 18; font.bold: true }
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
