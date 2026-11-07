// GaugeWorks main screen, designed at 1024x600 and scaled to the window.
import QtQuick

Rectangle {
    id: root
    readonly property var theme: backend.theme
    readonly property var cfg: backend.config
    readonly property var gauges: cfg.gauges || ({})
    readonly property var colors: theme.colors
    color: colors.background

    function val(key) { var v = backend.values[key]; return v === undefined ? 0 : v }
    function ok(key) { return key !== undefined && key !== "" && backend.fresh[key] === true }

    Item {
        id: stage
        width: 1024; height: 600
        anchors.centerIn: parent
        scale: Math.min(root.width / width, root.height / height)

        // ---- top bar
        Item {
            id: topBar
            width: parent.width; height: 44
            Text {
                x: 16; anchors.verticalCenter: parent.verticalCenter
                text: backend.status.profile || "JpCAN"
                color: colors.dim; font.family: theme.fonts.label; font.pixelSize: 18
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
                anchors.right: gear.left; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter
                color: colors.text; font.family: theme.fonts.digits; font.pixelSize: 20
                Timer { interval: 1000; running: true; repeat: true; triggeredOnStart: true
                        onTriggered: clock.text = Qt.formatTime(new Date(), "h:mm AP") }
            }
            Text {
                id: gear
                anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
                text: "⚙"
                color: colors.text; font.pixelSize: 32
                MouseArea { anchors.fill: parent; anchors.margins: -12; onClicked: settings.visible = true }
            }
        }

        // ---- main gauges
        Gauge {
            id: speedGauge
            theme: root.theme; cfg: gauges.speed || ({})
            visible: !!gauges.speed
            x: 6; y: 60; width: 300; height: 300
            value: val(cfg.key); valid: ok(cfg.key)
        }
        Gauge {
            id: tach
            theme: root.theme; cfg: gauges.tach || ({})
            visible: !!gauges.tach
            x: 512 - 190; y: 44; width: 380; height: 380
            value: val(cfg.key); valid: ok(cfg.key)
            shiftActive: backend.shift.enabled && valid && value >= backend.shift.rpm
            readonly property bool hasGear: (root.cfg.gear || "") !== ""
            bigText: hasGear ? (ok(root.cfg.gear) ? val(root.cfg.gear).toFixed(0) : "\u2013") : ""
            bigDim: hasGear && !ok(root.cfg.gear)
        }
        Gauge {
            id: boostGauge
            theme: root.theme; cfg: gauges.boost || ({})
            visible: !!gauges.boost
            x: 1024 - 306; y: 60; width: 300; height: 300
            value: val(cfg.key); valid: ok(cfg.key)
        }

        // ---- bottom row
        Gauge {
            theme: root.theme; cfg: gauges.coolant || ({})
            visible: !!gauges.coolant
            x: 8; y: 420; width: 172; height: 172
            value: val(cfg.key); valid: ok(cfg.key)
        }
        Gauge {
            theme: root.theme; cfg: gauges.trans || ({})
            visible: !!gauges.trans
            x: 180; y: 420; width: 172; height: 172
            value: val(cfg.key); valid: ok(cfg.key)
        }
        Grid {
            x: 362; y: 432; columns: 4; spacing: 8
            Repeater {
                model: cfg.tiles || []
                Tile {
                    width: 96; height: 76
                    theme: root.theme; cfg: modelData
                    value: val(modelData.key); valid: ok(modelData.key)
                }
            }
        }
        DualBar {
            readonly property var c: gauges.vgt || ({})
            visible: !!gauges.vgt
            x: 780; y: 432; width: 236; height: 160
            theme: root.theme; label: c.label || "VGT"
            desired: val(c.desired); desiredValid: ok(c.desired)
            actual: val(c.actual); actualValid: ok(c.actual)
        }

        Settings {
            id: settings
            objectName: "settingsPanel"
            anchors.fill: parent
            visible: false
            theme: root.theme; gw: backend
            onClose: visible = false
            onOpenFillup: { visible = false; fillup.visible = true }
            onOpenHistory: { visible = false; history.visible = true }
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
