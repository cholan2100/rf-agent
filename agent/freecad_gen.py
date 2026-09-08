"""
Task 4: FreeCAD Project and 3D Mechanical Model Generator.
Exports STEP 3D CAD model and creates native FreeCAD .FCStd project.
"""

import os
import subprocess
from typing import Dict, Any
from .spec import CircuitSpec

def generate_freecad_project(spec: CircuitSpec, pcb_path: str, output_dir: str, progress_callback=None) -> Dict[str, Any]:
    """
    Generate 3D STEP file from KiCad and package into a FreeCAD .FCStd document.
    """
    cad_dir = os.path.join(output_dir, "cad")
    os.makedirs(cad_dir, exist_ok=True)
    
    step_file = os.path.join(cad_dir, f"{spec.name}.step")
    fcstd_file = os.path.join(cad_dir, f"{spec.name}.FCStd")

    # 1. Export STEP from KiCad
    if progress_callback:
        progress_callback(f"Exporting 3D STEP mechanical model via kicad-cli...")
        
    step_cmd = [
        "kicad-cli", "pcb", "export", "step",
        "--output", step_file,
        pcb_path
    ]
    subprocess.run(step_cmd, capture_output=True, text=True, timeout=60)

    # 2. Create FreeCAD Document via FreeCAD Python API
    if progress_callback:
        progress_callback(f"Creating native FreeCAD document ({os.path.basename(fcstd_file)})...")

    fc_script = f"""
import FreeCAD
import Part
import Import

doc = FreeCAD.newDocument("{spec.name}")

# Import STEP model if available
step_path = r"{step_file}"
import os
if os.path.exists(step_path):
    Import.insert(step_path, doc.Name)
else:
    # Fallback to parametric substrate block
    substrate = Part.makeBox({spec.width_mm}, {spec.height_mm}, {spec.substrate_height_mm})
    obj = doc.addObject("Part::Feature", "Substrate_{spec.substrate_name}")
    obj.Shape = substrate
    obj.ViewObject.ShapeColor = (0.2, 0.4, 0.2)  # FR4 green

doc.recompute()
doc.saveAs(r"{fcstd_file}")
FreeCAD.closeDocument(doc.Name)
"""
    # Execute FreeCAD script inside container
    try:
        cmd = ["freecadcmd", "-c", fc_script]
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as e:
        # If freecadcmd fails, run via python3 since FreeCAD python module is available
        try:
            cmd = ["python3", "-c", fc_script]
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception:
            pass

    step_size_kb = round(os.path.getsize(step_file) / 1024, 1) if os.path.exists(step_file) else 0
    fcstd_size_kb = round(os.path.getsize(fcstd_file) / 1024, 1) if os.path.exists(fcstd_file) else 0

    return {
        "step_path": step_file,
        "step_size_kb": step_size_kb,
        "fcstd_path": fcstd_file,
        "fcstd_size_kb": fcstd_size_kb,
        "status": "success" if os.path.exists(fcstd_file) else "partial"
    }
