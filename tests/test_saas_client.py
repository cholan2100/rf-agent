"""
Unit Tests for RFSaasClient.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from agent.saas.client import RFSaasClient


class TestRFSaasClient(unittest.TestCase):

    def setUp(self):
        self.client = RFSaasClient(base_url="http://mock-saas:8000", api_key="secret-key")

    @patch("urllib.request.urlopen")
    def test_01_health_check(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "healthy", "service": "rf-suite-saas"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        health = self.client.check_health()
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["service"], "rf-suite-saas")

    @patch("urllib.request.urlopen")
    def test_02_synthesize_spec(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"name": "mock_filter", "z0_ohm": 50.0}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        spec = self.client.synthesize_spec("100MHz lowpass filter")
        self.assertEqual(spec["name"], "mock_filter")
        self.assertEqual(spec["z0_ohm"], 50.0)

    @patch("urllib.request.urlopen")
    def test_03_run_stages(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"project_name": "mock_filter", "status": "completed"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = self.client.run_stages("mock_filter", stages=["schematic", "pcb"])
        self.assertEqual(res["status"], "completed")


if __name__ == "__main__":
    unittest.main()
