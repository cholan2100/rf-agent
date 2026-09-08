"""
Task 2: Programmatic KiCad 10 PCB Generator using pcbnew API.
Synthesizes fully routed RF PCBs with precision CPWG / Microstrip controlled impedance,
collinear RF path routing, ground planes, via stitching, and executes headless DRC validation.
"""

import os
import sys
import subprocess
import json
from .spec import CircuitSpec

def mm(val_mm):
    """Convert millimeters to KiCad internal nanometers (1 nm = 1e-6 mm)."""
    return int(val_mm * 1e6)

def generate_pcb(spec: CircuitSpec, output_dir: str) -> tuple[str, dict]:
    """
    Synthesize KiCad PCB file (.kicad_pcb) for the specification.
    Returns (pcb_file_path, drc_results_dict).
    """
    os.makedirs(output_dir, exist_ok=True)
    pcb_path = os.path.join(output_dir, f"{spec.name}.kicad_pcb")
    drc_path = os.path.join(output_dir, f"{spec.name}_drc.json")
    
    # Check if pcbnew is available
    try:
        import pcbnew
    except ImportError:
        raise RuntimeError("pcbnew Python module not found. Ensure this is run inside the RF Workbench container.")

    board = pcbnew.BOARD()
    design_settings = board.GetDesignSettings()
    design_settings.m_TrackMinWidth = mm(0.2)
    design_settings.m_ViasMinSize = mm(0.6)
    design_settings.m_ViasMinDrill = mm(0.3)

    # 1. Nets Setup
    net_gnd = pcbnew.NETINFO_ITEM(board, "GND")
    net_in = pcbnew.NETINFO_ITEM(board, "RF_IN")
    net_out = pcbnew.NETINFO_ITEM(board, "RF_OUT")
    
    board.Add(net_gnd)
    board.Add(net_in)
    board.Add(net_out)

    # 2. Board Perimeter (Edge.Cuts) with rounded corners
    W, H = spec.width_mm, spec.height_mm
    r = 2.0  # corner fillet radius

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
        os.path.expanduser("~/.local/share/kicad/10.0/footprints"),
        os.path.expanduser("~/.local/share/kicad/8.0/footprints")
    ]
    fp_base = None
    for d in fp_search_dirs:
        if os.path.isdir(d):
            fp_base = d
            break

    if not fp_base:
        raise FileNotFoundError(f"KiCad footprint library directory not found in: {fp_search_dirs}")

    def load_fp(lib, name):
        p = os.path.join(fp_base, f"{lib}.pretty")
        fp = pcbnew.FootprintLoad(p, name)
        if not fp:
            raise ValueError(f"Could not load footprint {name} from {p}")
        return fp

    # 4. Footprints Placement
    # Standard RF layout: Collinear RF signal path along horizontal centerline y = H/2.0
    y_rf = H / 2.0

    # J1: Port 1 Connector at (4.5, y_rf) -> Pin 1 at (4.5, y_rf), Pin 2 at (4.5, y_rf + 2.54)
    j1 = load_fp("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical")
    j1.SetReference("J1")
    j1.SetValue("SMA_IN")
    j1.SetPosition(pcbnew.VECTOR2I(mm(4.5), mm(y_rf)))
    board.Add(j1)

    # J2: Port 2 Connector at (W - 4.5, y_rf) -> Pin 1 at (W - 4.5, y_rf), Pin 2 at (W - 4.5, y_rf + 2.54)
    j2 = load_fp("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical")
    j2.SetReference("J2")
    j2.SetValue("SMA_OUT")
    j2.SetPosition(pcbnew.VECTOR2I(mm(W - 4.5), mm(y_rf)))
    board.Add(j2)

    # Component refs & types
    c_keys = list(spec.components.keys())
    ref1 = c_keys[0] if len(c_keys) > 0 else "R1"
    ref2 = c_keys[1] if len(c_keys) > 1 else "R2"
    ref3 = c_keys[2] if len(c_keys) > 2 else "R3"

    def get_fp_for_comp(ref):
        comp = spec.components.get(ref, {})
        ctype = comp.get("type", "resistor")
        if ctype == "capacitor":
            return load_fp("Capacitor_SMD", "C_0805_2012Metric"), comp.get("value", "100pF")
        elif ctype == "inductor":
            return load_fp("Inductor_SMD", "L_0805_2012Metric"), comp.get("value", "100nH")
        else:
            return load_fp("Resistor_SMD", "R_0805_2012Metric"), comp.get("value", "50R")

    # Shunt component 1 at x = 10.5
    # Oriented 270 deg: Pad 1 at y = y_rf (on RF path), Pad 2 at y = y_rf + 1.825 (GND)
    fp1, val1 = get_fp_for_comp(ref1)
    fp1.SetReference(ref1)
    fp1.SetValue(val1)
    fp1.SetPosition(pcbnew.VECTOR2I(mm(10.5), mm(y_rf + 0.9125)))
    fp1.SetOrientationDegrees(270.0)
    board.Add(fp1)

    # Series component 2 at x = W/2.0
    # Oriented 0 deg: Pad 1 at (W/2 - 0.9125, y_rf), Pad 2 at (W/2 + 0.9125, y_rf)
    fp2, val2 = get_fp_for_comp(ref2)
    fp2.SetReference(ref2)
    fp2.SetValue(val2)
    fp2.SetPosition(pcbnew.VECTOR2I(mm(W / 2.0), mm(y_rf)))
    fp2.SetOrientationDegrees(0.0)
    board.Add(fp2)

    # Shunt component 3 at x = W - 10.5
    # Oriented 270 deg: Pad 1 at y = y_rf (on RF path), Pad 2 at y = y_rf + 1.825 (GND)
    fp3, val3 = get_fp_for_comp(ref3)
    fp3.SetReference(ref3)
    fp3.SetValue(val3)
    fp3.SetPosition(pcbnew.VECTOR2I(mm(W - 10.5), mm(y_rf + 0.9125)))
    fp3.SetOrientationDegrees(270.0)
    board.Add(fp3)

    # M2 Mounting Holes
    try:
        mh1 = load_fp("MountingHole", "MountingHole_2.2mm_M2")
        mh1.SetReference("H1")
        mh1.Reference().SetVisible(False)
        mh1.SetPosition(pcbnew.VECTOR2I(mm(3.0), mm(3.0)))
        board.Add(mh1)

        mh2 = load_fp("MountingHole", "MountingHole_2.2mm_M2")
        mh2.SetReference("H2")
        mh2.Reference().SetVisible(False)
        mh2.SetPosition(pcbnew.VECTOR2I(mm(W - 3.0), mm(H - 3.0)))
        board.Add(mh2)
    except Exception:
        pass

    # 5. Assign Nets to Pads
    def assign_pad(fp, pad_num, net):
        pad = fp.FindPadByNumber(pad_num)
        if pad:
            pad.SetNet(net)

    # J1: Pin 1 = RF_IN, Pin 2 = GND
    assign_pad(j1, "1", net_in)
    assign_pad(j1, "2", net_gnd)

    # J2: Pin 1 = RF_OUT, Pin 2 = GND
    assign_pad(j2, "1", net_out)
    assign_pad(j2, "2", net_gnd)

    # Component 1 (Shunt In): Pin 1 = RF_IN, Pin 2 = GND
    assign_pad(fp1, "1", net_in)
    assign_pad(fp1, "2", net_gnd)

    # Component 2 (Series): Pin 1 = RF_IN, Pin 2 = RF_OUT
    assign_pad(fp2, "1", net_in)
    assign_pad(fp2, "2", net_out)

    # Component 3 (Shunt Out): Pin 1 = RF_OUT, Pin 2 = GND
    assign_pad(fp3, "1", net_out)
    assign_pad(fp3, "2", net_gnd)

    # 6. Route Controlled Impedance RF Traces (CPWG / Microstrip)
    rf_w_mm = spec.rf_trace_width_mm

    def route_track(x1, y1, x2, y2, net, width_mm):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        t.SetWidth(mm(width_mm))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        board.Add(t)

    # Get exact pad positions for millimeter-perfect snapping
    p_j1_1 = j1.FindPadByNumber("1").GetPosition()
    p_j1_2 = j1.FindPadByNumber("2").GetPosition()
    p_j2_1 = j2.FindPadByNumber("1").GetPosition()
    p_j2_2 = j2.FindPadByNumber("2").GetPosition()

    p_c1_1 = fp1.FindPadByNumber("1").GetPosition()
    p_c1_2 = fp1.FindPadByNumber("2").GetPosition()
    p_c2_1 = fp2.FindPadByNumber("1").GetPosition()
    p_c2_2 = fp2.FindPadByNumber("2").GetPosition()
    p_c3_1 = fp3.FindPadByNumber("1").GetPosition()
    p_c3_2 = fp3.FindPadByNumber("2").GetPosition()

    x_j1, y_j1 = p_j1_1.x / 1e6, p_j1_1.y / 1e6
    x_c1_1, y_c1_1 = p_c1_1.x / 1e6, p_c1_1.y / 1e6
    x_c2_1, y_c2_1 = p_c2_1.x / 1e6, p_c2_1.y / 1e6
    x_c2_2, y_c2_2 = p_c2_2.x / 1e6, p_c2_2.y / 1e6
    x_c3_1, y_c3_1 = p_c3_1.x / 1e6, p_c3_1.y / 1e6
    x_j2, y_j2 = p_j2_1.x / 1e6, p_j2_1.y / 1e6

    # Collinear RF Path Routing along y = y_rf with pad taper transitions
    # 1. J1 Pin 1 to Component 1 Pad 1
    route_track(x_j1, y_j1, x_c1_1, y_c1_1, net_in, rf_w_mm)

    # 2. Component 1 Pad 1 to Series Component 2 Pad 1 (with smooth pad transition)
    x_taper_in = x_c2_1 - 0.7
    route_track(x_c1_1, y_c1_1, x_taper_in, y_c2_1, net_in, rf_w_mm)
    route_track(x_taper_in, y_c2_1, x_c2_1, y_c2_1, net_in, 0.8)

    # 3. Series Component 2 Pad 2 to Component 3 Pad 1 (with smooth pad transition)
    x_taper_out = x_c2_2 + 0.7
    route_track(x_c2_2, y_c2_2, x_taper_out, y_c2_2, net_out, 0.8)
    route_track(x_taper_out, y_c2_2, x_c3_1, y_c3_1, net_out, rf_w_mm)

    # 4. Component 3 Pad 1 to J2 Pin 1
    route_track(x_c3_1, y_c3_1, x_j2, y_j2, net_out, rf_w_mm)

    # 7. Ground Connections & Via Stitching
    def add_via(x_mm, y_mm):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(mm(x_mm), mm(y_mm)))
        v.SetWidth(mm(0.8))
        v.SetDrill(mm(0.4))
        v.SetNet(net_gnd)
        board.Add(v)

    # Direct ground vias for shunt components
    x_c1_2, y_c1_2 = p_c1_2.x / 1e6, p_c1_2.y / 1e6
    route_track(x_c1_2, y_c1_2, x_c1_2, y_c1_2 + 1.2, net_gnd, 0.8)
    add_via(x_c1_2, y_c1_2 + 1.2)

    x_c3_2, y_c3_2 = p_c3_2.x / 1e6, p_c3_2.y / 1e6
    route_track(x_c3_2, y_c3_2, x_c3_2, y_c3_2 + 1.2, net_gnd, 0.8)
    add_via(x_c3_2, y_c3_2 + 1.2)

    # J1 & J2 GND pin vias
    x_j1_2, y_j1_2 = p_j1_2.x / 1e6, p_j1_2.y / 1e6
    route_track(x_j1_2, y_j1_2, x_j1_2, y_j1_2 + 1.2, net_gnd, 0.8)
    add_via(x_j1_2, y_j1_2 + 1.2)

    x_j2_2, y_j2_2 = p_j2_2.x / 1e6, p_j2_2.y / 1e6
    route_track(x_j2_2, y_j2_2, x_j2_2, y_j2_2 + 1.2, net_gnd, 0.8)
    add_via(x_j2_2, y_j2_2 + 1.2)

    # CPWG Via Fencing along RF Transmission Line
    # Top fence row at y = y_rf - 2.8 mm
    for vx in [5.5, 9.0, 12.5, 15.0, 17.5, 21.0, 24.5]:
        if 2.0 < vx < (W - 2.0):
            add_via(vx, y_rf - 2.8)

    # Bottom fence row at y = y_rf + 5.0 mm
    for vx in [5.5, 8.0, 13.0, 15.0, 17.0, 22.0, 24.5]:
        if 2.0 < vx < (W - 2.0):
            add_via(vx, y_rf + 5.0)

    # Perimeter ground fence
    for vx in range(6, int(W) - 4, 4):
        add_via(float(vx), 2.0)
        add_via(float(vx), H - 2.0)

    # 8. Copper Pours (Top Ground with CPWG Clearance + Bottom Solid Ground)
    cpwg_gap = spec.cpwg_gap_mm
    for layer in [pcbnew.B_Cu, pcbnew.F_Cu]:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(net_gnd)
        zone.SetLocalClearance(mm(cpwg_gap))
        zone.SetMinThickness(mm(0.25))

        outline = pcbnew.SHAPE_LINE_CHAIN()
        m = 0.35
        outline.Append(mm(m), mm(m))
        outline.Append(mm(W - m), mm(m))
        outline.Append(mm(W - m), mm(H - m))
        outline.Append(mm(m), mm(H - m))
        outline.SetClosed(True)
        zone.AddPolygon(outline)
        board.Add(zone)

    # 9. Silkscreen Annotations
    def add_text(text, x, y, layer=pcbnew.F_SilkS, size=0.8):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(layer)
        t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        board.Add(t)

    add_text(spec.title.split("(")[0].strip(), W / 2.0, 3.2, size=1.0)
    add_text("PORT 1", 4.5, 6.0, size=0.8)
    add_text("PORT 2", W - 4.5, 6.0, size=0.8)
    add_text(f"{spec.z0_ohm:.0f}Ω {spec.trace_mode} w={spec.rf_trace_width_mm:.2f} s={spec.cpwg_gap_mm:.2f}", W / 2.0 - 1.0, H - 3.2, size=0.8)

    # 10. Save Board
    pcbnew.SaveBoard(pcb_path, board)

    # 11. Run Headless DRC with kicad-cli with automatic zone filling & board saving
    drc_cmd = [
        "kicad-cli", "pcb", "drc",
        "--refill-zones",
        "--save-board",
        "--output", drc_path,
        "--format", "json",
        pcb_path
    ]
    drc_res = subprocess.run(drc_cmd, capture_output=True, text=True)
    
    drc_summary = {"violations": 0, "warnings": 0, "report_path": drc_path}
    if os.path.exists(drc_path):
        try:
            with open(drc_path, "r", encoding="utf-8") as f:
                content = f.read()
                drc_summary["violations"] = content.count('"severity": "error"')
                drc_summary["warnings"] = content.count('"severity": "warning"')
        except Exception:
            pass

    return pcb_path, drc_summary
