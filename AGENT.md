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

### 1.1 Immediate Execution Policy (Zero Codebase Browsing Rule)
> [!CRITICAL]
> **WHEN A USER ASSIGNS A CIRCUIT DESIGN OR PCB CREATION WORKFLOW:**
> 1. **DO NOT BROWSE OR ANALYZE CODEBASE FILES**: Do NOT run `find_by_name`, `grep_search`, `list_dir`, or `view_file` on `agent/*.py` or other repository source files.
> 2. **DO NOT ENTER PLANNING MODE**: Do NOT create `implementation_plan.md` or ask architectural planning questions. The workflow architecture is already established and fully automated.
> 3. **DO NOT WRITE SCRATCH TEST SCRIPTS**: Do NOT write temporary Python scripts to test or research circuit algorithms.
> 4. **JUMP STRAIGHT INTO EXECUTION ON TURN 1**: Immediately launch **Task 1 (Schematic)** using the standard Docker execution command:
>    ```bash
>    wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --desc '<circuit description>' --stages schematic"
>    ```
>    The `agent.workflow` engine automatically parses the description, generates the mathematical circuit specifications, selects footprints, routes CPWG lines, and exports the high-DPI zoomed schematic render.

### 1.2 Default Hardware & PCB Architecture Baseline
> [!IMPORTANT]
> **If the user does not describe the PCB in detail, ALWAYS assume the standard baseline:**
> * **Substrate Material**: Standard **FR4** ($\varepsilon_r = 4.40$, $\tan\delta = 0.02$).
> * **Layer Stackup**: **2-Layer PCB** (`F.Cu` top RF path with coplanar ground pour, `B.Cu` solid reference ground plane).
> * **Substrate Thickness**: **1.60 mm** ($h = 1.60\text{ mm}$).
> * **Copper Thickness**: **1 oz** ($35\,\mu\text{m}$ / $0.035\text{ mm}$).
> * **RF Connectors**: Small 50Ω SMA Edge Mount Connectors from **Samtec** (`SMA-J-P-H-ST-EM1`, footprint `Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount`, `SMA_IN` at port 1, `SMA_OUT` at port 2). Do NOT use Amphenol connectors or pin headers for RF ports.
> * **Transmission Line**: **50.0Ω Grounded Coplanar Waveguide (CPWG)**:
>   - Signal trace width: $w = 1.87\text{ mm}$
>   - Ground clearance gap: $s = 0.40\text{ mm}$
>   - Effective dielectric constant: $\varepsilon_{eff} = 2.88$
>   - Phase velocity: $v_p = 1.767 \times 10^8\text{ m/s}$ ($t_{pd} = 5.66\text{ ps/mm}$)
> * **SMD Passives & Inductor Sourcing**:
>   - **Inductor Sourcing Hierarchy**: Default to **0603** footprint packages (`Inductor_SMD:L_0603_1608Metric`) from **Coilcraft** (0603CS / 0603HP wirewound) or **Murata** (LQW18AN / LQG18H). If specific values are not available from these vendors in 0603 (> 470 nH up to 2.2 µH), fall back to **0805** (`Inductor_SMD:L_0805_2012Metric`), or **1206** (`Inductor_SMD:L_1206_3216Metric`) for > 2.2 µH. **Do NOT prefer smaller components (e.g. 0402, 0201) unless strictly necessary**.
>   - **Resistors & Capacitors**: Standard **0805 Imperial / 2012 Metric** footprint packages with $45^\circ$ neckdown tapers ($1.87\text{ mm} \rightarrow 0.80\text{ mm}$).
> * **1-Port Circuits (Input-Only Circuits — Loads, Terminations, Standards)**:
>   - **Single Port Only (`num_ports = 1`, `J1` / `SMA_IN`)**: When the user requests a circuit where only the input side exists (e.g. "50 ohm Load circuit for calibration", "50 ohm termination", "SOLT calibration load/short/open"):
>     - Place **ONLY** the input connector `J1` on the left edge. **NEVER place an output connector `J2`** or route an output line.
>     - **NEVER replicate the circuit on the output side**: The input CPWG trace terminates directly into the shunt load (e.g. $R_1 \parallel R_2 = 50.0\,\Omega$ to ground). Do NOT create symmetrical output passives (no R3/R4).
>     - **Compact Board**: Use a compact form factor ($20.0\text{ mm} \times 16.0\text{ mm}$) with solid ground pour and perimeter via stitching filling the remaining board area.
>     - **1-Port Metrics**: Characterize Return Loss ($S_{11}$) and VSWR. Do NOT compute, plot, or report $S_{21}$ or $S_{22}$.
> * **Shielding**: Continuous ground via fencing rows ($0.4\text{ mm}$ drill, $0.8\text{ mm}$ pad) and perimeter stitching.

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

## 6. Human-in-the-Loop Stage Review Protocol & Interactive Popup Modals

To maintain total transparency, stability, and engineering rigor, the agent follows a strict **Interactive Popup Modal Review Protocol** (`ask_question`):

