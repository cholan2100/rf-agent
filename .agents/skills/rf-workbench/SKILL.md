---
name: rf-workbench
description: >-
  Autonomous RF/Microwave hardware engineer and PCB design suite. Use whenever the user asks
  to design, synthesize, simulate, route, render, or fabricate RF circuits, printed circuit boards,
  attenuators, filters, bias tees, Wilkinson dividers, or CPWG transmission lines in KiCad, FreeCAD,
  openEMS, and Qucs.
---

# Autonomous RF Hardware Engineer Skill

## Toolchain Architecture: Dependency on `rf-suite`
`rf-workbench` contains the AI design intellect, circuit specifications (`spec.py`), and layout synthesis algorithms. All heavy EDA/CAD and electromagnetic simulation solvers reside in the linked container environment `rf-suite` (`./rf-suite` Git submodule, pointing to `cholan2100/rf-suite`).

Autonomous agents invoke all solvers and Python engines headlessly through the standard cross-platform launchers in `rf-suite/bin/`:
- **Windows**: `rf-suite\bin\rf-run.bat <command>`
- **Linux / WSL**: `./rf-suite/bin/rf-run <command>`

---

## Turn 0: Mandatory Docker Readiness & Auto-Build Protocol
> [!CRITICAL]
> **BEFORE LAUNCHING ANY DESIGN WORKFLOW OR STAGE:**
> The AI Agent MUST test whether the `rf-suite` Docker environment is ready. If not, the Agent MUST build it first while keeping the user informed at every step.

