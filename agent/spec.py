"""
RF Circuit Specifications, Presets, and Impedance Synthesis for RF AI Suite.
Includes Wheeler/Hammerstad equations for Microstrip, Cohn/Ghione equations for CPWG,
and natural language parsing for custom RF circuits.
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
    topology, target RF metrics, and transmission line properties.
    """
    desc_lower = description.lower()
    
    # 1. Attenuator Detection (e.g. '6 dB attenuator', '20dB pi pad', '10 dB')
    att_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:db)?\s*(?:pi|tee|t)?\s*(?:attenuator|att|pad)?', desc_lower)
    is_attenuator = "attenuat" in desc_lower or "pad" in desc_lower or ("db" in desc_lower and not "filter" in desc_lower)
    
    if is_attenuator:
        att_db = 10.0
        if att_match:
            try:
                val = float(att_match.group(1))
                if 0.5 <= val <= 40.0:
                    att_db = val
            except Exception:
                pass
        
        # Calculate exact Pi-attenuator resistors
        A = 10.0 ** (att_db / 20.0)
        r_shunt = z0 * (A + 1.0) / (A - 1.0)
        r_series = z0 * (A * A - 1.0) / (2.0 * A)
        
        r_shunt_round = round(r_shunt, 1)
        r_series_round = round(r_series, 1)
        
        spec = CircuitSpec(
            name=f"attenuator_{int(att_db)}db",
            title=f"{att_db:.1f} dB RF Pi-Attenuator ({z0:.0f}Ω, DC-3GHz)",
            topology="attenuator",
            description=f"Precision {att_db:.1f} dB 50-ohm Pi-Attenuator (R_shunt={r_shunt_round}Ω, R_series={r_series_round}Ω) on {substrate_name}.",
            f_min_ghz=0.01,
            f_0_ghz=f0_ghz,
            f_max_ghz=round(max(3.0, f0_ghz * 2.0), 2),
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
                "R1": {"type": "resistor", "value": f"{r_shunt_round}R", "nominal_ohm": r_shunt_round, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Shunt Input"},
                "R2": {"type": "resistor", "value": f"{r_series_round}R", "nominal_ohm": r_series_round, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Series Resistor"},
                "R3": {"type": "resistor", "value": f"{r_shunt_round}R", "nominal_ohm": r_shunt_round, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Shunt Output"},
                "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": f"RF Port 1 ({z0:.0f}Ω)"},
                "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": f"RF Port 2 ({z0:.0f}Ω)"},
            }
        )
        return spec

    # 2. Low-Pass Filter Detection
    if "low" in desc_lower or "lpf" in desc_lower:
        fc = f0_ghz
        fc_match = re.search(r'(\d+(?:\.\d+)?)\s*(ghz|mhz)', desc_lower)
        if fc_match:
            try:
                v = float(fc_match.group(1))
                fc = v if fc_match.group(2) == "ghz" else v / 1000.0
            except Exception:
                pass
        # 3-pole Butterworth C-L-C
        c_val_pf = round((1.0 / (2.0 * math.pi * fc * 1e9 * z0)) * 1e12, 1)
        l_val_nh = round((2.0 * z0 / (2.0 * math.pi * fc * 1e9)) * 1e9, 1)
        
        return CircuitSpec(
            name=f"lowpass_filter_{str(fc).replace('.', '_')}ghz",
            title=f"{fc:.2f} GHz RF Low-Pass Filter (3-Pole, {z0:.0f}Ω)",
            topology="lowpass",
            description=f"3-Pole Butterworth Low-Pass Filter with {fc:.2f} GHz cutoff (C1={c_val_pf}pF, L1={l_val_nh}nH, C2={c_val_pf}pF).",
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
                "C1": {"type": "capacitor", "value": f"{c_val_pf}pF", "nominal_val": c_val_pf * 1e-12, "package": "Capacitor_SMD:C_0805_2012Metric", "role": "Shunt Input Capacitor"},
                "L1": {"type": "inductor", "value": f"{l_val_nh}nH", "nominal_val": l_val_nh * 1e-9, "package": "Inductor_SMD:L_0805_2012Metric", "role": "Series Inductor"},
                "C2": {"type": "capacitor", "value": f"{c_val_pf}pF", "nominal_val": c_val_pf * 1e-12, "package": "Capacitor_SMD:C_0805_2012Metric", "role": "Shunt Output Capacitor"},
                "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Input"},
                "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Output"},
            }
        )

    # 3. Bias Tee Detection
    if "bias" in desc_lower or "tee" in desc_lower:
        return CircuitSpec(
            name="bias_tee",
            title=f"Wideband RF Bias Tee ({f0_ghz:.1f} GHz, {z0:.0f}Ω)",
            topology="bias_tee",
            description="RF Bias Tee for DC power injection with 100nH RF choke inductor and 100pF DC blocking capacitor.",
            f_min_ghz=0.1,
            f_0_ghz=f0_ghz,
            f_max_ghz=round(f0_ghz * 2.0, 2),
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
                "C1": {"type": "capacitor", "value": "100pF", "nominal_val": 100e-12, "package": "Capacitor_SMD:C_0805_2012Metric", "role": "DC Blocking Capacitor"},
                "L1": {"type": "inductor", "value": "100nH", "nominal_val": 100e-9, "package": "Inductor_SMD:L_0805_2012Metric", "role": "RF Choke Inductor"},
                "J1": {"type": "connector", "value": "RF_IN", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Port (Pure RF)"},
                "J2": {"type": "connector", "value": "RF_DC_OUT", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF+DC Output"},
                "J3": {"type": "connector", "value": "DC_SUPPLY", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "+5V DC Power Input"},
            }
        )

    # 4. Fallback: Generic 50-ohm RF Circuit
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', title.lower()).strip('_')
    return CircuitSpec(
        name=safe_name or "custom_rf_board",
        title=title,
        topology="custom",
        description=description,
        f_min_ghz=max(0.01, round(f0_ghz * 0.1, 2)),
        f_0_ghz=f0_ghz,
        f_max_ghz=round(f0_ghz * 2.0, 2),
        z0_ohm=z0,
        target_s21_db=-1.0,
        target_s11_db=-20.0,
        width_mm=width_mm,
        height_mm=height_mm,
        substrate_name=substrate_name,
        dielectric_er=er,
        substrate_height_mm=h_mm,
        em_sim_type=em_sim_type,
        components={
            "R1": {"type": "resistor", "value": "50R", "nominal_ohm": 50.0, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Terminating Resistor"},
            "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Port 1"},
            "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Port 2"},
        }
    )


