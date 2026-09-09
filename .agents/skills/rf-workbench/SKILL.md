---
name: rf-workbench
description: >-
  Autonomous RF/Microwave hardware engineer and PCB design suite. Use whenever the user asks
  to design, synthesize, simulate, route, render, or fabricate RF circuits, printed circuit boards,
  attenuators, filters, bias tees, Wilkinson dividers, or CPWG transmission lines in KiCad, FreeCAD,
  openEMS, and Qucs.
---

# Autonomous RF Hardware Engineer Skill

## Default Hardware Baseline (Standard Assumptions)
> [!IMPORTANT]
> **If the user does not describe the PCB in detail, ALWAYS assume:**
> * **Material**: Standard **FR4** ($\varepsilon_r = 4.40$, $\tan\delta = 0.02$).
> * **Layers**: **2-Layer PCB** (`F.Cu` top RF path + ground pour, `B.Cu` solid reference ground plane).
> * **Thickness**: **1.60 mm** ($h = 1.60\text{ mm}$).
> * **Copper Weight**: **1 oz** ($35\,\mu\text{m}$ / $0.035\text{ mm}$).
> * **Connectors**: Small 50Ω SMA Edge Mount Connectors from **Samtec** (`SMA-J-P-H-ST-EM1`, footprint `Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount`, `SMA_IN` at port 1, `SMA_OUT` at port 2). Do NOT use Amphenol connectors or pin headers for RF ports.
> * **Transmission Line**: **50.0Ω Grounded Coplanar Waveguide (CPWG)** ($w = 1.87\text{ mm}$, $s = 0.40\text{ mm}$, $\varepsilon_{eff} = 2.88$, $v_p = 1.767 \times 10^8\text{ m/s}$).
> * **Inductor Sourcing & Footprint Rule**:
>   - **Default**: **0603** footprint packages (`Inductor_SMD:L_0603_1608Metric`) from **Coilcraft** (0603CS / 0603HP wirewound) or **Murata** (LQW18AN / LQG18H).
>   - **Fallback**: If specific values are not available from these vendors in 0603 (> 470 nH up to 2.2 µH), fall back to **0805** (`Inductor_SMD:L_0805_2012Metric`), or **1206** (`Inductor_SMD:L_1206_3216Metric`) for > 2.2 µH.
>   - **Constraint**: **Do NOT prefer smaller components (e.g. 0402, 0201) unless strictly necessary**.
> * **1-Port Circuits (Input-Only Circuits — Loads, Terminations, Standards)**:
>   - **Single Port Only (`num_ports = 1`, `J1` / `SMA_IN`)**: When the user asks for a circuit where only the input side exists (e.g. "50 ohm Load circuit for calibration", "50 ohm termination", "SOLT calibration load/short/open"):
>     - Place **ONLY** the input connector `J1` on the left edge. **NEVER place an output connector `J2`** or route an output line.
>     - **NEVER replicate the circuit on the output side**: The input trace terminates directly into the shunt load (e.g. $R_1 \parallel R_2 = 50.0\,\Omega$). Do NOT duplicate components (e.g., no R3/R4).
>     - **Compact Board**: Use a compact form factor ($20.0\text{ mm} \times 16.0\text{ mm}$) with solid ground pour and via stitching across the unused area.
>     - **1-Port Metrics**: Evaluate Return Loss ($S_{11}$) and VSWR. Do NOT compute, plot, or report $S_{21}$ / $S_{22}$.

## Immediate Execution Policy (Zero Codebase Browsing Rule)
> [!CRITICAL]
> **WHEN A USER ASSIGNS A CIRCUIT DESIGN OR PCB CREATION WORKFLOW:**
> 1. **DO NOT BROWSE OR ANALYZE CODEBASE FILES**: Do NOT run `find_by_name`, `grep_search`, `list_dir`, or `view_file` on `agent/*.py` or other repository source files.
> 2. **DO NOT ENTER PLANNING MODE**: Do NOT create `implementation_plan.md` or ask architectural planning questions. The workflow architecture is already established and fully automated.
> 3. **DO NOT WRITE SCRATCH TEST SCRIPTS**: Do NOT write temporary Python scripts to test or research circuit algorithms.
> 4. **JUMP STRAIGHT INTO EXECUTION ON TURN 1**: Immediately launch **Task 1 (Schematic)** using the standard execution command:
>    ```bash
>    # If running via the external RF container environment (rf-suite):
>    wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --desc '<circuit description>' --stages schematic"
>    # Or directly in a Python RF runtime environment:
>    python3 -m agent.workflow --desc '<circuit description>' --stages schematic
>    ```
>    The `agent.workflow` engine automatically parses the description, generates the mathematical circuit specifications, selects footprints, routes CPWG lines, and exports the high-DPI zoomed schematic render.

