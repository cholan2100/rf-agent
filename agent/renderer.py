"""
Task 3: KiCad 10 Native 3D Raytrace Renderer.
Renders photorealistic isometric, top, and bottom 3D board views with loaded components.
"""

import os
import subprocess
from typing import Dict, Any

def render_3d_pcb(pcb_path: str, output_dir: str, progress_callback=None) -> Dict[str, Any]:
    """
    Render photorealistic 3D views of the PCB (isometric, top, bottom) using kicad-cli.
    """
    renders_dir = os.path.join(output_dir, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    results = {}

    views = [
        ("iso", "iso_render.png", ["--rotate", "-45,0,45", "--floor", "--zoom", "1.25"]),
        ("top", "top_render.png", ["--side", "top", "--floor", "--zoom", "1.1"]),
        ("bottom", "bottom_render.png", ["--side", "bottom", "--floor", "--zoom", "1.1"])
    ]

    for key, filename, extra_args in views:
        out_file = os.path.join(renders_dir, filename)
        if progress_callback:
            progress_callback(f"Rendering 3D {key.upper()} view ({filename})...")

        cmd = [
            "kicad-cli", "pcb", "render",
            "--width", "1600",
            "--height", "1200",
            "--quality", "high",
            *extra_args,
            "--output", out_file,
            pcb_path
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                size_kb = round(os.path.getsize(out_file) / 1024, 1)
                results[key] = {
                    "path": out_file,
                    "filename": filename,
                    "size_kb": size_kb,
                    "status": "success"
                }
            else:
                results[key] = {
                    "path": out_file,
                    "filename": filename,
                    "size_kb": 0,
                    "status": "failed",
                    "error": res.stderr
                }
        except Exception as e:
            results[key] = {
                "path": out_file,
                "filename": filename,
                "size_kb": 0,
                "status": "error",
                "error": str(e)
            }

    return results
