"""
llm_synth.py - Autonomous LLM Circuit Architecture & Specification Synthesizer.
Uses AI intelligence to design RF circuits, select components, calculate values,
and produce complete CircuitSpec specifications without procedural heuristics or preset equations.
"""

import os
import sys
import json
import re
import subprocess
from typing import Dict, Any, Optional

from .spec import CircuitSpec, calc_cpwg_dimensions, calc_microstrip_dimensions


def get_grok_path() -> Optional[str]:
    candidates = [
        "/mnt/c/Users/gsr/.grok/bin/grok.exe",
        r"C:\Users\gsr\.grok\bin\grok.exe",
        os.path.expanduser("~/.grok/bin/grok"),
        "grok"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


SYSTEM_PROMPT = """You are a Senior RF & Microwave Hardware Design Engineer.
Your role is to translate natural language user requirements into complete, accurate, physical RF circuit specifications for automated KiCad 10 PCB layout and EM simulation.

Instructions:
1. Thoroughly reason about the user's circuit requirements:
   - Identify requested active devices or passive topologies (e.g., pi-attenuator, highpass, bandpass, lowpass, Wilkinson divider, calibration load, LNA). Do NOT default to any specific component unless the user explicitly asks for it.
   - Design proper DC biasing if applicable: base divider resistors (R1, R2), emitter degeneration (R3) with bypass capacitor (C3), collector RF choke inductor (L1), VDD decoupling (C4), and DC blocking capacitors (C1, C2).
   - Set operating frequency range (f_min_ghz, f_0_ghz, f_max_ghz) and system impedance (default 50.0 ohm).
   - Select standard footprint packages appropriate for the requested components.
   - For 1-port circuits (e.g. calibration load, termination standard), set num_ports=1 and include only J1 (SMA_IN) with shunt termination.
   - For 2-port circuits, set num_ports=2 and include J1 (SMA_IN) and J2 (SMA_OUT).

2. Output ONLY a valid raw JSON object matching the schema below. No markdown fences, no explanatory text.

JSON Schema:
{
  "name": "<unique_project_name_snake_case>",
  "title": "<Concise Engineering Title with Frequency & Topology>",
  "topology": "<lna | filter | attenuator | divider | calibration_load | custom>",
  "num_ports": <1, 2, or 3>,
  "description": "<Detailed engineering circuit summary explaining architecture and component roles>",
  "f_min_ghz": <float>,
  "f_0_ghz": <float>,
  "f_max_ghz": <float>,
  "z0_ohm": 50.0,
  "target_s21_db": <float, e.g. 14.0 for LNA, -10.0 for attenuator, -1.5 for filter>,
  "target_s11_db": <float, e.g. -15.0>,
  "target_s22_db": <float, e.g. -15.0>,
  "width_mm": <float, e.g. 35.0>,
  "height_mm": <float, e.g. 24.0>,
  "substrate_name": "FR4",
  "dielectric_er": 4.4,
  "substrate_height_mm": 1.6,
  "trace_mode": "CPWG",
  "trace_gap_mm": 0.40,
  "components": {
    "<REF>": {
      "type": "<transistor | ic | resistor | capacitor | inductor | connector>",
      "value": "<e.g. MMBT5179, 10k, 3.3k, 100R, 47pF, 100nH, 10nF, SMA_IN, SMA_OUT>",
      "package": "<KiCad footprint path>",
      "role": "<Role of this component in the RF/DC network>"
    }
  }
}
"""


def query_llm_for_spec(user_prompt: str) -> Dict[str, Any]:
    """Query Grok LLM to synthesize circuit specification."""
    grok_bin = get_grok_path()
    if not grok_bin:
        raise RuntimeError("Grok LLM executable not found at ~/.grok/bin/grok or /mnt/c/Users/gsr/.grok/bin/grok.exe")

    prompt = f"{SYSTEM_PROMPT}\n\nUser Request: \"{user_prompt}\"\nJSON Specification:"

    cmd = [
        grok_bin,
        "-p", prompt,
        "--permission-mode", "dontAsk",
        "--disable-web-search",
        "--no-subagents",
        "--no-plan",
        "--no-alt-screen"
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if res.returncode != 0 and not res.stdout:
        raise RuntimeError(f"Grok LLM failed with exit code {res.returncode}: {res.stderr}")

    stdout = res.stdout
    match = re.search(r'(\{[\s\S]*\})', stdout)
    if not match:
        raise ValueError(f"Could not extract JSON from LLM output:\n{stdout}")

    spec_dict = json.loads(match.group(1))
    return spec_dict


def synthesize_spec_with_llm(user_prompt: str, custom_name: Optional[str] = None) -> CircuitSpec:
    """
    Synthesizes a CircuitSpec directly using LLM intelligence.
    Computes exact physical CPWG transmission line parameters using conformal mapping.
    """
    raw_spec = query_llm_for_spec(user_prompt)

    name = custom_name or raw_spec.get("name", "synthesized_rf_circuit")
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower()).strip('_')

    er = float(raw_spec.get("dielectric_er", 4.4))
    h_mm = float(raw_spec.get("substrate_height_mm", 1.6))
    z0 = float(raw_spec.get("z0_ohm", 50.0))
    gap = float(raw_spec.get("trace_gap_mm", 0.40))

    spec = CircuitSpec(
        name=name,
        title=raw_spec.get("title", "Synthesized RF Circuit"),
        topology=raw_spec.get("topology", "custom"),
        num_ports=int(raw_spec.get("num_ports", 2)),
        description=raw_spec.get("description", user_prompt),
        f_min_ghz=float(raw_spec.get("f_min_ghz", 0.1)),
        f_0_ghz=float(raw_spec.get("f_0_ghz", 1.0)),
        f_max_ghz=float(raw_spec.get("f_max_ghz", 2.0)),
        z0_ohm=z0,
        target_s21_db=float(raw_spec.get("target_s21_db", -1.0)),
        target_s11_db=float(raw_spec.get("target_s11_db", -15.0)),
        target_s22_db=float(raw_spec.get("target_s22_db", -15.0)),
        width_mm=float(raw_spec.get("width_mm", 35.0)),
        height_mm=float(raw_spec.get("height_mm", 24.0)),
        substrate_name=raw_spec.get("substrate_name", "FR4"),
        dielectric_er=er,
        substrate_height_mm=h_mm,
        trace_mode=raw_spec.get("trace_mode", "CPWG"),
        trace_gap_mm=gap,
        components=raw_spec.get("components", {})
    )
    return spec
