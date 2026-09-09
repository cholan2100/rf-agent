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
│    Simulates high-frequency response -> Touchstone (.s2p)   │
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

## 4. Agent CLI Reference for `agent.workflow`

### Stage-by-Stage Modular Execution
Execute stages individually to allow human review at each step:
```bash
# Task 1: Schematic Synthesis & Zoomed Crop
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages schematic"

# Task 2: Controlled Impedance PCB Layout & DRC
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages pcb"

# Task 3: 3D Raytracing (Iso, Top, Bottom)
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages render"

# Task 4: Mechanical CAD & 3D STEP Assembly
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages cad"

# Task 5: openEMS EM Simulation -> Touchstone .s2p
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages em"

# Task 6: Qucsator Linear Co-Simulation
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages qucs"

# Task 7: RF Performance Charts (S-Params, Smith Chart, Stability, Zin)
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages charts"

# Task 8: Production Gerber & Drill ZIP Packaging
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages gerbers"

# Task 9: Performance Documentation & BOM
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages report"
```

### Full Autonomous Pipeline Execution
```bash
# From natural language description
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --desc '100 MHz LC Tank Bandpass Filter' --f0 0.1 --z0 50"

# From existing spec.json
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json"

# Preset execution (1: 10dB Attenuator, 2: 2.4GHz Filter, 3: Wilkinson)
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --preset 1"
```

---

## 5. Engineering Quality Standards

As an autonomous agent, you must ensure:
1. **Zero DRC Violations**: Inspect `projects/<name>/<name>_drc.json`. Every board must have `0 violations` and `0 warnings`.
2. **Strict Controlled Impedance**: All RF signal traces must use Grounded Coplanar Waveguide (CPWG) with top ground pour clearance $s = 0.40\text{ mm}$ and matched trace width $w$ calculated via conformal mapping.
3. **Smooth 45° Pad Transitions**: Wide RF traces ($w = 1.87\text{ mm}$) must taper down to $0.80\text{ mm}$ before entering 0805 SMD component pads to eliminate capacitive steps and pad collisions.
4. **Continuous Via Fencing**: Via stitching rows spaced along both sides of the RF line and the board perimeter.
5. **Complete Deliverables**: Verify that schematic, PCB, STEP model, Touchstone `.s2p`, Qucs dataset, plots, report, and Gerber ZIP are generated on disk.

---

## 6. Human-in-the-Loop Stage Review Protocol & Immediate Chat Visualization

To maintain total transparency and engineering rigor, the agent follows a strict **Human-in-the-Loop Gating & Chat Visualization Protocol** during execution:

### Mandatory Rules: Immediate Inline Chat Rendering & Stage Gating
1. **Single Native Markdown Image Display**: Never just state that renders are saved on disk or output only file links. Immediately upon completing any stage that produces visual assets (`schematic_zoomed.png`, `iso_render.png`, `top_render.png`, `bottom_render.png`, `sparam_plot.png`, `smith_chart.png`, etc.):
   - **Artifact Directory Sync**: Copy the generated `.png` files to the conversation artifact directory `<appDataDir>\brain\<conversation-id>\`.
   - **Native Markdown Embed (Single)**: Embed each image ONCE using standard Markdown syntax directly in the chat response:
     ```markdown
     ![Zoomed Schematic](file:///<artifact_path>/schematic_zoomed.png)
     ```
   - **No Redundant HTML Iframe Embeds**: Do NOT generate temporary review HTML files (`review_renders.html`) or `<agent-embed>` tags. Native Markdown image tags render cleanly, borderless, and at native resolution directly in the chat timeline without duplicate display or iframe scrollbars.
   - **No Empty Tool Turns**: **NEVER** call `ask_question` with empty message text or in an isolated step. The chat response must contain the embedded visual render(s), deliverables table, and engineering health check directly above the interactive question prompt.
2. **Never Advance Unattended**: Never execute subsequent stages automatically without explicit human confirmation.
3. **Interactive Handover**: In each stage review turn, present:
   - The embedded visual render(s) rendered directly in the chat window.
   - A deliverables breakdown table (file paths, sizes, metrics).
   - An engineering integrity check (DRC 0 errors, CPWG impedance 50Ω, Pass/Fail tolerances).
   - The interactive 3-option prompt via `ask_question`.


### Stage-by-Stage Review Deliverables Mapping

| Task # | Stage Name | Deliverable Files | Immediate Chat Visual Assets | Review Focus |
|---|---|---|---|---|
| **Task 1** | `schematic` | `<name>.kicad_sch`<br>`renders/schematic_zoomed.png` | Zoomed high-DPI schematic crop rendered inline in chat | Circuit topology, component values, reference designators, 50Ω ports |
| **Task 2** | `pcb` | `<name>.kicad_pcb`<br>`<name>_drc.json` | Headless DRC report summary (0 errors, 0 warnings) | CPWG trace width ($w$), gap ($s$), 45° pad tapers, via fencing rows |
| **Task 3** | `render` | `renders/iso_render.png`<br>`renders/top_render.png`<br>`renders/bottom_render.png` | Photorealistic 3D Raytraced Isometric, Top, and Bottom views in chat | SMD solder pad alignment, connector clearance, ground stitching aesthetics |
| **Task 4** | `cad` | `cad/<name>.step`<br>`cad/<name>.FCStd` | STEP assembly file size and FreeCAD geometry status | Enclosure fitment, board edge chamfers, M2 mounting hole placement |
| **Task 5** | `em` | `simulation/<name>.s2p`<br>`simulation/<name>_openems.m` | Touchstone frequency range and 201-point sweep summary | S-parameter passivity, causality, port reference impedance (50Ω) |
| **Task 6** | `qucs` | `simulation/<name>_qucs.sch`<br>`simulation/<name>.net`<br>`simulation/<name>.dat` | Qucsator co-simulation convergence & netlist status | 50Ω system termination, S-parameter block interconnection |
| **Task 7** | `charts` | `charts/sparam_plot.png`<br>`charts/smith_chart.png`<br>`charts/stability_plot.png`<br>`charts/impedance_plot.png` | Matplotlib 300 DPI plots displayed inline: S21/S11, Smith chart, Stability K, Zin | Insertion loss at $f_0$, Return loss margin ($<-15$ dB), passband ripple |
| **Task 8** | `gerbers` | `gerbers_<name>.zip` | Gerber file manifest & 26-layer verification | Complete production layers: copper, mask, silkscreen, paste, drill (.drl) |
| **Task 9** | `report` | `PERFORMANCE_REPORT.md` | Full performance summary markdown table and Bill of Materials | Spec vs Simulated delta, margin flags, component sourcing table |

### Handling User Response
* **User chooses Option 1 (Satisfied)**: Proceed to execute the next task in the workflow.
* **User chooses Option 2 (Reiterate / Adjust)**:
  1. Receive user suggestions (e.g., "Increase capacitance from 33pF to 47pF", "Widen board by 5mm", "Shift center frequency to 144 MHz").
  2. Update `projects/<name>/spec.json`.
  3. Re-run the current task (and any necessary upstream tasks) using `--stages <stage>`.
  4. Immediately display the updated visual render in the chat and re-prompt for confirmation.
* **User chooses Option 3 (Stop / Pause)**:
  1. Halt pipeline execution immediately.
  2. Confirm that all artifacts generated up to the current stage are safely preserved in `projects/<name>/`.
  3. Provide instructions on how to resume when ready.


