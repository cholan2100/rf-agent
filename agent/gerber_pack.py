"""
Task 10: Production Gerber Export & ZIP Packager.
Exports standard RS-274X Gerbers, Excellon NC Drill files,
and packages them into a production-ready fabrication ZIP archive.
"""

import os
import subprocess
import zipfile
from typing import Dict, Any
from .spec import CircuitSpec

def package_gerbers(spec: CircuitSpec, pcb_path: str, output_dir: str, progress_callback=None) -> Dict[str, Any]:
    """
    Export Gerbers & Drill files and build a clean ZIP archive for manufacturing.
    """
    gerber_dir = os.path.join(output_dir, "gerbers")
    os.makedirs(gerber_dir, exist_ok=True)

    zip_filename = f"gerbers_{spec.name}.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    # 1. Export Gerbers
    if progress_callback:
        progress_callback("Exporting RS-274X Gerber photoplot layers via kicad-cli...")

    cmd_gerbers = [
        "kicad-cli", "pcb", "export", "gerbers",
        "--output", gerber_dir + "/",
        pcb_path
    ]
    subprocess.run(cmd_gerbers, capture_output=True, text=True, check=True)

    # 2. Export Drill
    if progress_callback:
        progress_callback("Exporting Excellon NC drill files via kicad-cli...")

    cmd_drill = [
        "kicad-cli", "pcb", "export", "drill",
        "--output", gerber_dir + "/",
        pcb_path
    ]
    subprocess.run(cmd_drill, capture_output=True, text=True, check=True)

    # 3. Create ZIP Archive
    if progress_callback:
        progress_callback(f"Compressing manufacturing package into {zip_filename}...")

    files_added = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(gerber_dir):
            for file in sorted(files):
                file_full = os.path.join(root, file)
                zf.write(file_full, arcname=os.path.join("gerbers", file))
                files_added.append(file)

    zip_size_kb = round(os.path.getsize(zip_path) / 1024, 1) if os.path.exists(zip_path) else 0

    return {
        "zip_path": zip_path,
        "zip_filename": zip_filename,
        "zip_size_kb": zip_size_kb,
        "file_count": len(files_added),
        "files": files_added,
        "status": "success"
    }
