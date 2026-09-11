"""
Unit and Integration Tests for RF Suite Hosted SaaS Microservice API.
"""

import os
import sys
import unittest
from starlette.testclient import TestClient

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from agent.saas.app import app


class TestRFSaasApi(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_health_endpoint(self):
        """Test GET /health returns solver status and version metadata."""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "rf-suite-saas")
        self.assertIn("eda_tools", data)
        self.assertIn("kicad", data["eda_tools"])

    def test_02_synthesize_spec(self):
        """Test POST /v1/specs/synthesize parses natural language circuit requirements."""
        payload = {
            "prompt": "10dB symmetric Pi-attenuator for 2.4GHz Wi-Fi band with 50 Ohm CPWG line",
            "name": "test_saas_attenuator",
            "z0_ohm": 50.0,
            "substrate": "FR4",
            "er": 4.4,
            "h_mm": 1.6
        }
        resp = self.client.post("/v1/specs/synthesize", json=payload)
        self.assertEqual(resp.status_code, 200)
        spec = resp.json()
        self.assertEqual(spec["name"], "test_saas_attenuator")
        self.assertEqual(spec["z0_ohm"], 50.0)
        self.assertIn("R1", spec["components"])
        self.assertIn("R2", spec["components"])
        self.assertIn("R3", spec["components"])
        self.assertAlmostEqual(spec["rf_trace_width_mm"], 1.87, delta=0.05)

    def test_03_run_schematic_stage(self):
        """Test POST /v1/projects/{name}/run executes schematic generation headlessly."""
        payload = {
            "desc": "10dB symmetric Pi-attenuator for 2.4GHz with 50 Ohm CPWG line",
            "stages": ["schematic"]
        }
        resp = self.client.post("/v1/projects/test_saas_attenuator/run", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["project_name"], "test_saas_attenuator")
        self.assertIn("schematic", data["executed_stages"])
        self.assertIn("test_saas_attenuator.kicad_sch", str(data["artifacts"]) + str(data["stage_results"]))

    def test_04_artifact_streaming(self):
        """Test GET /v1/projects/{name}/artifacts/{path} streams generated files."""
        # Ensure project exists from test_03
        resp = self.client.get("/v1/projects/test_saas_attenuator/artifacts/spec.json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/json")
        spec_data = resp.json()
        self.assertEqual(spec_data["name"], "test_saas_attenuator")

    def test_05_path_traversal_protection(self):
        """Test that directory traversal attempts are rejected with 403/404."""
        resp = self.client.get("/v1/projects/test_saas_attenuator/artifacts/../../etc/passwd")
        self.assertIn(resp.status_code, [403, 404])


if __name__ == "__main__":
    unittest.main()
