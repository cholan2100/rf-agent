"""
RF AI Suite - Interactive Console Agent for Autonomous RF PCB Development.
Provides an interactive text console UI with live animated task progression,
technical activity reporting, artifact links, and design iteration loop.
"""

import os
import sys
import time
import argparse
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.prompt import Prompt, Confirm

from .spec import (
    CircuitSpec,
    PRESETS,
    PRESET_10DB_ATTENUATOR,
    PRESET_2_4GHZ_FILTER,
    PRESET_WILKINSON_DIVIDER,
    calc_microstrip_width
)
from .schematic_gen import generate_schematic
from .pcb_gen import generate_pcb
from .renderer import render_3d_pcb
from .freecad_gen import generate_freecad_project
from .em_solver import run_em_simulation
from .qucs_sim import run_qucs_simulation
from .chart_gen import render_rf_charts
from .report_gen import generate_performance_report
from .gerber_pack import package_gerbers

console = Console()

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

TASKS = [
    ("Task 1", "Develop Schematic on KiCad (.kicad_sch)"),
    ("Task 2", "Create KiCad PCB Layout (.kicad_pcb via pcbnew)"),
    ("Task 3", "Render 3D PCB Visualizations (kicad-cli)"),
    ("Task 4", "Create FreeCAD Project & 3D Mechanical Model"),
    ("Task 5", "FreeCAD-Microwave / openEMS Touchstone Extraction (.s2p)"),
    ("Task 6", "Create Qucs Project Schematic with Touchstone Co-Simulation"),
    ("Task 7", "Run Qucs Simulation Engine (qucsator-rf)"),
    ("Task 8", "Render High-Resolution RF Performance Charts (dB, Smith, K)"),
    ("Task 9", "Generate Performance Markdown Report Table"),
    ("Task 10", "Package Production Gerber & Drill ZIP Archive"),
    ("Task 11", "Design Reiteration & Tuning Loop"),
]

def render_dashboard(current_task_idx: int, frame_idx: int, current_activity: str, task_outputs: Dict[int, str]) -> Panel:
    """Build the Rich renderable for the live task dashboard."""
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("Status", width=4, justify="center")
    table.add_column("Task Description", ratio=1)

    spinner = SPINNER_FRAMES[frame_idx % len(SPINNER_FRAMES)]

    for idx, (t_id, t_name) in enumerate(TASKS):
        if idx < current_task_idx:
            # Completed
            status = Text("✔", style="bold green")
            desc = Text(f"{t_id}: {t_name}", style="green")
            table.add_row(status, desc)
            if idx in task_outputs:
                sub = Text(f"\t↳ {task_outputs[idx]}", style="dim cyan")
                table.add_row(Text(""), sub)
        elif idx == current_task_idx:
            # In progress
            status = Text(spinner, style="bold yellow")
            desc = Text(f"{t_id}: {t_name}", style="bold yellow")
            table.add_row(status, desc)
            act_text = Text(f"\t↳ {current_activity}", style="italic yellow")
            table.add_row(Text(""), act_text)
        else:
            # Pending
            status = Text("○", style="dim")
            desc = Text(f"{t_id}: {t_name}", style="dim")
            table.add_row(status, desc)

    return Panel(
        table,
        title="[bold cyan]⚡ PIPELINE EXECUTION PROGRESS[/bold cyan]",
        subtitle="[dim]RF AI Suite Autonomous Hardware Pipeline[/dim]",
        border_style="cyan"
    )


