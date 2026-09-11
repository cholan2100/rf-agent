"""
Remote Model Context Protocol (MCP) Server for RF Suite.
Enables AI Agents (Google Antigravity, Cursor, Claude Code) to invoke
cloud RF engineering tools as first-class native tool declarations over SSE or Stdio.
"""

import os
import sys
import json
from typing import Optional, List

# Ensure agent package in pythonpath
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from fastmcp import FastMCP
from agent.spec import CircuitSpec, parse_custom_circuit
from agent.workflow import execute_workflow, ALL_STAGES

# Initialize FastMCP Server
mcp = FastMCP(
    "RF Suite Cloud Engine",
    description="Autonomous RF/Microwave hardware engineering, PCB layout, and multi-physics EM simulation toolchain."
)

PROJECTS_ROOT = os.getenv("RF_PROJECTS_ROOT", os.path.join(repo_root, "projects"))


@mcp.tool()
def synthesize_rf_circuit(
    prompt: str,
    name: Optional[str] = None,
    f_0_ghz: Optional[float] = None,
    z0_ohm: float = 50.0,
    substrate: str = "FR4"
) -> str:
    """
    Synthesize mathematical design parameters, CPWG transmission line dimensions,
    and component values for an RF circuit from a natural language prompt.
    """
    spec = parse_custom_circuit(
        description=prompt,
        title=prompt,
        f0_ghz=f_0_ghz if f_0_ghz is not None else 1.5,
        z0=z0_ohm,
        substrate_name=substrate
    )
    if name:
        spec.name = name
    return json.dumps(spec.to_dict(), indent=2)


@mcp.tool()
def run_workflow_stage(
    project_name: str,
    stage: str,
    spec_json: Optional[str] = None
) -> str:
    """
    Execute a specific RF engineering workflow stage.
    Allowed stages: 'schematic', 'pcb', 'render', 'cad', 'em', 'qucs', 'charts', 'gerbers', 'report'.
    """
    if stage not in ALL_STAGES:
        return f"Error: Invalid stage '{stage}'. Must be one of: {ALL_STAGES}"

    project_dir = os.path.join(PROJECTS_ROOT, project_name)
    spec = None

    if spec_json:
        spec = CircuitSpec.from_dict(json.loads(spec_json))
        spec.name = project_name
    elif os.path.exists(os.path.join(project_dir, "spec.json")):
        with open(os.path.join(project_dir, "spec.json"), "r", encoding="utf-8") as f:
            spec = CircuitSpec.from_dict(json.load(f))
    else:
        return f"Error: Project '{project_name}' has no spec.json on server and no spec_json was provided."

    results = execute_workflow(
        spec=spec,
        project_root=PROJECTS_ROOT,
        stages=[stage],
        verbose=False
    )
    return json.dumps(results, indent=2)


@mcp.tool()
def check_pcb_drc(project_name: str) -> str:
    """
    Check the Design Rule Check (DRC) report for a generated KiCad 10 PCB.
    Returns error count, warning count, and violations.
    """
    drc_path = os.path.join(PROJECTS_ROOT, project_name, f"{project_name}_drc.json")
    if not os.path.exists(drc_path):
        return f"DRC report for '{project_name}' not found. Run 'pcb' stage first."
    with open(drc_path, "r", encoding="utf-8") as f:
        return f.read()


@mcp.tool()
def get_rf_circuit_summary(project_name: str) -> str:
    """
    Retrieve the full engineering status summary, component BOM, and S-parameters for a circuit.
    """
    summary_path = os.path.join(PROJECTS_ROOT, project_name, "summary.json")
    if not os.path.exists(summary_path):
        return f"Summary for '{project_name}' not found."
    with open(summary_path, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    # If run directly with arguments e.g. run sse or stdio
    mcp.run()
