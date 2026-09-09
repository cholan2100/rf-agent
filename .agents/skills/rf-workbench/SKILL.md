---
name: rf-workbench
description: >-
  Autonomous RF/Microwave hardware engineer and PCB design suite. Use whenever the user asks
  to design, synthesize, simulate, route, render, or fabricate RF circuits, printed circuit boards,
  attenuators, filters, bias tees, Wilkinson dividers, or CPWG transmission lines in KiCad, FreeCAD,
  openEMS, and Qucs.
---

# Autonomous RF Hardware Engineer Skill

Use this skill to autonomously design, synthesize, route, simulate, render, and package production-ready RF PCBs without requiring the user to run manual procedural scripts.

## Human-in-the-Loop Review Protocol (Mandatory)

When executing an RF design project, **never execute stages in a silent uninterrupted batch unless explicitly requested**.
Immediately upon completing **each task**, you must:
1. **Direct Inline Chat Image Rendering**: If the task generated visual renders (`schematic_zoomed.png`, `iso_render.png`, `top_render.png`, `sparam_plot.png`, etc.):
   - Copy `.png` files to the artifact directory `<appDataDir>\brain\<conversation-id>\`.
   - Embed an inline Generative UI review card (`<agent-embed src="file:///<artifact_path>/review_renders.html"></agent-embed>`) with base64 encoded images.
   - Also embed Markdown image tags (`![<Description>](<artifact_path>)`) directly in the chat text.
   - Never emit an empty tool turn when calling `ask_question`—always write out the visual cards and deliverables in the chat message!
2. **Show Deliverables Table**: Display the relative paths, file sizes, and status of generated files.
3. **Engineering Integrity Check**: Verify DRC violations (0 errors, 0 warnings) and electrical specifications.
4. **Interactive Confirmation via `ask_question`**: Prompt the user with exactly three choices:
   - `(Recommended) I am satisfied with the output of this task. Proceed to the next task.`
   - `I'd like to provide suggestions or adjust parameters to reiterate this task.`
   - `Stop the process here so I can review the deliverables and think through next steps.`

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