def prompt_user_for_spec(batch_mode: bool = False, preset_choice: Optional[str] = None) -> CircuitSpec:
    """Interactive questionnaire for user requirements with smart defaults."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]⚡ RF AI SUITE - AUTONOMOUS AGENTIC PCB DESIGNER[/bold cyan]\n"
        "[white]Synthesizes schematics, routed PCBs, 3D raytraces, EM Touchstone datasets,\n"
        "Qucs co-simulations, performance charts, and fabrication Gerbers.[/white]",
        border_style="cyan"
    ))

    if batch_mode:
        preset_key = preset_choice or "1"
        spec = PRESETS.get(preset_key, PRESET_10DB_ATTENUATOR)
        console.print(f"[green]Running in non-interactive batch mode with preset: [bold]{spec.title}[/bold][/green]")
        return spec

    console.print("\n[bold yellow]Select an RF Circuit Topology / Benchmark Preset:[/bold yellow]")
    console.print("  [bold cyan][1][/bold cyan] 10 dB RF Pi-Attenuator (50Ω, DC-3GHz) [bold green][Default Reference Benchmark][/bold green]")
    console.print("  [bold cyan][2][/bold cyan] 2.45 GHz Microstrip Bandpass Filter (Wi-Fi / ISM Band)")
    console.print("  [bold cyan][3][/bold cyan] 1.5 - 2.5 GHz 2-Way Wilkinson Power Divider (50Ω Split)")
    console.print("  [bold cyan][4][/bold cyan] Custom RF Circuit Specification")

    choice = Prompt.ask("Choose preset", choices=["1", "2", "3", "4"], default="1")

    if choice in ["1", "2", "3"]:
        spec = PRESETS[choice]
        console.print(f"\n[bold green]Loaded Preset:[/bold green] [cyan]{spec.title}[/cyan]")
        console.print(f"  • Frequency Range: {spec.f_min_ghz} GHz to {spec.f_max_ghz} GHz (Center f0 = {spec.f_0_ghz} GHz)")
        console.print(f"  • Target S21:      {spec.target_s21_db} dB | Return Loss S11: < {spec.target_s11_db} dB")
        console.print(f"  • Dimensions:      {spec.width_mm} mm × {spec.height_mm} mm (2 Layers, {spec.substrate_name} er={spec.dielectric_er})")
        console.print(f"  • Power Supply:    {spec.power_supply_type}")
        console.print(f"  • EM Solver:       {spec.em_sim_type.upper()}")

        use_defaults = Confirm.ask("\nUse preset default values?", default=True)
        if use_defaults:
            return spec

    # Custom or customized parameters
    console.print("\n[bold yellow]Configure RF Circuit Parameters:[/bold yellow]")
    title = Prompt.ask("Circuit Title", default="Custom RF Board")
    f_0 = float(Prompt.ask("Center Frequency f0 (GHz)", default="1.5"))
    f_min = float(Prompt.ask("Minimum Frequency f_min (GHz)", default=str(round(max(0.01, f_0 * 0.1), 2))))
    f_max = float(Prompt.ask("Maximum Frequency f_max (GHz)", default=str(round(f_0 * 2.0, 2))))
    width = float(Prompt.ask("PCB Width (mm)", default="30.0"))
    height = float(Prompt.ask("PCB Height (mm)", default="20.0"))

    console.print("\n[bold yellow]Substrate & Dielectric:[/bold yellow]")
    sub_choice = Prompt.ask("Substrate Type", choices=["FR4", "RO4003C", "RT5880"], default="FR4")
    er_map = {"FR4": 4.4, "RO4003C": 3.55, "RT5880": 2.2}
    h_map = {"FR4": 1.6, "RO4003C": 0.813, "RT5880": 0.508}
    er = er_map[sub_choice]
    h = h_map[sub_choice]

    console.print("\n[bold yellow]EM Simulation Type:[/bold yellow]")
    console.print("  [cyan][1][/cyan] Critical Traces & Transmission Lines (Fast, ~15-30s, low complexity)")
    console.print("  [cyan][2][/cyan] Multi-Port Full Board FDTD [yellow](⚠️ High Computational Complexity: 2-5 min full-wave solve)[/yellow]")
    em_opt = Prompt.ask("EM Simulation Option", choices=["1", "2"], default="1")
    em_type = "traces" if em_opt == "1" else "full_board"

    spec = CircuitSpec(
        name=title.lower().replace(" ", "_").replace("-", "_"),
        title=title,
        topology="attenuator" if "attenuator" in title.lower() else "custom",
        f_min_ghz=f_min,
        f_0_ghz=f_0,
        f_max_ghz=f_max,
        width_mm=width,
        height_mm=height,
        substrate_name=sub_choice,
        dielectric_er=er,
        substrate_height_mm=h,
        em_sim_type=em_type
    )
    return spec


def run_pipeline(spec: CircuitSpec, project_root: str = "projects", batch_mode: bool = False):
    """Execute the full 11-stage autonomous agent pipeline."""
    output_dir = os.path.join(project_root, spec.name)
    os.makedirs(output_dir, exist_ok=True)

    task_outputs = {}
    current_activity = "Initializing environment..."
    current_task_idx = 0
    frame_idx = 0

    def update_act(msg):
        nonlocal current_activity
        current_activity = msg

    with Live(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs), refresh_per_second=8, console=console) as live:
        
        # ----------------------------------------------------
        # Task 1: Develop Schematic on KiCad (.kicad_sch)
        # ----------------------------------------------------
        current_task_idx = 0
        update_act("Synthesizing KiCad 10 S-expression schematic (.kicad_sch)...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))
        time.sleep(0.4)

        sch_path = generate_schematic(spec, output_dir)
        task_outputs[0] = f"Schematic generated: {os.path.basename(sch_path)} ({os.path.getsize(sch_path):,} bytes)"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 2: Create KiCad PCB Layout (.kicad_pcb via pcbnew)
        # ----------------------------------------------------
        current_task_idx = 1
        update_act(f"Calculating 50Ω trace width ({spec.microstrip_width_mm:.2f}mm) & placing footprints...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))
        time.sleep(0.5)

        update_act("Routing RF microstrip tracks, ground pours, and via fencing...")
        live.update(render_dashboard(current_task_idx, frame_idx + 1, current_activity, task_outputs))

        pcb_path, drc_res = generate_pcb(spec, output_dir)
        v_count = drc_res.get("violations", 0)
        w_count = drc_res.get("warnings", 0)
        task_outputs[1] = f"PCB layout created: {os.path.basename(pcb_path)} (DRC: {v_count} errors, {w_count} warnings)"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 3: Render 3D PCB Visualizations (kicad-cli)
        # ----------------------------------------------------
        current_task_idx = 2
        update_act("Launching KiCad 10 raytracer for populated 3D renders...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))

        renders = render_3d_pcb(pcb_path, output_dir, progress_callback=lambda m: (update_act(m), live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))))
        iso_size = renders.get("iso", {}).get("size_kb", 0)
        top_size = renders.get("top", {}).get("size_kb", 0)
        bot_size = renders.get("bottom", {}).get("size_kb", 0)
        task_outputs[2] = f"3D Renders complete: iso ({iso_size} KB), top ({top_size} KB), bottom ({bot_size} KB)"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 4: Create FreeCAD Project & 3D Mechanical Model
        # ----------------------------------------------------
        current_task_idx = 3
        update_act("Exporting 3D STEP and assembling FreeCAD .FCStd document...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))

        fc_res = generate_freecad_project(spec, pcb_path, output_dir, progress_callback=lambda m: (update_act(m), live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))))
        task_outputs[3] = f"FreeCAD project ready: {os.path.basename(fc_res['fcstd_path'])} & {os.path.basename(fc_res['step_path'])} ({fc_res['step_size_kb']} KB)"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 5: FreeCAD-Microwave / openEMS Touchstone (.s2p)
        # ----------------------------------------------------
        current_task_idx = 4
        update_act(f"Extracting multi-port S-parameters via {spec.em_sim_type} solver...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))

        em_res = run_em_simulation(spec, output_dir, progress_callback=lambda m: (update_act(m), live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))))
        task_outputs[4] = f"Touchstone extracted: {os.path.basename(em_res['s2p_path'])} ({em_res['num_freq_points']} frequency points)"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 6: Create Qucs Project Schematic with Touchstone
        # ----------------------------------------------------
        current_task_idx = 5
        update_act("Synthesizing Qucs co-simulation schematic and netlist...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))
        time.sleep(0.4)

        qucs_res = run_qucs_simulation(spec, em_res["s2p_path"], output_dir, progress_callback=lambda m: (update_act(m), live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))))
        task_outputs[5] = f"Qucs project synthesized: {os.path.basename(qucs_res['sch_path'])}"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 7: Run Qucs Simulation Engine (qucsator-rf)
        # ----------------------------------------------------
        current_task_idx = 6
        update_act("Evaluating RF circuit co-simulation with qucsator solver...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))
        time.sleep(0.5)

        task_outputs[6] = f"Qucs simulation complete: dataset {os.path.basename(qucs_res['dat_path'])}"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 8: Render High-Resolution RF Performance Charts
        # ----------------------------------------------------
        current_task_idx = 7
        update_act("Plotting S-parameter curves, Smith chart, and stability factor...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))

        chart_files = render_rf_charts(spec, qucs_res["sim_data"], output_dir, progress_callback=lambda m: (update_act(m), live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))))
        task_outputs[7] = f"Generated {len(chart_files)} charts: S-Parameters, Smith Chart, Stability (K), Impedance"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 9: Generate Performance Markdown Report Table
        # ----------------------------------------------------
        current_task_idx = 8
        update_act("Compiling metrics into text-based comparison table & markdown report...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))

        # Gerber zip path for report link
        gerber_zip_path = os.path.join(output_dir, f"gerbers_{spec.name}.zip")
        rpt_path = generate_performance_report(spec, qucs_res["sim_data"], renders, chart_files, gerber_zip_path, output_dir, progress_callback=lambda m: (update_act(m), live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))))
        task_outputs[8] = f"Performance report generated: {os.path.basename(rpt_path)} ({os.path.getsize(rpt_path):,} bytes)"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 10: Package Production Gerber & Drill ZIP Archive
        # ----------------------------------------------------
        current_task_idx = 9
        update_act("Exporting fabrication Gerbers & drill files to production ZIP...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))

        gerber_res = package_gerbers(spec, pcb_path, output_dir, progress_callback=lambda m: (update_act(m), live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))))
        task_outputs[9] = f"Gerbers packaged: {gerber_res['zip_filename']} ({gerber_res['file_count']} layers, {gerber_res['zip_size_kb']} KB)"
        frame_idx += 1

        # ----------------------------------------------------
        # Task 11: Design Reiteration & Tuning Loop
        # ----------------------------------------------------
        current_task_idx = 10
        update_act("Waiting for user review and reiteration check...")
        live.update(render_dashboard(current_task_idx, frame_idx, current_activity, task_outputs))

    # All tasks 0 to 9 are finished. Now handle Task 11 interactively.
    console.print()
    if batch_mode:
        task_outputs[10] = "Batch execution complete (Reiteration check skipped in batch mode)"
        console.print(render_dashboard(11, frame_idx, "Finished", task_outputs))
        _print_summary(spec, output_dir, gerber_res["zip_path"], rpt_path)
        return

    # Interactive Task 11 Loop
    console.print(Panel(
        f"[bold green]✔ PIPELINE STAGES 1-10 COMPLETED SUCCESSFULLY![/bold green]\n\n"
        f"• Project Folder:    [cyan]{output_dir}[/cyan]\n"
        f"• Performance Table: [cyan]{rpt_path}[/cyan]\n"
        f"• Fabrication ZIP:   [cyan]{gerber_res['zip_path']}[/cyan]",
        border_style="green"
    ))

    reiterate = Confirm.ask("\n[bold yellow]Task 11: Would you like to reiterate or adjust parameters (e.g. tuning frequency, board size)?", default=False)
    if reiterate:
        console.print("[cyan]Opening parameter adjustment...[/cyan]")
        new_f0 = float(Prompt.ask("Adjust Center Frequency (GHz)", default=str(spec.f_0_ghz)))
        new_width = float(Prompt.ask("Adjust PCB Width (mm)", default=str(spec.width_mm)))
        spec.f_0_ghz = new_f0
        spec.width_mm = new_width
        console.print("[green]Re-running pipeline with updated parameters...[/green]\n")
        run_pipeline(spec, project_root, batch_mode=False)
    else:
        task_outputs[10] = "User approved deliverables - no reiterations required."
        console.print(render_dashboard(11, frame_idx, "All tasks completed.", task_outputs))
        _print_summary(spec, output_dir, gerber_res["zip_path"], rpt_path)


def _print_summary(spec: CircuitSpec, output_dir: str, zip_path: str, rpt_path: str):
    """Print final summary card with output deliverables."""
    console.print()
    table = Table(title="[bold green]📦 Final Generated RF Engineering Deliverables[/bold green]", box=None)
    table.add_column("Deliverable", style="cyan", justify="left")
    table.add_column("Path / File", style="white", justify="left")
    
    table.add_row("KiCad Schematic", os.path.join(output_dir, f"{spec.name}.kicad_sch"))
    table.add_row("KiCad PCB Layout", os.path.join(output_dir, f"{spec.name}.kicad_pcb"))
    table.add_row("3D Raytraced Renders", os.path.join(output_dir, "renders", "iso_render.png"))
    table.add_row("FreeCAD Mechanical STEP", os.path.join(output_dir, "cad", f"{spec.name}.step"))
    table.add_row("Touchstone S-Parameters", os.path.join(output_dir, "simulation", f"{spec.name}.s2p"))
    table.add_row("Qucs-S Simulation Data", os.path.join(output_dir, "simulation", f"{spec.name}.dat"))
    table.add_row("Performance Markdown Table", rpt_path)
    table.add_row("Fabrication Gerbers Archive", zip_path)

    console.print(Panel(table, border_style="green"))
    console.print(f"[bold green]✨ Autonomous RF PCB engineering run complete for {spec.title}![/bold green]\n")


def main():
    parser = argparse.ArgumentParser(description="RF AI Suite - Autonomous Agentic PCB Designer")
    parser.add_argument("--preset", type=str, choices=["1", "2", "3"], help="Preset number (1: 10dB Attenuator, 2: 2.4GHz Filter, 3: Wilkinson)")
    parser.add_argument("--batch", action="store_true", help="Run non-interactively without prompting")
    parser.add_argument("--output-dir", type=str, default="projects", help="Directory to store generated projects")
    args = parser.parse_args()

    spec = prompt_user_for_spec(batch_mode=args.batch, preset_choice=args.preset)
    run_pipeline(spec, project_root=args.output_dir, batch_mode=args.batch)


if __name__ == "__main__":
    main()
