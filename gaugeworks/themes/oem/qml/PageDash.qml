// Premium theme "dash" page: tach (gear in the hub) | economy + engine card |
// speedometer, chrome sub-dials, ODO and trip along the bottom.
// Slots: center = tach, left = speed, small1 = tach sub-dial, right/small2/panel
// = card bars. Fuel level (from the page's tiles) goes in the speedo sub-dial;
// without it, small2 moves there and oil takes its bar.
import QtQuick

Item {
    id: p
    property var theme
    property var pg: ({})
    property string gearKey: ""
    signal pick(string slot, string current)
    signal resetAsk(string kind)
    readonly property var sl: pg.slots || ({})
    readonly property var gz: pg.gauges || ({})
    readonly property var colors: theme ? theme.colors : ({})

    function val(k) { var v = backend.values[k]; return v === undefined ? 0 : v }
    function ok(k) { return k !== undefined && k !== "" && backend.fresh[k] === true }
    function tileUnits(key, dflt) {
        var t = pg.tiles || []
        for (var i = 0; i < t.length; i++) if (t[i].key === key) return t[i].units
        return dflt
    }
    readonly property string econUnits: tileUnits("econ_inst", backend.imperial ? "mpg" : "km/L")
    readonly property string distUnits: backend.imperial ? "mi" : "km"

    // speedo sub-dial: fuel if the page has it, else small2
    readonly property bool fuelSub: gz.fuel_level !== undefined
    readonly property var subR: fuelSub ? gz.fuel_level : (sl.small2 || ({}))
    readonly property var bars: {
        var out = []
        if (sl.right) out.push({slot: "right", cfg: sl.right})
        if (fuelSub && sl.small2) out.push({slot: "small2", cfg: sl.small2})
        if (sl.panel) out.push({slot: "panel", cfg: sl.panel})
        if (out.length < 3 && gz.oil_temp_std) out.push({slot: "", cfg: gz.oil_temp_std})
        return out.slice(0, 3)
    }

    Rectangle { y: 52; width: 1024; height: 1; color: Qt.rgba(0.56, 0.7, 0.88, 0.08) }
    Rectangle { y: 540; width: 1024; height: 1; color: Qt.rgba(0.56, 0.7, 0.88, 0.08) }

    // ---- tach
    OemDial {
        id: tach
        x: 10; y: 110; width: 392; height: 392
        visible: !!p.sl.center
        theme: p.theme; cfg: p.sl.center || ({})
        value: p.val(cfg.key); valid: p.ok(cfg.key)
        shiftActive: cfg.key === "rpm" && backend.shift.enabled && valid && value >= backend.shift.rpm
        readonly property bool hasGear: cfg.key === "rpm" && p.gearKey !== ""
        hubLabel: hasGear ? "GEAR" : (cfg.units || "").toUpperCase()
        hubText: hasGear ? (p.ok(p.gearKey) ? p.val(p.gearKey).toFixed(0) : "–")
                         : (valid ? value.toFixed(cfg.decimals || 0) : "--")
        hubDim: hasGear ? !p.ok(p.gearKey) : !valid
        hubSub: hasGear && valid ? Math.round(value).toLocaleString(Qt.locale("en_US"), "f", 0) + " rpm" : ""
        onHeld: p.pick("center", cfg.key || "")
    }
    OemSub {
        x: tach.x + 196 - 48; y: tach.y + 196 + 130 - 48; width: 96; height: 96
        visible: !!p.sl.small1 && !p.sl.small1.missing
        theme: p.theme; cfg: p.sl.small1 || ({})
        value: p.val(cfg.key); valid: p.ok(cfg.key)
        onHeld: p.pick("small1", cfg.key || "")
    }

    // ---- speedometer
    OemDial {
        id: speedo
        x: 622; y: 110; width: 392; height: 392
        visible: !!p.sl.left
        theme: p.theme; cfg: p.sl.left || ({})
        value: p.val(cfg.key); valid: p.ok(cfg.key)
        hubLabel: ""
        hubText: valid ? value.toFixed(0) : "--"
        hubDim: !valid
        hubSub: (cfg.units || "").toUpperCase()
        onHeld: p.pick("left", cfg.key || "")
    }
    OemSub {
        x: speedo.x + 196 - 48; y: speedo.y + 196 + 130 - 48; width: 96; height: 96
        visible: p.subR.key !== undefined && !p.subR.missing
        theme: p.theme; cfg: p.subR
        value: p.val(cfg.key); valid: p.ok(cfg.key)
        onHeld: if (!p.fuelSub) p.pick("small2", cfg.key || "")
    }

    // ---- centre card
    Rectangle {
        id: card
        x: 402; y: 104; width: 220; height: 402; radius: 16
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.rgba(0.08, 0.125, 0.18, 0.9) }
            GradientStop { position: 1; color: Qt.rgba(0.03, 0.045, 0.07, 0.92) }
        }
        border.color: Qt.rgba(0.6, 0.66, 0.74, 0.35)
        Rectangle { x: 16; width: parent.width - 32; height: 1; color: Qt.rgba(0.74, 0.84, 1, 0.3) }

        Text { x: 18; y: 18; text: "FUEL ECONOMY"; color: "#8796ab"
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 11; font.letterSpacing: 2 }
        Text {
            id: inst
            x: 16; y: 34
            text: p.ok("econ_inst") ? p.val("econ_inst").toFixed(1) : "--"
            color: p.colors.text; font.family: "Barlow Medium"; font.pixelSize: 50
        }
        Text { x: 122; y: 52; text: "INSTANT"; color: "#5f6d82"
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 11; font.letterSpacing: 1.5 }
        Text { x: 122; y: 67; text: p.econUnits.toUpperCase(); color: p.colors.dim
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 13; font.letterSpacing: 1.5 }

        // 30-minute instant economy history: one bar per 75 s
        Item {
            id: hist
            x: 18; y: 106; width: 184; height: 60
            property var samples: []
            readonly property real topV: Math.max.apply(null, [10, p.val("econ_tank")].concat(samples)) * 1.15
            function add(v) { var a = samples.slice(); a.push(v); if (a.length > 24) a.shift(); samples = a }
            Timer {
                interval: 75000; running: true; repeat: true; triggeredOnStart: true
                onTriggered: if (p.ok("econ_inst")) hist.add(p.val("econ_inst"))
            }
            Component.onCompleted: if (typeof demoMode !== "undefined" && demoMode) {
                var base = p.val("econ_inst") || 7, a = []
                for (var i = 0; i < 23; i++) a.push(base * (0.72 + 0.28 * Math.abs(Math.sin(i * 0.9)) + 0.06 * (i % 3)))
                a.push(base); samples = a
            }
            Repeater {
                model: hist.samples.length
                Rectangle {
                    readonly property real v: hist.samples[index]
                    width: 6; radius: 1.2
                    x: (24 - hist.samples.length + index) * 7.7
                    height: Math.max(2, hist.height * v / hist.topV); y: hist.height - height
                    opacity: index === hist.samples.length - 1 ? 1 : 0.35 + 0.4 * index / 24
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#4fb0ff" }
                        GradientStop { position: 1; color: "#1b4f8c" }
                    }
                }
            }
            Repeater {   // dashed tank-average line
                model: p.ok("econ_tank") ? 31 : 0
                Rectangle { x: index * 6; width: 3; height: 1; color: Qt.rgba(0.91, 0.93, 0.96, 0.55)
                            y: hist.height - hist.height * p.val("econ_tank") / hist.topV }
            }
            Rectangle { y: hist.height; width: parent.width; height: 1; color: Qt.rgba(0.43, 0.49, 0.58, 0.4) }
            Text { y: hist.height + 5; text: "30 MIN"; color: "#5f6d82"
                   font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 10; font.letterSpacing: 1 }
            Text { anchors.right: parent.right; y: hist.height + 5; text: "NOW"; color: "#5f6d82"
                   font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 10; font.letterSpacing: 1 }
        }

        // tank / trip averages (tap TRIP to reset it)
        Repeater {
            model: [{key: "econ_tank", label: "TANK AVG"}, {key: "econ_trip", label: "TRIP AVG"}]
            Item {
                x: 18 + index * 100; y: 196; width: 92; height: 46
                Text { text: modelData.label; color: p.colors.dim
                       font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 11; font.letterSpacing: 1.5 }
                Text {
                    id: av; y: 12
                    text: p.ok(modelData.key) ? p.val(modelData.key).toFixed(1) : "--"
                    color: p.colors.text; font.family: "Barlow Medium"; font.pixelSize: 26
                }
                Text { anchors.left: av.right; anchors.leftMargin: 4; anchors.baseline: av.baseline
                       text: p.econUnits; color: p.colors.dim
                       font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 11 }
                Text { anchors.right: parent.right; y: 0
                       visible: backend.econCorrected && backend.econFactor > 0
                       text: "corr"; color: p.colors.accent; font.pixelSize: 10; font.bold: true }
                MouseArea { anchors.fill: parent; enabled: modelData.key === "econ_trip"
                            onClicked: p.resetAsk("trip") }
            }
        }
        Rectangle { x: 116; y: 198; width: 1; height: 40; color: Qt.rgba(0.49, 0.61, 0.77, 0.18) }
        Rectangle { x: 18; y: 254; width: 184; height: 1; color: Qt.rgba(0.49, 0.61, 0.77, 0.18) }

        Column {
            x: 18; y: 272; width: 184; spacing: 12
            Repeater {
                model: p.bars
                OemBar {
                    width: 184; theme: p.theme; cfg: modelData.cfg
                    onHeld: if (modelData.slot !== "") p.pick(modelData.slot, modelData.cfg.key || "")
                }
            }
        }
    }

    // ---- bottom bar: odometer, trip distance
    Row {
        x: 36; y: 560; spacing: 10
        visible: backend.values["odometer"] !== undefined
        Text { anchors.baseline: odo.baseline; text: "ODO"; color: p.colors.dim
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 11; font.letterSpacing: 1.5 }
        Text { id: odo; text: Math.round(p.val("odometer")).toLocaleString(Qt.locale("en_US"), "f", 0) + " " + p.distUnits
               color: p.ok("odometer") ? p.colors.text : p.colors.dim; font.family: "Barlow Medium"; font.pixelSize: 17 }
    }
    Row {
        anchors.right: parent.right; anchors.rightMargin: 36; y: 560; spacing: 10
        visible: backend.values["trip_dist"] !== undefined
        Text { anchors.baseline: trip.baseline; text: "TRIP"; color: p.colors.dim
               font.family: "Barlow Semi Condensed SemiBold"; font.pixelSize: 11; font.letterSpacing: 1.5 }
        Text { id: trip; text: p.val("trip_dist").toFixed(1) + " " + p.distUnits
               color: p.colors.text; font.family: "Barlow Medium"; font.pixelSize: 17 }
    }
}
