"""
Task 1: Programmatic KiCad 10 Schematic Generator & Zoomed Render.
Synthesizes valid KiCad 10 S-expression schematics dynamically from netlists.
"""

import os
import uuid
import datetime
import subprocess
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    import cairosvg
except ImportError:
    cairosvg = None
from .spec import CircuitSpec

def _get_common_lib_symbols() -> str:
    """Standard graphical symbol definitions for R, C, L, SMA connector, and GND."""
    return """
		(symbol "Device:R"
			(rectangle (start -1.016 2.54) (end 1.016 -2.54) (stroke (width 0.254) (type default)) (fill (type none)))
			(pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			(pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
		)
		(symbol "Device:C"
			(polyline (pts (xy -2.032 0.635) (xy 2.032 0.635)) (stroke (width 0.35) (type default)))
			(polyline (pts (xy -2.032 -0.635) (xy 2.032 -0.635)) (stroke (width 0.35) (type default)))
			(pin passive line (at 0 3.81 270) (length 3.175) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			(pin passive line (at 0 -3.81 90) (length 3.175) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
		)
		(symbol "Device:L"
			(arc (start 0 2.54) (mid 1.27 1.27) (end 0 0) (stroke (width 0.254) (type default)))
			(arc (start 0 0) (mid 1.27 -1.27) (end 0 -2.54) (stroke (width 0.254) (type default)))
			(pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			(pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
		)
		(symbol "Connector:Conn_Coaxial"
			(circle (center 0 0) (radius 3.81) (stroke (width 0.254) (type default)) (fill (type none)))
			(circle (center 0 0) (radius 0.8) (stroke (width 0.254) (type default)) (fill (type outline)))
			(polyline (pts (xy -5.08 0) (xy -0.8 0)) (stroke (width 0.254) (type default)))
			(polyline (pts (xy 0 -3.81) (xy 0 -5.08)) (stroke (width 0.254) (type default)))
			(pin passive line (at -5.08 0 0) (length 0) (name "In" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			(pin passive line (at 0 -5.08 90) (length 0) (name "Ext" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
		)
		(symbol "power:GND"
			(polyline (pts (xy -1.27 0) (xy 1.27 0)) (stroke (width 0.254) (type default)))
			(polyline (pts (xy -0.762 -0.635) (xy 0.762 -0.635)) (stroke (width 0.254) (type default)))
			(polyline (pts (xy -0.254 -1.27) (xy 0.254 -1.27)) (stroke (width 0.254) (type default)))
			(pin power_in line (at 0 0 90) (length 0) (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
		)
		(symbol "Device:Amplifier_MMIC"
			(polyline (pts (xy -3.81 5.08) (xy 3.81 0)) (stroke (width 0.254) (type default)))
			(polyline (pts (xy 3.81 0) (xy -3.81 -5.08)) (stroke (width 0.254) (type default)))
			(polyline (pts (xy -3.81 -5.08) (xy -3.81 5.08)) (stroke (width 0.254) (type default)))
			(pin input line (at -6.35 0 0) (length 2.54) (name "IN" (effects (font (size 1.0 1.0)))) (number "1" (effects (font (size 1.0 1.0)))))
			(pin power_in line (at 0 -7.62 90) (length 2.54) (name "GND" (effects (font (size 1.0 1.0)))) (number "2" (effects (font (size 1.0 1.0)))))
			(pin output line (at 6.35 0 180) (length 2.54) (name "OUT" (effects (font (size 1.0 1.0)))) (number "3" (effects (font (size 1.0 1.0)))))
		)
		(symbol "Connector:Conn_01x02_Pin"
			(rectangle (start -1.27 2.54) (end 1.27 -2.54) (stroke (width 0.254) (type default)) (fill (type none)))
			(pin passive line (at -3.81 1.27 0) (length 2.54) (name "1" (effects (font (size 1.0 1.0)))) (number "1" (effects (font (size 1.0 1.0)))))
			(pin passive line (at -3.81 -1.27 0) (length 2.54) (name "2" (effects (font (size 1.0 1.0)))) (number "2" (effects (font (size 1.0 1.0)))))
		)
		(symbol "Device:Q_NPN_BEC"
			(pin input line (at -5.08 0 0) (length 2.54) (name "B" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			(pin passive line (at 2.54 -5.08 90) (length 2.54) (name "E" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
			(pin passive line (at 2.54 5.08 270) (length 2.54) (name "C" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
		)
"""

