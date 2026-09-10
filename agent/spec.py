"""
RF Circuit Specifications and Impedance Synthesis for RF AI Suite.
Includes Wheeler/Hammerstad equations for Microstrip, Cohn/Ghione equations for CPWG,
and natural language parsing for custom RF circuits synthesized cleanly from scratch.
"""

import math
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

@dataclass
class CircuitSpec:
    name: str = "attenuator_10db"
    title: str = "10 dB RF Pi-Attenuator (50Ω, DC-3GHz)"
    topology: str = "attenuator"  # 'attenuator', 'lowpass', 'highpass', 'bias_tee', 'divider', 'custom'
    num_ports: int = 2  # 1 for 1-port circuits (load, termination, SOLT match), 2 for 2-port, 3 for 3-port
    description: str = "Precision 10dB 50-ohm Pi-Attenuator using 0805 SMD thin-film resistors and SMA edge connectors."
    
    # Frequency range
    f_min_ghz: float = 0.01
    f_0_ghz: float = 1.5
    f_max_ghz: float = 3.0
    num_pts: int = 201
    z0_ohm: float = 50.0
    
    # Target RF Metrics
    target_s21_db: float = -10.0
    target_s11_db: float = -25.0
    target_s22_db: float = -25.0
    target_isolation_db: float = -10.0
    
    # PCB Physical Properties
    width_mm: float = 30.0
    height_mm: float = 20.0
    layers: int = 2
    substrate_name: str = "FR4"
    dielectric_er: float = 4.4
    loss_tangent: float = 0.02
    substrate_height_mm: float = 1.6
    copper_thickness_um: float = 35.0
    
    # RF Path Transmission Line Properties (Controlled Impedance)
    trace_mode: str = "CPWG"  # 'CPWG' (Coplanar Waveguide with Ground) or 'Microstrip'
    trace_gap_mm: float = 0.40  # Gap to top ground pour for CPWG
    
    # Power Supply
    power_supply_type: str = "Passive"  # 'Passive', 'DC Single Supply'
    power_voltage_v: float = 0.0
    current_ma: float = 0.0
    
    # EM Simulation Mode
    em_sim_type: str = "traces"  # 'traces' (fast) or 'full_board' (FDTD)
    
    # Required Analysis
    simulations_required: List[str] = field(default_factory=lambda: [
        "s_parameters", "stability", "impedance", "smith_chart"
    ])
    
    # Components & Values
    components: Dict[str, Any] = field(default_factory=dict)
    
    # Additional features
    additional_reqs: List[str] = field(default_factory=lambda: [
        "50-ohm Controlled Impedance RF Lines",
        "Ground Via Fencing Stitching",
        "Solid Bottom Ground Plane",
        "Corner Chamfer Radii (2.0mm)"
    ])

    @property
    def microstrip_width_mm(self) -> float:
        """Calculate the exact microstrip trace width for Z0."""
        w, _ = calc_microstrip_dimensions(self.dielectric_er, self.substrate_height_mm, self.z0_ohm)
        return w

    @property
    def cpwg_width_mm(self) -> float:
        """Calculate the exact CPWG trace width for Z0 and trace_gap_mm."""
        w, _, _ = calc_cpwg_dimensions(self.dielectric_er, self.substrate_height_mm, self.z0_ohm, self.trace_gap_mm)
        return w

    @property
    def rf_trace_width_mm(self) -> float:
        """Active RF trace width depending on trace mode (CPWG with top ground or pure Microstrip)."""
        if self.trace_mode == "CPWG":
            return self.cpwg_width_mm
        return self.microstrip_width_mm

    @property
    def effective_dielectric_constant(self) -> float:
        """Effective dielectric constant for the active transmission line mode."""
        if self.trace_mode == "CPWG":
            _, _, eps_eff = calc_cpwg_dimensions(self.dielectric_er, self.substrate_height_mm, self.z0_ohm, self.trace_gap_mm)
            return eps_eff
        _, eps_eff = calc_microstrip_dimensions(self.dielectric_er, self.substrate_height_mm, self.z0_ohm)
        return eps_eff

    @property
    def propagation_delay_ps_mm(self) -> float:
        """Signal propagation delay in picoseconds per millimeter."""
        c = 299.792458  # mm / ns = mm * 1e-3 / ps
        # v_p = c / sqrt(eps_eff)
        # delay = 1 / v_p = sqrt(eps_eff) / c (in ns/mm) * 1000 ps/ns
        return (math.sqrt(self.effective_dielectric_constant) / c) * 1000.0

    @property
    def cpwg_gap_mm(self) -> float:
        return self.trace_gap_mm

    @property
    def cpwg_eps_eff(self) -> float:
        _, _, eps_eff = calc_cpwg_dimensions(self.dielectric_er, self.substrate_height_mm, self.z0_ohm, self.trace_gap_mm)
        return eps_eff

    @property
    def cpwg_phase_velocity_m_s(self) -> float:
        c0 = 299792458.0
        return c0 / math.sqrt(self.cpwg_eps_eff)

    @property
    def cpwg_delay_ps_per_mm(self) -> float:
        return self.propagation_delay_ps_mm


# ----------------------------------------------------------------------
# Analytical RF Transmission Line Synthesis Functions
# ----------------------------------------------------------------------

def ellipk(k: float) -> float:
    """Complete elliptic integral of the first kind K(k) using polynomial approximation."""
    if k <= 0:
        return math.pi / 2.0
    if k >= 1.0:
        return 999.0
    m = k * k
    m1 = 1.0 - m
    if m1 < 1e-9:
        return 999.0
    # Hastings polynomial approximation
    a0, a1, a2 = 1.38629436112, 0.09666344259, 0.03590092383
    b0, b1, b2 = 0.5, 0.12498593597, 0.06880248576
    return (a0 + a1 * m1 + a2 * m1**2) - (b0 + b1 * m1 + b2 * m1**2) * math.log(m1)

def kp_over_k(k: float) -> float:
    """Ratio K'(k) / K(k) where k' = sqrt(1 - k^2)."""
    k_clamp = max(1e-6, min(k, 1.0 - 1e-6))
    kp = math.sqrt(1.0 - k_clamp * k_clamp)
    return ellipk(kp) / ellipk(k_clamp)

def calc_cpwg_dimensions(er: float, h_mm: float, z0: float = 50.0, s_mm: float = 0.40) -> Tuple[float, float, float]:
    """
    Synthesize Coplanar Waveguide with Ground (CPWG) trace width w (mm)
    for a given substrate er, thickness h (mm), desired Z0 (Ohm), and ground gap s (mm).
    Returns (w_mm, s_mm, eps_eff).
    """
    # Binary search for w in range [0.1mm, 10.0mm]
    low, high = 0.1, 10.0
    best_w = 1.85
    best_eps = 2.95

    for _ in range(30):
        mid = (low + high) / 2.0
        w = mid
        k = w / (w + 2.0 * s_mm)
        k1 = math.tanh((math.pi * w) / (4.0 * h_mm)) / math.tanh((math.pi * (w + 2.0 * s_mm)) / (4.0 * h_mm))
        
        # Effective dielectric constant for CPWG
        q1 = 1.0 / (kp_over_k(k))
        q2 = 1.0 / (kp_over_k(k1))
        eps_eff = (1.0 + er * (q2 / q1)) / (1.0 + (q2 / q1))
        
        z_calc = (60.0 * math.pi / math.sqrt(eps_eff)) / (1.0 / kp_over_k(k) + 1.0 / kp_over_k(k1))
        
        if z_calc > z0:
            low = mid  # Need wider line to lower impedance
        else:
            high = mid
        best_w = mid
        best_eps = eps_eff

    return round(best_w, 2), s_mm, round(best_eps, 2)


