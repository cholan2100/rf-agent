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
        raise RuntimeError("pcbnew Python module not found. Ensure this is run inside the RF Agent container.")

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
    net_vdd = pcbnew.NETINFO_ITEM(board, "VDD")
    net_bias = pcbnew.NETINFO_ITEM(board, "NET_BIAS")
    net_lna_in = pcbnew.NETINFO_ITEM(board, "NET_LNA_IN")
    net_lna_out = pcbnew.NETINFO_ITEM(board, "NET_LNA_OUT")
    net_base = pcbnew.NETINFO_ITEM(board, "NET_BASE")
    net_emitter = pcbnew.NETINFO_ITEM(board, "NET_EMITTER")
    net_collector = pcbnew.NETINFO_ITEM(board, "NET_COLLECTOR")
    
    board.Add(net_gnd)
    board.Add(net_in)
    board.Add(net_out)
    board.Add(net_mid)
    board.Add(net_vdd)
    board.Add(net_bias)
    board.Add(net_lna_in)
    board.Add(net_lna_out)
    board.Add(net_base)
    board.Add(net_emitter)
    board.Add(net_collector)

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

    # J2: Port 2 Connector (only for 2+ port circuits where J2 is defined)
    has_j2 = (spec.num_ports >= 2 and "J2" in spec.components)
    j2 = None
    is_edge_mount_j2 = False
    if has_j2:
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
        if ctype in ["ic", "amplifier"] or ref.startswith("U"):
            try:
                return load_fp("Package_TO_SOT_SMD", "SOT-89-3"), comp.get("value", "SPF5189Z")
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

    # J2: Pin 1 = RF_OUT, Pin 2 (all ground pads) = GND (if present)
    if has_j2 and j2 is not None:
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
    x_j1, y_j1 = p_j1_1.x / 1e6, p_j1_1.y / 1e6

    if has_j2 and j2 is not None:
        p_j2_1 = j2.FindPadByNumber("1").GetPosition()
        x_j2, y_j2 = p_j2_1.x / 1e6, p_j2_1.y / 1e6
    else:
        x_j2, y_j2 = W - 2.1, y_rf

    # J1 & J2 GND return stitching vias
    if is_edge_mount_j1:
        add_via(4.3, y_rf - 2.825)
        add_via(4.3, y_rf + 2.825)
    else:
        p_j1_2 = j1.FindPadByNumber("2").GetPosition()
        x_j1_2, y_j1_2 = p_j1_2.x / 1e6, p_j1_2.y / 1e6
        route_track(x_j1_2, y_j1_2, x_j1_2, y_j1_2 + 1.2, net_gnd, 0.8)
        add_via(x_j1_2, y_j1_2 + 1.2)

    if has_j2 and j2 is not None:
        if is_edge_mount_j2:
            add_via(W - 4.3, y_rf - 2.825)
            add_via(W - 4.3, y_rf + 2.825)
        else:
            p_j2_2 = j2.FindPadByNumber("2").GetPosition()
            x_j2_2, y_j2_2 = p_j2_2.x / 1e6, p_j2_2.y / 1e6
            route_track(x_j2_2, y_j2_2, x_j2_2, y_j2_2 + 1.2, net_gnd, 0.8)
            add_via(x_j2_2, y_j2_2 + 1.2)

    if spec.topology in ["calibration_load", "load"]:
        # 1-Port Precision Calibration Load Standard (J1 Input only)
        x_term1_a = 8.5
        x_term1_b = 11.0

        fp1, val1 = get_fp_for_comp("R1")
        fp1.SetReference("R1")
        fp1.SetValue(val1)
        fp1.Reference().SetVisible(False)
        fp1.Value().SetVisible(False)
        place_shunt_fp(fp1, x_term1_a, y_rf)
        board.Add(fp1)
        assign_pad(fp1, "1", net_in)
        assign_pad(fp1, "2", net_gnd)

        fps_to_via = [fp1]
        term_end_x = x_term1_a + 1.0

        if "R2" in spec.components:
            # R2 (Lower shunt to GND)
            fp2, val2 = get_fp_for_comp("R2")
            fp2.SetReference("R2")
            fp2.SetValue(val2)
            fp2.Reference().SetVisible(False)
            fp2.Value().SetVisible(False)
            fp2.SetOrientationDegrees(90.0)
            fp2.SetPosition(pcbnew.VECTOR2I(0, 0))
            p2_1 = fp2.FindPadByNumber("1")
            off_y2 = (p2_1.GetPosition().y / 1e6) if p2_1 else -0.9125
            fp2.SetPosition(pcbnew.VECTOR2I(mm(x_term1_b), mm(y_rf - off_y2)))
            board.Add(fp2)
            assign_pad(fp2, "1", net_in)
            assign_pad(fp2, "2", net_gnd)
            fps_to_via.append(fp2)
            term_end_x = x_term1_b

        # Route CPWG RF transmission line from J1 to termination
        route_track(x_j1, y_j1, term_end_x, y_rf, net_in, rf_w_mm)

        # Ground return vias for shunt resistors (routed outwards away from RF line)
        for fp in fps_to_via:
            p2 = fp.FindPadByNumber("2").GetPosition()
            x2, y2 = p2.x / 1e6, p2.y / 1e6
            dy = 1.2 if y2 > y_rf else -1.2
            route_track(x2, y2, x2, y2 + dy, net_gnd, 0.8)
            add_via(x2, y2 + dy)

        # CPWG Ground Fencing along Port 1
        for vx in [6.5]:
            add_via(vx, y_rf - 2.8)
            add_via(vx, y_rf + 2.8)

        # Solid ground stitching across the right section of the board
        for vx in range(int(term_end_x) + 3, int(W) - 3, 3):
            for vy in range(4, int(H) - 3, 3):
                add_via(float(vx), float(vy))

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

    elif spec.topology == "lna":
        x_center = W / 2.0

        if "Q1" in spec.components:
            # Discrete BJT LNA Layout (MMBT5179 SOT-23 + Base Bias Divider + Emitter Bias & Bypass + Collector Choke)
            # 1. Transistor Q1 (SOT-23)
            fp_q1, val_q1 = get_fp_for_comp("Q1")
            fp_q1.SetReference("Q1")
            fp_q1.SetValue(val_q1)
            fp_q1.SetOrientationDegrees(0.0)
            fp_q1.SetPosition(pcbnew.VECTOR2I(mm(x_center), mm(y_rf)))
            board.Add(fp_q1)

            # 2. Input DC Block C1 (0805, horizontal)
            fp_c1, val_c1 = get_fp_for_comp("C1")
            fp_c1.SetReference("C1")
            fp_c1.SetValue(val_c1)
            fp_c1.SetOrientationDegrees(0.0)
            fp_c1.SetPosition(pcbnew.VECTOR2I(mm(x_center - 7.0), mm(y_rf)))
            board.Add(fp_c1)

            # 3. Base Bias Upper Resistor R1 (0805, vertical)
            # Orientation 270: Pad 1 is at y - 0.9125 (top, VDD), Pad 2 is at y + 0.9125 (bottom, BASE)
            fp_r1, val_r1 = get_fp_for_comp("R1")
            fp_r1.SetReference("R1")
            fp_r1.SetValue(val_r1)
            fp_r1.SetOrientationDegrees(270.0)
            fp_r1.SetPosition(pcbnew.VECTOR2I(mm(x_center - 4.2), mm(y_rf - 5.0)))
            board.Add(fp_r1)

            # 4. Base Bias Lower Resistor R2 (0805, vertical)
            # Orientation 90: Pad 1 is at y + 0.9125 (bottom, BASE), Pad 2 is at y - 0.9125 (top, GND)
            fp_r2, val_r2 = get_fp_for_comp("R2")
            fp_r2.SetReference("R2")
            fp_r2.SetValue(val_r2)
            fp_r2.SetOrientationDegrees(90.0)
            fp_r2.SetPosition(pcbnew.VECTOR2I(mm(x_center - 1.8), mm(y_rf - 5.0)))
            board.Add(fp_r2)

            # 5. Emitter Degeneration Resistor R3 (0805, vertical)
            # Orientation 90: Pad 1 is at y + 0.9125 (bottom, GND), Pad 2 is at y - 0.9125 (top, EMITTER)
            fp_r3, val_r3 = get_fp_for_comp("R3")
            fp_r3.SetReference("R3")
            fp_r3.SetValue(val_r3)
            fp_r3.SetOrientationDegrees(90.0)
            fp_r3.SetPosition(pcbnew.VECTOR2I(mm(x_center - 1.5), mm(y_rf + 5.0)))
            board.Add(fp_r3)

            # 6. Emitter Bypass Capacitor C3 (0805, vertical)
            # Orientation 90: Pad 1 is at y + 0.9125 (bottom, GND), Pad 2 is at y - 0.9125 (top, EMITTER)
            fp_c3, val_c3 = get_fp_for_comp("C3")
            fp_c3.SetReference("C3")
            fp_c3.SetValue(val_c3)
            fp_c3.SetOrientationDegrees(90.0)
            fp_c3.SetPosition(pcbnew.VECTOR2I(mm(x_center + 1.5), mm(y_rf + 5.0)))
            board.Add(fp_c3)

            # 7. Collector RF Choke L1 (0603, vertical)
            # Orientation 270: Pad 1 is at y - 0.8 (top, VDD), Pad 2 is at y + 0.8 (bottom, COLLECTOR)
            fp_l1, val_l1 = get_fp_for_comp("L1")
            fp_l1.SetReference("L1")
            fp_l1.SetValue(val_l1)
            fp_l1.SetOrientationDegrees(270.0)
            fp_l1.SetPosition(pcbnew.VECTOR2I(mm(x_center + 1.5), mm(y_rf - 5.0)))
            board.Add(fp_l1)

            # 8. Output DC Block C2 (0805, horizontal)
            fp_c2, val_c2 = get_fp_for_comp("C2")
            fp_c2.SetReference("C2")
            fp_c2.SetValue(val_c2)
            fp_c2.SetOrientationDegrees(0.0)
            fp_c2.SetPosition(pcbnew.VECTOR2I(mm(x_center + 7.0), mm(y_rf)))
            board.Add(fp_c2)

            # 9. VDD Decoupling Capacitor C4 (0805, vertical)
            # Orientation 270: Pad 1 is at y - 0.9125 (top, VDD), Pad 2 is at y + 0.9125 (bottom, GND)
            fp_c4, val_c4 = get_fp_for_comp("C4")
            fp_c4.SetReference("C4")
            fp_c4.SetValue(val_c4)
            fp_c4.SetOrientationDegrees(270.0)
            fp_c4.SetPosition(pcbnew.VECTOR2I(mm(x_center + 4.2), mm(y_rf - 5.0)))
            board.Add(fp_c4)

            # 10. DC Supply Header J3
            j3, _ = load_connector_fp("J3", "+5V_GND")
            j3.SetPosition(pcbnew.VECTOR2I(mm(x_center - 9.0), mm(4.5)))
            board.Add(j3)

            # Assign Pads
            assign_pad(j1, "1", net_in)
            assign_pad(j1, "2", net_gnd)
            if has_j2 and j2 is not None:
                assign_pad(j2, "1", net_out)
                assign_pad(j2, "2", net_gnd)

            assign_pad(fp_q1, "1", net_base)
            assign_pad(fp_q1, "2", net_emitter)
            assign_pad(fp_q1, "3", net_collector)

            assign_pad(fp_c1, "1", net_in)
            assign_pad(fp_c1, "2", net_base)

            assign_pad(fp_r1, "1", net_vdd)
            assign_pad(fp_r1, "2", net_base)

            assign_pad(fp_r2, "1", net_base)
            assign_pad(fp_r2, "2", net_gnd)

            assign_pad(fp_r3, "1", net_gnd)
            assign_pad(fp_r3, "2", net_emitter)

            assign_pad(fp_c3, "1", net_gnd)
            assign_pad(fp_c3, "2", net_emitter)

            assign_pad(fp_l1, "1", net_vdd)
            assign_pad(fp_l1, "2", net_collector)

            assign_pad(fp_c2, "1", net_collector)
            assign_pad(fp_c2, "2", net_out)

            assign_pad(fp_c4, "1", net_vdd)
            assign_pad(fp_c4, "2", net_gnd)

            assign_pad(j3, "1", net_vdd)
            assign_pad(j3, "2", net_gnd)

            # Tracks Routing:
            p_q1_b = fp_q1.FindPadByNumber("1").GetPosition()
            p_q1_e = fp_q1.FindPadByNumber("2").GetPosition()
            p_q1_c = fp_q1.FindPadByNumber("3").GetPosition()
            x_b, y_b = p_q1_b.x / 1e6, p_q1_b.y / 1e6
            x_e, y_e = p_q1_e.x / 1e6, p_q1_e.y / 1e6
            x_c, y_c = p_q1_c.x / 1e6, p_q1_c.y / 1e6

            # 1. RF_IN from J1 to C1 Pad 1
            p_c1_1 = fp_c1.FindPadByNumber("1").GetPosition()
            p_c1_2 = fp_c1.FindPadByNumber("2").GetPosition()
            x_c1_1, x_c1_2 = p_c1_1.x / 1e6, p_c1_2.x / 1e6
            route_track(x_j1, y_j1, x_c1_1 - 0.7, y_rf, net_in, rf_w_mm)
            route_track(x_c1_1 - 0.7, y_rf, x_c1_1, y_rf, net_in, 0.8)

            # 2. NET_BASE: clean horizontal bus at y = y_rf - 2.5
            y_base_bus = y_rf - 2.5
            p_r1_2 = fp_r1.FindPadByNumber("2").GetPosition()
            p_r2_1 = fp_r2.FindPadByNumber("1").GetPosition()
            route_track(x_c1_2, y_rf, x_c1_2, y_base_bus, net_base, 0.4)
            route_track(x_c1_2, y_base_bus, x_b, y_base_bus, net_base, 0.4)
            route_track(p_r1_2.x / 1e6, p_r1_2.y / 1e6, p_r1_2.x / 1e6, y_base_bus, net_base, 0.4)
            route_track(p_r2_1.x / 1e6, p_r2_1.y / 1e6, p_r2_1.x / 1e6, y_base_bus, net_base, 0.4)
            route_track(x_b, y_base_bus, x_b, y_b, net_base, 0.4)

            # 3. NET_EMITTER: clean horizontal bus at y = y_rf + 2.5
            y_emitter_bus = y_rf + 2.5
            p_r3_2 = fp_r3.FindPadByNumber("2").GetPosition()
            p_c3_2 = fp_c3.FindPadByNumber("2").GetPosition()
            route_track(x_e, y_e, x_e, y_emitter_bus, net_emitter, 0.4)
            route_track(p_r3_2.x / 1e6, y_emitter_bus, p_c3_2.x / 1e6, y_emitter_bus, net_emitter, 0.4)
            route_track(p_r3_2.x / 1e6, y_emitter_bus, p_r3_2.x / 1e6, p_r3_2.y / 1e6, net_emitter, 0.4)
            route_track(p_c3_2.x / 1e6, y_emitter_bus, p_c3_2.x / 1e6, p_c3_2.y / 1e6, net_emitter, 0.4)

            # 4. NET_COLLECTOR: Pin 3 to L1 Pad 2 and C2 Pad 1
            p_l1_2 = fp_l1.FindPadByNumber("2").GetPosition()
            p_c2_1 = fp_c2.FindPadByNumber("1").GetPosition()
            p_c2_2 = fp_c2.FindPadByNumber("2").GetPosition()
            route_track(x_c, y_c, p_c2_1.x / 1e6, y_rf, net_collector, 0.6)
            route_track(p_l1_2.x / 1e6, y_c, p_l1_2.x / 1e6, p_l1_2.y / 1e6, net_collector, 0.4)

            # 5. RF_OUT: C2 Pad 2 to J2
            x_c2_2 = p_c2_2.x / 1e6
            route_track(x_c2_2, y_rf, x_c2_2 + 0.7, y_rf, net_out, 0.8)
            route_track(x_c2_2 + 0.7, y_rf, x_j2, y_j2, net_out, rf_w_mm)

            # 6. VDD Rail at y = 3.2 mm (well clear of all components)
            y_vdd_rail = 3.2
            p_r1_1 = fp_r1.FindPadByNumber("1").GetPosition()
            p_l1_1 = fp_l1.FindPadByNumber("1").GetPosition()
            p_c4_1 = fp_c4.FindPadByNumber("1").GetPosition()
            p_j3_1 = j3.FindPadByNumber("1").GetPosition()
            route_track(p_j3_1.x / 1e6, p_j3_1.y / 1e6, p_j3_1.x / 1e6, y_vdd_rail, net_vdd, 0.5)
            route_track(p_j3_1.x / 1e6, y_vdd_rail, p_c4_1.x / 1e6, y_vdd_rail, net_vdd, 0.5)
            route_track(p_r1_1.x / 1e6, p_r1_1.y / 1e6, p_r1_1.x / 1e6, y_vdd_rail, net_vdd, 0.4)
            route_track(p_l1_1.x / 1e6, p_l1_1.y / 1e6, p_l1_1.x / 1e6, y_vdd_rail, net_vdd, 0.4)
            route_track(p_c4_1.x / 1e6, p_c4_1.y / 1e6, p_c4_1.x / 1e6, y_vdd_rail, net_vdd, 0.4)

            # 7. Ground Vias (placed cleanly away from signal tracks)
            p_r2_2 = fp_r2.FindPadByNumber("2").GetPosition()
            add_via(p_r2_2.x / 1e6 + 1.2, p_r2_2.y / 1e6)
            route_track(p_r2_2.x / 1e6, p_r2_2.y / 1e6, p_r2_2.x / 1e6 + 1.2, p_r2_2.y / 1e6, net_gnd, 0.5)

            p_c4_2 = fp_c4.FindPadByNumber("2").GetPosition()
            add_via(p_c4_2.x / 1e6, p_c4_2.y / 1e6 + 1.2)
            route_track(p_c4_2.x / 1e6, p_c4_2.y / 1e6, p_c4_2.x / 1e6, p_c4_2.y / 1e6 + 1.2, net_gnd, 0.5)

            p_r3_1 = fp_r3.FindPadByNumber("1").GetPosition()
            add_via(p_r3_1.x / 1e6, p_r3_1.y / 1e6 + 1.2)
            route_track(p_r3_1.x / 1e6, p_r3_1.y / 1e6, p_r3_1.x / 1e6, p_r3_1.y / 1e6 + 1.2, net_gnd, 0.5)

            p_c3_1 = fp_c3.FindPadByNumber("1").GetPosition()
            add_via(p_c3_1.x / 1e6, p_c3_1.y / 1e6 + 1.2)
            route_track(p_c3_1.x / 1e6, p_c3_1.y / 1e6, p_c3_1.x / 1e6, p_c3_1.y / 1e6 + 1.2, net_gnd, 0.5)

            p_j3_2 = j3.FindPadByNumber("2").GetPosition()
            add_via(p_j3_2.x / 1e6 + 1.8, p_j3_2.y / 1e6)
            route_track(p_j3_2.x / 1e6, p_j3_2.y / 1e6, p_j3_2.x / 1e6 + 1.8, p_j3_2.y / 1e6, net_gnd, 0.5)

        else:
            # Active MMIC LNA Layout (SPF5189Z SOT-89 + CPWG + DC Bias Network)
            # 1. Active MMIC U1 (SOT-89-3)
            # Rotated 90 deg: Pin 1 at x_center - 1.5, Pin 3 at x_center + 1.5
            fp_u1, val_u1 = get_fp_for_comp("U1")
            fp_u1.SetReference("U1")
            fp_u1.SetValue(val_u1)
            fp_u1.SetOrientationDegrees(90.0)
            fp_u1.SetPosition(pcbnew.VECTOR2I(mm(x_center), mm(y_rf - 1.95)))
            board.Add(fp_u1)

            # 2. Input DC Block C1 (0805)
            fp_c1, val_c1 = get_fp_for_comp("C1")
            fp_c1.SetReference("C1")
            fp_c1.SetValue(val_c1)
            fp_c1.SetOrientationDegrees(0.0)
            fp_c1.SetPosition(pcbnew.VECTOR2I(mm(x_center - 11.0), mm(y_rf)))
            board.Add(fp_c1)

            # 3. Input Matching Inductor L1 (0603)
            fp_l1, val_l1 = get_fp_for_comp("L1")
            fp_l1.SetReference("L1")
            fp_l1.SetValue(val_l1)
            fp_l1.SetOrientationDegrees(0.0)
            fp_l1.SetPosition(pcbnew.VECTOR2I(mm(x_center - 5.5), mm(y_rf)))
            board.Add(fp_l1)

            # 4. Output DC Block C2 (0805)
            fp_c2, val_c2 = get_fp_for_comp("C2")
            fp_c2.SetReference("C2")
            fp_c2.SetValue(val_c2)
            fp_c2.SetOrientationDegrees(0.0)
            fp_c2.SetPosition(pcbnew.VECTOR2I(mm(x_center + 8.5), mm(y_rf)))
            board.Add(fp_c2)

            # 5. Output RF Choke Inductor L2 (0603, vertical)
            # Positioned at (x_center + 4.0, 9.0): Pad 2 (top) at y=8.21, Pad 1 (bottom) at y=9.79
            fp_l2, val_l2 = get_fp_for_comp("L2")
            fp_l2.SetReference("L2")
            fp_l2.SetValue(val_l2)
            fp_l2.SetOrientationDegrees(90.0)
            fp_l2.SetPosition(pcbnew.VECTOR2I(mm(x_center + 4.0), mm(9.0)))
            board.Add(fp_l2)

            # 6. Bias Resistor R1 (0805, horizontal)
            # Pad 1 (left) = VDD, Pad 2 (right) = NET_BIAS
            fp_r1, val_r1 = get_fp_for_comp("R1")
            fp_r1.SetReference("R1")
            fp_r1.SetValue(val_r1)
            fp_r1.SetOrientationDegrees(0.0)
            fp_r1.SetPosition(pcbnew.VECTOR2I(mm(x_center - 2.5), mm(6.55)))
            board.Add(fp_r1)

            # 7. Decoupling Capacitors C3 (100pF 0805) & C4 (10nF 0805)
            # Deg=270: Pad 1 is at y=6.55 (NET_BIAS rail), Pad 2 is at y=8.45 (GND)
            fp_c3, val_c3 = get_fp_for_comp("C3")
            fp_c3.SetReference("C3")
            fp_c3.SetValue(val_c3)
            fp_c3.SetOrientationDegrees(270.0)
            fp_c3.SetPosition(pcbnew.VECTOR2I(mm(x_center + 7.5), mm(7.5)))
            board.Add(fp_c3)

            fp_c4, val_c4 = get_fp_for_comp("C4")
            fp_c4.SetReference("C4")
            fp_c4.SetValue(val_c4)
            fp_c4.SetOrientationDegrees(270.0)
            fp_c4.SetPosition(pcbnew.VECTOR2I(mm(x_center + 12.0), mm(7.5)))
            board.Add(fp_c4)

            # 8. DC Header J3 (1x02 2.54mm Pin Header)
            # Deg=270: Pin 1 at (x, y), Pin 2 at (x - 2.54, y)
            j3, _ = load_connector_fp("J3", "+5V_IN")
            j3.SetPosition(pcbnew.VECTOR2I(mm(x_center - 8.5), mm(6.55)))
            j3.SetOrientationDegrees(270.0)
            board.Add(j3)

            # Assign Nets:
            assign_pad(j1, "1", net_in)
            assign_pad(j1, "2", net_gnd)

            assign_pad(fp_c1, "1", net_in)
            assign_pad(fp_c1, "2", net_mid)

            assign_pad(fp_l1, "1", net_mid)
            assign_pad(fp_l1, "2", net_lna_in)

            assign_pad(fp_u1, "1", net_lna_in)
            assign_pad(fp_u1, "2", net_gnd)
            assign_pad(fp_u1, "3", net_lna_out)

            # L2: Pad 1 (bottom) = NET_LNA_OUT, Pad 2 (top) = NET_BIAS
            assign_pad(fp_l2, "1", net_lna_out)
            assign_pad(fp_l2, "2", net_bias)

            assign_pad(fp_c2, "1", net_lna_out)
            assign_pad(fp_c2, "2", net_out)

            if has_j2 and j2 is not None:
                assign_pad(j2, "1", net_out)
                assign_pad(j2, "2", net_gnd)

            # J3: Pin 1 = VDD, Pin 2 = GND
            assign_pad(j3, "1", net_vdd)
            assign_pad(j3, "2", net_gnd)

            # R1: Pad 1 = VDD, Pad 2 = NET_BIAS
            assign_pad(fp_r1, "1", net_vdd)
            assign_pad(fp_r1, "2", net_bias)

            # C3 & C4: Pad 1 (y=6.55) = NET_BIAS, Pad 2 (y=8.45) = GND
            assign_pad(fp_c3, "1", net_bias)
            assign_pad(fp_c3, "2", net_gnd)
            assign_pad(fp_c4, "1", net_bias)
            assign_pad(fp_c4, "2", net_gnd)

            # Route Tracks:
            p_c1_1 = fp_c1.FindPadByNumber("1").GetPosition()
            p_c1_2 = fp_c1.FindPadByNumber("2").GetPosition()
            p_l1_1 = fp_l1.FindPadByNumber("1").GetPosition()
            p_l1_2 = fp_l1.FindPadByNumber("2").GetPosition()
            p_u1_1 = fp_u1.FindPadByNumber("1").GetPosition()
            p_u1_3 = fp_u1.FindPadByNumber("3").GetPosition()
            p_c2_1 = fp_c2.FindPadByNumber("1").GetPosition()
            p_c2_2 = fp_c2.FindPadByNumber("2").GetPosition()
            p_l2_1 = fp_l2.FindPadByNumber("1").GetPosition()
            p_l2_2 = fp_l2.FindPadByNumber("2").GetPosition()

            # RF_IN from J1 to C1 Pad 1
            x_c1_1 = p_c1_1.x / 1e6
            route_track(x_j1, y_j1, x_c1_1 - 0.7, y_rf, net_in, rf_w_mm)
            route_track(x_c1_1 - 0.7, y_rf, x_c1_1, y_rf, net_in, 0.8)

            # C1 Pad 2 to L1 Pad 1
            route_track(p_c1_2.x / 1e6, y_rf, p_l1_1.x / 1e6, y_rf, net_mid, 0.8)

            # L1 Pad 2 to U1 Pin 1
            route_track(p_l1_2.x / 1e6, y_rf, p_u1_1.x / 1e6, y_rf, net_lna_in, 0.8)

            # U1 Pin 3 to C2 Pad 1
            route_track(p_u1_3.x / 1e6, y_rf, p_c2_1.x / 1e6, y_rf, net_lna_out, 0.8)

            # C2 Pad 2 to J2
            x_c2_2 = p_c2_2.x / 1e6
            route_track(x_c2_2, y_rf, x_c2_2 + 0.7, y_rf, net_out, 0.8)
            route_track(x_c2_2 + 0.7, y_rf, x_j2, y_j2, net_out, rf_w_mm)

            # Bias choke L2 Pad 1 (bottom at y=9.79) down to U1 Pin 3 at y_rf=14.0
            x_l2 = p_l2_1.x / 1e6
            y_l2_bot = p_l2_1.y / 1e6
            x_u1_3 = p_u1_3.x / 1e6
            route_track(x_l2, y_l2_bot, x_l2, y_rf, net_lna_out, 0.5)
            route_track(x_l2, y_rf, x_u1_3, y_rf, net_lna_out, 0.8)

            # Bias rail (net_bias) at y=6.55 connecting R1 Pad 2, L2 Pad 2, C3 Pad 1, C4 Pad 1
            p_r1_2 = fp_r1.FindPadByNumber("2").GetPosition()
            p_c3_1 = fp_c3.FindPadByNumber("1").GetPosition()
            p_c4_1 = fp_c4.FindPadByNumber("1").GetPosition()
            x_r1_2 = p_r1_2.x / 1e6
            x_c4_1 = p_c4_1.x / 1e6
            y_rail = 6.55
            # Horizontal rail from R1 Pad 2 to C4 Pad 1 at y=6.55
            route_track(x_r1_2, y_rail, x_c4_1, y_rail, net_bias, 0.5)
            # L2 Pad 2 (y=8.21) up to rail at y=6.55
            route_track(p_l2_2.x / 1e6, p_l2_2.y / 1e6, p_l2_2.x / 1e6, y_rail, net_bias, 0.5)

            # VDD line connecting J3 Pin 1 to R1 Pad 1
            p_j3_1 = j3.FindPadByNumber("1").GetPosition()
            p_r1_1 = fp_r1.FindPadByNumber("1").GetPosition()
            route_track(p_j3_1.x / 1e6, p_j3_1.y / 1e6, p_r1_1.x / 1e6, p_r1_1.y / 1e6, net_vdd, 0.6)

            # Ground vias for J3 Pin 2, C3 Pad 2, C4 Pad 2
            p_j3_2 = j3.FindPadByNumber("2").GetPosition()
            p_c3_2 = fp_c3.FindPadByNumber("2").GetPosition()
            p_c4_2 = fp_c4.FindPadByNumber("2").GetPosition()
            
            # J3 Pin 2 to GND via (to the left)
            x_j3_2, y_j3_2 = p_j3_2.x / 1e6, p_j3_2.y / 1e6
            route_track(x_j3_2, y_j3_2, x_j3_2 - 1.5, y_j3_2, net_gnd, 0.6)
            add_via(x_j3_2 - 1.5, y_j3_2)

            # C3 & C4 GND vias (routed downwards towards y_rf)
            for pt in [p_c3_2, p_c4_2]:
                gx, gy = pt.x / 1e6, (pt.y / 1e6) + 1.8
                route_track(pt.x / 1e6, pt.y / 1e6, gx, gy, net_gnd, 0.6)
                add_via(gx, gy)

            # SOT-89 Tab Thermal Ground Vias under U1 Pad 2 (tab slug extends upwards)
            p_u1_2 = fp_u1.FindPadByNumber("2").GetPosition()
            x_tab, y_tab = p_u1_2.x / 1e6, p_u1_2.y / 1e6
            add_via(x_tab - 0.7, y_tab - 1.2)
            add_via(x_tab + 0.7, y_tab - 1.2)
            add_via(x_tab - 0.7, y_tab - 2.4)
            add_via(x_tab + 0.7, y_tab - 2.4)

    elif spec.topology in ["through", "transmission_line"] or len(c_keys) == 0:
        # Direct through CPWG transmission line from J1 to J2
        assign_pad(j1, "1", net_in)
        if has_j2 and j2 is not None:
            assign_pad(j2, "1", net_in)
        route_track(x_j1, y_j1, x_j2, y_j2, net_in, rf_w_mm)

    elif spec.topology == "highpass":
        # 3-Element T-Network High-Pass Filter: Series C1 - Shunt L1 to GND - Series C2
        ref1 = c_keys[0] if len(c_keys) > 0 else "C1"
        ref2 = c_keys[1] if len(c_keys) > 1 else "L1"
        ref3 = c_keys[2] if len(c_keys) > 2 else "C2"

        # C1 (Series at W/2 - 4.5)
        fp1, val1 = get_fp_for_comp(ref1)
        fp1.SetReference(ref1)
        fp1.SetValue(val1)
        fp1.SetPosition(pcbnew.VECTOR2I(mm(W / 2.0 - 4.5), mm(y_rf)))
        fp1.SetOrientationDegrees(0.0)
        board.Add(fp1)

        # L1 (Shunt at W/2.0 to GND)
        fp2, val2 = get_fp_for_comp(ref2)
        fp2.SetReference(ref2)
        fp2.SetValue(val2)
        place_shunt_fp(fp2, W / 2.0, y_rf)
        board.Add(fp2)

        # C2 (Series at W/2 + 4.5)
        fp3, val3 = get_fp_for_comp(ref3)
        fp3.SetReference(ref3)
        fp3.SetValue(val3)
        fp3.SetPosition(pcbnew.VECTOR2I(mm(W / 2.0 + 4.5), mm(y_rf)))
        fp3.SetOrientationDegrees(0.0)
        board.Add(fp3)

        assign_pad(fp1, "1", net_in)
        assign_pad(fp1, "2", net_mid)
        assign_pad(fp2, "1", net_mid)
        assign_pad(fp2, "2", net_gnd)
        assign_pad(fp3, "1", net_mid)
        assign_pad(fp3, "2", net_out)

        p_c1_1 = fp1.FindPadByNumber("1").GetPosition()
        p_c1_2 = fp1.FindPadByNumber("2").GetPosition()
        p_l1_1 = fp2.FindPadByNumber("1").GetPosition()
        p_l1_2 = fp2.FindPadByNumber("2").GetPosition()
        p_c2_1 = fp3.FindPadByNumber("1").GetPosition()
        p_c2_2 = fp3.FindPadByNumber("2").GetPosition()

        x_c1_1 = p_c1_1.x / 1e6
        x_c1_2 = p_c1_2.x / 1e6
        x_c2_1 = p_c2_1.x / 1e6
        x_c2_2 = p_c2_2.x / 1e6

        # J1 to C1 Pad 1 with taper
        x_taper_in = x_c1_1 - 0.7
        route_track(x_j1, y_j1, x_taper_in, y_j1, net_in, rf_w_mm)
        route_track(x_taper_in, y_j1, x_c1_1, y_j1, net_in, 0.8)

        # C1 Pad 2 to C2 Pad 1 via L1 Pad 1 (net_mid)
        route_track(x_c1_2, y_rf, x_c2_1, y_rf, net_mid, 0.8)

        # C2 Pad 2 to J2 with taper
        x_taper_out = x_c2_2 + 0.7
        route_track(x_c2_2, y_j2, x_taper_out, y_j2, net_out, 0.8)
        route_track(x_taper_out, y_j2, x_j2, y_j2, net_out, rf_w_mm)

        # L1 Pad 2 GND via
        x_l1_2, y_l1_2 = p_l1_2.x / 1e6, p_l1_2.y / 1e6
        route_track(x_l1_2, y_l1_2, x_l1_2, y_l1_2 + 1.2, net_gnd, 0.8)
        add_via(x_l1_2, y_l1_2 + 1.2)

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
    if spec.topology == "lna":
        if "Q1" in spec.components:
            # Discrete BJT LNA via fencing: keep clear of central bias area
            for vx in [6.5, 8.5, W - 8.5, W - 6.5]:
                if 5.0 < vx < (W - 5.0):
                    add_via(vx, y_rf - 2.8)
                    add_via(vx, y_rf + 3.0)
            for vx in [W - 11.0]:
                if 5.0 < vx < (W - 5.0):
                    add_via(vx, y_rf - 2.8)
                    add_via(vx, y_rf + 3.0)
        else:
            # Custom ground fencing for MMIC LNA avoiding DC bias routing
            for vx in [6.5, 8.5, W - 8.5, W - 6.5]:
                if 5.0 < vx < (W - 5.0):
                    add_via(vx, y_rf - 2.8)
                    add_via(vx, y_rf + 4.5)
            for vx in [12.0, 15.0, 25.0, 28.0, 31.0]:
                if 5.0 < vx < (W - 5.0):
                    add_via(vx, y_rf + 4.5)
    elif spec.topology not in ["calibration_load", "load"]:
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
        add_text("50Ω CAL LOAD", W / 2.0, 3.0, size=0.8)
        add_text("PORT 1", 7.0, 3.0, size=0.8)
        add_text(f"{spec.z0_ohm:.0f}Ω 1-PORT SOLT DC-{spec.f_max_ghz:.0f}GHz", W / 2.0, H - 3.0, size=0.7)
    elif spec.topology == "lna":
        device_name = spec.components.get("Q1", {}).get("value", spec.components.get("U1", {}).get("value", "LNA"))
        add_text(f"{device_name} LNA", W / 2.0, 2.5, size=0.8)
        add_text("RF IN", 8.5, y_rf - 3.5, size=0.8)
        add_text("RF OUT", W - 8.5, y_rf - 3.5, size=0.8)
        add_text("+5V", W / 2.0 - 8.5, 4.0, size=0.8)
        add_text(f"{spec.title.split('(')[0].strip()} | +{spec.target_s21_db:.1f}dB", W / 2.0, H - 2.5, size=0.8)
    else:
        title_short = spec.title.split("(")[0].strip()
        if len(title_short) > 20:
            title_short = f"{spec.f_0_ghz*1000.0:.0f}MHz LC Bandpass"
        add_text(title_short, W / 2.0, 3.2, size=0.8)
        add_text("PORT 1", 5.0, 4.5, size=0.8)
        if has_j2:
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
