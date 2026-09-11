"""
AWS Remote Execution & Synchronization Module for RF Suite.
Allows rf-agent to run EDA, simulation, and raytracing workflows on an AWS EC2 instance.
"""


def __getattr__(name):
    if name in ("run_remote_command", "get_aws_config", "check_instance_status"):
        from . import rf_remote_client
        return getattr(rf_remote_client, name)
    elif name in ("sync_workspace_to_aws", "sync_workspace_from_aws"):
        from . import sync_manager
        return getattr(sync_manager, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "run_remote_command",
    "get_aws_config",
    "check_instance_status",
    "sync_workspace_to_aws",
    "sync_workspace_from_aws",
]
