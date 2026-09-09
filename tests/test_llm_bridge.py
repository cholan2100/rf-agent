"""
Unit tests for the Agent LLM Bridge, IPC, and synthesis fallbacks using stdlib unittest.
"""

import os
import time
import json
import unittest
import tempfile
from agent.llm_bridge import AgentBridgeProvider, LLMClient
from agent.spec import CircuitSpec


class TestLLMBridge(unittest.TestCase):

    def test_bridge_request_response(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bridge_dir = os.path.join(tmp_dir, ".bridge")
            provider = AgentBridgeProvider(bridge_dir=bridge_dir, timeout_sec=2)

            req_id = "test_req_123"
            req_file = os.path.join(provider.req_dir, f"{req_id}.json")
            resp_file = os.path.join(provider.resp_dir, f"{req_id}.json")

            # Simulate pending request
            with open(req_file, "w", encoding="utf-8") as f:
                json.dump({"id": req_id, "user_prompt": "Test prompt", "task_type": "circuit_synthesis"}, f)

            pending = provider.list_pending_requests()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["id"], req_id)

            # Test responding with UTF-8 BOM
            response_payload = {
                "name": "test_filter",
                "title": "Test 2.4 GHz Lowpass Filter",
                "topology": "lowpass",
                "f_0_ghz": 2.4,
                "components": {
                    "C1": {"type": "capacitor", "value": "1.2pF", "nominal_val": 1.2e-12, "package": "Capacitor_SMD:C_0805_2012Metric", "role": "Shunt C"}
                }
            }
            # Write with utf-8-sig (BOM)
            with open(resp_file, "w", encoding="utf-8-sig") as f:
                json.dump(response_payload, f)

            # Provider should read and parse without error
            with open(resp_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            self.assertEqual(data["name"], "test_filter")
            self.assertEqual(data["f_0_ghz"], 2.4)

    def test_llm_client_build_spec(self):
        client = LLMClient(provider="analytical")
        mock_dict = {
            "name": "attenuator_3db",
            "title": "3 dB Precision Attenuator",
            "topology": "attenuator",
            "description": "3dB Pi attenuator",
            "f_0_ghz": 2.0,
            "target_s21_db": -3.0,
            "target_s11_db": -25.0,
            "components": {
                "R1": {"type": "resistor", "value": "294R", "nominal_val": 294.0, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Shunt"},
                "R2": {"type": "resistor", "value": "17.6R", "nominal_val": 17.6, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Series"},
                "R3": {"type": "resistor", "value": "294R", "nominal_val": 294.0, "package": "Resistor_SMD:R_0805_2012Metric", "role": "Shunt"}
            }
        }

        spec = client._build_spec_from_dict(
            d=mock_dict,
            z0=50.0,
            substrate_name="FR4",
            er=4.4,
            h_mm=1.6,
            width_mm=30.0,
            height_mm=20.0,
            em_sim_type="traces"
        )

        self.assertIsInstance(spec, CircuitSpec)
        self.assertEqual(spec.name, "attenuator_3db")
        self.assertEqual(spec.target_s21_db, -3.0)
        self.assertIn("J1", spec.components)
        self.assertIn("J2", spec.components)
        self.assertIn("R1", spec.components)
        self.assertIn("R2", spec.components)
        self.assertIn("R3", spec.components)

    def test_analytical_fallback_synthesis(self):
        client = LLMClient(provider="analytical")
        spec = client.synthesize_circuit("10 dB precision Pi-attenuator", f0_ghz=1.0)
        self.assertIsInstance(spec, CircuitSpec)
        self.assertIn("attenuator", spec.name)
        self.assertEqual(spec.target_s21_db, -10.0)


if __name__ == "__main__":
    unittest.main()
