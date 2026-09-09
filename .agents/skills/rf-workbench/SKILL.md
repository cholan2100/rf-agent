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
> * **Resistors & Capacitors**: Standard **0805 Imperial / 2012 Metric** footprint packages with $45^\circ$ neckdown tapers ($1.87\text{ mm} \rightarrow 0.80\text{ mm}$).

## Immediate Execution Policy (Zero Codebase Browsing Rule)
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

## Native Chat Handover & Render Protocol (100% Reliable Render Display)
> [!IMPORTANT]
> **DO NOT USE `ask_question` FOR STAGE REVIEWS**:
> Invoking the modal tool `ask_question` suppresses chat text and causes image renders to fail to display in the chat window. Always provide the stage review directly as visible chat text and end your turn without calling tools.

When executing an RF design project, **never execute stages in a silent uninterrupted batch unless explicitly requested**.
Immediately upon completing **each task**, you must:
1. **Copy Render(s) to Artifact Directory**:
   Copy all visual outputs (`schematic_zoomed.png`, `iso_render.png`, `top_render.png`, `sparam_plot.png`, etc.) from `d:\Workspace\rf\rf-workbench\projects\<name>\renders\` (or `charts\`) to `<appDataDir>\brain\<conversation-id>\` using PowerShell `Copy-Item`.
2. **Single Native Markdown Image Display**:
   Embed each image ONCE using standard Markdown image syntax directly in the chat response:
   ```markdown
   ![<Description>](file:///<appDataDir>/brain/<conversation-id>/<render_name>.png)
   ```
   *(Ensure Windows backslashes are converted to forward slashes in the `file:///` URI).*
   - Do NOT generate HTML review files (`review_renders.html`) or `<agent-embed>` iframe tags.
3. **Show Deliverables Table**: Display the relative paths, file sizes, and status of generated files.
4. **Engineering Integrity Check**: Verify DRC violations (0 errors, 0 warnings) and electrical specifications.
5. **Numbered Review Choices in Chat**: Provide context-specific review options tailored to the active stage:
   - `1. (Recommended) <Artifact> looks good, let's move to <Next Task>.` (e.g., *"Schematic looks good, let's move to PCB design."*)
   - `2. I'd like to adjust <parameters/components> to reiterate <Task>.` (e.g., *"I'd like to adjust component values or circuit topology to reiterate the schematic."*)
   - `3. Pause execution here so I can review the deliverables and think through next steps.`
6. **End Turn**: Stop calling tools. Prompt the user: *"Reply with **1** (or 'proceed') to continue to <Next Task>, or specify adjustments."*

If the user requests reiteration, update `projects/<name>/spec.json` and re-run the specific stage using `--stages <stage>`.




## Execution Commands

### 1. Stage-by-Stage Interactive Execution (Standard Flow)
Run each stage individually, reviewing deliverables with the user between stages:
```bash
# Task 1: Schematic & Zoomed Crop
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --desc '<circuit description>' --f0 <freq> --stages schematic"

# Task 2: PCB Layout & DRC
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages pcb"

# Task 3: 3D Raytrace Renders
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages render"

# Task 4: FreeCAD & STEP CAD
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages cad"

# Task 5: openEMS EM Simulation -> Touchstone .s2p
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages em"

# Task 6: Qucs-S Co-Simulation
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages qucs"

# Task 7: RF Performance Charts
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages charts"

# Task 8: Production Gerber ZIP
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages gerbers"

# Task 9: Performance Report & BOM
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages report"
```

### 2. Full Batch Pipeline Execution (Unattended)
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --desc '<circuit description>' --f0 <center_freq_ghz> --z0 50"
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
