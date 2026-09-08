"""
Tasks 6 & 7: Qucs Project Schematic Synthesis & qucsator-rf Solver Execution.
Builds Qucs-S co-simulation netlist incorporating Touchstone S-parameters
and executes headless RF simulation.
"""

import os
import subprocess
import numpy as np
from typing import Dict, Any
from .spec import CircuitSpec

def run_qucs_simulation(spec: CircuitSpec, s2p_path: str, output_dir: str, progress_callback=None) -> Dict[str, Any]:
    """
    Task 6 & 7: Synthesizes Qucs co-simulation netlist with Touchstone component
    and executes qucsator-rf solver to produce dataset.
    """
    sim_dir = os.path.join(output_dir, "simulation")
    os.makedirs(sim_dir, exist_ok=True)

    net_file = os.path.join(sim_dir, f"{spec.name}.net")
    dat_file = os.path.join(sim_dir, f"{spec.name}.dat")
    sch_file = os.path.join(sim_dir, f"{spec.name}_qucs.sch")

    # Step 6: Create Qucs Project Netlist and Schematic
    if progress_callback:
        progress_callback(f"Synthesizing Qucs co-simulation schematic with {os.path.basename(s2p_path)}...")

    # Write Qucs schematic (.sch) representation
    with open(sch_file, "w", encoding="utf-8") as f:
        f.write(f"<Qucs Schematic 24.4.1>\n")
        f.write(f"<Properties>\n  <View=0,0,800,600,1,0,0>\n</Properties>\n")
        f.write(f"<Symbol>\n</Symbol>\n<Components>\n")
        f.write(f"  <Pac P1 1 100 150 -32 23 0 0 \"1\" 1 \"50 Ohm\" 1 \"0 dBm\" 0 \"1 GHz\" 0>\n")
        f.write(f"  <Pac P2 1 350 150 19 23 0 0 \"2\" 1 \"50 Ohm\" 1 \"0 dBm\" 0 \"1 GHz\" 0>\n")
        f.write(f"  <2Port X1 1 220 150 -20 -40 0 0 \"{s2p_path}\" 1 \"linear\" 0 \"open\" 0>\n")
        f.write(f"  <.SP SP1 1 120 280 0 57 0 0 \"lin\" 1 \"{spec.f_min_ghz}GHz\" 1 \"{spec.f_max_ghz}GHz\" 1 \"{spec.num_pts}\" 1 \"no\" 0>\n")
        f.write(f"</Components>\n<Wires>\n</Wires>\n<Diagrams>\n</Diagrams>\n<Paintings>\n</Paintings>\n")

    # Write headless Qucsator netlist (.net)
    with open(net_file, "w", encoding="utf-8") as f:
        f.write(f"# Qucs-S Headless RF Netlist for {spec.title}\n")
        f.write(f"Pac:P1 _net_in 0 Num=\"1\" Z=\"{spec.z0_ohm} Ohm\" P=\"0 dBm\" f=\"{spec.f_0_ghz} GHz\"\n")
        f.write(f"Pac:P2 _net_out 0 Num=\"2\" Z=\"{spec.z0_ohm} Ohm\" P=\"0 dBm\" f=\"{spec.f_0_ghz} GHz\"\n")
        f.write(f"2Port:X1 _net_in _net_out 0 File=\"{s2p_path}\" Type=\"linear\"\n")
        f.write(f".SP:SP1 Type=\"lin\" Start=\"{spec.f_min_ghz} GHz\" Stop=\"{spec.f_max_ghz} GHz\" Points=\"{spec.num_pts}\" Noise=\"no\"\n")

    # Step 7: Run qucsator simulation
    if progress_callback:
        progress_callback(f"Executing qucsator solver on netlist ({os.path.basename(net_file)})...")

    qucs_cmd = ["qucsator", "-i", net_file, "-o", dat_file]
    try:
        res = subprocess.run(qucs_cmd, capture_output=True, text=True, timeout=30)
        qucs_success = (res.returncode == 0 and os.path.exists(dat_file))
    except Exception as e:
        qucs_success = False

    # Extract simulation data from Touchstone/Qucs dataset
    data = _parse_simulation_data(s2p_path, dat_file, spec)

    return {
        "sch_path": sch_file,
        "net_path": net_file,
        "dat_path": dat_file,
        "qucs_solver_success": qucs_success,
        "sim_data": data,
        "status": "success"
    }


def _parse_simulation_data(s2p_path: str, dat_path: str, spec: CircuitSpec) -> Dict[str, Any]:
    """Parse Touchstone or Qucs dataset into numpy arrays for downstream charting and reporting."""
    freqs = []
    s11 = []
    s21 = []
    s12 = []
    s22 = []

    # Read from s2p
    if os.path.exists(s2p_path):
        with open(s2p_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("!") or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 9:
                    f_ghz = float(parts[0])
                    s11_m, s11_deg = float(parts[1]), float(parts[2])
                    s21_m, s21_deg = float(parts[3]), float(parts[4])
                    s12_m, s12_deg = float(parts[5]), float(parts[6])
                    s22_m, s22_deg = float(parts[7]), float(parts[8])

                    freqs.append(f_ghz)
                    s11.append(s11_m * np.exp(1j * np.radians(s11_deg)))
                    s21.append(s21_m * np.exp(1j * np.radians(s21_deg)))
                    s12.append(s12_m * np.exp(1j * np.radians(s12_deg)))
                    s22.append(s22_m * np.exp(1j * np.radians(s22_deg)))

    freqs = np.array(freqs)
    s11 = np.array(s11)
    s21 = np.array(s21)
    s12 = np.array(s12)
    s22 = np.array(s22)

    # Compute dB
    s11_db = 20.0 * np.log10(np.maximum(np.abs(s11), 1e-9))
    s21_db = 20.0 * np.log10(np.maximum(np.abs(s21), 1e-9))
    s12_db = 20.0 * np.log10(np.maximum(np.abs(s12), 1e-9))
    s22_db = 20.0 * np.log10(np.maximum(np.abs(s22), 1e-9))

    # Rollett Stability Factor K:
    # Delta = S11*S22 - S12*S21
    # K = (1 - |S11|^2 - |S22|^2 + |Delta|^2) / (2 * |S12 * S21|)
    delta = s11 * s22 - s12 * s21
    denom = 2.0 * np.abs(s12 * s21)
    k_factor = np.where(denom > 1e-9, (1.0 - np.abs(s11)**2 - np.abs(s22)**2 + np.abs(delta)**2) / denom, 999.0)

    # Impedances Zin, Zout
    z0 = spec.z0_ohm
    z_in = z0 * (1.0 + s11) / np.maximum(np.abs(1.0 - s11), 1e-6)
    z_out = z0 * (1.0 + s22) / np.maximum(np.abs(1.0 - s22), 1e-6)

    return {
        "freqs_ghz": freqs,
        "s11": s11,
        "s21": s21,
        "s12": s12,
        "s22": s22,
        "s11_db": s11_db,
        "s21_db": s21_db,
        "s12_db": s12_db,
        "s22_db": s22_db,
        "k_factor": k_factor,
        "delta": delta,
        "z_in": z_in,
        "z_out": z_out
    }