# Pre-configured Presets
PRESET_10DB_ATTENUATOR = CircuitSpec(
    name="attenuator_10db",
    title="10 dB RF Pi-Attenuator (50Ω, DC-3GHz)",
    topology="attenuator",
    description="Precision 10 dB Pi-Attenuator with 50-ohm I/O matching, 0805 SMD thin-film resistors, and SMA ports.",
    f_min_ghz=0.01,
    f_0_ghz=1.5,
    f_max_ghz=3.0,
    z0_ohm=50.0,
    target_s21_db=-10.0,
    target_s11_db=-25.0,
    target_s22_db=-25.0,
    width_mm=30.0,
    height_mm=20.0,
    substrate_name="FR4",
    dielectric_er=4.4,
    substrate_height_mm=1.6,
    power_supply_type="Passive",
    em_sim_type="traces",
    components={
        "R1": {"type": "resistor", "value": "95.3R", "nominal_ohm": 96.2, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Shunt Input"},
        "R2": {"type": "resistor", "value": "71.5R", "nominal_ohm": 71.2, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Series Resistor"},
        "R3": {"type": "resistor", "value": "95.3R", "nominal_ohm": 96.2, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Shunt Output"},
        "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Port 1 (50Ω)"},
        "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "role": "RF Port 2 (50Ω)"},
    },
    additional_reqs=[
        "50-ohm Controlled Impedance CPWG Traces (w=1.85mm, gap=0.40mm)",
        "Ground Via Stitching (0.4mm drill, 0.8mm pad)",
        "Solid Bottom Ground Layer (B.Cu)",
        "Corner Radius Chamfers (2.0mm)"
    ]
)

PRESET_2_4GHZ_FILTER = CircuitSpec(
    name="bandpass_filter_2_4ghz",
    title="2.45 GHz Microstrip Bandpass Filter (Wi-Fi / ISM)",
    topology="filter",
    description="Coupled-line microstrip resonator bandpass filter centered at 2.45 GHz with 100 MHz bandwidth.",
    f_min_ghz=2.0,
    f_0_ghz=2.45,
    f_max_ghz=3.0,
    z0_ohm=50.0,
    target_s21_db=-2.0,
    target_s11_db=-18.0,
    width_mm=45.0,
    height_mm=25.0,
    substrate_name="FR4",
    dielectric_er=4.4,
    substrate_height_mm=1.6,
    power_supply_type="Passive",
    em_sim_type="traces"
)

PRESET_WILKINSON_DIVIDER = CircuitSpec(
    name="wilkinson_divider",
    title="1.5 - 2.5 GHz 2-Way Wilkinson Power Divider",
    topology="divider",
    description="Equal-split 2-way power divider with quarter-wave 70.7-ohm transform arms and 100-ohm isolation resistor.",
    f_min_ghz=1.0,
    f_0_ghz=2.0,
    f_max_ghz=3.0,
    z0_ohm=50.0,
    target_s21_db=-3.05,
    target_s11_db=-20.0,
    width_mm=40.0,
    height_mm=30.0,
    substrate_name="FR4",
    dielectric_er=4.4,
    substrate_height_mm=1.6,
    power_supply_type="Passive",
    em_sim_type="traces"
)

PRESETS = {
    "1": PRESET_10DB_ATTENUATOR,
    "2": PRESET_2_4GHZ_FILTER,
    "3": PRESET_WILKINSON_DIVIDER,
}
