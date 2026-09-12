"""
Modular Headless Workflow Engine for Autonomous RF Design.
Designed to be executed directly by AI Agents (like Antigravity) via CLI or Python API.
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, Optional, List
from .spec import CircuitSpec, parse_custom_circuit


ALL_STAGES = ["schematic", "pcb", "render", "cad", "em", "qucs", "charts", "gerbers", "report"]


def execute_workflow(
    spec: CircuitSpec,
    project_root: str = "projects",
    stages: Optional[List[str]] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Executes the RF engineering stages headlessly and returns structured metrics.
    """
    active_stages = set(stages if stages else ALL_STAGES)
    output_dir = os.path.join(project_root, spec.name)
    os.makedirs(output_dir, exist_ok=True)

    from .schematic_gen import generate_schematic
    from .pcb_gen import generate_pcb
    from .renderer import render_3d_pcb
    from .freecad_gen import generate_freecad_project
    from .em_solver import run_em_simulation
    from .qucs_sim import run_qucs_simulation, _parse_simulation_data
    from .chart_gen import render_rf_charts
    from .report_gen import generate_performance_report
    from .gerber_pack import package_gerbers


    # 1. Persist CircuitSpec JSON for agent inspection and reproducibility
    spec_json_path = os.path.join(output_dir, "spec.json")
    spec_dict = {
        "name": spec.name,
        "title": spec.title,
        "topology": spec.topology,
        "description": spec.description,
        "f_min_ghz": spec.f_min_ghz,
        "f_0_ghz": spec.f_0_ghz,
        "f_max_ghz": spec.f_max_ghz,
        "z0_ohm": spec.z0_ohm,
        "target_s21_db": spec.target_s21_db,
        "target_s11_db": spec.target_s11_db,
        "target_s22_db": spec.target_s22_db,
        "width_mm": spec.width_mm,
        "height_mm": spec.height_mm,
        "substrate_name": spec.substrate_name,
        "dielectric_er": spec.dielectric_er,
        "substrate_height_mm": spec.substrate_height_mm,
        "trace_mode": spec.trace_mode,
        "trace_gap_mm": spec.trace_gap_mm,
        "rf_trace_width_mm": spec.rf_trace_width_mm,
        "effective_dielectric_constant": spec.effective_dielectric_constant,
        "em_sim_type": spec.em_sim_type,
        "components": spec.components,
        "additional_reqs": spec.additional_reqs
    }
    with open(spec_json_path, "w", encoding="utf-8") as f:
        json.dump(spec_dict, f, indent=2)

    results = {
        "spec": spec_dict,
        "project_dir": output_dir,
        "stages": {},
        "status": "in_progress"
    }

    if verbose:
        print(f"═══ RF WORKFLOW ENGINE: {spec.title} ═══")
        print(f"Project Output Directory: {output_dir}")
        print(f"Substrate: {spec.substrate_name} (er={spec.dielectric_er}, h={spec.substrate_height_mm}mm)")
        print(f"Transmission Line: {spec.trace_mode} (Z0={spec.z0_ohm}Ω, w={spec.rf_trace_width_mm:.2f}mm, s={spec.trace_gap_mm:.2f}mm)")
        print("═" * 50)

    sch_path = os.path.join(output_dir, f"{spec.name}.kicad_sch")
    pcb_path = os.path.join(output_dir, f"{spec.name}.kicad_pcb")
    s2p_path = os.path.join(output_dir, "simulation", f"{spec.name}.s2p")
    renders = {}
    chart_files = []
    qucs_res = {"sim_data": {}}

    # Stage 1: Schematic
    if "schematic" in active_stages:
        if verbose:
            print("[1/9] Generating KiCad 10 schematic & zoomed render...")
        sch_path, zoomed_png = generate_schematic(spec, output_dir)
        sch_sz = os.path.getsize(sch_path) / 1024.0 if os.path.exists(sch_path) else 0
        img_sz = os.path.getsize(zoomed_png) / 1024.0 if os.path.exists(zoomed_png) else 0
        results["stages"]["schematic"] = {
            "sch_path": sch_path,
            "zoomed_render": zoomed_png,
            "size_bytes": os.path.getsize(sch_path) if os.path.exists(sch_path) else 0
        }
        if verbose:
            print(f"✔ Task 1 Deliverables: {sch_path} ({sch_sz:.1f} KB) | {zoomed_png} ({img_sz:.1f} KB)")

    # Stage 2: PCB Layout & DRC
    if "pcb" in active_stages:
        if verbose:
            print(f"[2/9] Synthesizing PCB layout ({spec.trace_mode} w={spec.rf_trace_width_mm:.2f}mm)...")
        pcb_path, drc_res = generate_pcb(spec, output_dir)
        pcb_sz = os.path.getsize(pcb_path) / 1024.0 if os.path.exists(pcb_path) else 0
        results["stages"]["pcb"] = {
            "pcb_path": pcb_path,
            "drc_violations": drc_res.get("violations", 0),
            "drc_warnings": drc_res.get("warnings", 0),
            "drc_json": drc_res.get("drc_json_path", "")
        }
        if verbose:
            print(f"✔ Task 2 Deliverables: {pcb_path} ({pcb_sz:.1f} KB) | DRC: {drc_res.get('violations', 0)} errors, {drc_res.get('warnings', 0)} warnings")

    # Stage 3: 3D Raytrace Render
    if "render" in active_stages and os.path.exists(pcb_path):
        if verbose:
            print("[3/9] Executing KiCad 3D raytracer (iso, top, bottom)...")
        renders = render_3d_pcb(pcb_path, output_dir)
        results["stages"]["render"] = renders
        if verbose:
            print("✔ Task 3 Deliverables (3D Raytraces):")
            for k, v in renders.items():
                print(f"  - {k.capitalize()}: {v.get('path')} ({v.get('size_kb', 0):.1f} KB)")

    # Stage 4: FreeCAD & STEP
    if "cad" in active_stages and os.path.exists(pcb_path):
        if verbose:
            print("[4/9] Exporting FreeCAD .FCStd project and mechanical 3D STEP...")
        fc_res = generate_freecad_project(spec, pcb_path, output_dir)
        results["stages"]["cad"] = fc_res
        if verbose:
            print(f"✔ Task 4 Deliverables: STEP {fc_res.get('step_size_kb', 0):.1f} KB | FCStd {fc_res.get('fcstd_size_kb', 0):.1f} KB")

    # Stage 5: EM & Touchstone
    if "em" in active_stages:
        if verbose:
            print(f"[5/9] Running EM solver ({spec.em_sim_type}) -> Touchstone .s2p...")
        em_res = run_em_simulation(spec, output_dir)
        s2p_path = em_res["s2p_path"]
        results["stages"]["em"] = em_res
        if verbose:
            print(f"✔ Task 5 Deliverables: {s2p_path} (EM Touchstone dataset)")

    # Stage 6 & 7: Qucs Co-Simulation
    if "qucs" in active_stages and os.path.exists(s2p_path):
        if verbose:
            print("[6/9] Running Qucsator RF co-simulation...")
        qucs_res = run_qucs_simulation(spec, s2p_path, output_dir)
        results["stages"]["qucs"] = {
            "sch_path": qucs_res["sch_path"],
            "net_path": qucs_res["net_path"],
            "dat_path": qucs_res["dat_path"],
            "qucs_success": qucs_res["qucs_solver_success"]
        }
        if verbose:
            print(f"✔ Task 6 Deliverables: {qucs_res['dat_path']} (Qucsator RF simulation dataset)")

    # Ensure sim_data is available for downstream charts/report even if qucs stage wasn't executed in this run
    from .qucs_sim import _parse_simulation_data
    dat_path = os.path.join(output_dir, "simulation", f"{spec.name}.dat")
    sim_data = qucs_res.get("sim_data") or {}
    if not sim_data and os.path.exists(s2p_path):
        sim_data = _parse_simulation_data(s2p_path, dat_path, spec)

    # Stage 7: RF Performance Charts
    if "charts" in active_stages and sim_data:
        if verbose:
            print("[7/9] Plotting publication-quality RF performance charts...")
        chart_files = render_rf_charts(spec, sim_data, output_dir)
        results["stages"]["charts"] = chart_files
        if verbose:
            print(f"✔ Task 7 Deliverables ({len(chart_files)} RF Performance Plots):")
            for cf in chart_files:
                sz = os.path.getsize(cf) / 1024.0 if os.path.exists(cf) else 0
                print(f"  - {os.path.basename(cf)}: {cf} ({sz:.1f} KB)")

    # Stage 8: Gerbers
    gerber_zip_path = os.path.join(output_dir, f"gerbers_{spec.name}.zip")
    if "gerbers" in active_stages and os.path.exists(pcb_path):
        if verbose:
            print("[8/9] Packaging 26-layer production Gerber and drill ZIP...")
        gerber_res = package_gerbers(spec, pcb_path, output_dir)
        results["stages"]["gerbers"] = gerber_res
        if verbose:
            print(f"✔ Task 8 Deliverables: {gerber_zip_path} ({gerber_res.get('zip_size_kb', 0):.1f} KB, {gerber_res.get('file_count', 0)} production layers)")

    # Stage 9: Performance Report
    if "report" in active_stages:
        if verbose:
            print("[9/9] Compiling markdown performance report and BOM...")
        # Discover existing renders if not generated in this run
        if not renders:
            renders_dir = os.path.join(output_dir, "renders")
            renders = {
                "iso": {"path": os.path.join(renders_dir, "iso_render.png"), "size_kb": 0},
                "top": {"path": os.path.join(renders_dir, "top_render.png"), "size_kb": 0},
                "bottom": {"path": os.path.join(renders_dir, "bottom_render.png"), "size_kb": 0}
            }
        # Discover existing charts if not generated in this run
        if not chart_files:
            charts_dir = os.path.join(output_dir, "charts")
            chart_files = [os.path.join(charts_dir, f) for f in ["sparam_plot.png", "smith_chart.png", "stability_plot.png", "impedance_plot.png"] if os.path.exists(os.path.join(charts_dir, f))]

        rpt_path = generate_performance_report(spec, sim_data, renders, chart_files, gerber_zip_path, output_dir)
        rpt_sz = os.path.getsize(rpt_path) / 1024.0 if os.path.exists(rpt_path) else 0
        results["stages"]["report"] = {
            "report_path": rpt_path,
            "report_size_bytes": os.path.getsize(rpt_path) if os.path.exists(rpt_path) else 0
        }
        if verbose:
            print(f"✔ Task 9 Deliverables: {rpt_path} ({rpt_sz:.1f} KB)")

    results["status"] = "success"
    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    if verbose:
        print("═" * 50)
        print(f"✔ Autonomous run completed successfully!")
        print(f"Deliverables directory: {output_dir}")
        print(f"Summary JSON:           {summary_path}")

    return results


