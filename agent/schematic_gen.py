"""
Task 1: Programmatic KiCad 10 Schematic Generator & Zoomed Render.
Synthesizes valid KiCad 10 S-expression schematics with complete symbol bodies,
and exports tightly cropped, high-resolution zoomed schematic images.
"""

import os
import uuid
import datetime
import subprocess
from PIL import Image
import cairosvg
from .spec import CircuitSpec

def generate_schematic(spec: CircuitSpec, output_dir: str, progress_callback=None) -> tuple[str, str]:
    """
    Generate KiCad 10 schematic (.kicad_sch) and high-DPI zoomed render image (.png).
    Returns (sch_path, zoomed_png_path).
    """
    os.makedirs(output_dir, exist_ok=True)
    renders_dir = os.path.join(output_dir, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    sch_path = os.path.join(output_dir, f"{spec.name}.kicad_sch")
    zoomed_png_path = os.path.join(renders_dir, "schematic_zoomed.png")
    
    gen_date = datetime.date.today().isoformat()
    sch_uuid = str(uuid.uuid4())

    if progress_callback:
        progress_callback("Synthesizing schematic S-expression netlist and symbols...")

    # Generate schematic text depending on topology
    if spec.topology == "attenuator":
        content = _generate_attenuator_sch(spec, sch_uuid, gen_date)
    elif spec.topology == "lowpass":
        content = _generate_lowpass_sch(spec, sch_uuid, gen_date)
    elif spec.topology == "bandpass_shunt" or (spec.topology in ["bandpass", "bpf"] and "shunt" in spec.description.lower()):
        content = _generate_bandpass_shunt_sch(spec, sch_uuid, gen_date)
    elif spec.topology in ["bandpass", "bpf"]:
        content = _generate_bandpass_lc_sch(spec, sch_uuid, gen_date)
    elif spec.topology == "bias_tee":
        content = _generate_bias_tee_sch(spec, sch_uuid, gen_date)
    else:
        content = _generate_generic_rf_sch(spec, sch_uuid, gen_date)
        
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Export Zoomed Schematic Render
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
        if os.path.exists(generated_svg):
            # Rasterize via cairosvg at 300 DPI equivalent (scale 3.0)
            cairosvg.svg2png(url=generated_svg, write_to=zoomed_png_path, scale=3.0)

            # Crop tightly to circuit content
            img = Image.open(zoomed_png_path)
            alpha = img.split()[-1]
            bbox = alpha.getbbox()

            if bbox:
                pad = 60
                x1 = max(0, bbox[0] - pad)
                y1 = max(0, bbox[1] - pad)
                x2 = min(img.width, bbox[2] + pad)
                y2 = min(img.height, bbox[3] + pad)
                cropped = img.crop((x1, y1, x2, y2))

                # Composite onto clean white background
                final_img = Image.new("RGBA", cropped.size, (255, 255, 255, 255))
                final_img.paste(cropped, (0, 0), cropped)
                final_img.convert("RGB").save(zoomed_png_path, "PNG", quality=95)
    except Exception as e:
        pass

    return sch_path, zoomed_png_path


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
"""

def _generate_attenuator_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Generate KiCad 10 S-expression schematic for a Pi-Attenuator."""
    u_j1, u_j2 = str(uuid.uuid4()), str(uuid.uuid4())
    u_r1, u_r2, u_r3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    u_gnd1, u_gnd2 = str(uuid.uuid4()), str(uuid.uuid4())

    r1_val = spec.components.get("R1", {}).get("value", "96R")
    r2_val = spec.components.get("R2", {}).get("value", "71R")
    r3_val = spec.components.get("R3", {}).get("value", "96R")

    return f"""(kicad_sch
	(version 20231120)
	(generator "rf_agent")
	(generator_version "10.0")
	(uuid "{root_uuid}")
	(paper "A4")
	(title_block
		(title "{spec.title}")
		(date "{gen_date}")
		(rev "1.0")
		(company "RF AI Suite")
		(comment 1 "Z0 = {spec.z0_ohm:.1f} Ohm | Target S21 = {spec.target_s21_db:+.1f} dB")
		(comment 2 "Substrate: {spec.substrate_name} (er={spec.dielectric_er}, h={spec.substrate_height_mm}mm, w_50={spec.rf_trace_width_mm:.2f}mm)")
	)
	(lib_symbols
{_get_common_lib_symbols()}
	)
	(symbol
		(lib_id "Connector:Conn_Coaxial")
		(at 38.1 76.2 0)
		(uuid "{u_j1}")
		(property "Reference" "J1" (at 38.1 68.58 0))
		(property "Value" "SMA_IN" (at 38.1 71.12 0))
		(property "Footprint" "Connector_Coaxial:SMA_Amphenol_132134_Vertical" (at 38.1 76.2 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "Device:R")
		(at 63.5 101.6 0)
		(uuid "{u_r1}")
		(property "Reference" "R1" (at 68.58 101.6 0))
		(property "Value" "{r1_val}" (at 68.58 104.14 0))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 63.5 101.6 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "Device:R")
		(at 88.9 76.2 90)
		(uuid "{u_r2}")
		(property "Reference" "R2" (at 88.9 68.58 0))
		(property "Value" "{r2_val}" (at 88.9 71.12 0))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 88.9 76.2 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "Device:R")
		(at 114.3 101.6 0)
		(uuid "{u_r3}")
		(property "Reference" "R3" (at 119.38 101.6 0))
		(property "Value" "{r3_val}" (at 119.38 104.14 0))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 114.3 101.6 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "Connector:Conn_Coaxial")
		(at 139.7 76.2 0)
		(uuid "{u_j2}")
		(property "Reference" "J2" (at 139.7 68.58 0))
		(property "Value" "SMA_OUT" (at 139.7 71.12 0))
		(property "Footprint" "Connector_Coaxial:SMA_Amphenol_132134_Vertical" (at 139.7 76.2 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "power:GND")
		(at 63.5 114.3 0)
		(uuid "{u_gnd1}")
		(property "Reference" "#PWR01" (at 63.5 118.11 0) (effects (hide yes)))
		(property "Value" "GND" (at 63.5 119.38 0))
	)
	(symbol
		(lib_id "power:GND")
		(at 114.3 114.3 0)
		(uuid "{u_gnd2}")
		(property "Reference" "#PWR02" (at 114.3 118.11 0) (effects (hide yes)))
		(property "Value" "GND" (at 114.3 119.38 0))
	)
	(wire (pts (xy 38.1 76.2) (xy 63.5 76.2)))
	(wire (pts (xy 63.5 76.2) (xy 63.5 97.79)))
	(wire (pts (xy 63.5 76.2) (xy 85.09 76.2)))
	(wire (pts (xy 92.71 76.2) (xy 114.3 76.2)))
	(wire (pts (xy 114.3 76.2) (xy 114.3 97.79)))
	(wire (pts (xy 114.3 76.2) (xy 139.7 76.2)))
	(wire (pts (xy 63.5 105.41) (xy 63.5 114.3)))
	(wire (pts (xy 114.3 105.41) (xy 114.3 114.3)))
	(label "RF_IN" (at 45.72 73.66 0))
	(label "RF_OUT" (at 132.08 73.66 0))
	(text "{spec.description}\\nZ0 = {spec.z0_ohm:.1f} Ohm Controlled Impedance (w = {spec.rf_trace_width_mm:.2f}mm)" (at 88.9 127.0 0) (effects (font (size 2.0 2.0))))
)
"""

def _generate_lowpass_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Generate KiCad 10 schematic for a 3-pole Low-Pass Filter."""
    u_j1, u_j2 = str(uuid.uuid4()), str(uuid.uuid4())
    u_c1, u_l1, u_c2 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    u_gnd1, u_gnd2 = str(uuid.uuid4()), str(uuid.uuid4())

    c1_val = spec.components.get("C1", {}).get("value", "2.1pF")
    l1_val = spec.components.get("L1", {}).get("value", "10.6nH")
    c2_val = spec.components.get("C2", {}).get("value", "2.1pF")

    return f"""(kicad_sch
	(version 20231120)
	(generator "rf_agent")
	(generator_version "10.0")
	(uuid "{root_uuid}")
	(paper "A4")
	(title_block
		(title "{spec.title}")
		(date "{gen_date}")
		(rev "1.0")
		(company "RF AI Suite")
		(comment 1 "Z0 = {spec.z0_ohm:.1f} Ohm | Cutoff fc = {spec.f_0_ghz:.2f} GHz")
	)
	(lib_symbols
{_get_common_lib_symbols()}
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 38.1 76.2 0) (uuid "{u_j1}")
		(property "Reference" "J1" (at 38.1 68.58 0))
		(property "Value" "SMA_IN" (at 38.1 71.12 0))
	)
	(symbol (lib_id "Device:C") (at 63.5 101.6 0) (uuid "{u_c1}")
		(property "Reference" "C1" (at 68.58 101.6 0))
		(property "Value" "{c1_val}" (at 68.58 104.14 0))
	)
	(symbol (lib_id "Device:L") (at 88.9 76.2 90) (uuid "{u_l1}")
		(property "Reference" "L1" (at 88.9 68.58 0))
		(property "Value" "{l1_val}" (at 88.9 71.12 0))
	)
	(symbol (lib_id "Device:C") (at 114.3 101.6 0) (uuid "{u_c2}")
		(property "Reference" "C2" (at 119.38 101.6 0))
		(property "Value" "{c2_val}" (at 119.38 104.14 0))
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 139.7 76.2 0) (uuid "{u_j2}")
		(property "Reference" "J2" (at 139.7 68.58 0))
		(property "Value" "SMA_OUT" (at 139.7 71.12 0))
	)
	(symbol (lib_id "power:GND") (at 63.5 114.3 0) (uuid "{u_gnd1}")
		(property "Reference" "#PWR01" (at 63.5 118.11 0) (effects (hide yes)))
		(property "Value" "GND" (at 63.5 119.38 0))
	)
	(symbol (lib_id "power:GND") (at 114.3 114.3 0) (uuid "{u_gnd2}")
		(property "Reference" "#PWR02" (at 114.3 118.11 0) (effects (hide yes)))
		(property "Value" "GND" (at 114.3 119.38 0))
	)
	(wire (pts (xy 38.1 76.2) (xy 63.5 76.2)))
	(wire (pts (xy 63.5 76.2) (xy 63.5 97.79)))
	(wire (pts (xy 63.5 76.2) (xy 85.09 76.2)))
	(wire (pts (xy 92.71 76.2) (xy 114.3 76.2)))
	(wire (pts (xy 114.3 76.2) (xy 114.3 97.79)))
	(wire (pts (xy 114.3 76.2) (xy 139.7 76.2)))
	(wire (pts (xy 63.5 105.41) (xy 63.5 114.3)))
	(wire (pts (xy 114.3 105.41) (xy 114.3 114.3)))
	(label "RF_IN" (at 45.72 73.66 0))
	(label "RF_OUT" (at 132.08 73.66 0))
	(text "3-Pole Butterworth Low-Pass Filter\\nfc = {spec.f_0_ghz:.2f} GHz | Z0 = {spec.z0_ohm:.1f} Ohm" (at 88.9 127.0 0) (effects (font (size 2.0 2.0))))
)
"""

def _generate_bandpass_lc_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Generate KiCad 10 schematic for an LC Tank Bandpass Filter."""
    u_j1, u_j2 = str(uuid.uuid4()), str(uuid.uuid4())
    u_c1, u_l1 = str(uuid.uuid4()), str(uuid.uuid4())
    u_gnd1, u_gnd2 = str(uuid.uuid4()), str(uuid.uuid4())

    c1_val = spec.components.get("C1", {}).get("value", "25.3pF")
    l1_val = spec.components.get("L1", {}).get("value", "100nH")

    return f"""(kicad_sch
	(version 20231120)
	(generator "rf_agent")
	(generator_version "10.0")
	(uuid "{root_uuid}")
	(paper "A4")
	(title_block
		(title "{spec.title}")
		(date "{gen_date}")
		(rev "1.0")
		(company "RF AI Suite")
		(comment 1 "Z0 = {spec.z0_ohm:.1f} Ohm | Resonance f0 = {spec.f_0_ghz*1000.0:.0f} MHz")
	)
	(lib_symbols
{_get_common_lib_symbols()}
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 38.1 76.2 0) (uuid "{u_j1}")
		(property "Reference" "J1" (at 38.1 68.58 0))
		(property "Value" "SMA_IN" (at 38.1 71.12 0))
	)
	(symbol (lib_id "Device:C") (at 76.2 76.2 90) (uuid "{u_c1}")
		(property "Reference" "C1" (at 76.2 68.58 0))
		(property "Value" "{c1_val}" (at 76.2 71.12 0))
		(property "Footprint" "Capacitor_SMD:C_0805_2012Metric" (at 76.2 76.2 0) (effects (hide yes)))
	)
	(symbol (lib_id "Device:L") (at 101.6 76.2 90) (uuid "{u_l1}")
		(property "Reference" "L1" (at 101.6 68.58 0))
		(property "Value" "{l1_val}" (at 101.6 71.12 0))
		(property "Footprint" "Inductor_SMD:L_0805_2012Metric" (at 101.6 76.2 0) (effects (hide yes)))
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 139.7 76.2 0) (uuid "{u_j2}")
		(property "Reference" "J2" (at 139.7 68.58 0))
		(property "Value" "SMA_OUT" (at 139.7 71.12 0))
	)
	(symbol (lib_id "power:GND") (at 38.1 86.36 0) (uuid "{u_gnd1}")
		(property "Reference" "#PWR01" (at 38.1 90.17 0) (effects (hide yes)))
		(property "Value" "GND" (at 38.1 91.44 0))
	)
	(symbol (lib_id "power:GND") (at 139.7 86.36 0) (uuid "{u_gnd2}")
		(property "Reference" "#PWR02" (at 139.7 90.17 0) (effects (hide yes)))
		(property "Value" "GND" (at 139.7 91.44 0))
	)
	(wire (pts (xy 38.1 76.2) (xy 72.39 76.2)))
	(wire (pts (xy 80.01 76.2) (xy 97.79 76.2)))
	(wire (pts (xy 105.41 76.2) (xy 139.7 76.2)))
	(wire (pts (xy 38.1 81.28) (xy 38.1 86.36)))
	(wire (pts (xy 139.7 81.28) (xy 139.7 86.36)))
	(label "RF_IN" (at 45.72 73.66 0))
	(label "RF_OUT" (at 125.0 73.66 0))
	(text "{spec.title}\\nf0 = {spec.f_0_ghz*1000.0:.0f} MHz | Z0 = {spec.z0_ohm:.1f} Ohm" (at 88.9 110.0 0) (effects (font (size 2.0 2.0))))
)
"""

