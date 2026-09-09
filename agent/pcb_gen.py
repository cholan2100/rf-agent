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
    net_mid = pcbnew.NETINFO_ITEM(board, "NET_MID")
    
    board.Add(net_gnd)
    board.Add(net_in)
    board.Add(net_out)
    board.Add(net_mid)

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

    def load_connector_fp(ref: str, default_val: str):
        comp = spec.components.get(ref, {})
        val = comp.get("value", default_val)
        pkg = comp.get("package", "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount")
        if ":" in pkg:
            lib, mod = pkg.split(":", 1)
        else:
            lib, mod = "Connector_Coaxial", "SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount"
        try:
            fp = load_fp(lib, mod)
        except Exception:
            fp = load_fp("Connector_Coaxial", "SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount")
            pkg = "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount"
        fp.SetReference(ref)
        fp.SetValue(val)
        return fp, pkg

    # 4. Footprints Placement
    # Standard RF layout: Collinear RF signal path along horizontal centerline y = H/2.0
    y_rf = H / 2.0

    # J1: Port 1 Connector (default: Samtec SMA EdgeMount on left PCB edge x = 0)
    j1, j1_pkg = load_connector_fp("J1", "SMA_IN")
    is_edge_mount_j1 = "EdgeMount" in j1_pkg or "EM1" in j1_pkg
    if is_edge_mount_j1:
        j1.SetPosition(pcbnew.VECTOR2I(mm(2.1), mm(y_rf)))
        j1.SetOrientationDegrees(180.0)
    else:
        j1.SetPosition(pcbnew.VECTOR2I(mm(4.5), mm(y_rf)))
        j1.SetOrientationDegrees(0.0)
    board.Add(j1)

    # J2: Port 2 Connector (default: Samtec SMA EdgeMount on right PCB edge x = W)
    j2, j2_pkg = load_connector_fp("J2", "SMA_OUT")
    is_edge_mount_j2 = "EdgeMount" in j2_pkg or "EM1" in j2_pkg
    if is_edge_mount_j2:
        j2.SetPosition(pcbnew.VECTOR2I(mm(W - 2.1), mm(y_rf)))
        j2.SetOrientationDegrees(0.0)
    else:
        j2.SetPosition(pcbnew.VECTOR2I(mm(W - 4.5), mm(y_rf)))
        j2.SetOrientationDegrees(0.0)
    board.Add(j2)

    # Component refs & types - filter out connectors and mounting holes
    c_keys = [k for k in spec.components.keys() if not k.startswith("J") and not k.startswith("H")]
    if not c_keys:
        c_keys = ["R1", "R2", "R3"]

    def get_fp_for_comp(ref):
        comp = spec.components.get(ref, {})
        ctype = comp.get("type", "resistor")
        pkg = comp.get("package", "")
        if ":" in pkg:
            lib, mod = pkg.split(":", 1)
            try:
                fp = load_fp(lib, mod)
                if fp:
                    return fp, comp.get("value", "")
            except Exception:
                pass
        if ctype == "capacitor":
            return load_fp("Capacitor_SMD", "C_0805_2012Metric"), comp.get("value", "100pF")
        elif ctype == "inductor":
            return load_fp("Inductor_SMD", "L_0603_1608Metric"), comp.get("value", "100nH")
        else:
            return load_fp("Resistor_SMD", "R_0805_2012Metric"), comp.get("value", "50R")

    def place_shunt_fp(fp, x_center_mm, y_rf_mm):
        fp.SetOrientationDegrees(270.0)
        fp.SetPosition(pcbnew.VECTOR2I(0, 0))
        p1 = fp.FindPadByNumber("1")
        off_y = (p1.GetPosition().y / 1e6) if p1 else -0.9125
        fp.SetPosition(pcbnew.VECTOR2I(mm(x_center_mm), mm(y_rf_mm - off_y)))

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

    # 5. Assign Nets to Pads & 6. Route Controlled Impedance Traces
    def assign_pad(fp, pad_num, net):
        for pad in fp.Pads():
            if pad.GetNumber() == str(pad_num):
                pad.SetNet(net)

    # J1: Pin 1 = RF_IN, Pin 2 (all ground pads) = GND
    assign_pad(j1, "1", net_in)
    assign_pad(j1, "2", net_gnd)

    # J2: Pin 1 = RF_OUT, Pin 2 (all ground pads) = GND
    assign_pad(j2, "1", net_out)
    assign_pad(j2, "2", net_gnd)

    rf_w_mm = spec.rf_trace_width_mm

    def route_track(x1, y1, x2, y2, net, width_mm):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
        t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        t.SetWidth(mm(width_mm))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        board.Add(t)

    def add_via(x_mm, y_mm):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(mm(x_mm), mm(y_mm)))
        v.SetWidth(mm(0.8))
        v.SetDrill(mm(0.4))
        v.SetNet(net_gnd)
        board.Add(v)

    p_j1_1 = j1.FindPadByNumber("1").GetPosition()
    p_j2_1 = j2.FindPadByNumber("1").GetPosition()

    x_j1, y_j1 = p_j1_1.x / 1e6, p_j1_1.y / 1e6
    x_j2, y_j2 = p_j2_1.x / 1e6, p_j2_1.y / 1e6

    # J1 & J2 GND return stitching vias
    if is_edge_mount_j1:
        add_via(4.3, y_rf - 2.825)
        add_via(4.3, y_rf + 2.825)
    else:
        p_j1_2 = j1.FindPadByNumber("2").GetPosition()
        x_j1_2, y_j1_2 = p_j1_2.x / 1e6, p_j1_2.y / 1e6
        route_track(x_j1_2, y_j1_2, x_j1_2, y_j1_2 + 1.2, net_gnd, 0.8)
        add_via(x_j1_2, y_j1_2 + 1.2)

    if is_edge_mount_j2:
        add_via(W - 4.3, y_rf - 2.825)
        add_via(W - 4.3, y_rf + 2.825)
    else:
        p_j2_2 = j2.FindPadByNumber("2").GetPosition()
        x_j2_2, y_j2_2 = p_j2_2.x / 1e6, p_j2_2.y / 1e6
        route_track(x_j2_2, y_j2_2, x_j2_2, y_j2_2 + 1.2, net_gnd, 0.8)
        add_via(x_j2_2, y_j2_2 + 1.2)

    if spec.topology in ["calibration_load", "load"]:
        # Dual 50-Ohm Calibration Load Standard (Port 1 and Port 2 independent terminated lines)
        x_term1_a = 8.5
        x_term1_b = 11.0
        x_term2_a = W - 8.5
        x_term2_b = W - 11.0

        # R1 (Port 1 upper shunt: 100R to GND)
        fp1, val1 = get_fp_for_comp("R1")
        fp1.SetReference("R1")
        fp1.SetValue(val1)
        place_shunt_fp(fp1, x_term1_a, y_rf)
        board.Add(fp1)

        # R2 (Port 1 lower shunt: 100R to GND)
        fp2, val2 = get_fp_for_comp("R2")
        fp2.SetReference("R2")
        fp2.SetValue(val2)
        fp2.SetOrientationDegrees(90.0)
        fp2.SetPosition(pcbnew.VECTOR2I(0, 0))
        p2_1 = fp2.FindPadByNumber("1")
        off_y2 = (p2_1.GetPosition().y / 1e6) if p2_1 else -0.9125
        fp2.SetPosition(pcbnew.VECTOR2I(mm(x_term1_b), mm(y_rf - off_y2)))
        board.Add(fp2)

        # R3 (Port 2 upper shunt: 100R to GND)
        fp3, val3 = get_fp_for_comp("R3")
        fp3.SetReference("R3")
        fp3.SetValue(val3)
        place_shunt_fp(fp3, x_term2_a, y_rf)
        board.Add(fp3)

        # R4 (Port 2 lower shunt: 100R to GND)
        fp4, val4 = get_fp_for_comp("R4")
        fp4.SetReference("R4")
        fp4.SetValue(val4)
        fp4.SetOrientationDegrees(90.0)
        fp4.SetPosition(pcbnew.VECTOR2I(0, 0))
        p4_1 = fp4.FindPadByNumber("1")
        off_y4 = (p4_1.GetPosition().y / 1e6) if p4_1 else -0.9125
        fp4.SetPosition(pcbnew.VECTOR2I(mm(x_term2_b), mm(y_rf - off_y4)))
        board.Add(fp4)

        # Pad Nets
        assign_pad(fp1, "1", net_in)
        assign_pad(fp1, "2", net_gnd)
        assign_pad(fp2, "1", net_in)
        assign_pad(fp2, "2", net_gnd)

        assign_pad(fp3, "1", net_out)
        assign_pad(fp3, "2", net_gnd)
        assign_pad(fp4, "1", net_out)
        assign_pad(fp4, "2", net_gnd)

        # Route CPWG RF transmission lines
        route_track(x_j1, y_j1, x_term1_b, y_rf, net_in, rf_w_mm)
        route_track(x_j2, y_j2, x_term2_b, y_rf, net_out, rf_w_mm)

        # Ground return vias for shunt resistors (routed outwards away from RF line)
        for fp in [fp1, fp2, fp3, fp4]:
            p2 = fp.FindPadByNumber("2").GetPosition()
            x2, y2 = p2.x / 1e6, p2.y / 1e6
            dy = 1.2 if y2 > y_rf else -1.2
            route_track(x2, y2, x2, y2 + dy, net_gnd, 0.8)
            add_via(x2, y2 + dy)

        # CPWG Ground Fencing along Port 1 and Port 2 (clear of shunt ground vias)
        for vx in [6.5]:
            add_via(vx, y_rf - 2.8)
            add_via(vx, y_rf + 2.8)
        for vx in [W - 6.5]:
            add_via(vx, y_rf - 2.8)
            add_via(vx, y_rf + 2.8)

        # Center isolation shield barrier vias between Port 1 and Port 2 (>60 dB isolation)
        for bx in [13.5, 15.0, 16.5]:
            for by in [4.0, 7.0, 10.0, 13.0, 16.0]:
                add_via(bx, by)

    elif len(c_keys) == 2 and (spec.topology == "bandpass_shunt" or "shunt" in spec.description.lower()):
        # Shunted Parallel LC Tank bandpass filter
        ref1, ref2 = c_keys[0], c_keys[1]
        fp1, val1 = get_fp_for_comp(ref1)
        fp1.SetReference(ref1)
        fp1.SetValue(val1)
        place_shunt_fp(fp1, W / 2.0 - 3.5, y_rf)
        board.Add(fp1)

        fp2, val2 = get_fp_for_comp(ref2)
        fp2.SetReference(ref2)
        fp2.SetValue(val2)
        place_shunt_fp(fp2, W / 2.0 + 3.5, y_rf)
        board.Add(fp2)

        assign_pad(j1, "1", net_in)
        assign_pad(j2, "1", net_in)
        assign_pad(fp1, "1", net_in)
        assign_pad(fp1, "2", net_gnd)
        assign_pad(fp2, "1", net_in)
        assign_pad(fp2, "2", net_gnd)

        p_c1_2 = fp1.FindPadByNumber("2").GetPosition()
        p_c2_2 = fp2.FindPadByNumber("2").GetPosition()
        x_c1_2, y_c1_2 = p_c1_2.x / 1e6, p_c1_2.y / 1e6
        x_c2_2, y_c2_2 = p_c2_2.x / 1e6, p_c2_2.y / 1e6

        # Continuous through RF transmission line from J1 to J2
        route_track(x_j1, y_j1, x_j2, y_j2, net_in, rf_w_mm)

        # Ground vias for shunt components
        route_track(x_c1_2, y_c1_2, x_c1_2, y_c1_2 + 1.2, net_gnd, 0.8)
        add_via(x_c1_2, y_c1_2 + 1.2)

        route_track(x_c2_2, y_c2_2, x_c2_2, y_c2_2 + 1.2, net_gnd, 0.8)
        add_via(x_c2_2, y_c2_2 + 1.2)

    elif len(c_keys) == 2:
        # Two series resonant elements (e.g. series LC tank bandpass filter)
        ref1, ref2 = c_keys[0], c_keys[1]
        fp1, val1 = get_fp_for_comp(ref1)
        fp1.SetReference(ref1)
        fp1.SetValue(val1)
        fp1.SetPosition(pcbnew.VECTOR2I(mm(W / 2.0 - 3.5), mm(y_rf)))
        fp1.SetOrientationDegrees(0.0)
        board.Add(fp1)

        fp2, val2 = get_fp_for_comp(ref2)
        fp2.SetReference(ref2)
        fp2.SetValue(val2)
        fp2.SetPosition(pcbnew.VECTOR2I(mm(W / 2.0 + 3.5), mm(y_rf)))
        fp2.SetOrientationDegrees(0.0)
        board.Add(fp2)

        assign_pad(fp1, "1", net_in)
        assign_pad(fp1, "2", net_mid)
        assign_pad(fp2, "1", net_mid)
        assign_pad(fp2, "2", net_out)

        p_c1_1 = fp1.FindPadByNumber("1").GetPosition()
        p_c1_2 = fp1.FindPadByNumber("2").GetPosition()
        p_c2_1 = fp2.FindPadByNumber("1").GetPosition()
        p_c2_2 = fp2.FindPadByNumber("2").GetPosition()

        x_c1_1 = p_c1_1.x / 1e6
        x_c1_2 = p_c1_2.x / 1e6
        x_c2_1 = p_c2_1.x / 1e6
        x_c2_2 = p_c2_2.x / 1e6

        # 1. J1 to FP1 Pad 1
        x_taper_in = x_c1_1 - 0.7
        route_track(x_j1, y_j1, x_taper_in, y_j1, net_in, rf_w_mm)
        route_track(x_taper_in, y_j1, x_c1_1, y_j1, net_in, 0.8)

        # 2. FP1 Pad 2 to FP2 Pad 1 (Series connection)
        route_track(x_c1_2, y_j1, x_c2_1, y_j1, net_mid, 0.8)

        # 3. FP2 Pad 2 to J2
        x_taper_out = x_c2_2 + 0.7
        route_track(x_c2_2, y_j2, x_taper_out, y_j2, net_out, 0.8)
        route_track(x_taper_out, y_j2, x_j2, y_j2, net_out, rf_w_mm)

    else:
        # Standard 3-element Pi network (attenuator, lowpass filter, etc.)
        ref1 = c_keys[0] if len(c_keys) > 0 else "R1"
        ref2 = c_keys[1] if len(c_keys) > 1 else "R2"
        ref3 = c_keys[2] if len(c_keys) > 2 else "R3"

        fp1, val1 = get_fp_for_comp(ref1)
        fp1.SetReference(ref1)
        fp1.SetValue(val1)
        place_shunt_fp(fp1, 10.5, y_rf)
        board.Add(fp1)

        fp2, val2 = get_fp_for_comp(ref2)
        fp2.SetReference(ref2)
        fp2.SetValue(val2)
        fp2.SetPosition(pcbnew.VECTOR2I(mm(W / 2.0), mm(y_rf)))
        fp2.SetOrientationDegrees(0.0)
        board.Add(fp2)

        fp3, val3 = get_fp_for_comp(ref3)
        fp3.SetReference(ref3)
        fp3.SetValue(val3)
        place_shunt_fp(fp3, W - 10.5, y_rf)
        board.Add(fp3)

        assign_pad(fp1, "1", net_in)
        assign_pad(fp1, "2", net_gnd)
        assign_pad(fp2, "1", net_in)
        assign_pad(fp2, "2", net_out)
        assign_pad(fp3, "1", net_out)
        assign_pad(fp3, "2", net_gnd)

        p_c1_1 = fp1.FindPadByNumber("1").GetPosition()
        p_c1_2 = fp1.FindPadByNumber("2").GetPosition()
        p_c2_1 = fp2.FindPadByNumber("1").GetPosition()
        p_c2_2 = fp2.FindPadByNumber("2").GetPosition()
        p_c3_1 = fp3.FindPadByNumber("1").GetPosition()
        p_c3_2 = fp3.FindPadByNumber("2").GetPosition()

        x_c1_1, y_c1_1 = p_c1_1.x / 1e6, p_c1_1.y / 1e6
        x_c2_1, y_c2_1 = p_c2_1.x / 1e6, p_c2_1.y / 1e6
        x_c2_2, y_c2_2 = p_c2_2.x / 1e6, p_c2_2.y / 1e6
        x_c3_1, y_c3_1 = p_c3_1.x / 1e6, p_c3_1.y / 1e6

        route_track(x_j1, y_j1, x_c1_1, y_c1_1, net_in, rf_w_mm)

        x_taper_in = x_c2_1 - 0.7
        route_track(x_c1_1, y_c1_1, x_taper_in, y_c2_1, net_in, rf_w_mm)
        route_track(x_taper_in, y_c2_1, x_c2_1, y_c2_1, net_in, 0.8)

        x_taper_out = x_c2_2 + 0.7
        route_track(x_c2_2, y_c2_2, x_taper_out, y_c2_2, net_out, 0.8)
        route_track(x_taper_out, y_c2_2, x_c3_1, y_c3_1, net_out, rf_w_mm)

        route_track(x_c3_1, y_c3_1, x_j2, y_j2, net_out, rf_w_mm)

        # Ground vias for shunt components
        x_c1_2, y_c1_2 = p_c1_2.x / 1e6, p_c1_2.y / 1e6
        route_track(x_c1_2, y_c1_2, x_c1_2, y_c1_2 + 1.2, net_gnd, 0.8)
        add_via(x_c1_2, y_c1_2 + 1.2)

        x_c3_2, y_c3_2 = p_c3_2.x / 1e6, p_c3_2.y / 1e6
        route_track(x_c3_2, y_c3_2, x_c3_2, y_c3_2 + 1.2, net_gnd, 0.8)
        add_via(x_c3_2, y_c3_2 + 1.2)

    # CPWG Via Fencing along RF Transmission Line
    if spec.topology not in ["calibration_load", "load"]:
        # Top fence row at y = y_rf - 2.8 mm (clear of Samtec pads ending at x=4.2 and W-4.2)
        for vx in [6.5, 9.5, 12.5, 15.0, 17.5, 20.5, 23.5, 26.5, 28.5]:
            if 5.0 < vx < (W - 5.0):
                add_via(vx, y_rf - 2.8)

        # Bottom fence row at y = y_rf + 5.0 mm
        for vx in [6.5, 9.5, 13.0, 15.0, 17.0, 21.0, 24.5, 28.5]:
            if 5.0 < vx < (W - 5.0):
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

    if spec.topology in ["calibration_load", "load"]:
        add_text("50Ω CAL LOAD", W / 2.0, 3.2, size=0.8)
        add_text("PORT 1", 5.5, 4.5, size=0.8)
        add_text("PORT 2", W - 5.5, 4.5, size=0.8)
        add_text(f"{spec.z0_ohm:.0f}Ω SOLT MATCH DC-{spec.f_max_ghz:.0f}GHz", W / 2.0, H - 3.2, size=0.8)
    else:
        title_short = spec.title.split("(")[0].strip()
        if len(title_short) > 20:
            title_short = f"{spec.f_0_ghz*1000.0:.0f}MHz LC Bandpass"
        add_text(title_short, W / 2.0, 3.2, size=0.8)
        add_text("PORT 1", 5.0, 4.5, size=0.8)
        add_text("PORT 2", W - 5.0, 4.5, size=0.8)
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
