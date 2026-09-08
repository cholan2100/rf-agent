"""
Task 1: Programmatic KiCad 10 Schematic Generator.
Synthesizes valid KiCad 10 S-expression schematic (.kicad_sch) files.
"""

import os
import uuid
import datetime
from .spec import CircuitSpec

def generate_schematic(spec: CircuitSpec, output_dir: str) -> str:
    """
    Generate a KiCad 10 schematic file (.kicad_sch) for the given circuit specification.
    Returns the absolute path to the generated schematic file.
    """
    os.makedirs(output_dir, exist_ok=True)
    sch_path = os.path.join(output_dir, f"{spec.name}.kicad_sch")
    
    gen_date = datetime.date.today().isoformat()
    sch_uuid = str(uuid.uuid4())
    
    # Generate schematic text depending on topology
    if spec.topology == "attenuator":
        content = _generate_attenuator_sch(spec, sch_uuid, gen_date)
    elif spec.topology == "filter":
        content = _generate_filter_sch(spec, sch_uuid, gen_date)
    else:
        content = _generate_generic_rf_sch(spec, sch_uuid, gen_date)
        
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return sch_path


def _generate_attenuator_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Generate KiCad 10 S-expression schematic for a 10dB Pi-Attenuator."""
    u_j1 = str(uuid.uuid4())
    u_j2 = str(uuid.uuid4())
    u_r1 = str(uuid.uuid4())
    u_r2 = str(uuid.uuid4())
    u_r3 = str(uuid.uuid4())
    u_gnd1 = str(uuid.uuid4())
    u_gnd2 = str(uuid.uuid4())
    u_gnd3 = str(uuid.uuid4())

    r1_val = spec.components.get("R1", {}).get("value", "95.3R")
    r2_val = spec.components.get("R2", {}).get("value", "71.5R")
    r3_val = spec.components.get("R3", {}).get("value", "95.3R")

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
		(comment 1 "Z0 = {spec.z0_ohm} Ohm | Target S21 = {spec.target_s21_db} dB")
		(comment 2 "Substrate: {spec.substrate_name} (er={spec.dielectric_er}, h={spec.substrate_height_mm}mm)")
	)
	(lib_symbols
		(symbol "Device:R"
			(pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			(pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
		)
		(symbol "Connector:Conn_Coaxial"
			(pin passive line (at -5.08 0 0) (length 2.54) (name "In" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			(pin passive line (at 0 -5.08 90) (length 2.54) (name "Ext" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
		)
		(symbol "power:GND"
			(pin power_in line (at 0 0 90) (length 0) (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
		)
	)
	(symbol
		(lib_id "Connector:Conn_Coaxial")
		(at 38.1 76.2 0)
		(unit 1)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(uuid "{u_j1}")
		(property "Reference" "J1" (at 38.1 68.58 0))
		(property "Value" "SMA_IN" (at 38.1 71.12 0))
		(property "Footprint" "Connector_Coaxial:SMA_Amphenol_132134_Vertical" (at 38.1 76.2 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "Device:R")
		(at 63.5 101.6 0)
		(unit 1)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(uuid "{u_r1}")
		(property "Reference" "R1" (at 68.58 101.6 0))
		(property "Value" "{r1_val}" (at 68.58 104.14 0))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 63.5 101.6 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "Device:R")
		(at 88.9 76.2 90)
		(unit 1)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(uuid "{u_r2}")
		(property "Reference" "R2" (at 88.9 68.58 0))
		(property "Value" "{r2_val}" (at 88.9 71.12 0))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 88.9 76.2 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "Device:R")
		(at 114.3 101.6 0)
		(unit 1)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(uuid "{u_r3}")
		(property "Reference" "R3" (at 119.38 101.6 0))
		(property "Value" "{r3_val}" (at 119.38 104.14 0))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 114.3 101.6 0) (effects (hide yes)))
	)
	(symbol
		(lib_id "Connector:Conn_Coaxial")
		(at 139.7 76.2 0)
		(unit 1)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
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
	(text "Pi-Attenuator Topology\\nR1 = R3 = 96.2 Ohm (Shunt)\\nR2 = 71.2 Ohm (Series)\\nZ0 = 50 Ohm Matching" (at 88.9 127.0 0) (effects (font (size 2.0 2.0))))
)
"""

def _generate_filter_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Generate KiCad schematic for a filter circuit."""
    return _generate_generic_rf_sch(spec, root_uuid, gen_date)

def _generate_generic_rf_sch(spec: CircuitSpec, root_uuid: str, gen_date: str) -> str:
    """Fallback generator for arbitrary RF circuit."""
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
)
"""
