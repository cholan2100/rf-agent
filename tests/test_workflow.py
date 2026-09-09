"""
Unit tests for the headless workflow engine.
"""

import os
import unittest
import tempfile
from agent.workflow import execute_workflow, load_spec_from_json
from agent.spec import PRESET_10DB_ATTENUATOR


class TestWorkflowEngine(unittest.TestCase):

    def test_workflow_execution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Test running schematic and PCB stages headlessly
            results = execute_workflow(
                spec=PRESET_10DB_ATTENUATOR,
                project_root=tmp_dir,
                stages=["schematic", "pcb", "em"],
                verbose=False
            )

            self.assertEqual(results["status"], "success")
            proj_dir = os.path.join(tmp_dir, PRESET_10DB_ATTENUATOR.name)
            self.assertTrue(os.path.isdir(proj_dir))
            self.assertTrue(os.path.isfile(os.path.join(proj_dir, "spec.json")))
            self.assertTrue(os.path.isfile(os.path.join(proj_dir, f"{PRESET_10DB_ATTENUATOR.name}.kicad_sch")))
            self.assertTrue(os.path.isfile(os.path.join(proj_dir, f"{PRESET_10DB_ATTENUATOR.name}.kicad_pcb")))
            self.assertTrue(os.path.isfile(os.path.join(proj_dir, "simulation", f"{PRESET_10DB_ATTENUATOR.name}.s2p")))

            # Test loading spec from json
            loaded = load_spec_from_json(os.path.join(proj_dir, "spec.json"))
            self.assertEqual(loaded.name, PRESET_10DB_ATTENUATOR.name)
            self.assertEqual(loaded.z0_ohm, 50.0)


if __name__ == "__main__":
    unittest.main()