def load_spec_from_json(json_path: str) -> CircuitSpec:
    """Load a CircuitSpec directly from a JSON file."""
    with open(json_path, "r", encoding="utf-8-sig") as f:
        d = json.load(f)

    return CircuitSpec(
        name=d.get("name", "custom_circuit"),
        title=d.get("title", "Custom RF Board"),
        topology=d.get("topology", "custom"),
        description=d.get("description", ""),
        f_min_ghz=float(d.get("f_min_ghz", 0.1)),
        f_0_ghz=float(d.get("f_0_ghz", 1.5)),
        f_max_ghz=float(d.get("f_max_ghz", 3.0)),
        z0_ohm=float(d.get("z0_ohm", 50.0)),
        target_s21_db=float(d.get("target_s21_db", -10.0)),
        target_s11_db=float(d.get("target_s11_db", -20.0)),
        target_s22_db=float(d.get("target_s22_db", -20.0)),
        width_mm=float(d.get("width_mm", 30.0)),
        height_mm=float(d.get("height_mm", 20.0)),
        substrate_name=d.get("substrate_name", "FR4"),
        dielectric_er=float(d.get("dielectric_er", 4.4)),
        substrate_height_mm=float(d.get("substrate_height_mm", 1.6)),
        trace_mode=d.get("trace_mode", "CPWG"),
        trace_gap_mm=float(d.get("trace_gap_mm", 0.40)),
        em_sim_type=d.get("em_sim_type", "traces"),
        components=d.get("components", {}),
        additional_reqs=d.get("additional_reqs", [])
    )


