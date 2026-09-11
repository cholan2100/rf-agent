"""
Tests for RF Suite AWS integration, configuration loading, and remote execution logic.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add repository root to python path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agent.aws.rf_remote_client import get_aws_config, check_instance_status, is_aws_mode, execute_ssm_command
from agent.aws.sync_manager import get_sync_config, sync_workspace_to_aws, sync_workspace_from_aws


class TestAWSIntegration(unittest.TestCase):

    def setUp(self):
        # Save original environment
        self.orig_env = os.environ.copy()

    def tearDown(self):
        # Restore environment
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_default_config_is_local(self):
        os.environ["RF_BACKEND"] = "local"
        os.environ.pop("AWS_INSTANCE_ID", None)
        cfg = get_aws_config()
        self.assertEqual(cfg["backend"], "local")
        self.assertFalse(is_aws_mode())

    def test_aws_mode_enabled_via_env(self):
        os.environ["RF_BACKEND"] = "aws"
        os.environ["AWS_REGION"] = "us-west-2"
        os.environ["AWS_INSTANCE_ID"] = "i-1234567890abcdef0"
        os.environ["AWS_S3_BUCKET"] = "test-rf-bucket"

        cfg = get_aws_config()
        self.assertEqual(cfg["backend"], "aws")
        self.assertEqual(cfg["region"], "us-west-2")
        self.assertEqual(cfg["instance_id"], "i-1234567890abcdef0")
        self.assertEqual(cfg["bucket"], "test-rf-bucket")
        self.assertTrue(is_aws_mode())

    @patch("subprocess.run")
    def test_check_instance_status(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.stdout = "running\n"
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        status = check_instance_status("i-test", "us-east-1")
        self.assertEqual(status, "running")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("describe-instances", args)
        self.assertIn("i-test", args)

    @patch("subprocess.run")
    def test_execute_ssm_command_send(self, mock_run):
        # Mock send-command response
        mock_send = MagicMock()
        mock_send.stdout = "cmd-12345\n"
        mock_send.returncode = 0

        # Mock get-command-invocation response
        mock_inv = MagicMock()
        mock_inv.returncode = 0
        mock_inv.stdout = '{"Status": "Success", "ResponseCode": 0, "StandardOutputContent": "Done", "StandardErrorContent": ""}'

        mock_run.side_effect = [mock_send, mock_inv]

        code, out, err = execute_ssm_command("i-test", ["echo Hello"], region="us-east-1", wait=True, poll_interval=0.01)
        self.assertEqual(code, 0)
        self.assertEqual(out, "Done")
        self.assertEqual(err, "")

    @patch("subprocess.run")
    def test_sync_workspace_to_aws(self, mock_run):
        os.environ["AWS_S3_BUCKET"] = "test-bucket"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ.pop("AWS_INSTANCE_ID", None)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        res = sync_workspace_to_aws(verbose=False)
        self.assertTrue(res)
        self.assertTrue(mock_run.called)
        args = mock_run.call_args[0][0]
        self.assertIn("s3", args)
        self.assertIn("sync", args)


if __name__ == "__main__":
    unittest.main()
