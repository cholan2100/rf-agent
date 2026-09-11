"""
FastAPI Microservice Engine for Hosted RF Design SaaS.
Exposes REST endpoints for circuit synthesis, layout routing, 3D raytracing,
full-wave EM simulation, co-simulation, and artifact delivery.
"""

import os
import sys
import glob
import json
import shutil
import platform
import subprocess
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Security, Depends, status, Query
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .models import (
    SynthesizeRequest,
    CircuitSpecModel,
    StageRunRequest,
    StageRunResponse,
    CircuitSummaryResponse,
    HealthResponse
)

# Ensure agent package is in pythonpath
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from agent.spec import CircuitSpec, parse_custom_circuit
from agent.workflow import execute_workflow, ALL_STAGES


app = FastAPI(
    title="RF Suite Cloud Design Engine API",
    description="Autonomous RF/Microwave hardware engineering & multi-physics simulation SaaS microservice.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for web dashboards and IDE integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECTS_ROOT = os.getenv("RF_PROJECTS_ROOT", os.path.join(repo_root, "projects"))
API_KEY = os.getenv("RF_SAAS_API_KEY", "")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    query_key: Optional[str] = Security(api_key_query)
):
    """Verifies API Key if RF_SAAS_API_KEY is configured."""
    if not API_KEY:
        return True  # Open if no key configured
    key = header_key or query_key
    if key == API_KEY:
        return True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key"
    )


