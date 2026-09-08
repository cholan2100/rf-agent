#!/usr/bin/env python3
"""
Simple 5V LED Indicator PCB Generator using KiCad's pcbnew Python API.
Synthesizes a 2-layer PCB (25mm x 20mm) with:
- J1: 2-pin power connector (Pin 1: +5V, Pin 2: GND)
- R1: 330 Ohm 0805 current-limiting resistor
- D1: 0805 SMD LED
- M2 mounting holes
- Top and bottom ground copper zones
- 100% routed copper tracks
"""

import os
import sys
import pcbnew

def mm(val):
    return int(val * 1e6)

def create_board(output_path="led_board.kicad_pcb"):
    print("=" * 60)
    print("  Synthesizing Simple LED PCB via KiCad Python API")
    print("=" * 60)

    board = pcbnew.BOARD()
    design_settings = board.GetDesignSettings()
    design_settings.m_TrackMinWidth = mm(0.25)

    # 1. Nets Setup
    net_gnd = pcbnew.NETINFO_ITEM(board, "GND")
    net_vcc = pcbnew.NETINFO_ITEM(board, "+5V")
    net_anode = pcbnew.NETINFO_ITEM(board, "NET_LED_ANODE")

    board.Add(net_gnd)
    board.Add(net_vcc)
    board.Add(net_anode)

    print(f"Created nets: GND (ID {net_gnd.GetNetCode()}), +5V (ID {net_vcc.GetNetCode()}), NET_LED_ANODE (ID {net_anode.GetNetCode()})")

    # 2. Board Dimensions: 25.0 mm x 20.0 mm
    W, H = 25.0, 20.0
    r = 2.0  # Corner radius

    # Edge.Cuts with rounded corners
    def add_line(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        s.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.15))
        board.Add(s)

    def add_arc(cx, cy, sx, sy, ex, ey):
        arc = pcbnew.PCB_SHAPE(board)
        arc.SetShape(pcbnew.SHAPE_T_ARC)
        arc.SetCenter(pcbnew.VECTOR2I(mm(cx), mm(cy)))
        arc.SetStart(pcbnew.VECTOR2I(mm(sx), mm(sy)))
        arc.SetEnd(pcbnew.VECTOR2I(mm(ex), mm(ey)))
        arc.SetLayer(pcbnew.Edge_Cuts)
        arc.SetWidth(mm(0.15))
        board.Add(arc)

    # Perimeter segments
    add_line(r, 0, W - r, 0)
    add_arc(W - r, r, W - r, 0, W, r)
    add_line(W, r, W, H - r)
    add_arc(W - r, H - r, W, H - r, W - r, H)
    add_line(W - r, H, r, H)
    add_arc(r, H - r, r, H, 0, H - r)
    add_line(0, H - r, 0, r)
    add_arc(r, r, 0, r, r, 0)

    # 3. Locate Footprint Libraries
    fp_search_dirs = [
        "/usr/share/kicad/footprints",
        "D:/Programs/KiCad/share/kicad/footprints",
        os.path.expanduser("~/.local/share/kicad/8.0/footprints")
    ]
    fp_base = None
    for d in fp_search_dirs:
        if os.path.isdir(d):
            fp_base = d
            break

    if not fp_base:
        raise FileNotFoundError(f"KiCad footprint directory not found in: {fp_search_dirs}")

    print(f"Using footprint library base: {fp_base}")

    def load_fp(lib, name):
        p = os.path.join(fp_base, f"{lib}.pretty")
        fp = pcbnew.FootprintLoad(p, name)
        if not fp:
            raise ValueError(f"Cannot load footprint {name} from {p}")
        return fp

    # 4. Footprints Placement
    # J1: 2-pin 2.54mm Header at (5.0, 10.0)
    j1 = load_fp("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical")
    j1.SetReference("J1")
    j1.SetValue("+5V_GND")
    j1.SetPosition(pcbnew.VECTOR2I(mm(5.0), mm(10.0)))
    board.Add(j1)

    # R1: 0805 SMD Resistor at (13.0, 7.5), oriented horizontal
    r1 = load_fp("Resistor_SMD", "R_0805_2012Metric")
    r1.SetReference("R1")
    r1.SetValue("330R")
    r1.SetPosition(pcbnew.VECTOR2I(mm(13.0), mm(7.5)))
    board.Add(r1)

    # D1: 0805 SMD LED at (19.0, 10.0), oriented vertical
    d1 = load_fp("LED_SMD", "LED_0805_2012Metric")
    d1.SetReference("D1")
    d1.SetValue("RED_LED")
    d1.SetPosition(pcbnew.VECTOR2I(mm(19.0), mm(10.0)))
    d1.SetOrientationDegrees(90.0)
    board.Add(d1)

    # M2 Mounting Holes at (3.0, 3.0) and (22.0, 17.0)
    try:
        mh1 = load_fp("MountingHole", "MountingHole_2.2mm_M2")
        mh1.SetReference("H1")
        mh1.Reference().SetVisible(False)
        mh1.SetPosition(pcbnew.VECTOR2I(mm(3.0), mm(3.0)))
        board.Add(mh1)

        mh2 = load_fp("MountingHole", "MountingHole_2.2mm_M2")
        mh2.SetReference("H2")
        mh2.Reference().SetVisible(False)
        mh2.SetPosition(pcbnew.VECTOR2I(mm(22.0), mm(17.0)))
        board.Add(mh2)
    except Exception as e:
        print(f"Note: Mounting hole footprint skipped: {e}")

    # 5. Assign Nets to Pads
    def assign_pad_net(fp, pad_num, net):
        pad = fp.FindPadByNumber(pad_num)
        if pad:
            pad.SetNet(net)
        else:
            print(f"Warning: Pad {pad_num} not found on {fp.GetReference()}")

    # J1: Pin 1 = +5V, Pin 2 = GND
    assign_pad_net(j1, "1", net_vcc)
    assign_pad_net(j1, "2", net_gnd)

    # R1: Pin 1 = +5V, Pin 2 = NET_LED_ANODE
    assign_pad_net(r1, "1", net_vcc)
    assign_pad_net(r1, "2", net_anode)

    # D1: Pin 2 (Anode) = NET_LED_ANODE, Pin 1 (Cathode) = GND
    assign_pad_net(d1, "2", net_anode)
    assign_pad_net(d1, "1", net_gnd)

    # 6. Route Copper Tracks
    def route_track(x1, y1, x2, y2, net, width_mm=0.5):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        t.SetWidth(mm(width_mm))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        board.Add(t)

    # Route +5V from J1 Pin 1 (5.0, 8.73) to R1 Pin 1 (12.05, 7.5)
    pad_j1_1 = j1.FindPadByNumber("1").GetPosition()
    pad_r1_1 = r1.FindPadByNumber("1").GetPosition()
    pad_r1_2 = r1.FindPadByNumber("2").GetPosition()
    pad_d1_2 = d1.FindPadByNumber("2").GetPosition()
    pad_d1_1 = d1.FindPadByNumber("1").GetPosition()
    pad_j1_2 = j1.FindPadByNumber("2").GetPosition()

    # Track 1: J1-1 (+5V) -> R1-1 (+5V) with 45-degree dogleg
    x_j1_1, y_j1_1 = pad_j1_1.x / 1e6, pad_j1_1.y / 1e6
    x_r1_1, y_r1_1 = pad_r1_1.x / 1e6, pad_r1_1.y / 1e6
    route_track(x_j1_1, y_j1_1, x_j1_1 + 2.0, y_j1_1 - 1.0, net_vcc, 0.5)
    route_track(x_j1_1 + 2.0, y_j1_1 - 1.0, x_r1_1 - 1.0, y_r1_1, net_vcc, 0.5)
    route_track(x_r1_1 - 1.0, y_r1_1, x_r1_1, y_r1_1, net_vcc, 0.5)

    # Track 2: R1-2 (Anode) -> D1-2 (Anode)
    x_r1_2, y_r1_2 = pad_r1_2.x / 1e6, pad_r1_2.y / 1e6
    x_d1_2, y_d1_2 = pad_d1_2.x / 1e6, pad_d1_2.y / 1e6
    route_track(x_r1_2, y_r1_2, x_d1_2 - 1.5, y_r1_2, net_anode, 0.4)
    route_track(x_d1_2 - 1.5, y_r1_2, x_d1_2, y_d1_2, net_anode, 0.4)

    # Track 3: D1-1 (Cathode / GND) -> J1-2 (GND)
    x_d1_1, y_d1_1 = pad_d1_1.x / 1e6, pad_d1_1.y / 1e6
    x_j1_2, y_j1_2 = pad_j1_2.x / 1e6, pad_j1_2.y / 1e6
    route_track(x_d1_1, y_d1_1, x_d1_1, y_d1_1 + 2.5, net_gnd, 0.5)
    route_track(x_d1_1, y_d1_1 + 2.5, x_j1_2 + 2.5, y_d1_1 + 2.5, net_gnd, 0.5)
    route_track(x_j1_2 + 2.5, y_d1_1 + 2.5, x_j1_2, y_j1_2, net_gnd, 0.5)

    # 7. Copper Pour (Solid Bottom GND Zone + Top GND Fill)
    for layer, net in [(pcbnew.B_Cu, net_gnd), (pcbnew.F_Cu, net_gnd)]:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(net)
        zone.SetLocalClearance(mm(0.35))
        zone.SetMinThickness(mm(0.2))
        
        # Zone outline (inset 0.3mm from edge)
        outline = pcbnew.SHAPE_LINE_CHAIN()
        margin = 0.3
        outline.Append(mm(margin), mm(margin))
        outline.Append(mm(W - margin), mm(margin))
        outline.Append(mm(W - margin), mm(H - margin))
        outline.Append(mm(margin), mm(H - margin))
        outline.SetClosed(True)
        zone.AddPolygon(outline)
        board.Add(zone)

    # 8. Silkscreen Markings
    def add_text(text_str, x, y, layer=pcbnew.F_SilkS, size_mm=1.0):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text_str)
        t.SetLayer(layer)
        t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        t.SetTextSize(pcbnew.VECTOR2I(mm(size_mm), mm(size_mm)))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        board.Add(t)

    add_text("LED INDICATOR", W / 2.0, 2.5, size_mm=1.2)
    add_text("+5V", 5.0, 6.0, size_mm=0.8)
    add_text("GND", 8.5, 12.54, size_mm=0.8)
    add_text("REV 1.0", W / 2.0, 17.5, size_mm=0.8)

    # 9. Save Board
    pcbnew.SaveBoard(output_path, board)
    print(f"\n[SUCCESS] PCB file successfully generated: {output_path}")
    print(f"  Dimensions: {W} mm x {H} mm")
    print(f"  Tracks: {len(board.GetTracks())}")
    print(f"  Zones: {board.GetAreaCount()}")
    print("=" * 60)

if __name__ == "__main__":
    try:
        out_file = sys.argv[1] if len(sys.argv) > 1 else "led_board.kicad_pcb"
        create_board(out_file)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