def main():
    parser = argparse.ArgumentParser(description="RF AI Suite - Headless Agent Workflow Engine")
    parser.add_argument("--desc", type=str, help="Natural language description of the RF circuit")
    parser.add_argument("--spec-file", type=str, help="Path to existing spec.json")
    parser.add_argument("--name", type=str, default=None, help="Custom project name")
    parser.add_argument("--f0", type=float, default=1.5, help="Center frequency in GHz")
    parser.add_argument("--z0", type=float, default=50.0, help="System impedance in Ohms")
    parser.add_argument("--substrate", type=str, default="FR4", help="Laminate name")
    parser.add_argument("--er", type=float, default=4.4, help="Dielectric constant")
    parser.add_argument("--h", type=float, default=1.6, help="Substrate thickness in mm")
    parser.add_argument("--width", type=float, default=35.0, help="Board width in mm")
    parser.add_argument("--height", type=float, default=20.0, help="Board height in mm")
    parser.add_argument("--em-mode", type=str, choices=["traces", "full_board"], default="traces")
    parser.add_argument("--stages", type=str, default=None, help="Comma-separated list of stages to run")
    parser.add_argument("--output-dir", type=str, default="projects", help="Output directory")
    parser.add_argument("--backend", type=str, choices=["local", "saas", "aws_saas", "aws"], default=os.getenv("RF_BACKEND", "local"), help="Execution backend (local, saas, aws_saas, aws)")
    parser.add_argument("--json", action="store_true", help="Print only JSON summary to stdout")
    args = parser.parse_args()

    spec = None
    if args.spec_file and os.path.exists(args.spec_file):
        spec = load_spec_from_json(args.spec_file)
    elif args.desc:
        spec = parse_custom_circuit(
            description=args.desc,
            title=args.desc,
            f0_ghz=args.f0,
            z0=args.z0,
            width_mm=args.width,
            height_mm=args.height,
            substrate_name=args.substrate,
            er=args.er,
            h_mm=args.h,
            em_sim_type=args.em_mode
        )
        if args.name:
            spec.name = args.name
    else:
        parser.error(
            "A circuit description (--desc '<description>') or an existing specification file "
            "(--spec-file <path>) is required. Presets have been removed; "
            "every circuit must be synthesized from scratch based on user requirements."
        )

    stages = args.stages.split(",") if args.stages else None

    # SaaS Hosted Microservice Execution path (local SaaS or AWS SaaS)
    if args.backend.lower() in ("saas", "aws_saas", "aws"):
        from agent.saas.client import RFSaasClient
        client = RFSaasClient()
        if not args.json:
            print(f"[RF SaaS Client] Dispatching stages {stages or 'ALL'} to Hosted API ({client.base_url})...")
        saas_res = client.run_stages(spec.name, stages=stages, spec=spec.to_dict())
        local_proj = os.path.join(args.output_dir, spec.name)
        client.sync_all_artifacts(spec.name, local_proj)
        if not args.json:
            print(f"✔ SaaS execution complete! Artifacts synced to {local_proj}")
        if args.json:
            print(json.dumps(saas_res, indent=2))
        return

    results = execute_workflow(spec, project_root=args.output_dir, stages=stages, verbose=not args.json)

    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
