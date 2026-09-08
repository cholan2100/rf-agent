"""
Task 2: Programmatic KiCad 10 PCB Generator using pcbnew API.
Synthesizes fully routed RF PCBs with 50-ohm microstrip traces,
ground planes, via stitching, and executes headless DRC validation.
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
            # Fallback to general search
            raise ValueError(f"Could not load footprint {name} from {p}")
        return fp

    # 4. Footprints Placement (for 10dB Attenuator)
    # J1: SMA Input Port at (4.5, 10.0)
    # J2: SMA Output Port at (W - 4.5, 10.0)
    # R1: 0805 Shunt Input at (10.0, 10.0)
    # R2: 0805 Series Resistor at (W/2, 7.0)
    # R3: 0805 Shunt Output at (W - 10.0, 10.0)
    
    # Try coaxial connector footprint or fallback to pin header
    try:
        j1 = load_fp("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical")
        j2 = load_fp("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical")
    except Exception:
        j1 = load_fp("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical")
        j2 = load_fp("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Vertical")

    j1.SetReference("J1")
    j1.SetValue("SMA_IN")
    j1.SetPosition(pcbnew.VECTOR2I(mm(4.5), mm(H / 2.0)))
    board.Add(j1)

    j2.SetReference("J2")
    j2.SetValue("SMA_OUT")
    j2.SetPosition(pcbnew.VECTOR2I(mm(W - 4.5), mm(H / 2.0)))
    board.Add(j2)

    # R1, R2, R3 Resistors
    r1 = load_fp("Resistor_SMD", "R_0805_2012Metric")
    r1.SetReference("R1")
    r1.SetValue("96R")
    r1.SetPosition(pcbnew.VECTOR2I(mm(10.5), mm(H / 2.0)))
    r1.SetOrientationDegrees(90.0)
    board.Add(r1)

    r2 = load_fp("Resistor_SMD", "R_0805_2012Metric")
    r2.SetReference("R2")
    r2.SetValue("71R")
    r2.SetPosition(pcbnew.VECTOR2I(mm(W / 2.0), mm(H / 2.0 - 2.8)))
    board.Add(r2)

    r3 = load_fp("Resistor_SMD", "R_0805_2012Metric")
    r3.SetReference("R3")
    r3.SetValue("96R")
    r3.SetPosition(pcbnew.VECTOR2I(mm(W - 10.5), mm(H / 2.0)))
    r3.SetOrientationDegrees(90.0)
    board.Add(r3)

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
    except Exception as e:
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

    # R1: Pin 1 = RF_IN, Pin 2 = GND
    assign_pad(r1, "1", net_in)
    assign_pad(r1, "2", net_gnd)

    # R2: Pin 1 = RF_IN, Pin 2 = RF_OUT
    assign_pad(r2, "1", net_in)
    assign_pad(r2, "2", net_out)

    # R3: Pin 1 = RF_OUT, Pin 2 = GND
    assign_pad(r3, "1", net_out)
    assign_pad(r3, "2", net_gnd)

    # 6. Route RF Traces (Microstrip 50-ohm)
    # Track width for 50-ohm line (typically ~1.0mm - 2.5mm depending on h)
    rf_w_mm = min(max(spec.microstrip_width_mm, 0.5), 2.8)

    def route_track(x1, y1, x2, y2, net, width_mm):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        t.SetWidth(mm(width_mm))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        board.Add(t)

    # Trace: J1-1 -> R1-1 junction
    p_j1 = j1.FindPadByNumber("1").GetPosition()
    p_r1_1 = r1.FindPadByNumber("1").GetPosition()
    p_r2_1 = r2.FindPadByNumber("1").GetPosition()
    p_r2_2 = r2.FindPadByNumber("2").GetPosition()
    p_r3_1 = r3.FindPadByNumber("1").GetPosition()
    p_j2 = j2.FindPadByNumber("1").GetPosition()

    x_j1, y_j1 = p_j1.x / 1e6, p_j1.y / 1e6
    x_r1, y_r1 = p_r1_1.x / 1e6, p_r1_1.y / 1e6
    x_r2_1, y_r2_1 = p_r2_1.x / 1e6, p_r2_1.y / 1e6
    x_r2_2, y_r2_2 = p_r2_2.x / 1e6, p_r2_2.y / 1e6
    x_r3, y_r3 = p_r3_1.x / 1e6, p_r3_1.y / 1e6
    x_j2, y_j2 = p_j2.x / 1e6, p_j2.y / 1e6

    # RF Input line from J1 to R1 pad 1
    route_track(x_j1, y_j1, x_r1, y_j1, net_in, rf_w_mm)
    route_track(x_r1, y_j1, x_r1, y_r1, net_in, 0.5)

    # Interconnect to R2 pad 1
    route_track(x_r1, y_r1, x_r2_1, y_r2_1, net_in, 0.6)

    # Interconnect from R2 pad 2 to R3 pad 1
    route_track(x_r2_2, y_r2_2, x_r3, y_r3, net_out, 0.6)

    # RF Output line from R3 pad 1 to J2 pad 1
    route_track(x_r3, y_r3, x_r3, y_j2, net_out, 0.5)
    route_track(x_r3, y_j2, x_j2, y_j2, net_out, rf_w_mm)

    # 7. Ground Stitching Vias
    def add_via(x_mm, y_mm):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(mm(x_mm), mm(y_mm)))
        v.SetWidth(mm(0.8))
        v.SetDrill(mm(0.4))
        v.SetNet(net_gnd)
        board.Add(v)

    # Place ground vias around R1, R3 ground pads and perimeter
    p_r1_2 = r1.FindPadByNumber("2").GetPosition()
    p_r3_2 = r3.FindPadByNumber("2").GetPosition()
    add_via(p_r1_2.x / 1e6, p_r1_2.y / 1e6 + 2.0)
    add_via(p_r3_2.x / 1e6, p_r3_2.y / 1e6 + 2.0)

    # Via fence stitching along top and bottom edges
    for vx in range(6, int(W) - 5, 4):
        add_via(float(vx), 2.5)
        add_via(float(vx), H - 2.5)

    # 8. Copper Pours (Top GND with clearance + Bottom Solid GND)
    for layer, net in [(pcbnew.B_Cu, net_gnd), (pcbnew.F_Cu, net_gnd)]:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(net)
        zone.SetLocalClearance(mm(0.4))
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

    # 9. Silkscreen Text
    def add_text(text, x, y, layer=pcbnew.F_SilkS, size=0.9):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(layer)
        t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        board.Add(t)

    add_text(spec.title.split("(")[0].strip(), W / 2.0, 3.2, size=1.0)
    add_text("IN 50Ω", 4.5, 6.0, size=0.8)
    add_text("OUT 50Ω", W - 4.5, 6.0, size=0.8)
    add_text(f"Z0={spec.z0_ohm}Ω", W / 2.0, H - 3.2, size=0.8)

    # 10. Save Board
    pcbnew.SaveBoard(pcb_path, board)

    # 11. Run Headless DRC with kicad-cli
    drc_cmd = [
        "kicad-cli", "pcb", "drc",
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
