# RF Agent Skills Catalog (SKILLS.md)

> [!IMPORTANT]
> **Thin catalog — AGENTS.md is the canonical source.**
> This file is a **high-level index** of the agent's skills. The **complete, authoritative operating protocol** (Turn 0 Repository Self-Provisioning (submodule + Docker + greeting), Immediate Execution Policy, Default Hardware Baseline, Interactive Review Protocol, and full CLI reference) lives in **[AGENTS.md](AGENTS.md)** and is **not duplicated here**. Read and follow `AGENTS.md` first; use this catalog only for orientation.
>
> **Editing rule**: Never edit protocol or baseline rules here. Update [AGENTS.md](AGENTS.md) — this catalog inherits changes automatically.

This document indexes the operational capabilities of the **Autonomous RF Hardware Engineer Agent**.

---

## Toolchain Architecture: Dependency on `rf-suite`

The hardware design intellect and workflow orchestration reside in `rf-agent`. All heavy EDA/CAD and electromagnetic simulation solvers reside in the linked container environment `rf-suite` (`./rf-suite` Git submodule, pointing to `cholan2100/rf-suite`).

Autonomous agents invoke all solvers and Python engines headlessly through the standard launchers in `rf-suite/bin/` (full protocol in [AGENTS.md](AGENTS.md), §1.1–1.2):
- **Windows**: `rf-suite\bin\rf-run.bat <command>`
- **Linux / WSL**: `./rf-suite/bin/rf-run <command>`

---

## Skills Index

| Skill | Domain | Canonical Protocol Section in AGENTS.md |
|---|---|---|
| **1** | RF Requirements Engineering & CPWG Transmission Line Synthesis | §1.4 Default Hardware Baseline; §1.3 Immediate Execution Policy |
| **2** | Programmatic KiCad 10 Schematic Generation & Rasterization | §1.3; §4 Task 1 (`--stages schematic`) |
| **3** | Controlled Impedance PCB Layout with `pcbnew` | §1.4; §4 Task 2 (`--stages pcb`); §5 Engineering Quality Standards |
| **4** | High-Fidelity 3D Raytraced Hardware Rendering | §4 Task 3 (`--stages render`) |
| **5** | Mechanical CAD Modeling & STEP Assembly | §4 Task 4 (`--stages cad`) |
| **6** | Multi-Port S-Parameter EM Extraction (openEMS) | §4 Task 5 (`--stages em`) |
| **7** | Qucs-S Co-Simulation Netlist & Solver Execution | §4 Task 6 (`--stages qucs`) |
| **8** | Publication-Quality RF Performance Visualization | §4 Task 7 (`--stages charts`) |
| **9** | Performance Documentation & BOM Generation | §4 Task 9 (`--stages report`) |
| **10** | Production Gerber & Drill ZIP Packaging | §4 Task 8 (`--stages gerbers`) |
| **11** | Parametric Tuning & Design Optimization Loop | §1 Operating Philosophy, step 6 |
| **12** | Human-in-the-Loop Stage Review & Interactive Popup Modals | §6 Interactive Popup Review Protocol |

Referenced skills (SOLT calibration standards, 1-port terminations, bias tees) follow the Default Hardware Baseline in [AGENTS.md](AGENTS.md) §1.4 — in particular, 1-port circuits use **only** `J1`/`SMA_IN` and report only $S_{11}$ / VSWR.

---

## RF Engineering Reference Math (unique content — kept here, canonical for formulas)

> These closed-form relations are reference material for skills 1, 6, 8, and 11. Circuit assumptions and when to apply them are governed by [AGENTS.md](AGENTS.md) §1.4.

### Grounded Coplanar Waveguide (CPWG) Physics
When top copper ground pour is present with gap $s$, the RF signal line is a **Grounded Coplanar Waveguide (CPWG)**, backed by a continuous bottom ground plane.
The characteristic impedance $Z_0$ is computed via conformal mapping:
$$Z_0 = \frac{60\pi}{\sqrt{\varepsilon_{eff}}} \left[ \frac{K(k)}{K(k')} + \frac{K(k_1)}{K(k_1')} \right]^{-1}$$

Where:
$$k = \frac{w}{w + 2s}, \quad k' = \sqrt{1 - k^2}$$
$$k_1 = \frac{\tanh(\pi w / 4h)}{\tanh(\pi (w + 2s) / 4h)}, \quad k_1' = \sqrt{1 - k_1^2}$$
$$\varepsilon_{eff} = 1 + \frac{\varepsilon_r - 1}{2} \frac{K(k')K(k_1)}{K(k)K(k_1')}$$
$$\text{Propagation Delay } t_{pd} = \frac{\sqrt{\varepsilon_{eff}}}{c_0}, \quad v_p = \frac{c_0}{\sqrt{\varepsilon_{eff}}}$$

**Standard FR4 Values ($h = 1.60\text{ mm}, \varepsilon_r = 4.40, s = 0.40\text{ mm}$):**
* $w = \mathbf{1.87\text{ mm}}$ for $Z_0 = 50.0\,\Omega$
* $\varepsilon_{eff} = \mathbf{2.88}$
* $v_p = 1.767 \times 10^8\text{ m/s}$, $t_{pd} = 5.66\text{ ps/mm}$

### Closed-Form Passive Circuit Synthesis
* **Symmetric Pi-Attenuators**:
  $$K = 10^{\text{Atten}_{\text{dB}} / 20}$$
  $$R_{\text{shunt}} = Z_0 \frac{K + 1}{K - 1}, \quad R_{\text{series}} = Z_0 \frac{K^2 - 1}{2K}$$
* **Series LC Tank Bandpass Filters**:
  $$f_0 = \frac{1}{2\pi \sqrt{L C}} \implies C = \frac{1}{(2\pi f_0)^2 L}$$
* **Butterworth 3-Pole Low-Pass Filters**:
  $$C_1 = C_2 = \frac{1}{2\pi f_c Z_0}, \quad L_1 = \frac{2 Z_0}{2\pi f_c}$$
* **Wideband RF Bias Tees**:
  $$X_L = 2\pi f_0 L \gg Z_0 \quad (L = 100\text{ nH}), \quad X_C = \frac{1}{2\pi f_0 C} \ll Z_0 \quad (C = 100\text{ pF})$$

---

## Execution Commands

The full stage-by-stage CLI reference (Tasks 1–9, Windows + Linux/WSL) is maintained **only** in [AGENTS.md](AGENTS.md) §4. Quick form:

```bash
# Full pipeline (Linux / WSL):
./rf-suite/bin/rf-run python3 -m agent.workflow --desc "<circuit description>"

# Windows:
rf-suite\bin\rf-run.bat python -m agent.workflow --desc "<circuit description>"

# Individual stages: append --stages <schematic|pcb|render|cad|em|qucs|charts|gerbers|report>
```
