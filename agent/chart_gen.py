"""
Task 8: RF Performance Chart Renderer.
Generates publication-quality charts for S-parameters, Smith chart,
Rollett stability factor, and characteristic impedance.
"""

import os
import matplotlib
matplotlib.use("Agg")  # Headless backend
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any
from .spec import CircuitSpec

def render_rf_charts(spec: CircuitSpec, sim_data: Dict[str, Any], output_dir: str, progress_callback=None) -> Dict[str, Any]:
    """
    Render 4 comprehensive RF performance charts:
    1. sparam_plot.png: S11 & S21 in dB vs Frequency
    2. smith_chart.png: Input & Output Smith Chart loci
    3. stability_plot.png: Rollett stability factor K vs Frequency
    4. impedance_plot.png: Real and Imaginary Zin vs Frequency
    """
    charts_dir = os.path.join(output_dir, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    freqs = sim_data["freqs_ghz"]
    s11_db = sim_data["s11_db"]
    s21_db = sim_data["s21_db"]
    s11 = sim_data["s11"]
    s22 = sim_data["s22"]
    k_factor = sim_data["k_factor"]
    z_in = sim_data["z_in"]

    chart_files = {}

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Chart 1: S-Parameters (dB)
    if progress_callback:
        progress_callback("Rendering S-parameter frequency response chart (dB)...")
    is_load = spec.topology in ["calibration_load", "load"]
    s21_label = "S21 (Port-to-Port Isolation)" if is_load else "S21 (Insertion Loss / Gain)"
    ax.plot(freqs, s21_db, color="#1f77b4", linewidth=2.2, label=s21_label)
    ax.plot(freqs, s11_db, color="#d62728", linewidth=2.0, linestyle="--", label="S11 (Return Loss)")
    if is_load and "s22_db" in sim_data:
        ax.plot(freqs, sim_data["s22_db"], color="#9467bd", linewidth=1.5, linestyle=":", label="S22 (Port 2 Return Loss)")
    if spec.target_s21_db:
        lbl = f"Target Isolation ({spec.target_s21_db} dB)" if is_load else f"Target S21 ({spec.target_s21_db} dB)"
        ax.axhline(spec.target_s21_db, color="#2ca02c", linestyle=":", alpha=0.8, label=lbl)
    ax.set_title(f"{spec.title} - S-Parameter Performance", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Frequency (GHz)", fontsize=11)
    ax.set_ylabel("Magnitude (dB)", fontsize=11)
    y_min = min(np.min(s11_db) - 5, np.min(s21_db) - 5, -50)
    y_max = max(np.max(s21_db) + 5, np.max(s11_db) + 5, 5)
    ax.set_ylim([y_min, y_max])
    ax.legend(loc="upper right" if is_load else "lower right", frameon=True)
    ax.grid(True, linestyle="--", alpha=0.6)
    fig.tight_layout()
    sparam_path = os.path.join(charts_dir, "sparam_plot.png")
    fig.savefig(sparam_path)
    plt.close(fig)
    chart_files["sparam"] = sparam_path

    # Chart 2: Smith Chart
    if progress_callback:
        progress_callback("Rendering RF impedance loci on Smith Chart...")
    smith_path = os.path.join(charts_dir, "smith_chart.png")
    try:
        import skrf as rf
        s2p_file = os.path.join(output_dir, "simulation", f"{spec.name}.s2p")
        if os.path.exists(s2p_file):
            ntwk = rf.Network(s2p_file)
            fig, ax = plt.subplots(figsize=(7, 7), dpi=150)
            ntwk.plot_s_smith(ax=ax, draw_labels=True)
            ax.set_title(f"{spec.title} - Smith Chart (50Ω Reference)", fontsize=12, fontweight="bold")
            fig.tight_layout()
            fig.savefig(smith_path)
            plt.close(fig)
        else:
            raise FileNotFoundError("s2p file not found")
    except Exception:
        # Fallback polar plot resembling Smith Chart
        fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(7, 7), dpi=150)
        theta_11 = np.angle(s11)
        r_11 = np.abs(s11)
        ax.plot(theta_11, r_11, color="#1f77b4", linewidth=2.2, label="S11 Reflection Locus")
        ax.set_rmax(1.0)
        ax.set_rticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_title(f"{spec.title} - Complex Reflection Locus", fontsize=12, fontweight="bold", pad=15)
        ax.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(smith_path)
        plt.close(fig)
    chart_files["smith"] = smith_path

    # Chart 3: Rollett Stability Factor K
    if progress_callback:
        progress_callback("Rendering Rollett stability factor (K) curve...")
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    ax.plot(freqs, k_factor, color="#2ca02c", linewidth=2.2, label="Rollett Stability Factor (K)")
    ax.axhline(1.0, color="#d62728", linestyle="--", linewidth=1.5, label="Unconditional Stability Threshold (K = 1.0)")
    ax.set_title(f"{spec.title} - Rollett Stability Factor (K > 1.0)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Frequency (GHz)", fontsize=11)
    ax.set_ylabel("Stability Factor (K)", fontsize=11)
    # Clip large K for visualization
    ax.set_ylim([0.0, min(np.max(k_factor) * 1.1, 10.0)])
    ax.legend(loc="upper right", frameon=True)
    ax.grid(True, linestyle="--", alpha=0.6)
    fig.tight_layout()
    stab_path = os.path.join(charts_dir, "stability_plot.png")
    fig.savefig(stab_path)
    plt.close(fig)
    chart_files["stability"] = stab_path

    # Chart 4: Input Impedance (Real & Imaginary)
    if progress_callback:
        progress_callback("Rendering input/output impedance vs frequency...")
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    ax.plot(freqs, np.real(z_in), color="#9467bd", linewidth=2.2, label="Re(Zin) - Resistance (Ω)")
    ax.plot(freqs, np.imag(z_in), color="#ff7f0e", linewidth=1.8, linestyle="--", label="Im(Zin) - Reactance (Ω)")
    ax.axhline(spec.z0_ohm, color="#7f7f7f", linestyle=":", label=f"System Reference ({spec.z0_ohm} Ω)")
    ax.set_title(f"{spec.title} - Characteristic Impedance", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Frequency (GHz)", fontsize=11)
    ax.set_ylabel("Impedance (Ω)", fontsize=11)
    ax.set_ylim([0, 100])
    ax.legend(loc="upper right", frameon=True)
    ax.grid(True, linestyle="--", alpha=0.6)
    fig.tight_layout()
    z_path = os.path.join(charts_dir, "impedance_plot.png")
    fig.savefig(z_path)
    plt.close(fig)
    chart_files["impedance"] = z_path

    return chart_files
