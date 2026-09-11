---
name: rf-agent
description: >-
  Autonomous RF/Microwave hardware engineer and PCB design suite. Use whenever the user asks
  to design, synthesize, simulate, route, render, or fabricate RF circuits, printed circuit boards,
  attenuators, filters, bias tees, Wilkinson dividers, or CPWG transmission lines in KiCad, FreeCAD,
  openEMS, and Qucs.
---

# Autonomous RF Hardware Engineer Skill

> [!IMPORTANT]
> **Thin discovery file — AGENTS.md is the canonical source.**
> The complete, authoritative protocol for this skill lives in **[AGENTS.md](../../../AGENTS.md)** at the repository root and is **not duplicated here**. Before executing any part of this skill you MUST read `AGENTS.md` and follow it in full: Turn 0 Repository Self-Provisioning (§1.2), Immediate Execution Policy (§1.3), Default Hardware Baseline (§1.4), Interactive Popup Review Protocol (§6), and the full CLI reference (§4). When this file and `AGENTS.md` differ, **`AGENTS.md` wins**. Edit protocol rules **only in `AGENTS.md`**.

## Activation Summary

When this skill activates (RF circuit / PCB design, simulation, or fabrication request):

1. **Read `AGENTS.md` first** — it defines the complete 9-stage workflow and all engineering rules.
2. **Turn 0 — Repository Self-Provisioning (three gates, strictly in order; exact commands: `AGENTS.md` §1.2)**:
   - **Gate 1 — Submodule**: If `rf-suite\bin\rf-run.bat` (Windows) or `./rf-suite/bin/rf-run` (Linux/WSL) is **missing** (fresh clones do not check out submodules by default), inform the user, run `git submodule update --init --recursive`, and verify the launcher now exists before continuing.
   - **Gate 2 — Docker**: Only after Gate 1 passes, check whether the `rf-suite:latest` Docker image exists; if missing, inform the user and run `docker compose build` in `rf-suite/`.
   - **Gate 3 — Invitation Greeting**: When initialization is complete, if no circuit was prompted upfront, ask the user what RF circuit they would like to design today, with example prompts (`AGENTS.md` §1.2). If a circuit description was provided, proceed immediately to Task 1.
3. **Execute**: Launch the workflow through the standard launchers — no codebase browsing, no planning mode, no scratch scripts (`AGENTS.md` §1.3):
   ```bash
   # Windows:
   rf-suite\bin\rf-run.bat python -m agent.workflow --desc "<circuit description>" --stages schematic
   # Linux / WSL:
   ./rf-suite/bin/rf-run python3 -m agent.workflow --desc "<circuit description>" --stages schematic
   ```
4. **Review gates**: After each stage, present deliverables in chat and confirm via `ask_question` before proceeding (`AGENTS.md` §6).

For RF reference math (CPWG conformal mapping, Pi-attenuators, LC filters, bias tees), see `SKILLS.md` at the repository root.
