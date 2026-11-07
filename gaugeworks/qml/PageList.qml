// "list" template (diagnostic): every channel, scrollable. "?" = unverified.
import QtQuick

Item {
    id: p
    property var theme
    property var pg: ({})
    property var diag: []
    property string gearKey: ""
    signal pick(string slot, string current)
    signal resetAsk(string kind)
    function val(k) { var v = backend.values[k]; return v === undefined ? 0 : v }
    function ok(k) { return k !== undefined && k !== "" && backend.fresh[k] === true }
    function fmt(v) {
        var a = Math.abs(v)
        if (Math.abs(v - Math.round(v)) < 0.005 || a >= 1000) return v.toFixed(0)
        return a >= 10 ? v.toFixed(1) : v.toFixed(2)
    }

    ListView {
        id: lv
        x: 12; y: 52; width: 1000; height: 540
        clip: true
        model: p.diag
        spacing: 2
        delegate: Rectangle {
            width: lv.width; height: 44
            color: index % 2 ? "transparent" : p.theme.colors.panel
            Text { x: 14; anchors.verticalCenter: parent.verticalCenter
                   text: modelData.name + (modelData.verified ? "" : "  ?"); color: p.theme.colors.text; font.pixelSize: 21 }
            Text { x: 640; width: 220; horizontalAlignment: Text.AlignRight; anchors.verticalCenter: parent.verticalCenter
                   text: p.ok(modelData.key) ? p.fmt(p.val(modelData.key)) : "--"
                   color: p.theme.colors.text; font.family: p.theme.fonts.digits; font.pixelSize: 24; font.bold: true }
            Text { x: 880; anchors.verticalCenter: parent.verticalCenter
                   text: modelData.units; color: p.theme.colors.dim; font.pixelSize: 19 }
        }
    }
}
