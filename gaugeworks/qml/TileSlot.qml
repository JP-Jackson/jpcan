// A tile that can be re-assigned with press-and-hold.
import QtQuick

Tile {
    id: ts
    property int index: 0
    signal pick(string slot, string current)
    signal resetAsk(string kind)
    readonly property string resetKind: cfg.key === "econ_trip" ? "trip" : cfg.key === "econ_last" ? "roll" : ""
    value: { var v = backend.values[cfg.key]; return v === undefined ? 0 : v }
    valid: cfg.key !== undefined && backend.fresh[cfg.key] === true
    MouseArea {
        anchors.fill: parent
        pressAndHoldInterval: 600
        onPressAndHold: ts.pick("tile" + ts.index, ts.cfg.key || "")
        onClicked: if (backend.editMode) ts.pick("tile" + ts.index, ts.cfg.key || "")
                   else if (ts.resetKind !== "") ts.resetAsk(ts.resetKind)
    }
}