## Interactive Popup Review Protocol (`ask_question`)
> [!IMPORTANT]
> **MANDATORY POPUP CONFIRMATION WITH NATIVE IMAGE DISPLAY**:
> User interaction between stages MUST be presented as **interactive popup modals** using `ask_question`.
> To guarantee that the schematic and 3D renders are always 100% visible in the chat alongside the popup:
> 1. **Never emit an empty message body**: When calling `ask_question`, you MUST provide the full visible chat message containing the embedded image, deliverables table, and engineering verification.
> 2. **Single Native Markdown Image Display**: Embed each image ONCE using standard Markdown syntax directly in the chat message:
>    ```markdown
>    ![<Description>](file:///<appDataDir>/brain/<conversation-id>/<render_name>.png)
>    ```
>    *(Ensure Windows backslashes are converted to forward slashes in the `file:///` URI).*
> 3. **Copy to Artifacts Directory**: Always copy generated `.png` assets from `projects/<name>/renders/` (or `charts/`) to `<appDataDir>\brain\<conversation-id>\` using PowerShell `Copy-Item` before embedding.
> 4. **Display Deliverables Table & DRC Check**: List file paths, sizes, and 0 DRC violations.
> 5. **Invoke `ask_question` in the SAME Turn**: Trigger the popup modal with context-specific options:
>    - **Option 1 (Proceed)**: `(Recommended) <Artifact> looks good, let's move to <Next Task>.` (e.g., *"Schematic looks good, let's move to PCB design."*)
>    - **Option 2 (Reiterate / Adjust)**: `I'd like to adjust <parameters/components> to reiterate <Task>.` (e.g., *"I'd like to adjust component values or circuit topology to reiterate the schematic."*)
>    - **Option 3 (Pause / Stop)**: `Pause execution here so I can review the deliverables and think through next steps.`

If the user requests reiteration, update `projects/<name>/spec.json` and re-run the specific stage using `--stages <stage>`.




## Execution Commands

You can execute the workflow stages either directly in a Python RF runtime environment (`python3 -m agent.workflow [args]`) or via the external RF container environment (`rf-suite`):

### 1. Stage-by-Stage Interactive Execution (Standard Flow)
Run each stage individually, reviewing deliverables with the user between stages:
```bash
# Task 1: Schematic & Zoomed Crop
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --desc '<circuit description>' --f0 <freq> --stages schematic"
# Direct: python3 -m agent.workflow --desc '<circuit description>' --f0 <freq> --stages schematic

# Task 2: PCB Layout & DRC
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages pcb"
# Direct: python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages pcb

# Task 3: 3D Raytrace Renders
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages render"
# Direct: python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages render

# Task 4: FreeCAD & STEP CAD
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages cad"
# Direct: python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages cad

# Task 5: openEMS EM Simulation -> Touchstone .s2p / .s1p
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages em"
# Direct: python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages em

# Task 6: Qucs-S Co-Simulation
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages qucs"
# Direct: python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages qucs

# Task 7: RF Performance Charts
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages charts"
# Direct: python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages charts

# Task 8: Production Gerber ZIP
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages gerbers"
# Direct: python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages gerbers

# Task 9: Performance Report & BOM
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages report"
# Direct: python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages report
```

### 2. Full Batch Pipeline Execution (Unattended)
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-suite/docker-compose.yml exec -T -w /workspace/rf-workbench rf-suite python3 -m agent.workflow --desc '<circuit description>' --f0 <center_freq_ghz> --z0 50"
# Direct: python3 -m agent.workflow --desc '<circuit description>' --f0 <center_freq_ghz> --z0 50
```

## Quality Assurance Checklist
1. **DRC Validation**: Verify `projects/<name>/<name>_drc.json` contains `0 violations` and `0 warnings`.
2. **Impedance Matching**: Ensure transmission lines adhere to 50Ω Grounded Coplanar Waveguide (CPWG) dimensions ($w = 1.87\text{ mm}$, $s = 0.40\text{ mm}$ on 1.6mm FR4).
3. **Artifact Integrity**: Check that all deliverables exist in `projects/<name>/`:
   - `renders/schematic_zoomed.png` (Task 1)
   - `<name>_drc.json` (Task 2)
   - `renders/iso_render.png`, `renders/top_render.png`, `renders/bottom_render.png` (Task 3)
   - `cad/<name>.step`, `cad/<name>.FCStd` (Task 4)
   - `simulation/<name>.s2p` (Task 5)
   - `simulation/<name>.dat` (Task 6)
   - `charts/sparam_plot.png`, `charts/smith_chart.png` (Task 7)
   - `gerbers_<name>.zip` (Task 8)
   - `PERFORMANCE_REPORT.md` (Task 9)