def calc_microstrip_dimensions(er: float, h_mm: float, z0: float = 50.0) -> Tuple[float, float]:
    """
    Synthesize standard Microstrip trace width w (mm) and effective permittivity.
    Returns (w_mm, eps_eff).
    """
    A = (z0 / 60.0) * math.sqrt((er + 1.0) / 2.0) + ((er - 1.0) / (er + 1.0)) * (0.23 + 0.11 / er)
    B = (377.0 * math.pi) / (2.0 * z0 * math.sqrt(er))
    
    w_over_h_A = (8.0 * math.exp(A)) / (math.exp(2.0 * A) - 2.0)
    if w_over_h_A < 2.0:
        w_over_h = w_over_h_A
    else:
        w_over_h = (2.0 / math.pi) * (B - 1.0 - math.log(2.0 * B - 1.0) + 
                                      ((er - 1.0) / (2.0 * er)) * (math.log(B - 1.0) + 0.39 - 0.61 / er))
    
    width_mm = round(w_over_h * h_mm, 2)
    eps_eff = (er + 1.0) / 2.0 + ((er - 1.0) / 2.0) / math.sqrt(1.0 + 12.0 * h_mm / width_mm)
    return max(width_mm, 0.2), round(eps_eff, 2)

def calc_microstrip_width(er: float, h_mm: float, z0: float = 50.0) -> float:
    """Convenience alias returning only width (mm)."""
    w, _ = calc_microstrip_dimensions(er, h_mm, z0)
    return w


# ----------------------------------------------------------------------
# Inductor Sourcing & Footprint Selection Rules
# ----------------------------------------------------------------------

def select_inductor_package_and_vendor(l_val_h: float) -> dict:
    """
    Selects optimal RF inductor footprint, manufacturer, and series:
    - Default to 0603 from Coilcraft (0603CS / 0603HP) or Murata (LQW18AN / LQG18H).
      Standard high-Q wirewound RF chip ranges: ~1.0 nH up to 470 nH.
    - If specific value not available in 0603 (> 470 nH up to 2.2 uH): fall back to 0805 (Coilcraft 0805CS/HP, Murata LQW21HN).
    - If value > 2.2 uH (up to 10 uH): fall back to 1206 (Coilcraft 1206CS).
    - Do NOT prefer smaller components (e.g. 0402, 0201) unless strictly necessary.
    """
    l_nh = l_val_h * 1e9
    if l_nh <= 470.0:
        return {
            "package": "Inductor_SMD:L_0603_1608Metric",
            "vendor": "Coilcraft / Murata",
            "series": "0603CS / LQW18AN",
            "package_name": "0603"
        }
    elif l_nh <= 2200.0:
        return {
            "package": "Inductor_SMD:L_0805_2012Metric",
            "vendor": "Coilcraft / Murata",
            "series": "0805CS / LQW21HN",
            "package_name": "0805"
        }
    else:
        return {
            "package": "Inductor_SMD:L_1206_3216Metric",
            "vendor": "Coilcraft",
            "series": "1206CS",
            "package_name": "1206"
        }


def extract_rf_frequency(text: str, default_f0: Optional[float] = 1.5) -> Optional[float]:
    """
    Extracts RF center frequency in GHz from user description, prioritizing
    standard numeric frequency notations (GHz, MHz, kHz) before falling back
    to common industry named RF bands.
    """
    t_lower = text.lower()

    # 1. Explicit numeric frequency (e.g. 100MHz, 2.45 GHz, 900 kHz, 433.92 MHz)
    m_f = re.search(r'(\d+(?:\.\d+)?)\s*(ghz|mhz|khz)', t_lower)
    if m_f:
        try:
            v = float(m_f.group(1))
            u = m_f.group(2)
            if u == "ghz":
                return v
            elif u == "mhz":
                return v / 1000.0
            elif u == "khz":
                return v / 1e6
        except Exception:
            pass

    # 2. Check named RF bands only if no explicit numeric frequency is present
    if "fm" in t_lower or "broadcast" in t_lower:
        return 0.100  # 100 MHz FM broadcast
    if "adsb" in t_lower or "ads-b" in t_lower or "1090" in t_lower:
        return 1.090  # 1090 MHz Mode-S / ADS-B
    if "gps l1" in t_lower or "gnss" in t_lower or ("gps" in t_lower and "l2" not in t_lower):
        return 1.5754  # 1575.42 MHz GPS L1
    if "gps l2" in t_lower:
        return 1.2276  # 1227.60 MHz GPS L2
    if "wifi 5" in t_lower or "5ghz" in t_lower or "5.8" in t_lower:
        return 5.800  # 5.8 GHz ISM / Wi-Fi
    if any(k in t_lower for k in ["wifi", "bluetooth", "ble", "ism 2.4", "2.4g"]):
        return 2.400  # 2.4 GHz ISM / Wi-Fi
    if "5g" in t_lower or "sub-6" in t_lower or "c-band" in t_lower:
        return 3.500  # 3.5 GHz Sub-6 Mid-Band
    if "915" in t_lower or "us915" in t_lower:
        return 0.915  # 915 MHz ISM / LoRa
    if "868" in t_lower or "eu868" in t_lower:
        return 0.868  # 868 MHz ISM / LoRa
    if "433" in t_lower:
        return 0.433  # 433.92 MHz ISM
    if "airband" in t_lower or "aviation" in t_lower:
        return 0.125  # 125 MHz VHF Airband
    if "2m" in t_lower or "144" in t_lower:
        return 0.144  # 144 MHz 2-meter HAM
    if "70cm" in t_lower or "430" in t_lower:
        return 0.430  # 430 MHz 70-centimeter HAM

    return default_f0


