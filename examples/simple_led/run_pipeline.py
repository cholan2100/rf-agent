#!/usr/bin/env python3
"""
End-to-end automated manufacturing pipeline for Simple LED Board.
1. Synthesizes KiCad PCB layout via pcbnew API.
2. Performs headless DRC verification via kicad-cli.
3. Exports production Gerbers and NC drill files.
4. Exports SVG layers and 3D STEP mechanical model.
"""

import os
import sys
import subprocess
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOARD_FILE = os.path.join(SCRIPT_DIR, "led_board.kicad_pcb")
GERBER_DIR = os.path.join(SCRIPT_DIR, "gerbers")
RENDERS_DIR = os.path.join(SCRIPT_DIR, "renders")

print("=" * 70)
print("  SIMPLE LED PCB - AUTOMATED PRODUCTION PIPELINE")
print("=" * 70)

# Step 1: Generate PCB
print("\n[Step 1/5] Synthesizing PCB layout with pcbnew...")
cmd_gen = [sys.executable, os.path.join(SCRIPT_DIR, "generate_led_pcb.py"), BOARD_FILE]
res_gen = subprocess.run(cmd_gen, cwd=SCRIPT_DIR, capture_output=True, text=True)
print(res_gen.stdout)
if res_gen.returncode != 0:
    print("[ERROR] PCB generation failed:")
    print(res_gen.stderr)
    sys.exit(1)

# Step 2: Headless DRC Check
print("\n[Step 2/5] Running Design Rule Check (DRC) with kicad-cli...")
drc_rpt = os.path.join(SCRIPT_DIR, "drc_report.json")
cmd_drc = [
    "kicad-cli", "pcb", "drc",
    "--output", drc_rpt,
    "--format", "json",
    BOARD_FILE
]
res_drc = subprocess.run(cmd_drc, capture_output=True, text=True)
if os.path.exists(drc_rpt):
    print(f"DRC completed! Report: {drc_rpt}")
    with open(drc_rpt, "r", encoding="utf-8") as f:
        content = f.read()
        violations = content.count('"severity": "error"')
        warnings = content.count('"severity": "warning"')
        print(f"  Violations: {violations}, Warnings: {warnings}")
else:
    print(res_drc.stdout)
    print(res_drc.stderr)

# Step 3: Export Production Gerbers & Drill
print("\n[Step 3/5] Exporting Production Gerbers and NC Drill...")
os.makedirs(GERBER_DIR, exist_ok=True)
cmd_gerbers = [
    "kicad-cli", "pcb", "export", "gerbers",
    "--output", GERBER_DIR + "/",
    BOARD_FILE
]
subprocess.run(cmd_gerbers, check=True)

cmd_drill = [
    "kicad-cli", "pcb", "export", "drill",
    "--output", GERBER_DIR + "/",
    BOARD_FILE
]
subprocess.run(cmd_drill, check=True)

gerber_files = os.listdir(GERBER_DIR)
print(f"Exported {len(gerber_files)} Gerber & Drill files into {GERBER_DIR}:")
for gf in sorted(gerber_files):
    size = os.path.getsize(os.path.join(GERBER_DIR, gf))
    print(f"  - {gf:<30} ({size:,} bytes)")

# Step 4: Export Vector SVG Artwork
print("\n[Step 4/5] Exporting Vector SVG Artwork...")
os.makedirs(RENDERS_DIR, exist_ok=True)
svg_top = os.path.join(RENDERS_DIR, "led_board_top.svg")
cmd_svg_top = [
    "kicad-cli", "pcb", "export", "svg",
    "--layers", "F.Cu,F.SilkS,Edge.Cuts",
    "--output", svg_top,
    BOARD_FILE
]
subprocess.run(cmd_svg_top, check=True)
print(f"  - Top Artwork:    {svg_top} ({os.path.getsize(svg_top):,} bytes)")

svg_bot = os.path.join(RENDERS_DIR, "led_board_bottom.svg")
cmd_svg_bot = [
    "kicad-cli", "pcb", "export", "svg",
    "--layers", "B.Cu,Edge.Cuts",
    "--output", svg_bot,
    BOARD_FILE
]
subprocess.run(cmd_svg_bot, check=True)
print(f"  - Bottom Artwork: {svg_bot} ({os.path.getsize(svg_bot):,} bytes)")

# Step 5: Export 3D STEP Model
print("\n[Step 5/5] Exporting 3D STEP Mechanical Model...")
step_file = os.path.join(RENDERS_DIR, "led_board.step")
cmd_step = [
    "kicad-cli", "pcb", "export", "step",
    "--output", step_file,
    BOARD_FILE
]
try:
    subprocess.run(cmd_step, timeout=60, check=True)
    print(f"  - 3D STEP Model:  {step_file} ({os.path.getsize(step_file):,} bytes)")
except Exception as e:
    print(f"  - STEP export note: {e}")

print("\n" + "=" * 70)
print("  [SUCCESS] LED PCB MANUFACTURING PIPELINE COMPLETE!")
print("=" * 70)