def _generate_bandpass_shunt_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Generate KiCad 10 schematic for a Shunted Parallel LC Tank Bandpass Filter."""
    u_j1, u_j2 = str(uuid.uuid4()), str(uuid.uuid4())
    u_c1, u_l1 = str(uuid.uuid4()), str(uuid.uuid4())
    u_gnd1, u_gnd2 = str(uuid.uuid4()), str(uuid.uuid4())

    c1_val = spec.components.get("C1", {}).get("value", "26.4pF")
    l1_val = spec.components.get("L1", {}).get("value", "100nH")

    return f"""(kicad_sch
	(version 20231120)
	(generator "rf_agent")
	(generator_version "10.0")
	(uuid "{root_uuid}")
	(paper "A4")
	(title_block
		(title "{spec.title}")
		(date "{gen_date}")
		(rev "1.0")
		(company "RF AI Suite")
		(comment 1 "Z0 = {spec.z0_ohm:.1f} Ohm | Resonance f0 = {spec.f_0_ghz*1000.0:.0f} MHz")
		(comment 2 "Topology: Shunted Parallel LC Tank | Substrate: {spec.substrate_name} (h={spec.substrate_height_mm}mm, er={spec.dielectric_er})")
	)
	(lib_symbols
{_get_common_lib_symbols()}
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 38.1 76.2 0) (uuid "{u_j1}")
		(property "Reference" "J1" (at 38.1 68.58 0))
		(property "Value" "SMA_IN" (at 38.1 71.12 0))
	)
	(symbol (lib_id "Device:C") (at 76.2 101.6 0) (uuid "{u_c1}")
		(property "Reference" "C1" (at 81.28 101.6 0))
		(property "Value" "{c1_val}" (at 81.28 104.14 0))
		(property "Footprint" "Capacitor_SMD:C_0805_2012Metric" (at 76.2 101.6 0) (effects (hide yes)))
	)
	(symbol (lib_id "Device:L") (at 101.6 101.6 0) (uuid "{u_l1}")
		(property "Reference" "L1" (at 106.68 101.6 0))
		(property "Value" "{l1_val}" (at 106.68 104.14 0))
		(property "Footprint" "Inductor_SMD:L_0805_2012Metric" (at 101.6 101.6 0) (effects (hide yes)))
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 139.7 76.2 0) (uuid "{u_j2}")
		(property "Reference" "J2" (at 139.7 68.58 0))
		(property "Value" "SMA_OUT" (at 139.7 71.12 0))
	)
	(symbol (lib_id "power:GND") (at 88.9 121.92 0) (uuid "{u_gnd1}")
		(property "Reference" "#PWR01" (at 88.9 125.73 0) (effects (hide yes)))
		(property "Value" "GND" (at 88.9 127.0 0))
	)
	(wire (pts (xy 38.1 76.2) (xy 88.9 76.2)))
	(wire (pts (xy 88.9 76.2) (xy 139.7 76.2)))
	(wire (pts (xy 88.9 76.2) (xy 88.9 83.82)))
	(wire (pts (xy 88.9 83.82) (xy 76.2 83.82)))
	(wire (pts (xy 88.9 83.82) (xy 101.6 83.82)))
	(wire (pts (xy 76.2 83.82) (xy 76.2 97.79)))
	(wire (pts (xy 101.6 83.82) (xy 101.6 97.79)))
	(wire (pts (xy 76.2 105.41) (xy 76.2 114.3)))
	(wire (pts (xy 101.6 105.41) (xy 101.6 114.3)))
	(wire (pts (xy 76.2 114.3) (xy 101.6 114.3)))
	(wire (pts (xy 88.9 114.3) (xy 88.9 121.92)))
	(label "RF_IN" (at 45.72 73.66 0))
	(label "RF_OUT" (at 132.08 73.66 0))
	(text "Shunted Parallel LC Tank Bandpass Filter\\nf0 = {spec.f_0_ghz*1000.0:.0f} MHz | Z0 = {spec.z0_ohm:.1f} Ohm" (at 88.9 137.0 0) (effects (font (size 2.0 2.0))))
)
"""

def _generate_bias_tee_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Generate KiCad 10 schematic for an RF Bias Tee."""
    u_j1, u_j2, u_j3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    u_c1, u_l1 = str(uuid.uuid4()), str(uuid.uuid4())
    return f"""(kicad_sch
	(version 20231120)
	(generator "rf_agent")
	(generator_version "10.0")
	(uuid "{root_uuid}")
	(paper "A4")
	(title_block
		(title "{spec.title}")
		(date "{gen_date}")
		(rev "1.0")
		(company "RF AI Suite")
		(comment 1 "Z0 = {spec.z0_ohm:.1f} Ohm | Bias Supply: {spec.power_voltage_v:.1f}V")
	)
	(lib_symbols
{_get_common_lib_symbols()}
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 38.1 76.2 0) (uuid "{u_j1}")
		(property "Reference" "J1" (at 38.1 68.58 0))
		(property "Value" "RF_IN" (at 38.1 71.12 0))
	)
	(symbol (lib_id "Device:C") (at 76.2 76.2 90) (uuid "{u_c1}")
		(property "Reference" "C1" (at 76.2 68.58 0))
		(property "Value" "100pF" (at 76.2 71.12 0))
	)
	(symbol (lib_id "Device:L") (at 101.6 50.8 0) (uuid "{u_l1}")
		(property "Reference" "L1" (at 106.68 50.8 0))
		(property "Value" "100nH" (at 106.68 53.34 0))
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 101.6 25.4 90) (uuid "{u_j3}")
		(property "Reference" "J3" (at 101.6 17.78 0))
		(property "Value" "DC_IN" (at 101.6 20.32 0))
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 139.7 76.2 0) (uuid "{u_j2}")
		(property "Reference" "J2" (at 139.7 68.58 0))
		(property "Value" "RF_DC_OUT" (at 139.7 71.12 0))
	)
	(wire (pts (xy 38.1 76.2) (xy 72.39 76.2)))
	(wire (pts (xy 80.01 76.2) (xy 101.6 76.2)))
	(wire (pts (xy 101.6 76.2) (xy 101.6 54.61)))
	(wire (pts (xy 101.6 46.99) (xy 101.6 25.4)))
	(wire (pts (xy 101.6 76.2) (xy 139.7 76.2)))
	(label "RF_IN" (at 45.72 73.66 0))
	(label "RF_DC_OUT" (at 125.0 73.66 0))
	(text "Wideband RF Bias Tee\\nZ0 = {spec.z0_ohm:.1f} Ohm" (at 88.9 110.0 0) (effects (font (size 2.0 2.0))))
)
"""

