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

## Quick Execution Commands

### 1. Autonomous End-to-End Synthesis from Natural Language
Execute the full 9-stage engineering pipeline inside the container:
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --desc '<circuit description>' --f0 <center_freq_ghz> --z0 50"
```

### 2. Execution with Presets
```bash
# Preset 1: 10 dB Precision Pi-Attenuator (DC-3GHz)
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --preset 1"

# Preset 2: 2.45 GHz Microstrip Bandpass Filter
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --preset 2"

# Preset 3: 1.5 - 2.5 GHz 2-Way Wilkinson Power Divider
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --preset 3"
```

### 3. Selective Stage Execution
Run only specific stages (e.g. after modifying `spec.json`):
```bash
wsl -d Debian bash -c "docker compose -f /mnt/d/Workspace/rf/rf-workbench/docker-compose.yml exec -T -w /workspace/rf-workbench rf-workbench python3 -m agent.workflow --spec-file projects/<name>/spec.json --stages em,qucs,charts,report"
```

## Quality Assurance Checklist
1. **DRC Validation**: Verify `projects/<name>/<name>_drc.json` contains `0 violations` and `0 warnings`.
2. **Impedance Matching**: Ensure transmission lines adhere to 50Ω Grounded Coplanar Waveguide (CPWG) dimensions ($w = 1.87\text{ mm}$, $s = 0.40\text{ mm}$ on 1.6mm FR4).
3. **Artifact Integrity**: Check that all deliverables exist in `projects/<name>/`:
   - `schematic_zoomed.png` (Task 1)
   - `iso_render.png`, `top_render.png`, `bottom_render.png` (Task 3)
   - `<name>.step` (Task 4)
   - `<name>.s2p` (Task 5)
   - `charts/*.png` (Task 8)
   - `PERFORMANCE_REPORT.md` (Task 9)
   - `gerbers_<name>.zip` (Task 10)