def _generate_netlist_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Generates a KiCad schematic dynamically from the spec.components and spec.nets."""
    
    out = [
        "(kicad_sch",
        "	(version 20231120)",
        "	(generator \"rf_agent\")",
        "	(generator_version \"10.0\")",
        f"	(uuid \"{root_uuid}\")",
        "	(paper \"A4\")",
        "	(title_block",
        f"		(title \"{spec.title}\")",
        f"		(date \"{gen_date}\")",
        "		(rev \"1.0\")",
        "		(company \"RF AI Suite\")",
        "	)",
        "	(lib_symbols",
        _get_common_lib_symbols(),
        "	)"
    ]

    def get_lib_id(ctype: str) -> str:
        t = ctype.lower()
        if "resistor" in t: return "Device:R"
        if "capacitor" in t: return "Device:C"
        if "inductor" in t: return "Device:L"
        if "connector" in t: return "Connector:Conn_Coaxial"
        if "transistor" in t: return "Device:Q_NPN_BEC"
        if "ic" in t: return "Device:Amplifier_MMIC"
        return "Device:R"

    x_start = 40.0
    y_start = 50.0
    x_spacing = 30.0
    y_spacing = 30.0
    
    comps = list(spec.components.keys())
    
    col = 0
    row = 0
    pin_locations = {}
    
    for ref in comps:
        c = spec.components[ref]
        lib_id = get_lib_id(c.get("type", ""))
        val = c.get("value", "")
        fp = c.get("package", "")
        
        x = x_start + col * x_spacing
        y = y_start + row * y_spacing
        
        u = str(uuid.uuid4())
        
        out.append(f'	(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} 0) (uuid "{u}")')
        out.append(f'		(property "Reference" "{ref}" (at {x:.2f} {y-7.62:.2f} 0))')
        out.append(f'		(property "Value" "{val}" (at {x:.2f} {y-5.08:.2f} 0))')
        out.append(f'		(property "Footprint" "{fp}" (at {x:.2f} {y:.2f} 0) (effects (hide yes)))')
        out.append('	)')
        
        if lib_id == "Connector:Conn_Coaxial":
            pin_locations[f"{ref}.1"] = (x - 5.08, y)
            pin_locations[f"{ref}.2"] = (x, y - 5.08)
        elif lib_id in ["Device:R", "Device:C", "Device:L"]:
            pin_locations[f"{ref}.1"] = (x, y + 3.81)
            pin_locations[f"{ref}.2"] = (x, y - 3.81)
        elif lib_id == "Device:Q_NPN_BEC":
            pin_locations[f"{ref}.1"] = (x - 5.08, y)
            pin_locations[f"{ref}.2"] = (x + 2.54, y - 5.08)
            pin_locations[f"{ref}.3"] = (x + 2.54, y + 5.08)
        else:
            pin_locations[f"{ref}.1"] = (x - 2.54, y)
            pin_locations[f"{ref}.2"] = (x + 2.54, y)
            pin_locations[f"{ref}.3"] = (x, y + 2.54)
        
        col += 1
        if col > 4:
            col = 0
            row += 1

    if hasattr(spec, "nets") and spec.nets:
        for net_name, pins in spec.nets.items():
            for pin in pins:
                if pin in pin_locations:
                    px, py = pin_locations[pin]
                    sx = px - 2.54
                    sy = py
                    out.append(f'	(wire (pts (xy {px:.2f} {py:.2f}) (xy {sx:.2f} {sy:.2f})))')
                    out.append(f'	(label "{net_name}" (at {sx:.2f} {sy:.2f} 0))')

    out.append(")")
    return "\n".join(out)

def generate_schematic(spec: CircuitSpec, output_dir: str, progress_callback=None) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    renders_dir = os.path.join(output_dir, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    sch_path = os.path.join(output_dir, f"{spec.name}.kicad_sch")
    zoomed_png_path = os.path.join(renders_dir, "schematic_zoomed.png")
    
    gen_date = datetime.date.today().isoformat()
    sch_uuid = str(uuid.uuid4())
    
    content = _generate_netlist_sch(spec, sch_uuid, gen_date)
        
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(content)

    if progress_callback:
        progress_callback("Exporting vector schematic and rendering zoomed high-DPI image...")

    try:
        cmd_svg = [
            "kicad-cli", "sch", "export", "svg",
            "--exclude-drawing-sheet",
            "--no-background-color",
            "--output", renders_dir,
            sch_path
        ]
        subprocess.run(cmd_svg, capture_output=True, text=True, check=True)

        generated_svg = os.path.join(renders_dir, f"{spec.name}.svg")
        if os.path.exists(generated_svg) and cairosvg is not None and Image is not None:
            cairosvg.svg2png(url=generated_svg, write_to=zoomed_png_path, scale=3.0)
            img = Image.open(zoomed_png_path)
            if img.mode == 'RGBA':
                alpha = img.split()[-1]
                bbox = alpha.getbbox()
                if bbox:
                    pad = 60
                    x1 = max(0, bbox[0] - pad)
                    y1 = max(0, bbox[1] - pad)
                    x2 = min(img.width, bbox[2] + pad)
                    y2 = min(img.height, bbox[3] + pad)
                    cropped = img.crop((x1, y1, x2, y2))
                    final_img = Image.new("RGBA", cropped.size, (255, 255, 255, 255))
                    final_img.paste(cropped, (0, 0), cropped)
                    final_img.convert("RGB").save(zoomed_png_path, "PNG", quality=95)
    except Exception as e:
        print(f"Failed to generate schematic render: {e}")

    return sch_path, zoomed_png_path