def get_tool_versions() -> Dict[str, str]:
    """Inspects installed EDA tool versions."""
    versions = {}
    
    # KiCad
    try:
        res = subprocess.run(["kicad-cli", "version"], capture_output=True, text=True, timeout=5)
        versions["kicad"] = res.stdout.strip() if res.returncode == 0 else "kicad-cli not found"
    except Exception:
        versions["kicad"] = "not installed"

    # FreeCAD
    try:
        res = subprocess.run(["freecadcmd", "--version"], capture_output=True, text=True, timeout=5)
        versions["freecad"] = res.stdout.strip() if res.returncode == 0 else "FreeCADCmd not found"
    except Exception:
        versions["freecad"] = "not installed"

    # openEMS
    try:
        res = subprocess.run(["openEMS", "--version"], capture_output=True, text=True, timeout=5)
        versions["openems"] = res.stdout.strip() if res.returncode == 0 else "openEMS available"
    except Exception:
        versions["openems"] = "available via octave/python"

    # Qucsator
    try:
        res = subprocess.run(["qucsator", "--version"], capture_output=True, text=True, timeout=5)
        versions["qucsator"] = res.stdout.strip().split("\n")[0] if res.returncode == 0 else "qucsator not found"
    except Exception:
        versions["qucsator"] = "not installed"

    return versions


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint reporting solver readiness and versions."""
    return HealthResponse(
        status="healthy",
        service="rf-suite-saas",
        version="1.0.0",
        backend="cloud_container",
        eda_tools=get_tool_versions(),
        python_version=platform.python_version(),
        platform=platform.platform()
    )


@app.post("/v1/specs/synthesize", response_model=Dict[str, Any], dependencies=[Depends(verify_api_key)])
def synthesize_spec(req: SynthesizeRequest):
    """
    Synthesizes a complete CircuitSpec (with math, transmission line dimensions,
    and component selections) from a natural language circuit description.
    """
    try:
        spec = parse_custom_circuit(
            description=req.prompt,
            title=req.prompt,
            z0=req.z0_ohm,
            f0_ghz=req.f_0_ghz if req.f_0_ghz is not None else 1.5,
            substrate_name=req.substrate,
            er=req.er,
            h_mm=req.h_mm
        )
        if req.name:
            spec.name = req.name
        return spec.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to synthesize circuit spec: {str(e)}")


@app.get("/v1/projects", response_model=List[str], dependencies=[Depends(verify_api_key)])
def list_projects():
    """Lists existing circuit projects in the workspace."""
    if not os.path.exists(PROJECTS_ROOT):
        return []
    return [
        d for d in os.listdir(PROJECTS_ROOT)
        if os.path.isdir(os.path.join(PROJECTS_ROOT, d))
    ]


@app.post("/v1/projects/{project_name}/run", response_model=StageRunResponse, dependencies=[Depends(verify_api_key)])
def run_project_stages(project_name: str, req: StageRunRequest):
    """
    Executes one or more modular engineering stages for a circuit project.
    Stages: schematic, pcb, render, cad, em, qucs, charts, gerbers, report.
    """
    os.makedirs(PROJECTS_ROOT, exist_ok=True)
    project_dir = os.path.join(PROJECTS_ROOT, project_name)
    spec_path = os.path.join(project_dir, "spec.json")

    spec = None
    # 1. Spec provided in payload
    if req.spec:
        spec = CircuitSpec.from_dict(req.spec)
        spec.name = project_name
    # 2. Spec on disk
    elif os.path.exists(spec_path):
        with open(spec_path, "r", encoding="utf-8") as f:
            spec = CircuitSpec.from_dict(json.load(f))
    # 3. Prompt description provided
    elif req.desc:
        spec = parse_custom_circuit(description=req.desc, title=req.desc)
        spec.name = project_name
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' has no spec.json on server and no spec/desc was provided."
        )

    stages_to_run = req.stages if req.stages else ALL_STAGES
    for stg in stages_to_run:
        if stg not in ALL_STAGES:
            raise HTTPException(status_code=400, detail=f"Invalid stage '{stg}'. Valid stages: {ALL_STAGES}")

    try:
        results = execute_workflow(
            spec=spec,
            project_root=PROJECTS_ROOT,
            stages=stages_to_run,
            verbose=False
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")

    # Collect available artifact relative paths
    artifacts = {}
    if os.path.exists(project_dir):
        for root, _, files in os.walk(project_dir):
            for file in files:
                rel = os.path.relpath(os.path.join(root, file), project_dir).replace("\\", "/")
                artifacts[rel] = f"/v1/projects/{project_name}/artifacts/{rel}"

    return StageRunResponse(
        project_name=project_name,
        status=results.get("status", "completed"),
        executed_stages=stages_to_run,
        stage_results=results.get("stages", {}),
        artifacts=artifacts,
        summary=results.get("spec", {})
    )


@app.get("/v1/projects/{project_name}/summary", response_model=CircuitSummaryResponse, dependencies=[Depends(verify_api_key)])
def get_project_summary(project_name: str):
    """Returns project metadata, DRC violation metrics, S-parameters, and artifacts list."""
    project_dir = os.path.join(PROJECTS_ROOT, project_name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    summary_file = os.path.join(project_dir, "summary.json")
    spec_file = os.path.join(project_dir, "spec.json")
    drc_file = os.path.join(project_dir, f"{project_name}_drc.json")

    spec_data = {}
    if os.path.exists(spec_file):
        with open(spec_file, "r", encoding="utf-8") as f:
            spec_data = json.load(f)

    stages_data = {}
    if os.path.exists(summary_file):
        with open(summary_file, "r", encoding="utf-8") as f:
            stages_data = json.load(f).get("stages", {})

    drc_violations = 0
    drc_warnings = 0
    if os.path.exists(drc_file):
        try:
            with open(drc_file, "r", encoding="utf-8") as f:
                drc_json = json.load(f)
                violations = drc_json.get("violations", [])
                drc_violations = len([v for v in violations if v.get("severity") == "error"])
                drc_warnings = len([v for v in violations if v.get("severity") == "warning"])
        except Exception:
            pass

    artifacts = {}
    for root, _, files in os.walk(project_dir):
        for file in files:
            rel = os.path.relpath(os.path.join(root, file), project_dir).replace("\\", "/")
            artifacts[rel] = f"/v1/projects/{project_name}/artifacts/{rel}"

    return CircuitSummaryResponse(
        name=project_name,
        title=spec_data.get("title", project_name),
        status="active",
        drc_violations=drc_violations,
        drc_warnings=drc_warnings,
        spec=spec_data,
        stages=stages_data,
        artifacts=artifacts
    )


@app.get("/v1/projects/{project_name}/artifacts/{file_path:path}", dependencies=[Depends(verify_api_key)])
def get_project_artifact(project_name: str, file_path: str):
    """Directly streams or downloads a generated deliverable file (.png, .kicad_pcb, .step, .s2p, .zip)."""
    project_dir = os.path.join(PROJECTS_ROOT, project_name)
    full_path = os.path.abspath(os.path.join(project_dir, file_path))

    # Path traversal protection
    if not full_path.startswith(os.path.abspath(project_dir)):
        raise HTTPException(status_code=403, detail="Forbidden path traversal")

    if not os.path.exists(full_path) or os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail=f"Artifact '{file_path}' not found")

    mime_types = {
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".jpg": "image/jpeg",
        ".json": "application/json",
        ".s2p": "text/plain",
        ".s1p": "text/plain",
        ".dat": "text/plain",
        ".net": "text/plain",
        ".kicad_sch": "text/plain",
        ".kicad_pcb": "text/plain",
        ".step": "application/octet-stream",
        ".fcstd": "application/octet-stream",
        ".zip": "application/zip",
        ".drl": "text/plain",
        ".gbr": "text/plain",
        ".gtl": "text/plain",
        ".gbl": "text/plain"
    }
    ext = os.path.splitext(full_path)[1].lower()
    media_type = mime_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=full_path,
        media_type=media_type,
        filename=os.path.basename(full_path)
    )
