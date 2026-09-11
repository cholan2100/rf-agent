"""
Pydantic Data Models for RF Suite Hosted SaaS Microservice & MCP API.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class SynthesizeRequest(BaseModel):
    prompt: str = Field(..., description="Natural language description of the RF circuit (e.g. '10dB Pi attenuator for 2.4GHz')")
    name: Optional[str] = Field(None, description="Optional custom machine name for the circuit project")
    f_0_ghz: Optional[float] = Field(None, description="Optional center frequency in GHz")
    z0_ohm: float = Field(50.0, description="Target characteristic impedance (default: 50.0 Ohms)")
    substrate: str = Field("FR4", description="Substrate material name (default: FR4)")
    er: float = Field(4.4, description="Relative dielectric constant (default: 4.4)")
    h_mm: float = Field(1.6, description="Substrate thickness in millimeters (default: 1.6mm)")
    trace_gap_mm: float = Field(0.40, description="CPWG ground clearance gap in mm (default: 0.40mm)")


class CircuitSpecModel(BaseModel):
    name: str
    title: str
    topology: str
    description: str
    f_min_ghz: float
    f_0_ghz: float
    f_max_ghz: float
    z0_ohm: float = 50.0
    target_s21_db: Optional[float] = None
    target_s11_db: Optional[float] = None
    target_s22_db: Optional[float] = None
    width_mm: float = 35.0
    height_mm: float = 20.0
    substrate_name: str = "FR4"
    dielectric_er: float = 4.4
    substrate_height_mm: float = 1.6
    trace_mode: str = "CPWG"
    trace_gap_mm: float = 0.40
    rf_trace_width_mm: float = 1.87
    effective_dielectric_constant: float = 2.88
    em_sim_type: str = "traces"
    components: Dict[str, Any] = Field(default_factory=dict)
    additional_reqs: List[str] = Field(default_factory=list)


class StageRunRequest(BaseModel):
    stages: Optional[List[str]] = Field(
        None,
        description="List of stages to execute (e.g. ['schematic', 'pcb']). If omitted, executes all remaining stages."
    )
    spec: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional full CircuitSpec JSON override. If omitted, uses existing project spec."
    )
    desc: Optional[str] = Field(
        None,
        description="Optional natural language prompt to synthesize spec if project does not exist yet."
    )


class StageRunResponse(BaseModel):
    project_name: str
    status: str
    executed_stages: List[str]
    stage_results: Dict[str, Any]
    artifacts: Dict[str, str] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class CircuitSummaryResponse(BaseModel):
    name: str
    title: str
    status: str
    drc_violations: int = 0
    drc_warnings: int = 0
    spec: Dict[str, Any] = Field(default_factory=dict)
    stages: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, str] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    backend: str
    eda_tools: Dict[str, str]
    python_version: str
    platform: str
