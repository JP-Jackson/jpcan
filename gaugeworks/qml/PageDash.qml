// "dash" template: speed | big tach (with gear) | boost, two small gauges,
// 4x2 tiles and an optional panel (VGT). Designed at 1024x600.
import QtQuick

Item {
    id: p
    property var theme
    property var pg: ({})
    property string gearKey: ""
    signal pick(string slot, string current)
    signal resetAsk(string kind)
    readonly property var sl: pg.slots || ({})

    SlotView { x: 6; y: 60; width: 300; height: 300; theme: p.theme; cfg: p.sl.left || ({}); slotName: "left"
               visible: !!p.sl.left; gearKey: p.gearKey; onPick: (s, c) => p.pick(s, c) }
    SlotView { x: 322; y: 44; width: 380; height: 380; theme: p.theme; cfg: p.sl.center || ({}); slotName: "center"
               visible: !!p.sl.center; gearKey: p.gearKey; onPick: (s, c) => p.pick(s, c) }
    SlotView { x: 718; y: 60; width: 300; height: 300; theme: p.theme; cfg: p.sl.right || ({}); slotName: "right"
               visible: !!p.sl.right; gearKey: p.gearKey; onPick: (s, c) => p.pick(s, c) }
    SlotView { x: 8; y: 420; width: 172; height: 172; theme: p.theme; cfg: p.sl.small1 || ({}); slotName: "small1"
               visible: !!p.sl.small1; onPick: (s, c) => p.pick(s, c) }
    SlotView { x: 180; y: 420; width: 172; height: 172; theme: p.theme; cfg: p.sl.small2 || ({}); slotName: "small2"
               visible: !!p.sl.small2; onPick: (s, c) => p.pick(s, c) }
    Grid {
        x: 362; y: 432; columns: 4; spacing: 8
        Repeater {
            model: p.pg.tiles || []
            TileSlot { width: 96; height: 76; theme: p.theme; cfg: modelData; index: model.index
                       onPick: (s, c) => p.pick(s, c); onResetAsk: (k) => p.resetAsk(k) }
        }
    }
    SlotView { x: 780; y: 432; width: 236; height: 160; theme: p.theme; cfg: p.sl.panel || ({}); slotName: "panel"
               visible: !!p.sl.panel; onPick: (s, c) => p.pick(s, c) }
}
