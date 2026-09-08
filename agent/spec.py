"""
RF Circuit Specifications and Presets for RF AI Suite.
Defines circuit parameters, substrate properties, and calculation helpers.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class CircuitSpec:
    name: str = "attenuator_10db"
    title: str = "10 dB RF Pi-Attenuator (50Ω, DC-3GHz)"
    topology: str = "attenuator"  # 'attenuator', 'filter', 'divider', 'custom'
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
    components: Dict[str, Any] = field(default_factory=lambda: {
        "R1": {"type": "resistor", "value": "95.3R", "nominal_ohm": 96.2, "package": "R_0805_2012Metric", "role": "Shunt Input"},
        "R2": {"type": "resistor", "value": "71.5R", "nominal_ohm": 71.2, "package": "R_0805_2012Metric", "role": "Series Resistor"},
        "R3": {"type": "resistor", "value": "95.3R", "nominal_ohm": 96.2, "package": "R_0805_2012Metric", "role": "Shunt Output"},
        "J1": {"type": "connector", "value": "SMA_IN", "package": "Connector_Coaxial:SMA_Amphenol_132134_Vertical", "role": "RF Port 1 (50Ω)"},
        "J2": {"type": "connector", "value": "SMA_OUT", "package": "Connector_Coaxial:SMA_Amphenol_132134_Vertical", "role": "RF Port 2 (50Ω)"},
    })
    
    # Additional features
    additional_reqs: List[str] = field(default_factory=lambda: [
        "50-ohm Microstrip I/O Traces",
        "Ground Via Fencing Stitching",
        "Solid Bottom Ground Plane",
        "Corner Chamfer Radii (2.0mm)"
    ])

    @property
    def microstrip_width_mm(self) -> float:
        """Calculate the 50-ohm microstrip trace width for given substrate."""
        return calc_microstrip_width(self.dielectric_er, self.substrate_height_mm, self.z0_ohm)


def calc_microstrip_width(er: float, h_mm: float, z0: float = 50.0) -> float:
    """
    Synthesize microstrip trace width (w) in mm for a desired characteristic impedance Z0
    using Wheeler / Hammerstad-Jensen closed-form synthesis.
    """
    A = (z0 / 60.0) * math.sqrt((er + 1.0) / 2.0) + ((er - 1.0) / (er + 1.0)) * (0.23 + 0.11 / er)
    B = (377.0 * math.pi) / (2.0 * z0 * math.sqrt(er))
    
    # Initial estimate
    w_over_h_A = (8.0 * math.exp(A)) / (math.exp(2.0 * A) - 2.0)
    if w_over_h_A < 2.0:
        w_over_h = w_over_h_A
    else:
        w_over_h = (2.0 / math.pi) * (B - 1.0 - math.log(2.0 * B - 1.0) + 
                                      ((er - 1.0) / (2.0 * er)) * (math.log(B - 1.0) + 0.39 - 0.61 / er))
    
    width_mm = round(w_over_h * h_mm, 3)
    return max(width_mm, 0.2)  # Minimum 0.2mm manufacturable


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
        "50-ohm Microstrip I/O Traces (~3.0mm width)",
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