### Docker Host Architecture Rule (Windows vs Linux)
> [!IMPORTANT]
> **Docker Daemon Environment**:
> * **On Windows**: Docker is by default located and managed inside the **WSL Debian** environment (`wsl -d Debian`). When running Docker commands directly on Windows, execute them via WSL: `wsl -d Debian bash -c "docker ..."`. The Windows batch scripts in `rf-suite\bin\` (`rf-run.bat`, `rf-bash.bat`, `rf-gui.bat`) automatically detect this and target the WSL Debian container environment.
> * **On Linux**: Docker is typically native and accessible directly in the standard system PATH (`docker ...`).

1. **Test Docker Readiness**:
   Check if the `rf-suite:latest` Docker image is present:
   ```bash
   # On Windows (Docker is in WSL Debian by default):
   wsl -d Debian bash -c "docker images -q rf-suite:latest"
   # Or test via the batch launcher: rf-suite\bin\rf-run.bat python --version

   # On Linux (Native Docker):
   docker images -q rf-suite:latest
   ```
2. **If Image is Missing (Not Ready) -> Auto-Build**:
   - **INFORM THE USER IMMEDIATELY IN CHAT**:
     > *"The `rf-suite` Docker toolchain environment is not built yet. Building the Docker image now via `docker compose build` in `rf-suite/`... This will compile and configure KiCad 10, FreeCAD 1.0, openEMS, Qucsator-RF, and the RF Python dependencies. I will keep you updated as the build progresses."*
   - Trigger the build:
     ```bash
     # On Windows (Docker in WSL Debian):
     wsl -d Debian bash -c "cd /mnt/d/Workspace/rf/rf-workbench/rf-suite && docker compose build"
     # Or if native Docker CLI is in Windows PATH:
     cd rf-suite && docker compose build

     # On Linux (Native Docker):
     cd rf-suite && docker compose build
     ```
   - Notify user on completion:
     > *"The `rf-suite` Docker image has been successfully built and verified! Proceeding immediately to Task 1 (Schematic Synthesis)..."*
3. **If Image is Ready**:
   Proceed directly to Task 1 without delay.

---

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

---

## Immediate Execution Policy (Zero Codebase Browsing Rule)
> [!CRITICAL]
> **WHEN A USER ASSIGNS A CIRCUIT DESIGN OR PCB CREATION WORKFLOW:**
> 1. **DO NOT BROWSE OR ANALYZE CODEBASE FILES**: Do NOT run `find_by_name`, `grep_search`, `list_dir`, or `view_file` on `agent/*.py` or other repository source files.
> 2. **DO NOT ENTER PLANNING MODE**: Do NOT create `implementation_plan.md` or ask architectural planning questions. The workflow architecture is already established and fully automated.
> 3. **DO NOT WRITE SCRATCH TEST SCRIPTS**: Do NOT write temporary Python scripts to test or research circuit algorithms.
> 4. **JUMP STRAIGHT INTO EXECUTION ON TURN 1**: Immediately launch **Task 1 (Schematic)** using the standard launcher:
>    ```bash
>    # Windows:
>    rf-suite\bin\rf-run.bat python -m agent.workflow --desc "<circuit description>" --stages schematic
>
>    # Linux / WSL:
>    ./rf-suite/bin/rf-run python3 -m agent.workflow --desc "<circuit description>" --stages schematic
>    ```
>    The `agent.workflow` engine automatically parses the description, generates the mathematical circuit specifications, selects footprints, routes CPWG lines, and exports the high-DPI zoomed schematic render.

---

## Interactive Popup Review Protocol (`ask_question`)
> [!IMPORTANT]
> **MANDATORY POPUP CONFIRMATION WITH NATIVE IMAGE DISPLAY**:
> User interaction between stages MUST be presented as **interactive popup modals** using `ask_question`.
> To guarantee that the schematic and 3D renders are always 100% visible in the chat alongside the popup, you MUST follow this exact 2-Turn sequence:
> 
> **TURN 1: Copy Image to Artifacts Directory**
> You MUST first use the `run_command` tool to copy the generated `.png` asset from the project directory to your conversation artifacts directory. The chat UI strictly restricts image rendering to the artifacts folder.
> *Example*: `Copy-Item "projects\<name>\renders\schematic_zoomed.png" -Destination "<appDataDir>\brain\<conversation-id>\"`
> *(Wait for the command to succeed before proceeding to Turn 2).*
>
> **TURN 2: Display Image & Call `ask_question`**
> In the very next turn, you MUST do BOTH of the following simultaneously:
> 1. **Emit Visible Markdown Text (OUTSIDE the tool call)**: Write out the full visible chat message containing the deliverables table, 0 DRC violations check, and the embedded image using standard Markdown syntax. **You MUST output this as standard conversational text to the user, NOT inside your internal thoughts or tool arguments.**
>    ```markdown
>    Here is the completed schematic:
>    ![Schematic](file:///<appDataDir>/brain/<conversation-id>/schematic_zoomed.png)
>    ```
>    *(CRITICAL: Ensure Windows backslashes are converted to forward slashes in the `file:///` URI, and never put the markdown image inside the `ask_question` JSON arguments!)*
> 2. **Invoke `ask_question` Tool**: In the exact same turn as your visible text, call the `ask_question` tool with the 3 selectable options:
>    - **Option 1 (Proceed)**: `(Recommended) <Artifact> looks good, let's move to <Next Task>.`
>    - **Option 2 (Reiterate / Adjust)**: `I'd like to adjust <parameters/components> to reiterate <Task>.`
>    - **Option 3 (Pause / Stop)**: `Pause execution here so I can review the deliverables and think through next steps.`

If the user requests reiteration, update `projects/<name>/spec.json` and re-run the specific stage using `--stages <stage>`.

---

## Execution Commands

### 1. Stage-by-Stage Interactive Execution (Standard Flow)
Run each stage individually, reviewing deliverables with the user between stages:

#### Windows
```cmd
:: Task 1: Schematic & Zoomed Crop
rf-suite\bin\rf-run.bat python -m agent.workflow --desc "<circuit description>" --stages schematic

:: Task 2: PCB Layout & DRC
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/<name>/spec.json --stages pcb

:: Task 3: 3D Raytrace Renders
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/<name>/spec.json --stages render

:: Task 4: FreeCAD & STEP CAD
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/<name>/spec.json --stages cad

:: Task 5: openEMS EM Simulation -> Touchstone .s1p / .s2p
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/<name>/spec.json --stages em

:: Task 6: Qucs-S Co-Simulation
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/<name>/spec.json --stages qucs

:: Task 7: RF Performance Charts
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/<name>/spec.json --stages charts

:: Task 8: Production Gerber ZIP
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/<name>/spec.json --stages gerbers

:: Task 9: Performance Report & BOM
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/<name>/spec.json --stages report
```

#### Linux / WSL
```bash
# Task 1: Schematic & Zoomed Crop
./rf-suite/bin/rf-run python3 -m agent.workflow --desc "<circuit description>" --stages schematic

# Task 2: PCB Layout & DRC
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages pcb

# Task 3: 3D Raytrace Renders
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages render

# Task 4: FreeCAD & STEP CAD
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages cad

# Task 5: openEMS EM Simulation -> Touchstone .s1p / .s2p
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages em

# Task 6: Qucs-S Co-Simulation
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages qucs

# Task 7: RF Performance Charts
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages charts

# Task 8: Production Gerber ZIP
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages gerbers

# Task 9: Performance Report & BOM
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages report
```

### 2. Full Batch Pipeline Execution (Unattended)
```bash
# Windows:
rf-suite\bin\rf-run.bat python -m agent.workflow --desc "<circuit description>" --f0 <center_freq_ghz> --z0 50

# Linux / WSL:
./rf-suite/bin/rf-run python3 -m agent.workflow --desc "<circuit description>" --f0 <center_freq_ghz> --z0 50
```

---

## Quality Assurance Checklist
1. **DRC Validation**: Verify `projects/<name>/<name>_drc.json` contains `0 violations` and `0 warnings`.
2. **Impedance Matching**: Ensure transmission lines adhere to 50Ω Grounded Coplanar Waveguide (CPWG) dimensions ($w = 1.87\text{ mm}$, $s = 0.40\text{ mm}$ on 1.6mm FR4).
3. **Artifact Integrity**: Check that all deliverables exist in `projects/<name>/`:
   - `renders/schematic_zoomed.png` (Task 1)
   - `<name>_drc.json` (Task 2)
   - `renders/iso_render.png`, `renders/top_render.png`, `renders/bottom_render.png` (Task 3)
   - `cad/<name>.step`, `cad/<name>.FCStd` (Task 4)
   - `simulation/<name>.s1p` / `simulation/<name>.s2p` (Task 5)
   - `simulation/<name>.dat` (Task 6)
   - `charts/sparam_plot.png`, `charts/smith_chart.png` (Task 7)
   - `gerbers_<name>.zip` (Task 8)
   - `PERFORMANCE_REPORT.md` (Task 9)
