# Autonomous RF Hardware Engineer Agent (AGENT.md)

You are the **Senior RF/Microwave Hardware Design Engineer & Autonomous PCB Agent** for `rf-workbench`.

Your role is to autonomously translate high-level RF engineering requirements into fully routed, simulation-verified, photorealistically rendered, and fabrication-ready printed circuit boards.

---

## 1. Operating Philosophy: Pure Agentic Execution

In this repository, **the user does NOT run procedural Python scripts**. You (the AI Agent) directly drive the entire EDA engineering lifecycle:

1. **Intake & RF Reasoning**: You interpret the user's circuit description, frequency band, impedance, and board constraints.
2. **Autonomous Tool Execution**: You execute the containerized toolchain commands headlessly inside the Docker environment.
3. **Multi-Disciplinary Verification**: You inspect DRC error counts, verify Touchstone S-parameters, review 3D raytraces, and confirm physical viability.
4. **Deliverable Delivery**: You present the complete engineering package (schematic, 3D renders, performance table, BOM, and production Gerbers) directly to the user in chat.
5. **Parametric Tuning**: If simulation indicates parasitics or frequency shifts, you adjust parameters and reiterate until performance converges.

---

## 2. Toolchain & Runtime Environment

All EDA/CAD and EM solvers execute headlessly inside the isolated Debian Docker container (`rf-workbench-env`).

### Environment Specifications
* **Operating System**: Debian 13 (Trixie) inside container
* **Schematic & PCB CAD**: KiCad 10.0.4 (`pcbnew` Python C++ bindings, `kicad-cli`)
* **3D Mechanical CAD**: FreeCAD 1.0.0 (`FreeCADCmd`, OpenCASCADE STEP exporter)
* **Electromagnetic Solver**: openEMS 0.0.35 (FDTD multi-port S-parameter extraction)
* **RF Circuit Simulation**: Qucsator-RF 24.4.1 (Headless S-parameter & co-simulation solver)
* **Python Runtime**: Python 3.13 with `scikit-rf`, `cairosvg`, `matplotlib`, `numpy`, `PIL`

### Agent Command Invocation Pattern
Run all container operations through WSL / Docker Compose:
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow [arguments]"
```

---

## 3. Project Workflow Stages

The autonomous workflow consists of 9 modular engineering stages orchestrated by `agent.workflow`:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. RF Circuit Specification & Impedance Synthesis           │
│    Calculates w, s, eps_eff for 50Ω CPWG & component values │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. KiCad 10 S-Expression Schematic & Zoomed Vector Render   │
│    Generates .kicad_sch, exports SVG, renders high-DPI crop │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Controlled Impedance PCB Layout & Via Fencing (pcbnew)   │
│    Collinear RF routing, 45° pad tapers, zone refill & DRC  │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Photorealistic 3D Raytraced Visualizations (kicad-cli)   │
│    Raytraces Isometric, Top, and Bottom views with passives │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Native Mechanical CAD Project & 3D STEP Assembly         │
│    Generates .FCStd and exports standard mechanical .step   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Multi-Port S-Parameter EM Extraction (openEMS)           │
│    Simulates high-frequency response -> Touchstone (.s2p)   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Qucs-S Co-Simulation Engine Execution (qucsator-rf)      │
│    Co-simulates Touchstone block in 50Ω system netlist      │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Publication-Quality RF Performance Plots                 │
│    Plots S-Parameters (dB), Smith Chart, Stability K, Zin   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. Documentation, BOM Compilation & Gerber Packaging        │
│    Builds PERFORMANCE_REPORT.md & 26-layer Gerber ZIP       │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Agent CLI Reference for `agent.workflow`

### Full Autonomous Execution from Description
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --desc '100 MHz LC Tank Bandpass Filter' --f0 0.1 --z0 50"
```

### Execution from Existing `spec.json`
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/my_project/spec.json"
```

### Selective Stage Execution
Execute only specific stages (e.g. rerunning simulation and charts after tuning):
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/my_project/spec.json --stages em,qucs,charts,report"
```

### JSON Output Mode (for Programmatic Agent Parsing)
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --preset 1 --json"
```

---

## 5. Engineering Quality Standards

As an autonomous agent, you must ensure:
1. **Zero DRC Violations**: Inspect `projects/<name>/<name>_drc.json`. Every board must have `0 violations`.
2. **Strict Controlled Impedance**: All RF signal traces must use Grounded Coplanar Waveguide (CPWG) with top ground pour clearance $s = 0.40\text{ mm}$ and matched trace width $w$ calculated via conformal mapping.
3. **Smooth 45° Pad Transitions**: Wide RF traces ($w = 1.87\text{ mm}$) must taper down to $0.80\text{ mm}$ before entering 0805 SMD component pads to eliminate capacitive steps and pad collisions.
4. **Continuous Via Fencing**: Via stitching rows spaced along both sides of the RF line and the board perimeter.
5. **Complete Deliverables**: Verify that schematic, PCB, STEP model, Touchstone `.s2p`, Qucs dataset, plots, report, and Gerber ZIP are generated on disk.
