# RF Workbench

[![KiCad](https://img.shields.io/badge/KiCad-10.0.4-314CB0?logo=kicad&logoColor=white)](https://kicad.org/)
[![FreeCAD](https://img.shields.io/badge/FreeCAD-1.0.0-CB333B?logo=freecad&logoColor=white)](https://www.freecad.org/)
[![openEMS](https://img.shields.io/badge/openEMS-v0.37.0--rc2-00599C)](https://openems.de/)
[![Qucs-S](https://img.shields.io/badge/Qucs--S-24.4.1-green)](https://ra3xdh.github.io/)
[![ngspice](https://img.shields.io/badge/ngspice-44.2-blue)](https://ngspice.sourceforge.io/)
[![Python](https://img.shields.io/badge/Python-3.13.5-3776AB?logo=python&logoColor=white)](https://www.python.org/)

An autonomous AI RF/Microwave hardware engineering engine and PCB design suite. `rf-workbench` enables AI coding agents and human engineers to autonomously synthesize schematics, route controlled-impedance coplanar waveguides, perform headless DRC verification, execute 3D electromagnetic FDTD simulations, and generate production-ready Gerber archives and raytraced 3D visualizations.

---

## Key Capabilities

- **Autonomous AI Agent Native**: Orchestrated by `agent.workflow` with programmatic KiCad (`pcbnew`), FreeCAD, openEMS, and Qucsator interfaces for complete headless hardware design.
- **Controlled-Impedance Synthesis**: Grounded Coplanar Waveguide (CPWG) synthesis with closed-form conformal mapping equations for 50Ω transmission lines, 45° neckdown tapers, and ground via fences.
- **Multi-Port & 1-Port Support**: Full support for 2-port circuits (filters, attenuators, power dividers) and dedicated 1-port termination/calibration standards (loads, shorts, opens) with single-ended Return Loss ($S_{11}$) and VSWR verification.
- **Headless Design Rule Checks (DRC)**: Automated zero-tolerance DRC audits verifying 0 violations and 0 warnings prior to fabrication export.
- **Photorealistic Raytraced 3D Renders**: Headless multi-angle board rendering (Isometric, Top, Bottom) with component 3D packages using KiCad 10's native CLI raytracer.
- **Full-Wave 3D EM & Circuit Co-Simulation**: openEMS FDTD solver extraction yielding Touchstone `.s2p` / `.s1p` matrices, co-simulated with Qucsator in a standard 50Ω system.
- **Fabrication Packaging**: Production-grade RS-274X Gerber & Excellon NC drill ZIP packages, vector SVGs, 3D STEP mechanical assemblies, and engineering markdown reports with BOMs.

---

## Tool Suite & Version Matrix

| Category | Tool / Package | Version | Scope & Capabilities |
| :--- | :--- | :--- | :--- |
| **PCB & EDA** | **KiCad 10** | 10.0.4 | Schematic capture, headless DRC verification, Gerber/drill generation |
| | **KiCad Python (`pcbnew`)** | 10.0.4 | Programmatic board synthesis, trace routing, via stitching, copper fills |
| | **KiCad 3D Raytracer** | 10.0.4 | Headless photorealistic raytraced 3D board rendering (`kicad-cli pcb render`) |
| | **RF-tools-KiCAD** | Latest | Automated via fence stitching, track rounding, solder mask expansion |
| **Electromagnetics** | **openEMS & CSXCAD** | v0.37.0-rc2 | 3D full-wave FDTD solver, multi-port S-parameter matrix extraction |
| | **AppCSXCAD** | v0.37.0 | Interactive 3D FDTD mesh, bounding box, and excitation port visualizer |
| **Circuit Simulation**| **Qucs-S** | 24.4.1 | Schematic capture, Touchstone `.sNp` co-simulation, AC/DC analysis |
| | **qucsator-rf** | 1.0.3 | High-speed RF solver fork, stability factors ($K, \mu$), noise parameters |
| | **ngspice** | 44.2 | SPICE engine for non-linear transistor DC bias and transient sweeps |
| **3D Mechanical CAD**| **FreeCAD** | 1.0.0 | Parametric CAD modeling, headless STEP/STL generation, clearance audits |
| | **FreeCAD-Microwave** | Master | Transmission line calculators (CPWG, microstrip), FreeCAD-to-openEMS export |
| **RF & Math Stack** | **scikit-rf (`skrf`)** | >=1.2 | S-parameter matrix operations, de-embedding, Smith charts, Touchstone I/O |
| | **Scientific Python** | `numpy`, `scipy`, `matplotlib`, `pandas` | Numerical computation, optimization, publication-quality RF plotting |
| | **Vector & Raster** | `pypdfium2`, `pillow`, `cairosvg` | High-DPI rasterization of schematic and layout artwork |

---


## Quick Start

## Workflow Architecture

The automated pipeline consists of 9 sequential, modular stages:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. KiCad 10 Schematic & Zoomed Vector Crop (schematic)      │
│    Generates .kicad_sch, exports SVG, renders high-DPI crop │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Controlled Impedance PCB Layout & DRC (pcb)              │
│    Collinear CPWG routing, 45° tapers, zone refill & DRC    │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Photorealistic 3D Raytraced Visualizations (render)      │
│    Raytraces Isometric, Top, and Bottom views with passives │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Native Mechanical CAD Project & 3D STEP Assembly (cad)   │
│    Generates .FCStd and exports standard mechanical .step   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Multi-Port S-Parameter EM Extraction (em)                │
│    Simulates high-frequency response -> Touchstone (.sNp)   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Qucs-S Co-Simulation Engine Execution (qucs)             │
│    Co-simulates Touchstone block in 50Ω system netlist      │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Publication-Quality RF Performance Plots (charts)        │
│    Plots S-Parameters (dB), Smith Chart, Stability K, Zin   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Production Gerber & Drill ZIP Packaging (gerbers)        │
│    Packages 26-layer Gerber and drill archive               │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. Comprehensive Performance Report & BOM (report)          │
│    Compiles PERFORMANCE_REPORT.md with margin analysis      │
└─────────────────────────────────────────────────────────────┘
```

---

## Runtime Environments

`rf-workbench` can be executed in two environments:

1. **Direct Python Runtime**: Any environment (Linux, WSL, macOS, or Windows) with Python 3.10+ and the required EDA/solver packages installed:
   ```bash
   pip install -r requirements.txt
   ```
2. **RF Suite Linux Container (`rf-suite`)**: The dedicated companion container environment (`../rf-suite` / `rf-linux-env`) provides pre-compiled KiCad 10, FreeCAD 1.0, openEMS, Qucsator-RF, and X11/noVNC desktop with zero host pollution:
   ```bash
   wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow [arguments]"
   ```

---

## CLI Usage

### Stage-by-Stage Modular Execution
Run individual stages to review deliverables interactively between steps:
```bash
# Task 1: Schematic Synthesis & Zoomed Crop
python3 -m agent.workflow --desc "50 ohm Load circuit for calibration" --stages schematic

# Task 2: Controlled Impedance PCB Layout & DRC
python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages pcb

# Task 3: 3D Raytracing (Iso, Top, Bottom)
python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages render

# Task 4: Mechanical CAD & 3D STEP Assembly
python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages cad

# Task 5: openEMS EM Simulation -> Touchstone .s2p / .s1p
python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages em

# Task 6: Qucs-S Co-Simulation
python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages qucs

# Task 7: RF Performance Charts
python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages charts

# Task 8: Production Gerber ZIP
python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages gerbers

# Task 9: Performance Documentation & BOM
python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages report
```

### Full Unattended Batch Execution
```bash
# From natural language description
python3 -m agent.workflow --desc "100 MHz LC Tank Bandpass Filter" --f0 0.1 --z0 50

# From existing spec.json
python3 -m agent.workflow --spec-file projects/<name>/spec.json

# Built-in presets (1: 10dB Attenuator, 2: 2.4GHz Filter, 3: Wilkinson)
python3 -m agent.workflow --preset 1
```

---

## Reference Example: Simple LED PCB

The repository includes an end-to-end automated manufacturing pipeline in `examples/simple_led/` demonstrating how hardware can be synthesized, verified, and exported headlessly.

<p align="center">
  <img src="examples/simple_led/renders/iso_render.png" alt="Simple LED PCB 3D Raytrace Render" width="700">
</p>

### Running the Example
```bash
python examples/simple_led/run_pipeline.py
```

---

## Project Structure

```
rf-workbench/
├── agent/                          # Autonomous RF workflow engine
│   ├── __init__.py
│   ├── workflow.py                 # Master 9-stage orchestrator
│   ├── spec.py                     # Circuit spec models, presets, RF math
│   ├── schematic_gen.py            # KiCad 10 schematic synthesis & SVG export
│   ├── pcb_gen.py                  # CPWG layout, 45° tapers, zone fill & DRC
│   ├── render_gen.py               # Headless raytraced 3D renders (Iso, Top, Bottom)
│   ├── cad_gen.py                  # FreeCAD parametric modeling & STEP assembly
│   ├── em_solver.py                # openEMS FDTD solver & Touchstone .sNp export
│   ├── qucs_runner.py              # Qucsator linear circuit co-simulation
│   ├── chart_gen.py                # S-parameters & Smith chart plotting
│   ├── gerber_gen.py               # RS-274X Gerber & NC drill ZIP packager
│   └── report_gen.py               # PERFORMANCE_REPORT.md & BOM generator
├── .agents/skills/rf-workbench/    # AI Agent skill definition (SKILL.md)
├── projects/                       # Generated design projects & deliverables
├── examples/                       # Automated reference examples
│   └── simple_led/                 # Automated reference manufacturing pipeline
├── tests/                          # Workflow unit tests & diagnostics
│   ├── test_workflow.py            # Headless workflow engine tests
│   └── verify_environment.py       # 14-point EDA/solver diagnostic suite
├── AGENT.md                        # Autonomous agent operating handbook
├── SKILLS.md                       # RF engineering skills catalog
├── requirements.txt                # Python RF & scientific dependencies
└── README.md
```

---

## Quality Assurance & Verification

Every design synthesized by `rf-workbench` is verified against strict RF engineering criteria:
- **0 DRC Violations**: Clearances, track widths, and zone connectivity audited via `kicad-cli`.
- **50Ω Impedance Matching**: CPWG dimensions verified with coplanar ground clearances ($w = 1.87\text{ mm}$, $s = 0.40\text{ mm}$ on 1.6mm FR4).
- **Component Sourcing**: Industry-standard high-Q RF SMD components (Samtec SMA edge-mount connectors, Coilcraft/Murata 0603 inductors).
- **1-Port Circuit Integrity**: True single-port architecture without phantom output paths or symmetric component duplication.

---

## License

This project is licensed under the [MIT License](LICENSE).

