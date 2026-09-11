"""
AWS Remote Execution & Synchronization Module for RF Suite.
Allows rf-agent to run EDA, simulation, and raytracing workflows on an AWS EC2 instance.
"""

from .rf_remote_client import run_remote_command, get_aws_config, check_instance_status
from .sync_manager import sync_workspace_to_aws, sync_workspace_from_aws

__all__ = [
    "run_remote_command",
    "get_aws_config",
    "check_instance_status",
    "sync_workspace_to_aws",
    "sync_workspace_from_aws",
]
