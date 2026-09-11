"""
Workspace Synchronization Manager for AWS-hosted RF Suite.
Handles bidirectional syncing of project files between local workstation and AWS.
"""

import os
import sys
import subprocess
import shutil
from typing import Dict, Optional


def load_env_file(env_path: Optional[str] = None) -> Dict[str, str]:
    """Loads key-value pairs from .env file into a dictionary and environment."""
    config = {}
    if not env_path:
        # Check standard locations: root of repo or rf-suite
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        possible_paths = [
            os.path.join(repo_root, ".env"),
            os.path.join(repo_root, "rf-suite", ".env"),
        ]
        for p in possible_paths:
            if os.path.isfile(p):
                env_path = p
                break

    if env_path and os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    config[key] = val
                    if key not in os.environ:
                        os.environ[key] = val
    return config


def get_sync_config() -> Dict[str, str]:
    """Retrieves sync configuration from environment or .env."""
    load_env_file()
    return {
        "bucket": os.getenv("AWS_S3_BUCKET", ""),
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "instance_id": os.getenv("AWS_INSTANCE_ID", ""),
        "remote_method": os.getenv("RF_REMOTE_METHOD", "ssm"),
        "remote_workspace": os.getenv("RF_REMOTE_WORKSPACE", "/opt/rf-agent-host/workspace"),
        "ssh_host": os.getenv("AWS_SSH_HOST", ""),
        "ssh_user": os.getenv("AWS_SSH_USER", "ubuntu"),
        "ssh_key": os.getenv("AWS_SSH_KEY", ""),
    }


