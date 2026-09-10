"""
Unit tests for the headless workflow engine and dynamic circuit synthesis.
"""

import os
import unittest
import tempfile
from agent.workflow import execute_workflow, load_spec_from_json
from agent.spec import parse_custom_circuit, extract_rf_frequency, extract_component_overrides


class TestWorkflowEngine(unittest.TestCase):

    def test_workflow_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Dynamic circuit synthesized clean from scratch
            spec = parse_custom_circuit(
                description="Precision 10 dB RF Pi-Attenuator with 50-ohm matching at 1.5 GHz",
                f0_ghz=1.5,
                z0=50.0
            )

            results = execute_workflow(
                spec=spec,
                project_root=tmp_dir,
                stages=["schematic", "pcb", "em"],
                verbose=False
            )

            self.assertEqual(results["status"], "success")
            proj_dir = os.path.join(tmp_dir, spec.name)
            self.assertTrue(os.path.isdir(proj_dir))
            self.assertTrue(os.path.isfile(os.path.join(proj_dir, "spec.json")))
            self.assertTrue(os.path.isfile(os.path.join(proj_dir, f"{spec.name}.kicad_sch")))
            self.assertTrue(os.path.isfile(os.path.join(proj_dir, f"{spec.name}.kicad_pcb")))
            self.assertTrue(os.path.isfile(os.path.join(proj_dir, "simulation", f"{spec.name}.s2p")))

            # Test loading spec from json
            loaded = load_spec_from_json(os.path.join(proj_dir, "spec.json"))
            self.assertEqual(loaded.name, spec.name)
            self.assertEqual(loaded.z0_ohm, 50.0)

    def test_frequency_extraction_precedence(self):
        # Explicit numeric frequency must take precedence over named bands
        f = extract_rf_frequency("2.45 GHz Wi-Fi bandpass filter")
        self.assertEqual(f, 2.45)

        f_mhz = extract_rf_frequency("433.92 MHz ISM transmitter filter")
        self.assertAlmostEqual(f_mhz, 0.43392, places=4)

    def test_component_overrides(self):
        # User specified explicit components
        spec = parse_custom_circuit(
            description="6 dB attenuator with R1=150.5R, R2=37.4R, R3=150.5R at 2.45 GHz",
            f0_ghz=2.45
        )
        self.assertEqual(spec.f_0_ghz, 2.45)
        self.assertEqual(spec.components["R1"]["nominal_ohm"], 150.5)
        self.assertEqual(spec.components["R2"]["nominal_ohm"], 37.4)
        self.assertEqual(spec.components["R3"]["nominal_ohm"], 150.5)

    def test_through_line_synthesis(self):
        spec = parse_custom_circuit(
            description="50 ohm CPWG transmission line through test fixture at 5.8 GHz"
        )
        self.assertEqual(spec.topology, "through")
        self.assertEqual(spec.f_0_ghz, 5.8)
        self.assertEqual(len(spec.components), 2)  # J1 and J2 only, zero dummy resistors
        self.assertIn("J1", spec.components)
        self.assertIn("J2", spec.components)


if __name__ == "__main__":
    unittest.main()

