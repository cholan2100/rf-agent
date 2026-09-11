# RF Design SaaS Microservice & FastMCP API (`rf-saas`)

This document provides complete documentation for the **Hosted RF Design Microservice & FastMCP Server**.

The SaaS model decouples AI Agent harnesses (Antigravity, Cursor, Claude Code, etc.) from underlying container runtimes, operating system environments, and direct cloud instance administration. The agent interacts with `rf-suite` purely through standard REST endpoints or Model Context Protocol (MCP) tool calls.

---

## 1. Architectural Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │ CLIENT / HARNESS LAYER                                      │
 │ - Antigravity / Cursor / Claude Desktop                     │
 │ - rf-agent Workflow CLI (python -m agent.workflow --backend saas)
 │ - Standard REST / FastMCP Client (RFSaasClient)             │
 └──────────────────────────────┬──────────────────────────────┘
                                │ HTTPS / REST / SSE MCP
                                │ (Bearer Auth Header)
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ HOSTED RF SERVICE (AWS App Runner / Cloud / Local Docker)   │
 │                                                             │
 │  FastAPI Gateway (Port 8000)                                │
 │  ├── REST API: /health, /v1/specs/*, /v1/projects/*         │
 │  └── FastMCP Server: /sse, /messages (JSON-RPC tools)       │
 │                                                             │
 │  Containerized RF Engine (rf-suite:latest)                  │
 │  ├── KiCad 10.0.4 (pcbnew, DRC, vector SVG/PNG rendering)   │
 │  ├── FreeCAD 1.0.0 (3D STEP mechanical model assembly)      │
 │  ├── openEMS v0.37 (3D FDTD EM solver -> Touchstone .sNp)   │
 │  ├── Qucsator-RF 1.0.3 & ngspice 44.2 (Co-simulation)       │
 │  └── RF Scientific Stack (scikit-rf, numpy, scipy)          │
 └─────────────────────────────────────────────────────────────┘
```

### Key Advantages of the SaaS Model
1. **Zero Cloud/OS Administration**: The AI harness never needs SSH keys, AWS Session Manager (SSM) agent, or AWS credentials to run RF designs.
2. **Zero Local Heavy Toolchain Burden**: KiCad 10, FreeCAD 1.0, and openEMS stay entirely in the cloud container.
3. **Instant Tool Invocations via MCP**: LLMs can call RF design stages as native agent tools with typed schemas.
4. **Auto-Scaling & Zero Idle Cost**: Deployed on AWS App Runner, compute scales down to zero provisioned concurrency when idle.

---

## 2. Quick Start

### Running the Server Locally (via Local Docker Container)

#### Windows:
```cmd
rf-suite\bin\rf-saas-server.bat
```

#### Linux / WSL:
```bash
./rf-suite/bin/rf-saas-server
```

The server starts at `http://localhost:8000`. Interactive Swagger API docs are available at `http://localhost:8000/docs`.

### Running Workflow via SaaS Backend

Set `RF_BACKEND=saas` and `RF_SAAS_URL=http://localhost:8000` in `.env`:
```bash
python -m agent.workflow --desc "10dB symmetric Pi-attenuator for 2.4GHz Wi-Fi band" --backend saas
```

---

## 3. REST API Reference

All requests accept and return standard JSON. When `RF_API_KEY` is configured on the server, requests must include the header:
```http
Authorization: Bearer <your-api-key>
```

### 3.1 Health & Toolchain Status
- **Endpoint**: `GET /health`
- **Description**: Returns server status, uptime, and installed tool versions (KiCad, FreeCAD, openEMS, Qucsator).
- **Example Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "tools": {
    "kicad": "10.0.4",
    "freecad": "1.0.0",
    "openems": "v0.37.0-rc2",
    "qucsator": "1.0.3"
  },
  "auth_required": false
}
```

### 3.2 Synthesize Circuit Specification
- **Endpoint**: `POST /v1/specs/synthesize`
- **Description**: Autonomously parses a high-level circuit description, computes physical line parameters (CPWG trace width, dielectric constants), and returns a complete `CircuitSpecModel`.
- **Request Body**:
```json
{
  "description": "10dB symmetric Pi-attenuator for 2.4GHz Wi-Fi band with 50Ω CPWG lines",
  "project_name": "pi_attenuator_2p4ghz",
  "z0": 50.0,
  "f0_ghz": 2.4,
  "substrate": "FR4",
  "h_mm": 1.6
}
```
- **Example Response**:
```json
{
  "name": "pi_attenuator_2p4ghz",
  "title": "10dB Symmetric Pi-Attenuator (2.4GHz)",
  "topology": "pi_attenuator",
  "f0_ghz": 2.4,
  "z0": 50.0,
  "attenuation_db": 10.0,
  "rf_trace_width_mm": 1.87,
  "rf_gap_mm": 0.4,
  "effective_dielectric_constant": 2.88,
  "substrate_name": "FR4",
  "dielectric_h_mm": 1.6,
  "er": 4.4,
  "components": [
    {"ref": "R1", "value": "96.2", "footprint": "Resistor_SMD:R_0805_2012Metric", "package": "0805"},
    {"ref": "R2", "value": "71.2", "footprint": "Resistor_SMD:R_0805_2012Metric", "package": "0805"},
    {"ref": "R3", "value": "96.2", "footprint": "Resistor_SMD:R_0805_2012Metric", "package": "0805"}
  ]
}
```

### 3.3 Execute Workflow Stage
- **Endpoint**: `POST /v1/projects/{project_id}/run`
- **Description**: Runs one or more EDA/physics workflow stages for a specified project.
- **Path Parameter**: `project_id` (string, e.g. `pi_attenuator_2p4ghz`)
- **Request Body**:
```json
{
  "stage": "schematic",
  "spec": { ... }
}
```
Supported `stage` values:
- `schematic`: Generates `.kicad_sch`, exports SVG, renders high-DPI zoomed schematic.
- `pcb`: Routes CPWG lines, pours ground zones, executes DRC.
- `render`: Raytraces photorealistic isometric, top, and bottom 3D board views.
- `cad`: FreeCAD 1.0 mechanical model generation and `.step` export.
- `em`: openEMS 3D FDTD full-wave electromagnetic S-parameter extraction.
- `qucs`: Qucsator linear co-simulation.
- `charts`: S-parameter dB plots, Smith chart, Stability K, and input impedance.
- `gerbers`: Production Gerber archive (`gerbers.zip`).
- `report`: Comprehensive `PERFORMANCE_REPORT.md` and BOM.

- **Example Response**:
```json
{
  "status": "success",
  "project_id": "pi_attenuator_2p4ghz",
  "stage": "schematic",
  "duration_seconds": 1.45,
  "artifacts": [
    "pi_attenuator_2p4ghz.kicad_sch",
    "schematic.svg",
    "schematic_zoomed.png"
  ],
  "drc_errors": null,
  "message": "Stage schematic completed in 1.45s"
}
```

### 3.4 Get Project Summary
- **Endpoint**: `GET /v1/projects/{project_id}/summary`
- **Description**: Inspects project directory, lists all generated artifacts, and returns DRC status if available.

### 3.5 Download Project Artifacts
- **Endpoint**: `GET /v1/projects/{project_id}/artifacts/{file_path:path}`
- **Description**: Streams project artifacts (PNG renders, Gerber ZIPs, STEP files, SVG schematics, Touchstone `.s2p` files) with appropriate MIME types.
- **Example**: `GET /v1/projects/pi_attenuator/artifacts/iso_render.png`

---

## 4. Model Context Protocol (FastMCP) Integration

The SaaS service includes a built-in **FastMCP** server (`agent/saas/mcp_server.py`), allowing AI agents in Antigravity or Cursor to invoke RF design capabilities directly as native tool calls.

### Launching FastMCP Server

```bash
# Windows
rf-suite\bin\rf-run.bat python -m agent.saas.mcp_server

# Linux / WSL
./rf-suite/bin/rf-run python3 -m agent.saas.mcp_server
```

### Client Configuration (Cursor / Antigravity / Claude Desktop)

Add the following to your `mcpServers` configuration (`claude_desktop_config.json` or cursor settings):

```json
{
  "mcpServers": {
    "rf-suite": {
      "command": "rf-suite/bin/rf-run.bat",
      "args": ["python", "-m", "agent.saas.mcp_server"]
    }
  }
}
```

Or over SSE against a hosted deployment:
```json
{
  "mcpServers": {
    "rf-suite-cloud": {
      "url": "https://api.rf-suite.yourdomain.com/sse",
      "headers": {
        "Authorization": "Bearer <YOUR_RF_API_KEY>"
      }
    }
  }
}
```

### Exposed MCP Tools

1. `synthesize_rf_circuit`: Synthesizes mathematical RF circuit specs, dielectric calculations, and component values from prompt.
2. `run_workflow_stage`: Executes a specific EDA or simulation stage (`schematic`, `pcb`, `render`, `cad`, `em`, `qucs`, `charts`, `gerbers`, `report`).
3. `check_pcb_drc`: Headless KiCad 10 DRC check returning unrouted nets and clearance violations.
4. `get_rf_circuit_summary`: Fetches project status, generated artifacts, and S-parameter metrics.

---

## 5. Python Client (`RFSaasClient`)

The client lives in [`agent/saas/client.py`](file:///d:/Workspace/rf/rf-agent-ai/agent/saas/client.py) and uses **only standard library modules** (`urllib.request`, `json`), requiring zero external dependencies on the client workstation.

### Usage Example:
```python
from agent.saas.client import RFSaasClient

# Connect to hosted service
client = RFSaasClient(base_url="https://api.rf-suite.yourdomain.com", api_key="secret-token")

# Check service health
health = client.health()
print(f"Connected to RF Suite v{health['version']} with tools: {health['tools']}")

# Synthesize circuit
spec = client.synthesize_spec("10dB Pi-attenuator for 2.4GHz", project_name="my_attenuator")

# Execute schematic and render
result = client.run_stage("my_attenuator", "schematic", spec=spec)
print(f"Schematic generated: {result['artifacts']}")

# Download isometric 3D render
client.download_artifact("my_attenuator", "iso_render.png", "local_iso.png")
```

---

## 6. AWS App Runner 1-Click Deployment

AWS App Runner provides fully managed container execution, automated TLS certificates, auto-scaling, and zero provisioned concurrency costs when idle.

### Automated Deployment via CLI
```bash
python aws/deploy_saas.py --region us-east-1 --api-key "my-secure-rf-key"
```

The script:
1. Validates AWS credentials.
2. Creates an Amazon ECR repository `rf-suite-saas`.
3. Builds and pushes the `rf-suite:latest` Docker image to ECR.
4. Deploys the CloudFormation stack [`aws/saas_apprunner.yaml`](file:///d:/Workspace/rf/rf-agent-ai/aws/saas_apprunner.yaml).
5. Returns the live HTTPS service URL (e.g. `https://xyz123.us-east-1.awsapprunner.com`).