def _generate_generic_rf_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Fallback generic 2-port RF circuit schematic."""
    u_j1, u_j2 = str(uuid.uuid4()), str(uuid.uuid4())
    u_r1 = str(uuid.uuid4())
    return f"""(kicad_sch
	(version 20231120)
	(generator "rf_agent")
	(generator_version "10.0")
	(uuid "{root_uuid}")
	(paper "A4")
	(title_block
		(title "{spec.title}")
		(date "{gen_date}")
		(rev "1.0")
		(company "RF AI Suite")
	)
	(lib_symbols
{_get_common_lib_symbols()}
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 38.1 76.2 0) (uuid "{u_j1}")
		(property "Reference" "J1" (at 38.1 68.58 0))
		(property "Value" "SMA_IN" (at 38.1 71.12 0))
	)
	(symbol (lib_id "Device:R") (at 88.9 76.2 90) (uuid "{u_r1}")
		(property "Reference" "R1" (at 88.9 68.58 0))
		(property "Value" "50R" (at 88.9 71.12 0))
	)
	(symbol (lib_id "Connector:Conn_Coaxial") (at 139.7 76.2 0) (uuid "{u_j2}")
		(property "Reference" "J2" (at 139.7 68.58 0))
		(property "Value" "SMA_OUT" (at 139.7 71.12 0))
	)
	(wire (pts (xy 38.1 76.2) (xy 85.09 76.2)))
	(wire (pts (xy 92.71 76.2) (xy 139.7 76.2)))
	(label "RF_IN" (at 45.72 73.66 0))
	(label "RF_OUT" (at 132.08 73.66 0))
)
"""
