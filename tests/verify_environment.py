#!/usr/bin/env python3
"""
Diagnostic & Verification Test Suite for RF Workbench Linux Environment.
Validates all tools, Python modules, solvers, and workbenches used in FM Radio LNA Design.
"""

import sys
import subprocess
import os

print("=" * 70)
print("  RF Workbench Linux Environment - System Verification")
print("=" * 70)

results = []

def test_check(name, func):
    try:
        ok, msg = func()
        status = "[PASS]" if ok else "[FAIL]"
        results.append((name, ok, msg))
        print(f" {status:6s} | {name:<35} | {msg}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f" {'[FAIL]':6s} | {name:<35} | Exception: {e}")

# 1. KiCad CLI
def check_kicad_cli():
    try:
        res = subprocess.run(["kicad-cli", "--version"], capture_output=True, text=True, timeout=10)
        return res.returncode == 0, res.stdout.strip() or "Installed"
    except Exception as e:
        return False, str(e)
test_check("KiCad CLI (kicad-cli)", check_kicad_cli)

# 2. KiCad Python API (pcbnew)
def check_pcbnew():
    try:
        import pcbnew
        board = pcbnew.BOARD()
        return True, f"Loaded pcbnew (KiCad {pcbnew.GetBuildVersion()})"
    except Exception as e:
        return False, str(e)
test_check("KiCad Python API (pcbnew)", check_pcbnew)

# 3. FreeCAD CLI
def check_freecad_cli():
    try:
        res = subprocess.run(["freecadcmd", "--version"], capture_output=True, text=True, timeout=10)
        return res.returncode == 0, res.stdout.strip() or "Installed"
    except Exception as e:
        return False, str(e)
test_check("FreeCAD CLI (freecadcmd)", check_freecad_cli)

# 4. FreeCAD Python API
def check_freecad_python():
    try:
        import FreeCAD
        import Part
        import Mesh
        box = Part.makeBox(10, 10, 10)
        return True, f"FreeCAD {FreeCAD.Version()[0]}.{FreeCAD.Version()[1]} (Solid Volume: {box.Volume:.1f})"
    except Exception as e:
        return False, str(e)
test_check("FreeCAD Python (FreeCAD, Part)", check_freecad_python)

# 5. FreeCAD Microwave Workbench
def check_freecad_microwave():
    try:
        from Microwave.Solvers.openems import preflight, read, run, write
        from Microwave.Solvers.openems.materials import VACUUM_PERMITTIVITY
        return True, f"Microwave Workbench OK (eps_0 = {VACUUM_PERMITTIVITY:.3e})"
    except Exception as e:
        return False, str(e)
test_check("FreeCAD Microwave Workbench", check_freecad_microwave)

# 6. openEMS Binary
def check_openems_bin():
    try:
        res = subprocess.run(["openEMS"], capture_output=True, text=True, timeout=10)
        # openEMS outputs version header to stdout even without args
        out = res.stdout + res.stderr
        for line in out.splitlines():
            if "openEMS" in line and "version" in line:
                return True, line.strip().strip("|").strip()
        return True, "openEMS executable OK"
    except Exception as e:
        return False, str(e)
test_check("openEMS FDTD Solver", check_openems_bin)

# 7. openEMS Python Bindings
def check_openems_python():
    try:
        import CSXCAD
        import openEMS
        csx = CSXCAD.ContinuousStructure()
        grid = csx.GetGrid()
        return True, "openEMS and CSXCAD Python modules imported OK"
    except Exception as e:
        return False, str(e)
test_check("openEMS / CSXCAD Python API", check_openems_python)

# 8. Qucsator RF Solver
def check_qucsator():
    try:
        res = subprocess.run(["qucsator", "-v"], capture_output=True, text=True, timeout=10)
        first_line = (res.stdout + res.stderr).splitlines()[0] if (res.stdout or res.stderr) else "Installed"
        return res.returncode == 0 or "Qucsator" in first_line, first_line.strip()
    except Exception as e:
        return False, str(e)
test_check("qucsator / qucsator_rf Solver", check_qucsator)

# 9. ngspice Engine
def check_ngspice():
    try:
        res = subprocess.run(["ngspice", "-v"], capture_output=True, text=True, timeout=10)
        out = res.stdout + res.stderr
        for line in out.splitlines():
            if "ngspice" in line and "Circuit" in line:
                return True, line.strip().strip("*").strip()
        return True, "ngspice OK"
    except Exception as e:
        return False, str(e)
test_check("ngspice Circuit Simulator", check_ngspice)

# 10. scikit-rf (skrf)
def check_skrf():
    try:
        import skrf as rf
        freq = rf.Frequency(88, 108, 101, 'mhz')
        return True, f"scikit-rf {rf.__version__} (Frequency sweep: {freq.npoints} pts)"
    except Exception as e:
        return False, str(e)
test_check("scikit-rf (skrf)", check_skrf)

# 11. High-DPI Rendering (pypdfium2 & Pillow)
def check_rendering():
    try:
        import pypdfium2
        import PIL.Image
        v_pdf = getattr(pypdfium2, "V_PYPDFIUM2", getattr(pypdfium2, "__version__", "5.x"))
        return True, f"pypdfium2 {v_pdf}, Pillow {PIL.__version__}"
    except Exception as e:
        return False, str(e)
test_check("Mask Rendering (pypdfium2 & PIL)", check_rendering)

# 12. kicad-mcp-server
def check_mcp_server():
    try:
        import kicad_mcp_server
        return True, "kicad-mcp-server Python module OK"
    except Exception as e:
        return False, str(e)
test_check("KiCad MCP Server", check_mcp_server)

# 13. RF-tools-KiCAD Plugin
def check_rf_tools():
    try:
        paths = [
            "/root/.local/share/kicad/10.0/scripting/plugins/RF-tools-KiCAD",
            "/root/.local/share/kicad/8.0/scripting/plugins/RF-tools-KiCAD",
            "/usr/share/kicad/plugins/RF-tools-KiCAD"
        ]
        found = any(os.path.isdir(p) for p in paths)
        return found, "RF-tools-KiCAD plugin directory located" if found else "Directory missing"
    except Exception as e:
        return False, str(e)
test_check("RF-tools-KiCAD Plugin", check_rf_tools)

# 14. KiCad 10 Raytracer CLI (kicad-cli pcb render)
def check_kicad_render():
    try:
        res = subprocess.run(["kicad-cli", "pcb", "render", "--help"], capture_output=True, text=True, timeout=10)
        return res.returncode == 0, "Native 3D Raytracer supported" if res.returncode == 0 else "kicad-cli pcb render not supported"
    except Exception as e:
        return False, str(e)
test_check("KiCad Raytracer (pcb render)", check_kicad_render)

print("=" * 70)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f"Summary: {passed}/{total} tests passed ({failed} failed).")
if failed == 0:
    print("ALL TOOLS AND WORKBENCHES OPERATIONAL!")
else:
    print("Some components require inspection. Check logs above.")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
