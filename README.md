# RF Workbench - Dockerized RF & Microwave Engineering Suite

An all-in-one containerized Linux engineering suite designed for RF, microwave, PCB design, and electromagnetic co-simulation workflows.

This project packages all the tools, solvers, CAD suites, workbenches, and Python libraries utilized in advanced RF design workflows (such as the **FM Radio LNA Design**), enabling you, collaborators, and autonomous AI coding agents to plug in any current or future RF project folder without installing heavy EDA and CAD software on the host machine.

---

## 1. Tool Suite Inventory

| Tool / Library | Version / Scope | Primary Role in RF Workflows |
| :--- | :--- | :--- |
| **KiCad 8** | 8.0 Release (`kicad`, `kicad-cli`) | Schematic capture, DRC verification, Gerber/drill export, 3D STEP & raytrace rendering |
| **KiCad Python (`pcbnew`)** | Full C++ Python API | Programmatic PCB generation, automated trace routing, via stitching, copper pours |
| **openEMS & CSXCAD** | v0.0.36 + Python bindings | 3D full-wave FDTD electromagnetic solver, multi-port S-parameter extraction, Touchstone generation |
| **AppCSXCAD** | GUI 3D Mesh Viewer | Visual inspection of openEMS 3D geometries, bounding boxes, excitation ports, and FDTD grids |
| **Qucs-S** | v24.x + GUI | Circuit schematic capture, Touchstone `.s4p` co-simulation, AC/DC analysis, harmonic balance |
| **qucsator-rf** | RF solver fork | High-speed headless S-parameter evaluation, stability factor ($K, \mu$) calculation |
| **ngspice** | ngspice-46 | SPICE circuit simulation, non-linear transistor DC bias & transient analysis |
| **FreeCAD** | 0.21 / 1.0 + Python API | Headless 3D CAD modeling, STEP/STL export, automated boolean collision/clearance checks |
| **freecad-microwave** | Workbench | Transmission line calculators (CPWG, microstrip, stripline), FreeCAD-to-openEMS export |
| **RF-tools-KiCAD** | KiCad Action Plugin | Automated via fence stitching, circular trace rounding, track length matching, solder mask expanders |
| **kicad-mcp-server** | FastMCP Server | AI agent schematic synthesis, symbol library extractor, headless DRC/ERC inspectors |
| **scikit-rf (`skrf`)** | Latest | S-parameter matrix math, interpolation, de-embedding, Smith chart plotting, Touchstone I/O |
| **Python Scientific** | `numpy`, `scipy`, `matplotlib`, `pandas`, `h5py` | Numerical calculation, data analysis, publication-grade RF plotting |
| **Mask Rendering** | `pypdfium2`, `pillow`, `cairosvg`, `svglib` | High-DPI rasterization of PCB photomasks, etching films, and vector diagrams |
| **Web GUI Desktop** | **noVNC + Openbox** (Port 6080) | Zero-install interactive desktop accessible in your browser (no Windows X-server required) |

---

## 2. Prerequisites

1. **Docker Desktop** (or Docker Engine on Linux):
   - For Windows: Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) with **WSL 2 backend** enabled.
   - For Linux: Standard Docker Engine and `docker compose-plugin`.

---

## 3. Quick Start

### Step 1: Open Terminal in `rf-workbench`
```powershell
cd D:\Workspace\rf\rf-workbench
```