def find_repo_root() -> str:
    """Finds repository root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def sync_workspace_to_aws(project_name: Optional[str] = None, verbose: bool = True) -> bool:
    """
    Syncs local projects/ directory or specific project to AWS.
    If S3 bucket is configured, syncs local -> S3 -> EC2.
    """
    cfg = get_sync_config()
    repo_root = find_repo_root()
    local_projects_dir = os.path.join(repo_root, "projects")
    
    if not os.path.exists(local_projects_dir):
        os.makedirs(local_projects_dir, exist_ok=True)

    # 1. S3-based Synchronization
    if cfg["bucket"]:
        if project_name:
            local_src = os.path.join(local_projects_dir, project_name)
            s3_dest = f"s3://{cfg['bucket']}/workspace/projects/{project_name}"
        else:
            local_src = local_projects_dir
            s3_dest = f"s3://{cfg['bucket']}/workspace/projects"

        if os.path.exists(local_src):
            if verbose:
                print(f"[Sync Up] Syncing local files to S3: {local_src} -> {s3_dest}...")
            cmd = [
                "aws", "s3", "sync",
                local_src, s3_dest,
                "--region", cfg["region"],
                "--exclude", "*.pyc",
                "--exclude", "__pycache__/*",
                "--exclude", "*.tmp",
                "--delete"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                if verbose:
                    print(f"[Sync Up] Warning: Local to S3 sync failed: {res.stderr}")
                return False

        # Also sync agent code to ensure latest workflow logic is on remote host
        local_agent_dir = os.path.join(repo_root, "agent")
        s3_agent_dest = f"s3://{cfg['bucket']}/workspace/agent"
        if os.path.exists(local_agent_dir):
            cmd_agent = [
                "aws", "s3", "sync",
                local_agent_dir, s3_agent_dest,
                "--region", cfg["region"],
                "--exclude", "*.pyc",
                "--exclude", "__pycache__/*",
                "--delete"
            ]
            subprocess.run(cmd_agent, capture_output=True, text=True)

        # Instruct EC2 instance to pull from S3
        if cfg["instance_id"] and cfg["remote_method"] == "ssm":
            if verbose:
                print(f"[Sync Up] Instructing AWS instance {cfg['instance_id']} to pull workspace and agent from S3...")
            remote_cmd = (
                f"aws s3 sync s3://{cfg['bucket']}/workspace/projects {cfg['remote_workspace']}/projects "
                f"--region {cfg['region']} --delete && "
                f"aws s3 sync s3://{cfg['bucket']}/workspace/agent {cfg['remote_workspace']}/agent "
                f"--region {cfg['region']} --delete"
            )
            from .rf_remote_client import execute_ssm_command
            res_code, out, err = execute_ssm_command(cfg["instance_id"], [remote_cmd], region=cfg["region"], wait=True)
            if res_code != 0:
                if verbose:
                    print(f"[Sync Up] Remote S3 pull error: {err or out}")
                return False

        if verbose:
            print("[Sync Up] Project and agent code sync to AWS complete.")
        return True

    # 2. SSH / SCP-based Synchronization
    elif cfg["ssh_host"]:
        remote_dest = f"{cfg['ssh_user']}@{cfg['ssh_host']}:{cfg['remote_workspace']}/projects/"
        if verbose:
            print(f"[Sync Up] Syncing via SCP/rsync to {remote_dest}...")
        
        # Check if rsync is available
        if shutil.which("rsync"):
            ssh_opt = f"ssh -i {cfg['ssh_key']}" if cfg['ssh_key'] else "ssh"
            cmd = ["rsync", "-avz", "-e", ssh_opt, "--exclude", "__pycache__", local_projects_dir + "/", remote_dest]
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode == 0
        else:
            # Fallback to scp
            cmd = ["scp", "-r"]
            if cfg["ssh_key"]:
                cmd.extend(["-i", cfg["ssh_key"]])
            cmd.extend([local_projects_dir, f"{cfg['ssh_user']}@{cfg['ssh_host']}:{cfg['remote_workspace']}/"])
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode == 0

    if verbose:
        print("[Sync Up] Notice: Neither AWS_S3_BUCKET nor AWS_SSH_HOST configured. Skipping pre-sync.")
    return True


def sync_workspace_from_aws(project_name: Optional[str] = None, verbose: bool = True) -> bool:
    """
    Syncs output files and deliverables from AWS back to local workstation.
    EC2 -> S3 -> local projects/
    """
    cfg = get_sync_config()
    repo_root = find_repo_root()
    local_projects_dir = os.path.join(repo_root, "projects")
    os.makedirs(local_projects_dir, exist_ok=True)

    # 1. S3-based Synchronization
    if cfg["bucket"]:
        # Remote pushes to S3 first
        if cfg["instance_id"] and cfg["remote_method"] == "ssm":
            if verbose:
                print(f"[Sync Down] Pushing remote deliverables from EC2 to S3...")
            remote_cmd = (
                f"aws s3 sync {cfg['remote_workspace']}/projects s3://{cfg['bucket']}/workspace/projects "
                f"--region {cfg['region']} --delete"
            )
            from .rf_remote_client import execute_ssm_command
            res_code, out, err = execute_ssm_command(cfg["instance_id"], [remote_cmd], region=cfg["region"], wait=True)
            if res_code != 0:
                if verbose:
                    print(f"[Sync Down] Remote S3 upload error: {err or out}")

        # Local pulls from S3
        if project_name:
            s3_src = f"s3://{cfg['bucket']}/workspace/projects/{project_name}"
            local_dest = os.path.join(local_projects_dir, project_name)
        else:
            s3_src = f"s3://{cfg['bucket']}/workspace/projects"
            local_dest = local_projects_dir

        if verbose:
            print(f"[Sync Down] Pulling deliverables from S3 to local: {s3_src} -> {local_dest}...")
        cmd = [
            "aws", "s3", "sync",
            s3_src, local_dest,
            "--region", cfg["region"],
            "--exclude", "*.pyc",
            "--exclude", "__pycache__/*",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            if verbose:
                print(f"[Sync Down] Successfully retrieved deliverables to {local_dest}")
            return True
        else:
            if verbose:
                print(f"[Sync Down] S3 pull error: {res.stderr}")
            return False

    # 2. SSH / SCP-based Synchronization
    elif cfg["ssh_host"]:
        remote_src = f"{cfg['ssh_user']}@{cfg['ssh_host']}:{cfg['remote_workspace']}/projects/"
        if verbose:
            print(f"[Sync Down] Syncing deliverables via rsync/SCP from {remote_src}...")
        if shutil.which("rsync"):
            ssh_opt = f"ssh -i {cfg['ssh_key']}" if cfg['ssh_key'] else "ssh"
            cmd = ["rsync", "-avz", "-e", ssh_opt, remote_src, local_projects_dir + "/"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode == 0
        else:
            cmd = ["scp", "-r"]
            if cfg["ssh_key"]:
                cmd.extend(["-i", cfg["ssh_key"]])
            cmd.extend([remote_src, local_projects_dir])
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode == 0

    return False