def parse_component_value(text: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Parses a component value string like '100R', '49.9 ohm', '10pF', '22nH', '1.5uH', '0.1uF', '1k'.
    Returns (nominal_numeric_value, formatted_value_string, component_type: 'resistor'|'capacitor'|'inductor').
    """
    t = text.strip()

    # Capacitors: e.g. 10pF, 4.7pF, 100nF, 0.1uF, 10µF
    m_c = re.match(r'^([0-9.]+)\s*(pf|nf|uf|µf|f)$', t, re.IGNORECASE)
    if m_c:
        v = float(m_c.group(1))
        u = m_c.group(2).lower()
        if u == "pf":
            return v * 1e-12, f"{v:g}pF", "capacitor"
        elif u == "nf":
            return v * 1e-9, f"{v:g}nF", "capacitor"
        elif u in ["uf", "µf"]:
            return v * 1e-6, f"{v:g}uF", "capacitor"
        elif u == "f":
            return v, f"{v:g}F", "capacitor"

    # Inductors: e.g. 10nH, 47nH, 100nH, 1.5uH, 2.2µH
    m_l = re.match(r'^([0-9.]+)\s*(nh|uh|µh|mh|h)$', t, re.IGNORECASE)
    if m_l:
        v = float(m_l.group(1))
        u = m_l.group(2).lower()
        if u == "nh":
            return v * 1e-9, f"{v:g}nH", "inductor"
        elif u in ["uh", "µh"]:
            return v * 1e-6, f"{v:g}uH", "inductor"
        elif u == "mh":
            return v * 1e-3, f"{v:g}mH", "inductor"
        elif u == "h":
            return v, f"{v:g}H", "inductor"

    # Resistors: e.g. 100R, 49.9R, 50 ohm, 50Ω, 1k, 1kΩ, 4.7k
    m_k = re.match(r'^([0-9.]+)\s*[kK](?:[rR]|ohm|ohms|Ω)?$', t, re.IGNORECASE)
    if m_k:
        v = float(m_k.group(1)) * 1000.0
        return v, f"{float(m_k.group(1)):g}k", "resistor"
    m_r = re.match(r'^([0-9.]+)\s*(?:[rR]|ohm|ohms|Ω)?$', t, re.IGNORECASE)
    if m_r:
        v = float(m_r.group(1))
        return v, f"{v:g}R", "resistor"

    return None, None, None


def extract_component_overrides(description: str) -> Dict[str, Dict[str, Any]]:
    """
    Extracts explicit component value assignments from user prompt, such as:
    'R1=100R', 'R2=50R', 'C1=10pF', 'L1=22nH', 'R_shunt=95.3R', 'R_series=71.5R'
    """
    overrides: Dict[str, Dict[str, Any]] = {}
    
    # 1. Match patterns like R1=100R, R1: 50 ohm, C1=10pF, L1=22nH, R_shunt=100R
    pattern = re.compile(
        r'\b([RCL]\d+|r_shunt|r_series|c_shunt|c_series|l_shunt|l_series)\s*[:=]\s*([0-9.]+\s*(?:[pnumk]?[rfh]|ohm|ohms|Ω)?)\b',
        re.IGNORECASE
    )
    for match in pattern.finditer(description):
        ref_raw = match.group(1)
        val_str = match.group(2)
        nominal, val_formatted, comp_type = parse_component_value(val_str)
        if nominal is not None:
            ref_clean = ref_raw.upper()
            overrides[ref_clean] = {
                "nominal": nominal,
                "value": val_formatted,
                "type": comp_type
            }

    # 2. Match general L=22nH, C=10pF, R=50R
    gen_pattern = re.compile(
        r'\b([RCL])\s*[:=]\s*([0-9.]+\s*(?:[pnumk]?[rfh]|ohm|ohms|Ω)?)\b',
        re.IGNORECASE
    )
    for match in gen_pattern.finditer(description):
        kind = match.group(1).upper()
        val_str = match.group(2)
        nominal, val_formatted, comp_type = parse_component_value(val_str)
        if nominal is not None and comp_type is not None:
            overrides[kind] = {
                "nominal": nominal,
                "value": val_formatted,
                "type": comp_type
            }

    return overrides


# ----------------------------------------------------------------------
# Natural Language & Custom Circuit Description Parser
# ----------------------------------------------------------------------

def parse_custom_circuit(
    description: str,
    title: str = "Custom RF Circuit",
    z0: float = 50.0,
    f0_ghz: float = 1.5,
    substrate_name: str = "FR4",
    er: float = 4.4,
    h_mm: float = 1.6,
    width_mm: float = 30.0,
    height_mm: float = 20.0,
    em_sim_type: str = "traces"
) -> CircuitSpec:
    """
    Intelligently parses user circuit description and synthesizes component values,
    topology, target RF metrics, and transmission line properties from scratch.
    """
    desc_lower = description.lower()
    overrides = extract_component_overrides(description)

    # 0. Primary: Pure LLM Architecture & Component Synthesis (Always go LLM when available)
    try:
        from .llm_synth import synthesize_spec_with_llm, get_grok_path
        if get_grok_path():
            spec = synthesize_spec_with_llm(description)
            if substrate_name != "FR4":
                spec.substrate_name = substrate_name
                spec.dielectric_er = er
                spec.substrate_height_mm = h_mm
            return spec
    except Exception:
        pass

    # Check if user explicitly mentioned system impedance z0 in description
    m_z = re.search(r'\b(50|75|100)\s*(?:ohm|ohms|Ω)\b', desc_lower)
    if m_z:
        try:
            z_extracted = float(m_z.group(1))
            if z_extracted > 0 and z0 == 50.0:
                z0 = z_extracted
        except Exception:
            pass

    # 0. Through-Line / Transmission Line Test Board (no shunt components)
    is_through = (
        ("through" in desc_lower or "thru" in desc_lower or "transmission line" in desc_lower or "cpwg line" in desc_lower or "test fixture" in desc_lower or "straight trace" in desc_lower)
        and "attenuat" not in desc_lower
        and "filter" not in desc_lower
        and "lna" not in desc_lower
        and "bias" not in desc_lower
        and "load" not in desc_lower
        and "calib" not in desc_lower
    )
    if is_through:
        f_thru = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or f0_ghz
        f_max = max(3.0, round(f_thru * 2.0, 2))
        f_thru_mhz = int(round(f_thru * 1000.0))
        f_label = f"{f_thru_mhz}MHz" if f_thru < 1.0 else f"{f_thru:.2f}GHz"
        name_str = f"cpwg_through_{f_label.lower().replace('.', '_')}"
        return CircuitSpec(
            name=name_str,
            title=f"{z0:.0f}Ω Grounded Coplanar Waveguide (CPWG) Through Line ({f_label})",
            topology="through",
            num_ports=2,
            description=f"Precision {z0:.0f}-ohm Grounded Coplanar Waveguide (CPWG) transmission line test fixture on {substrate_name} with continuous ground via stitching.",
            f_min_ghz=0.01,
            f_0_ghz=f_thru,
            f_max_ghz=f_max,
            z0_ohm=z0,
            target_s21_db=-0.1,
            target_s11_db=-30.0,
            target_s22_db=-30.0,
            width_mm=max(width_mm, 30.0),
            height_mm=height_mm,
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            em_sim_type=em_sim_type,
            components={
                "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Input (Port 1)"},
                "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Output (Port 2)"},
            },
            additional_reqs=[
                f"{z0:.0f}-ohm Controlled Impedance CPWG Trace (w=1.87mm, gap=0.40mm)",
                "Perimeter Ground Via Stitching (0.4mm drill, 0.8mm pad)",
                "Solid Bottom Ground Reference Plane (B.Cu)",
                "Corner Radius Chamfers (2.0mm)"
            ]
        )

    # 1. Calibration Load / 50Ω Termination Standard (1-Port)
    # Must NOT match when user is designing an active amplifier, LNA, filter, or transistor circuit
    is_not_amp_or_filter = not any(k in desc_lower for k in ["lna", "amp", "amplifier", "filter", "attenuat", "transistor", "mmbt", "bfg", "2n3904", "bjt", "bpf", "lpf", "hpf"])
    is_explicit_load = is_not_amp_or_filter and (
        "calib" in desc_lower or "solt" in desc_lower or
        "calibration load" in desc_lower or "dummy load" in desc_lower or "termination standard" in desc_lower or
        (re.search(r'\b(?:50|75)\s*(?:ohm|ohms|Ω)?\s*(?:load|termination)\b', desc_lower) and "into" not in desc_lower and "with" not in desc_lower)
    )
    if is_explicit_load:
        f_load = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or f0_ghz
        f_max = max(3.0, round(f_load * 2.0, 2))
        is_single = "single" in desc_lower or ("R1" in overrides and "R2" not in overrides)
        
        comps = {
            "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": f"Port 1 ({z0:.0f}Ω Load Input)"}
        }
        
        if is_single:
            r1_nom = overrides["R1"]["nominal"] if "R1" in overrides else (overrides["R"]["nominal"] if "R" in overrides else z0)
            r1_val = overrides["R1"]["value"] if "R1" in overrides else (overrides["R"]["value"] if "R" in overrides else f"{r1_nom:g}R")
            comps["R1"] = {
                "type": "resistor", "value": r1_val, "nominal_ohm": r1_nom,
                "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Vishay",
                "series": "RR0816 / PAT", "role": f"Shunt {r1_val} Termination"
            }
            reqs = [
                f"{z0:.0f}-ohm Controlled Impedance CPWG Trace (w=1.87mm, gap=0.40mm)",
                "Ground Via Fencing Stitching (0.4mm drill, 0.8mm pad)",
                f"Single {r1_val} Shunt Termination Resistor",
                "Solid Bottom Ground Plane (B.Cu)",
                "Corner Radius Chamfers (2.0mm)"
            ]
        else:
            # Dual symmetric parallel resistors for low inductance
            r_dual = z0 * 2.0
            r1_nom = overrides["R1"]["nominal"] if "R1" in overrides else r_dual
            r1_val = overrides["R1"]["value"] if "R1" in overrides else f"{r1_nom:g}R"
            r2_nom = overrides["R2"]["nominal"] if "R2" in overrides else r_dual
            r2_val = overrides["R2"]["value"] if "R2" in overrides else f"{r2_nom:g}R"
            comps["R1"] = {
                "type": "resistor", "value": r1_val, "nominal_ohm": r1_nom,
                "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Vishay",
                "series": "RR0816 / PAT", "role": "Shunt Upper Termination"
            }
            comps["R2"] = {
                "type": "resistor", "value": r2_val, "nominal_ohm": r2_nom,
                "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Vishay",
                "series": "RR0816 / PAT", "role": "Shunt Lower Termination"
            }
            reqs = [
                f"{z0:.0f}-ohm Controlled Impedance CPWG Trace (w=1.87mm, gap=0.40mm)",
                "Ground Via Fencing Stitching (0.4mm drill, 0.8mm pad)",
                f"Dual Parallel {r1_val} Low-Inductance Shunt Termination (R1 || R2 = {z0:.0f}Ω)",
                "Solid Bottom Ground Plane (B.Cu)",
                "Corner Radius Chamfers (2.0mm)"
            ]

        return CircuitSpec(
            name=f"calibration_load_{int(z0)}ohm",
            title=f"{z0:.0f}Ω RF Calibration Load Standard (1-Port DC-{f_max:.0f}GHz)",
            topology="calibration_load",
            num_ports=1,
            description=f"Precision {z0:.0f}-ohm RF calibration load standard for 1-port VNA calibration on {substrate_name} CPWG.",
            f_min_ghz=0.01,
            f_0_ghz=f_load,
            f_max_ghz=f_max,
            z0_ohm=z0,
            target_s21_db=-60.0,
            target_s11_db=-30.0,
            target_s22_db=-30.0,
            target_isolation_db=-60.0,
            width_mm=25.0,
            height_mm=20.0,
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            em_sim_type=em_sim_type,
            components=comps,
            additional_reqs=reqs
        )

    # 2. Attenuator Detection (e.g. '6 dB attenuator', '20dB pi pad', '10 dB')
    att_match = re.search(r'(\d+(?:\.\d+)?)\s*db\s*(?:pi|tee|t)?\s*(?:attenuator|att|pad)?', desc_lower)
    is_attenuator = ("attenuat" in desc_lower or "pad" in desc_lower or (bool(att_match) and "filter" not in desc_lower and "lna" not in desc_lower and "amp" not in desc_lower)) and ("lna" not in desc_lower and "amp" not in desc_lower)

    # 3. LNA / Active RF Amplifier Detection (e.g. 'create a LNA circuit with mmbt5179', '1090MHz LNA', 'Low Noise Amp')
    is_lna = (
        "lna" in desc_lower
        or "low noise amp" in desc_lower
        or "low-noise amp" in desc_lower
        or "mmbt5179" in desc_lower
        or "bfg520" in desc_lower
        or (("amplifier" in desc_lower or " gain" in desc_lower or "transistor" in desc_lower) and "pad" not in desc_lower and "attenuat" not in desc_lower)
    )
    
    if is_lna:
        f_amp = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or 0.433

        f_amp_mhz = int(round(f_amp * 1000.0))
        f_label = f"{f_amp_mhz}MHz" if f_amp < 1.0 or f_amp_mhz == 1090 else f"{f_amp:.2f}GHz"

        # Check for discrete RF transistor (BJT) vs MMIC
        is_discrete_bjt = any(k in desc_lower for k in ["mmbt5179", "5179", "bfg520", "2n3904", "bjt", "transistor", "discrete", "npn"])

        if is_discrete_bjt:
            transistor_part = "MMBT5179"
            if "bfg520" in desc_lower:
                transistor_part = "BFG520"
            elif "2n3904" in desc_lower or "mmbt3904" in desc_lower:
                transistor_part = "MMBT3904"

            safe_proj_name = f"lna_{transistor_part.lower()}_{f_label.lower().replace('.', '_')}"
            circuit_title = f"{f_label} Discrete {transistor_part} Active RF LNA ({z0:.0f}Ω, +14dB)"
            circuit_desc = (
                f"Discrete {f_label} Low-Noise Amplifier using {transistor_part} NPN RF BJT transistor "
                f"in SOT-23 package with active base bias divider, emitter degeneration & bypass, "
                f"collector RF choke, and 50Ω CPWG controlled-impedance transmission lines."
            )

            # Component synthesis for discrete BJT LNA
            # 1. Base bias divider (VCC=5V, VB~1.25V, VE~0.55V, IE~5.5mA)
            r1_nom = overrides["R1"]["nominal"] if "R1" in overrides else 10000.0
            r1_val = overrides["R1"]["value"] if "R1" in overrides else "10k"
            r2_nom = overrides["R2"]["nominal"] if "R2" in overrides else 3300.0
            r2_val = overrides["R2"]["value"] if "R2" in overrides else "3.3k"

            # 2. Emitter degeneration resistor & bypass capacitor
            r3_nom = overrides["R3"]["nominal"] if "R3" in overrides else 100.0
            r3_val = overrides["R3"]["value"] if "R3" in overrides else "100R"
            c3_val = "1nF" if f_amp <= 0.2 else "100pF"
            c3_nom = 1e-9 if f_amp <= 0.2 else 100e-12
            if "C3" in overrides:
                c3_val = overrides["C3"]["value"]
                c3_nom = overrides["C3"]["nominal"]

            # 3. Collector RF Choke (XL >= 250 ohm)
            l_choke_calc = round(max(22.0, min(680.0, 40.0 / max(0.05, f_amp))))
            l1_nom = overrides["L1"]["nominal"] if "L1" in overrides else l_choke_calc * 1e-9
            l1_val = overrides["L1"]["value"] if "L1" in overrides else f"{l_choke_calc:g}nH"
            ind_choke_info = select_inductor_package_and_vendor(l1_nom)

            # 4. DC Blocking capacitors
            c_block_val = "100pF" if f_amp < 0.3 else ("47pF" if f_amp < 1.0 else "10pF")
            c_block_nom = 100e-12 if f_amp < 0.3 else (47e-12 if f_amp < 1.0 else 10e-12)
            c1_val = overrides["C1"]["value"] if "C1" in overrides else c_block_val
            c1_nom = overrides["C1"]["nominal"] if "C1" in overrides else c_block_nom
            c2_val = overrides["C2"]["value"] if "C2" in overrides else c_block_val
            c2_nom = overrides["C2"]["nominal"] if "C2" in overrides else c_block_nom

            bjt_comps = {
                "Q1": {
                    "type": "transistor",
                    "value": transistor_part,
                    "package": "Package_TO_SOT_SMD:SOT-23",
                    "vendor": "ON Semiconductor / Fairchild",
                    "series": transistor_part,
                    "role": f"Discrete NPN RF Low-Noise Transistor (fT=1.4GHz, SOT-23)"
                },
                "C1": {
                    "type": "capacitor", "value": c1_val, "nominal_val": c1_nom,
                    "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK",
                    "series": "GRM / C0G", "role": "Input DC Blocking Capacitor"
                },
                "R1": {
                    "type": "resistor", "value": r1_val, "nominal_ohm": r1_nom,
                    "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Yageo",
                    "series": "RR0816", "role": "Base Bias Upper Divider Resistor (VCC to Base)"
                },
                "R2": {
                    "type": "resistor", "value": r2_val, "nominal_ohm": r2_nom,
                    "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Yageo",
                    "series": "RR0816", "role": "Base Bias Lower Divider Resistor (Base to GND)"
                },
                "R3": {
                    "type": "resistor", "value": r3_val, "nominal_ohm": r3_nom,
                    "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Yageo",
                    "series": "RR0816", "role": "Emitter DC Bias Stabilization Resistor (RE)"
                },
                "C3": {
                    "type": "capacitor", "value": c3_val, "nominal_val": c3_nom,
                    "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK",
                    "series": "GRM / C0G", "role": "Emitter RF AC Bypass Capacitor (CE)"
                },
                "L1": {
                    "type": "inductor", "value": l1_val, "nominal_val": l1_nom,
                    "package": ind_choke_info["package"], "vendor": ind_choke_info["vendor"],
                    "series": ind_choke_info["series"], "role": "Collector RF Choke Inductor to VCC"
                },
                "C2": {
                    "type": "capacitor", "value": c2_val, "nominal_val": c2_nom,
                    "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK",
                    "series": "GRM / C0G", "role": "Output DC Blocking Capacitor"
                },
                "C4": {
                    "type": "capacitor", "value": "10nF", "nominal_val": 10e-9,
                    "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK",
                    "series": "GRM / X7R", "role": "Power Supply VCC Decoupling Capacitor"
                },
                "J1": {
                    "type": "connector", "value": "SMA_IN",
                    "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount",
                    "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Input (Port 1)"
                },
                "J2": {
                    "type": "connector", "value": "SMA_OUT",
                    "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount",
                    "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Output (Port 2)"
                },
                "J3": {
                    "type": "connector", "value": "+5V_GND",
                    "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
                    "vendor": "Samtec", "series": "TSW", "role": "DC Power Header (+5V/GND)"
                }
            }

            return CircuitSpec(
                name=safe_proj_name,
                title=circuit_title,
                topology="lna",
                description=circuit_desc,
                f_min_ghz=round(max(0.01, f_amp * 0.5), 3),
                f_0_ghz=round(f_amp, 4),
                f_max_ghz=round(min(3.0, f_amp * 2.0), 3),
                z0_ohm=z0,
                target_s21_db=14.0,
                target_s11_db=-15.0,
                target_s22_db=-15.0,
                width_mm=max(width_mm, 35.0),
                height_mm=max(height_mm, 24.0),
                substrate_name=substrate_name,
                dielectric_er=er,
                substrate_height_mm=h_mm,
                power_supply_type="Active (+5V DC)",
                power_voltage_v=5.0,
                em_sim_type=em_sim_type,
                components=bjt_comps,
                additional_reqs=[
                    f"Controlled Impedance 50Ω CPWG RF Path (w={calc_cpwg_dimensions(er, h_mm, z0)[0]:.2f}mm, gap=0.40mm)",
                    f"Discrete {transistor_part} NPN Transistor Biasing Network (VCC=+5V)",
                    "Continuous Ground Via Perimeter Stitching (0.4mm drill, 0.8mm pad)",
                    "Solid Bottom Ground Reference Plane (B.Cu)",
                    "Corner Fillet Radii (2.0mm)"
                ]
            )

        # Otherwise synthesize Active MMIC LNA (SPF5189Z)
        safe_proj_name = f"lna_{f_label.lower().replace('.', '_')}"
        if "adsb" in desc_lower or "ads-b" in desc_lower or f_amp_mhz == 1090:
            safe_proj_name = "lna_adsb_1090mhz"
            circuit_title = "1090 MHz ADS-B Active Low-Noise Amplifier (SPF5189Z LNA, +18.5dB)"
            circuit_desc = "Precision 1090 MHz ADS-B Low-Noise Amplifier using active SPF5189Z MMIC (NF=0.6dB, Gain=+18.5dB) with 50Ω CPWG matching, RF choke bias injection, and +5V DC supply."
        elif "fm" in desc_lower or abs(f_amp - 0.1) < 0.01:
            safe_proj_name = "lna_fm_100mhz"
            circuit_title = "100 MHz FM Radio Active Low-Noise Amplifier (SPF5189Z LNA, +18.5dB)"
            circuit_desc = "Active 100 MHz FM Radio Low-Noise Amplifier using SPF5189Z MMIC (NF=0.6dB, Gain=+18.5dB) with 50Ω CPWG matching, RF choke bias network, and +5V DC supply."
        else:
            circuit_title = f"{f_label} Active RF Low-Noise Amplifier (SPF5189Z LNA, +18.5dB)"
            circuit_desc = f"Active {f_label} Low-Noise Amplifier using SPF5189Z MMIC (NF=0.6dB, Gain=+18.5dB) with 50Ω CPWG transmission line matching, RF choke bias network, and +5V DC header."

        l_in_nh = round(8.2 * (1.09 / max(0.05, f_amp)), 1)
        l_in_h = l_in_nh * 1e-9
        ind_in_info = select_inductor_package_and_vendor(l_in_h)
        ind_choke_info = select_inductor_package_and_vendor(47e-9)

        return CircuitSpec(
            name=safe_proj_name,
            title=circuit_title,
            topology="lna",
            description=circuit_desc,
            f_min_ghz=round(max(0.05, f_amp * 0.5), 3),
            f_0_ghz=round(f_amp, 4),
            f_max_ghz=round(f_amp * 1.8, 3),
            z0_ohm=z0,
            target_s21_db=18.5,
            target_s11_db=-16.0,
            target_s22_db=-16.0,
            width_mm=max(width_mm, 40.0),
            height_mm=max(height_mm, 28.0),
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            power_supply_type="Active (+5V DC)",
            power_voltage_v=5.0,
            em_sim_type=em_sim_type,
            components={
                "U1": {
                    "type": "ic",
                    "value": "SPF5189Z",
                    "package": "Package_TO_SOT_SMD:SOT-89-3",
                    "vendor": "Qorvo / Mini-Circuits",
                    "series": "SPF5189Z",
                    "role": "Active RF MMIC Amplifier (+18.5dB Gain, 0.6dB NF)"
                },
                "C1": {
                    "type": "capacitor",
                    "value": "47pF",
                    "nominal_val": 47e-12,
                    "package": "Capacitor_SMD:C_0805_2012Metric",
                    "vendor": "Murata / TDK",
                    "series": "GRM / C Series C0G",
                    "role": "RF Input DC Blocking Capacitor"
                },
                "L1": {
                    "type": "inductor",
                    "value": f"{l_in_nh}nH",
                    "nominal_val": l_in_h,
                    "package": ind_in_info["package"],
                    "vendor": ind_in_info["vendor"],
                    "series": ind_in_info["series"],
                    "role": f"Input RF Matching Inductor ({f_label})"
                },
                "L2": {
                    "type": "inductor",
                    "value": "47nH",
                    "nominal_val": 47e-9,
                    "package": ind_choke_info["package"],
                    "vendor": ind_choke_info["vendor"],
                    "series": ind_choke_info["series"],
                    "role": "Active Bias RF Choke Inductor"
                },
                "C2": {
                    "type": "capacitor",
                    "value": "47pF",
                    "nominal_val": 47e-12,
                    "package": "Capacitor_SMD:C_0805_2012Metric",
                    "vendor": "Murata / TDK",
                    "series": "GRM / C Series C0G",
                    "role": "RF Output DC Blocking Capacitor"
                },
                "C3": {
                    "type": "capacitor",
                    "value": "100pF",
                    "nominal_val": 100e-12,
                    "package": "Capacitor_SMD:C_0805_2012Metric",
                    "vendor": "Murata / TDK",
                    "series": "GRM / C Series C0G",
                    "role": "High-Frequency Bias Decoupling Capacitor"
                },
                "C4": {
                    "type": "capacitor",
                    "value": "10nF",
                    "nominal_val": 10e-9,
                    "package": "Capacitor_SMD:C_0805_2012Metric",
                    "vendor": "Murata / TDK",
                    "series": "GRM / C Series X7R",
                    "role": "Low-Frequency Supply Decoupling Capacitor"
                },
                "R1": {
                    "type": "resistor",
                    "value": "10R",
                    "nominal_ohm": 10.0,
                    "package": "Resistor_SMD:R_0805_2012Metric",
                    "vendor": "Susumu / Vishay",
                    "series": "RR0816 / PAT",
                    "role": "DC Bias Limiting & Stability Resistor"
                },
                "J1": {
                    "type": "connector",
                    "value": "SMA_IN",
                    "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount",
                    "vendor": "Samtec",
                    "series": "SMA-J-P-H-ST-EM1",
                    "role": "RF Port 1 (50Ω SMA Input)"
                },
                "J2": {
                    "type": "connector",
                    "value": "SMA_OUT",
                    "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount",
                    "vendor": "Samtec",
                    "series": "SMA-J-P-H-ST-EM1",
                    "role": "RF Port 2 (50Ω SMA Output)"
                },
                "J3": {
                    "type": "connector",
                    "value": "DC_VDD_5V",
                    "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
                    "vendor": "Molex / Standard",
                    "series": "2.54mm Header",
                    "role": "+5V DC Power Input & GND Return"
                }
            },
            additional_reqs=[
                "50-ohm Controlled Impedance CPWG Traces (w=1.85mm, gap=0.40mm)",
                "Ground Thermal Via Stitching under SOT-89 slug (4x 0.3mm vias)",
                "Solid Bottom Ground Layer (B.Cu)",
                "Active +5V DC Supply with Multi-Tier Decoupling",
                "Corner Radius Chamfers (2.0mm)"
            ]
        )
    
    if is_attenuator:
        f_att = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or f0_ghz
        att_db = 10.0
        if att_match:
            try:
                val = float(att_match.group(1))
                if 0.1 <= val <= 60.0:
                    att_db = val
            except Exception:
                pass
        
        # Calculate exact Pi-attenuator resistors
        A = 10.0 ** (att_db / 20.0)
        calc_r_shunt = z0 * (A + 1.0) / (A - 1.0)
        calc_r_series = z0 * (A * A - 1.0) / (2.0 * A)
        
        # Check overrides
        if "R_SHUNT" in overrides:
            r1_nom = r3_nom = overrides["R_SHUNT"]["nominal"]
            r1_val = r3_val = overrides["R_SHUNT"]["value"]
        else:
            r1_nom = overrides.get("R1", {}).get("nominal", round(calc_r_shunt, 1))
            r1_val = overrides.get("R1", {}).get("value", f"{round(calc_r_shunt, 1)}R")
            r3_nom = overrides.get("R3", {}).get("nominal", round(calc_r_shunt, 1))
            r3_val = overrides.get("R3", {}).get("value", f"{round(calc_r_shunt, 1)}R")

        if "R_SERIES" in overrides:
            r2_nom = overrides["R_SERIES"]["nominal"]
            r2_val = overrides["R_SERIES"]["value"]
        else:
            r2_nom = overrides.get("R2", {}).get("nominal", round(calc_r_series, 1))
            r2_val = overrides.get("R2", {}).get("value", f"{round(calc_r_series, 1)}R")

        f_max = max(3.0, round(f_att * 2.0, 2))
        return CircuitSpec(
            name=f"attenuator_{int(att_db)}db",
            title=f"{att_db:.1f} dB RF Pi-Attenuator ({z0:.0f}Ω, DC-{f_max:.0f}GHz)",
            topology="attenuator",
            description=f"Precision {att_db:.1f} dB {z0:.0f}-ohm Pi-Attenuator (R1={r1_val}, R2={r2_val}, R3={r3_val}) on {substrate_name}.",
            f_min_ghz=0.01,
            f_0_ghz=f_att,
            f_max_ghz=f_max,
            z0_ohm=z0,
            target_s21_db=-round(att_db, 1),
            target_s11_db=-25.0,
            target_s22_db=-25.0,
            width_mm=width_mm,
            height_mm=height_mm,
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            em_sim_type=em_sim_type,
            components={
                "R1": {"type": "resistor", "value": r1_val, "nominal_ohm": r1_nom, "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Vishay", "series": "RR0816 / PAT", "role": "Shunt Input"},
                "R2": {"type": "resistor", "value": r2_val, "nominal_ohm": r2_nom, "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Vishay", "series": "RR0816 / PAT", "role": "Series Resistor"},
                "R3": {"type": "resistor", "value": r3_val, "nominal_ohm": r3_nom, "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Vishay", "series": "RR0816 / PAT", "role": "Shunt Output"},
                "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": f"RF Port 1 ({z0:.0f}Ω SMA)"},
                "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": f"RF Port 2 ({z0:.0f}Ω SMA)"},
            }
        )

    # 4. High-Pass Filter Detection
    if ("high" in desc_lower and "pass" in desc_lower) or "hpf" in desc_lower:
        fc = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or 1.5
        c_f_calc = 1.0 / (2.0 * math.pi * fc * 1e9 * z0)
        l_h_calc = z0 / (4.0 * math.pi * fc * 1e9)
        
        c1_nom = overrides.get("C1", {}).get("nominal", c_f_calc)
        c1_val = overrides.get("C1", {}).get("value", f"{round(c1_nom * 1e12, 1)}pF")
        l1_nom = overrides.get("L1", {}).get("nominal", (overrides.get("L", {}).get("nominal", l_h_calc)))
        l1_val = overrides.get("L1", {}).get("value", (overrides.get("L", {}).get("value", f"{round(l1_nom * 1e9, 1)}nH")))
        c2_nom = overrides.get("C2", {}).get("nominal", c_f_calc)
        c2_val = overrides.get("C2", {}).get("value", f"{round(c2_nom * 1e12, 1)}pF")
        
        ind_info = select_inductor_package_and_vendor(l1_nom)
        fc_mhz_str = f"{fc * 1000.0:.0f}MHz" if fc < 1.0 else f"{fc:.2f}GHz"

        return CircuitSpec(
            name=f"highpass_filter_{fc_mhz_str.lower().replace('.', '_')}",
            title=f"{fc_mhz_str} RF High-Pass Filter (3-Pole, {z0:.0f}Ω)",
            topology="highpass",
            description=f"3-Pole Butterworth High-Pass Filter with {fc_mhz_str} cutoff (C1={c1_val}, L1={l1_val}, C2={c2_val}).",
            f_min_ghz=round(max(0.01, fc * 0.2), 3),
            f_0_ghz=fc,
            f_max_ghz=round(fc * 3.0, 3),
            z0_ohm=z0,
            target_s21_db=-0.8,
            target_s11_db=-20.0,
            width_mm=max(width_mm, 35.0),
            height_mm=height_mm,
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            em_sim_type=em_sim_type,
            components={
                "C1": {"type": "capacitor", "value": c1_val, "nominal_val": c1_nom, "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK", "series": "GRM / C Series C0G", "role": "Series Input High-Pass Capacitor"},
                "L1": {"type": "inductor", "value": l1_val, "nominal_val": l1_nom, "package": ind_info["package"], "vendor": ind_info["vendor"], "series": ind_info["series"], "role": "Shunt Inductor to Ground"},
                "C2": {"type": "capacitor", "value": c2_val, "nominal_val": c2_nom, "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK", "series": "GRM / C Series C0G", "role": "Series Output High-Pass Capacitor"},
                "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Input"},
                "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Output"},
            }
        )

    # 5. Low-Pass Filter Detection
    if "low" in desc_lower or "lpf" in desc_lower:
        fc = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or 1.5
        c_calc = (1.0 / (2.0 * math.pi * fc * 1e9 * z0))
        l_calc = (2.0 * z0 / (2.0 * math.pi * fc * 1e9))
        
        c1_nom = overrides.get("C1", {}).get("nominal", c_calc)
        c1_val = overrides.get("C1", {}).get("value", f"{round(c1_nom * 1e12, 1)}pF")
        l1_nom = overrides.get("L1", {}).get("nominal", (overrides.get("L", {}).get("nominal", l_calc)))
        l1_val = overrides.get("L1", {}).get("value", (overrides.get("L", {}).get("value", f"{round(l1_nom * 1e9, 1)}nH")))
        c2_nom = overrides.get("C2", {}).get("nominal", c_calc)
        c2_val = overrides.get("C2", {}).get("value", f"{round(c2_nom * 1e12, 1)}pF")
        
        ind_info = select_inductor_package_and_vendor(l1_nom)
        fc_str = f"{int(round(fc * 1000))}mhz" if fc < 1.0 else f"{fc:.2f}ghz".replace('.', '_')
        fc_display = f"{fc * 1000:.0f} MHz" if fc < 1.0 else f"{fc:.2f} GHz"

        return CircuitSpec(
            name=f"lowpass_filter_{fc_str}",
            title=f"{fc_display} RF Low-Pass Filter (3-Pole, {z0:.0f}Ω)",
            topology="lowpass",
            description=f"3-Pole Butterworth Low-Pass Filter with {fc_display} cutoff (C1={c1_val}, L1={l1_val}, C2={c2_val}).",
            f_min_ghz=round(fc * 0.1, 2),
            f_0_ghz=fc,
            f_max_ghz=round(fc * 2.5, 2),
            z0_ohm=z0,
            target_s21_db=-0.8,
            target_s11_db=-20.0,
            width_mm=max(width_mm, 35.0),
            height_mm=height_mm,
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            em_sim_type=em_sim_type,
            components={
                "C1": {"type": "capacitor", "value": c1_val, "nominal_val": c1_nom, "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK", "series": "GRM / C Series C0G", "role": "Shunt Input Capacitor"},
                "L1": {"type": "inductor", "value": l1_val, "nominal_val": l1_nom, "package": ind_info["package"], "vendor": ind_info["vendor"], "series": ind_info["series"], "role": "Series Inductor"},
                "C2": {"type": "capacitor", "value": c2_val, "nominal_val": c2_nom, "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK", "series": "GRM / C Series C0G", "role": "Shunt Output Capacitor"},
                "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Input"},
                "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Output"},
            }
        )

    # 6. Bandpass Filter / LC Tank Detection
    if "bandpass" in desc_lower or "bpf" in desc_lower or "tank" in desc_lower or ("pass" in desc_lower and "high" not in desc_lower and "low" not in desc_lower):
        f0 = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or 1.5
        omega0 = 2.0 * math.pi * f0 * 1e9
        
        has_user_l = "L1" in overrides or "L" in overrides
        has_user_c = "C1" in overrides or "C" in overrides
        
        if has_user_l and has_user_c:
            l_h = overrides.get("L1", {}).get("nominal", overrides.get("L", {}).get("nominal"))
            c_f = overrides.get("C1", {}).get("nominal", overrides.get("C", {}).get("nominal"))
            calc_f0 = 1.0 / (2.0 * math.pi * math.sqrt(l_h * c_f) * 1e9)
            f0 = round(calc_f0, 4)
        elif has_user_l:
            l_h = overrides.get("L1", {}).get("nominal", overrides.get("L", {}).get("nominal"))
            c_f = 1.0 / (omega0**2 * l_h)
        elif has_user_c:
            c_f = overrides.get("C1", {}).get("nominal", overrides.get("C", {}).get("nominal"))
            l_h = 1.0 / (omega0**2 * c_f)
        else:
            # Realistic L and C matching ~50 ohm reactance at f0
            l_h = z0 / omega0
            c_f = 1.0 / (omega0 * z0)
            
        l_nh = round(l_h * 1e9, 1)
        c_pf = round(c_f * 1e12, 1)
        l_val_str = overrides.get("L1", {}).get("value", overrides.get("L", {}).get("value", f"{l_nh}nH"))
        c_val_str = overrides.get("C1", {}).get("value", overrides.get("C", {}).get("value", f"{c_pf}pF"))
        
        ind_info = select_inductor_package_and_vendor(l_h)
        f0_mhz_str = f"{f0 * 1000.0:.0f}MHz" if f0 < 1.0 else f"{f0:.2f}GHz"
        is_shunt = "shunt" in desc_lower or "parallel" in desc_lower

        top_name = "bandpass_shunt" if is_shunt else "bandpass"
        desc_type = "Shunted parallel" if is_shunt else "Series"
        
        return CircuitSpec(
            name=f"bpf_{f0_mhz_str.lower().replace('.', '_')}_lc",
            title=f"{f0_mhz_str} {desc_type} LC Tank Bandpass Filter ({z0:.0f}Ω)",
            topology=top_name,
            description=f"{desc_type} LC tank bandpass filter centered at {f0_mhz_str} (L={l_val_str}, C={c_val_str}) with 50-ohm CPWG I/O.",
            f_min_ghz=round(max(0.01, f0 * 0.1), 3),
            f_0_ghz=f0,
            f_max_ghz=round(f0 * 2.0, 3),
            z0_ohm=z0,
            target_s21_db=-0.5,
            target_s11_db=-20.0,
            width_mm=max(width_mm, 35.0),
            height_mm=height_mm,
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            em_sim_type=em_sim_type,
            components={
                "C1": {"type": "capacitor", "value": c_val_str, "nominal_val": c_f, "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / Johanson", "series": "GRM / High-Q C0G", "role": f"{desc_type} Tank Capacitor"},
                "L1": {"type": "inductor", "value": l_val_str, "nominal_val": l_h, "package": ind_info["package"], "vendor": ind_info["vendor"], "series": ind_info["series"], "role": f"{desc_type} Tank Inductor"},
                "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Input"},
                "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Output"},
            }
        )

    # 7. Bias Tee Detection
    if "bias" in desc_lower or "tee" in desc_lower:
        f_bt = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or f0_ghz
        c1_nom = overrides.get("C1", {}).get("nominal", 100e-12)
        c1_val = overrides.get("C1", {}).get("value", f"{round(c1_nom * 1e12, 1)}pF")
        l1_nom = overrides.get("L1", {}).get("nominal", 100e-9)
        l1_val = overrides.get("L1", {}).get("value", f"{round(l1_nom * 1e9, 1)}nH")
        ind_info = select_inductor_package_and_vendor(l1_nom)
        return CircuitSpec(
            name="bias_tee",
            title=f"Wideband RF Bias Tee ({f_bt:.1f} GHz, {z0:.0f}Ω)",
            topology="bias_tee",
            description=f"RF Bias Tee for DC power injection with {l1_val} RF choke inductor and {c1_val} DC blocking capacitor.",
            f_min_ghz=0.1,
            f_0_ghz=f_bt,
            f_max_ghz=round(f_bt * 2.0, 2),
            z0_ohm=z0,
            target_s21_db=-0.5,
            target_s11_db=-22.0,
            power_supply_type="DC Single Supply",
            power_voltage_v=5.0,
            width_mm=max(width_mm, 35.0),
            height_mm=height_mm,
            substrate_name=substrate_name,
            dielectric_er=er,
            substrate_height_mm=h_mm,
            em_sim_type=em_sim_type,
            components={
                "C1": {"type": "capacitor", "value": c1_val, "nominal_val": c1_nom, "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK", "series": "GRM / C Series C0G", "role": "DC Blocking Capacitor"},
                "L1": {"type": "inductor", "value": l1_val, "nominal_val": l1_nom, "package": ind_info["package"], "vendor": ind_info["vendor"], "series": ind_info["series"], "role": "RF Choke Inductor"},
                "J1": {"type": "connector", "value": "RF_IN", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Port (Pure RF)"},
                "J2": {"type": "connector", "value": "RF_DC_OUT", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF+DC Output"},
                "J3": {"type": "connector", "value": "DC_SUPPLY", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "vendor": "Molex / Standard", "series": "2.54mm Header", "role": "+5V DC Power Input"},
            }
        )

    # 8. Fallback / Custom RF Circuit
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', title.lower()).strip('_')
    f_custom = extract_rf_frequency(desc_lower, default_f0=f0_ghz) or f0_ghz
    
    comps = {
        "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Port 1"},
        "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount", "vendor": "Samtec", "series": "SMA-J-P-H-ST-EM1", "role": "RF Port 2"},
    }
    
    if overrides:
        for ref, o in overrides.items():
            if ref in ["R", "C", "L", "R_SHUNT", "R_SERIES"]:
                continue
            ctype = o["type"]
            val_str = o["value"]
            nom = o["nominal"]
            if ctype == "resistor":
                comps[ref] = {"type": "resistor", "value": val_str, "nominal_ohm": nom, "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Vishay", "series": "RR0816 / PAT", "role": f"{ref} Resistor"}
            elif ctype == "capacitor":
                comps[ref] = {"type": "capacitor", "value": val_str, "nominal_val": nom, "package": "Capacitor_SMD:C_0805_2012Metric", "vendor": "Murata / TDK", "series": "GRM / C Series C0G", "role": f"{ref} Capacitor"}
            elif ctype == "inductor":
                ind_info = select_inductor_package_and_vendor(nom)
                comps[ref] = {"type": "inductor", "value": val_str, "nominal_val": nom, "package": ind_info["package"], "vendor": ind_info["vendor"], "series": ind_info["series"], "role": f"{ref} Inductor"}
    else:
        comps["R1"] = {"type": "resistor", "value": f"{z0:.0f}R", "nominal_ohm": z0, "package": "Resistor_SMD:R_0805_2012Metric", "vendor": "Susumu / Vishay", "series": "RR0816 / PAT", "role": "Terminating Resistor"}

    return CircuitSpec(
        name=safe_name or "custom_rf_board",
        title=title,
        topology="custom",
        description=description,
        f_min_ghz=max(0.01, round(f_custom * 0.1, 2)),
        f_0_ghz=f_custom,
        f_max_ghz=round(f_custom * 2.0, 2),
        z0_ohm=z0,
        target_s21_db=-1.0,
        target_s11_db=-20.0,
        width_mm=width_mm,
        height_mm=height_mm,
        substrate_name=substrate_name,
        dielectric_er=er,
        substrate_height_mm=h_mm,
        em_sim_type=em_sim_type,
        components=comps
    )