### Step 2: Build the Container Image
```powershell
docker compose build
```
*(This compiles openEMS, qucsator-rf, installs KiCad 8, FreeCAD, and all Python dependencies. Subsequent runs use Docker's layer cache).*

### Step 3: Start the Environment
```powershell
docker compose up -d
```

### Step 4: Open the Web Desktop
Navigate to **[http://localhost:6080/vnc.html](http://localhost:6080/vnc.html)** in Edge, Chrome, or Firefox.
- You will see a clean graphical desktop with Openbox window manager.
- Right-click anywhere on the desktop to launch **KiCad, Qucs-S, FreeCAD, AppCSXCAD**, or a **Terminal**.
- Default VNC password: `rfworkbench` (configurable in `.env`).

Or simply double-click **`bin\rf-gui.bat`** in Windows Explorer!

---

## 4. How to Plug in Project Files

This environment is designed so projects live on your host machine while all computation, CAD rendering, and simulation occur inside the container.

### Option A: Mount Sibling RF Projects (Default)
By default, `.env` mounts `..` (the parent directory `D:\Workspace\rf`):
```ini
PROJECT_PATH=..
```
Inside the container, `/workspace` gives immediate access to all existing and future RF projects:
- `/workspace/lna-ai/`
- `/workspace/LNA_FM_thin_v2/`
- `/workspace/adsb-hackrf/`
- `/workspace/mw_filter_900mhz/`

### Option B: Mount a Specific Project
To isolate the container to a specific project folder:
In `.env`:
```ini
PROJECT_PATH=../lna-ai
# or absolute path:
# PROJECT_PATH=D:\Workspace\rf\lna-ai
```
Now `/workspace` is that project's root folder.

### Option C: On-The-Fly Mount via Command Line
Run any script on any folder without modifying `.env`:
```powershell
docker compose run --rm -v "D:\Projects\FilterDesign:/workspace" rf-workbench python run_simulation.py
```

---

## 5. Convenience Launchers (`bin/`)

For maximum productivity on Windows, pre-configured shortcuts are in `bin/`:

| Shortcut | Description |
| :--- | :--- |
| **`bin\rf-gui.bat`** (or `.ps1`) | Starts the container and opens the noVNC interactive desktop in your browser. |
| **`bin\rf-bash.bat`** (or `.ps1`) | Opens an interactive bash terminal inside `/workspace`. |
| **`bin\rf-run.bat <command>`** | Executes any command/script headlessly inside the container. |
| **`bin\rf-kicad.bat`** | Launches KiCad GUI on the desktop and opens your browser. |
| **`bin\rf-qucs.bat`** | Launches Qucs-S GUI on the desktop and opens your browser. |
| **`bin\rf-freecad.bat`** | Launches FreeCAD GUI on the desktop and opens your browser. |
| **`bin\rf-openems.bat`** | Launches AppCSXCAD 3D mesh viewer on the desktop. |

### Examples of `rf-run`:
```powershell
# Run the FM LNA PCB generator:
bin\rf-run python lna-ai/kicad/build_clean_lna_pcb.py

# Run openEMS 4-port FDTD simulation:
bin\rf-run python lna-ai/openems/simulate_full_board_4port.py

# Run Qucs RF co-simulation:
bin\rf-run python lna-ai/qucs-sim/run_full_board_cosim.py

# Run headless DRC check:
bin\rf-run kicad-cli pcb drc lna-ai/kicad/lna_fm_98mhz.kicad_pcb

# Generate high-res photomasks:
bin\rf-run python lna-ai/kicad/render_masks.py
```

---

## 6. Verifying the Installation

To verify that all tools, solvers, Python APIs, and workbenches are operational:

```powershell
bin\rf-run python /opt/rf-linux-env/tests/verify_environment.py
```

The diagnostic test verifies:
- [x] KiCad CLI (`kicad-cli`) and Python API (`pcbnew`)
- [x] FreeCAD CLI (`freecadcmd`) and Python API (`FreeCAD`, `Part`, `Mesh`)
- [x] FreeCAD Microwave Workbench (`Microwave.Solvers.openems`)
- [x] openEMS binary and Python modules (`CSXCAD`, `openEMS`)
- [x] Qucs-S solvers (`qucsator`, `qucsator_rf`, `ngspice`)
- [x] scikit-rf (`skrf`) Touchstone reading & matrix analysis
- [x] High-DPI mask rendering (`pypdfium2`, `PIL`)
- [x] kicad-mcp-server integration
- [x] RF-tools-KiCAD plugin directory

---

## 7. Putting this Project onto GitHub

This repository is completely self-contained and pre-configured with a clean `.gitignore`. To publish it to GitHub:

```powershell
cd D:\Workspace\rf\rf-workbench

# Initialize git repository
git init

# Stage files (ignores .env, caches, and logs automatically)
git add .

# Create initial commit
git commit -m "feat: initial commit of RF workbench docker compose linux environment"

# Link to your remote GitHub repository
git branch -M main
git remote add origin https://github.com/<your-username>/rf-workbench.git

# Push to GitHub
git push -u origin main
```

---

## 8. Directory Architecture

```
rf-workbench/
├── docker-compose.yml              # Primary container & volume orchestrator
├── Dockerfile                      # Layered Dockerfile installing all EDA & RF tools
├── .env.example                    # Template environment variables (committed)
├── .env                            # Active settings (project mount, resolution, ports; git-ignored)
├── .gitignore                      # Git ignore rules for clean repo maintenance
├── entrypoint.sh                   # Dual-mode startup (Xvfb, noVNC desktop, CLI runner)
├── requirements.txt                # Python RF, CAD, simulation, and rendering packages
├── config/
│   ├── openbox-rc.xml              # Lightweight window manager settings & keybindings
│   └── openbox-menu.xml            # Desktop right-click menu for KiCad, Qucs-S, FreeCAD, AppCSXCAD
├── scripts/
│   ├── install_openems.sh          # Builds openEMS, CSXCAD, and Python bindings
│   ├── install_qucs.sh             # Installs Qucs-S, qucsator-rf, and ngspice
│   └── setup_plugins.sh            # Installs RF-tools-KiCAD, FreeCAD-Microwave, kicad-mcp-server
├── bin/                            # Windows convenience launchers (.bat and .ps1)
│   ├── rf-bash.bat / .ps1          # Interactive bash shell
│   ├── rf-run.bat / .ps1           # Headless command runner
│   ├── rf-gui.bat / .ps1           # Web browser desktop launcher
│   ├── rf-kicad.bat                # Direct KiCad shortcut
│   ├── rf-qucs.bat                 # Direct Qucs-S shortcut
│   ├── rf-freecad.bat              # Direct FreeCAD shortcut
│   └── rf-openems.bat              # Direct AppCSXCAD shortcut
├── tests/
│   └── verify_environment.py       # Comprehensive diagnostic verification suite
└── README.md                       # Complete documentation & usage guide
```