### Mandatory Rules: Interactive Modal Popups with Native Image Display
> [!IMPORTANT]
> **MANDATORY POPUP CONFIRMATION VIA `ask_question`**:
> User review confirmations between stages MUST be triggered as **interactive popup modals** using `ask_question`.
> To guarantee that visual renders (`schematic_zoomed.png`, `iso_render.png`, `top_render.png`, `sparam_plot.png`, etc.) are always 100% visible in the chat alongside the popup dialog:
> 1. **Never emit an empty message body**: When calling `ask_question`, you MUST write out the full visible chat message containing the embedded image, deliverables table, and engineering verification.
> 2. **Single Native Markdown Image Display**: Embed each image ONCE using standard Markdown syntax directly in the chat response:
>    ```markdown
>    ![<Description>](file:///<appDataDir>/brain/<conversation-id>/<render_name>.png)
>    ```
>    *(Ensure Windows backslashes are converted to forward slashes in the `file:///` URI).*
> 3. **Copy to Artifacts Directory**: Always copy generated `.png` assets from `projects/<name>/renders/` (or `charts/`) to `<appDataDir>\brain\<conversation-id>\` using PowerShell `Copy-Item` before embedding.
> 4. **Display Deliverables Table & DRC Check**: List file paths, sizes (KB), and 0 DRC violations.
> 5. **Invoke `ask_question` in the SAME Turn**: Provide the 3 selectable options in the modal dialog:
>    - **Option 1 (Proceed)**: `(Recommended) <Artifact> looks good, let's move to <Next Task>.` (e.g., *"Schematic looks good, let's move to PCB design."*)
>    - **Option 2 (Reiterate / Adjust)**: `I'd like to adjust <parameters/components> to reiterate <Task>.` (e.g., *"I'd like to adjust component values or circuit topology to reiterate the schematic."*)
>    - **Option 3 (Pause / Stop)**: `Pause execution here so I can review the deliverables and think through next steps.`

### Stage-by-Stage Review & Context-Aware Prompt Mapping

| Task # | Stage | Visual Deliverable In Chat | Option 1 (Proceed) | Option 2 (Reiterate / Adjust) |
|---|---|---|---|---|
| **Task 1** | `schematic` | Zoomed KiCad 10 schematic crop | `(Recommended) Schematic looks good, let's move to PCB design.` | `I'd like to adjust component values or circuit topology to reiterate the schematic.` |
| **Task 2** | `pcb` | 0-error DRC report & layout metrics | `(Recommended) PCB layout & DRC look good, let's move to 3D raytracing.` | `I'd like to modify board dimensions, clearance, or trace routing for the PCB.` |
| **Task 3** | `render` | 3D Raytraced Isometric & Top views | `(Recommended) 3D renders look great, let's generate mechanical CAD & STEP assembly.` | `I'd like to adjust component placement or raytracing angles and re-render.` |
| **Task 4** | `cad` | STEP assembly & FreeCAD status | `(Recommended) Mechanical STEP assembly looks solid, let's run openEMS simulation.` | `I'd like to adjust mounting holes or enclosure constraints for mechanical CAD.` |
| **Task 5** | `em` | Touchstone 201-point sweep & S-params | `(Recommended) Touchstone S-parameters look good, let's run Qucs co-simulation.` | `I'd like to modify frequency sweep range or substrate parameters for EM simulation.` |
| **Task 6** | `qucs` | Qucsator convergence & netlist status | `(Recommended) Qucs simulation converged, let's plot RF performance charts.` | `I'd like to adjust termination impedance or simulation parameters in Qucs.` |
| **Task 7** | `charts` | Matplotlib S21/S11, Smith, Zin, K charts | `(Recommended) RF charts & response look great, let's package production Gerbers.` | `I'd like to tune circuit parameters or chart scales to optimize RF response.` |
| **Task 8** | `gerbers` | 26-layer Gerber manifest & drill file | `(Recommended) Gerbers packaged, let's generate the final performance report & BOM.` | `I'd like to adjust layer stackup or manufacturing rules before finalizing Gerbers.` |
| **Task 9** | `report` | Markdown report table & complete BOM | `(Recommended) Performance report & BOM look great, engineering package complete.` | `I'd like to update project specifications, margins, or documentation notes.` |

> [!NOTE]
> **Option 3** is always: `"Pause execution here so I can review the deliverables and think through next steps."`

### Handling User Response
* **User chooses Option 1 (Proceed)**: Proceed immediately to execute the next task in the workflow.
* **User chooses Option 2 (Reiterate / Adjust)**:
  1. Receive user suggestions (e.g., "Increase capacitance from 26pF to 33pF", "Widen board by 5mm", "Change center frequency to 144 MHz").
  2. Update `projects/<name>/spec.json`.
  3. Re-run the current task (and any necessary upstream tasks) using `--stages <stage>`.
  4. Immediately display the updated visual render in the chat and re-prompt for confirmation.
* **User chooses Option 3 (Pause / Stop)**:
  1. Halt pipeline execution immediately.
  2. Confirm that all artifacts generated up to the current stage are safely preserved in `projects/<name>/`.
  3. Provide instructions on how to resume when ready.



