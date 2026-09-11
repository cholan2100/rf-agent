"""
AWS Remote Execution Client for RF Suite.
Dispatches EDA/simulation commands to AWS EC2 via AWS SSM or SSH,
streaming output and managing bidirectional workspace synchronization.
"""

import os
import sys
import json
import time
import shutil
import shlex
import subprocess
import argparse
import webbrowser
from typing import Dict, List, Tuple, Optional

try:
    from .sync_manager import sync_workspace_to_aws, sync_workspace_from_aws
except ImportError:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from agent.aws.sync_manager import sync_workspace_to_aws, sync_workspace_from_aws


def load_env_file(env_path: Optional[str] = None) -> Dict[str, str]:
    """Loads key-value pairs from .env file."""
    config = {}
    if not env_path:
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


def get_aws_config() -> Dict[str, str]:
    """Returns the consolidated AWS configuration."""
    load_env_file()
    return {
        "backend": os.getenv("RF_BACKEND", "local").lower(),
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "instance_id": os.getenv("AWS_INSTANCE_ID", ""),
        "bucket": os.getenv("AWS_S3_BUCKET", ""),
        "remote_method": os.getenv("RF_REMOTE_METHOD", "ssm").lower(),
        "remote_workspace": os.getenv("RF_REMOTE_WORKSPACE", "/opt/rf-agent-host/workspace"),
        "compose_dir": os.getenv("RF_COMPOSE_DIR", "/opt/rf-agent-host/rf-suite"),
        "ssh_host": os.getenv("AWS_SSH_HOST", ""),
        "ssh_user": os.getenv("AWS_SSH_USER", "ubuntu"),
        "ssh_key": os.getenv("AWS_SSH_KEY", ""),
    }


def is_aws_mode() -> bool:
    """Returns True if AWS backend is active."""
    cfg = get_aws_config()
    return cfg["backend"] == "aws" or bool(cfg["instance_id"])


def check_instance_status(instance_id: Optional[str] = None, region: Optional[str] = None) -> str:
    """Returns the EC2 instance state: running, stopped, pending, etc."""
    cfg = get_aws_config()
    iid = instance_id or cfg["instance_id"]
    reg = region or cfg["region"]
    if not iid:
        return "not_configured"

    cmd = [
        "aws", "ec2", "describe-instances",
        "--instance-ids", iid,
        "--region", reg,
        "--query", "Reservations[0].Instances[0].State.Name",
        "--output", "text"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"error: {e.stderr.strip()}"
    except FileNotFoundError:
        return "aws_cli_missing"


def start_instance(instance_id: Optional[str] = None, region: Optional[str] = None, wait: bool = True) -> bool:
    """Starts the EC2 instance and waits until running."""
    cfg = get_aws_config()
    iid = instance_id or cfg["instance_id"]
    reg = region or cfg["region"]
    if not iid:
        print("[RF Suite AWS] Error: No AWS_INSTANCE_ID configured.")
        return False

    print(f"[RF Suite AWS] Starting instance {iid} ({reg})...")
    cmd = ["aws", "ec2", "start-instances", "--instance-ids", iid, "--region", reg]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[RF Suite AWS] Failed to start instance: {res.stderr}")
        return False

    if wait:
        print("[RF Suite AWS] Waiting for instance to become 'running'...", end="", flush=True)
        for _ in range(60):
            time.sleep(3)
            status = check_instance_status(iid, reg)
            print(".", end="", flush=True)
            if status == "running":
                print(" Ready!")
                # Give SSM agent and docker service a few seconds to stabilize
                time.sleep(5)
                return True
            elif status.startswith("error"):
                print(f"\n[RF Suite AWS] Error checking status: {status}")
                return False
        print("\n[RF Suite AWS] Timeout waiting for instance to start.")
        return False
    return True


def stop_instance(instance_id: Optional[str] = None, region: Optional[str] = None) -> bool:
    """Stops the EC2 instance to prevent unnecessary charges."""
    cfg = get_aws_config()
    iid = instance_id or cfg["instance_id"]
    reg = region or cfg["region"]
    if not iid:
        print("[RF Suite AWS] Error: No AWS_INSTANCE_ID configured.")
        return False

    print(f"[RF Suite AWS] Stopping instance {iid} ({reg}) to conserve cloud costs...")
    cmd = ["aws", "ec2", "stop-instances", "--instance-ids", iid, "--region", reg]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"✔ Instance {iid} stop initiated successfully.")
        return True
    else:
        print(f"[RF Suite AWS] Failed to stop instance: {res.stderr}")
        return False


def execute_ssm_command(
    instance_id: str,
    commands: List[str],
    region: str = "us-east-1",
    wait: bool = True,
    poll_interval: float = 2.0,
    timeout_sec: int = 600
) -> Tuple[int, str, str]:
    """
    Executes shell commands on EC2 via AWS Systems Manager (SSM) Send-Command.
    Returns (exit_code, stdout, stderr).
    """
    cmd_params = json.dumps({"commands": commands})
    send_cmd = [
        "aws", "ssm", "send-command",
        "--instance-ids", instance_id,
        "--region", region,
        "--document-name", "AWS-RunShellScript",
        "--parameters", cmd_params,
        "--query", "Command.CommandId",
        "--output", "text"
    ]
    res = subprocess.run(send_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return 1, "", f"SSM send-command error: {res.stderr}"

    command_id = res.stdout.strip()
    if not wait:
        return 0, f"Command sent with ID: {command_id}", ""

    # Poll command invocation status
    start_time = time.time()
    get_cmd = [
        "aws", "ssm", "get-command-invocation",
        "--command-id", command_id,
        "--instance-id", instance_id,
        "--region", region,
        "--output", "json"
    ]

    while time.time() - start_time < timeout_sec:
        time.sleep(poll_interval)
        inv_res = subprocess.run(get_cmd, capture_output=True, text=True)
        if inv_res.returncode != 0:
            continue
        try:
            data = json.loads(inv_res.stdout)
            status = data.get("Status", "Pending")
            if status in ["Success", "Failed", "TimedOut", "Cancelled"]:
                code = data.get("ResponseCode", 0 if status == "Success" else 1)
                stdout = data.get("StandardOutputContent", "")
                stderr = data.get("StandardErrorContent", "")
                return code, stdout, stderr
        except Exception:
            pass

    return 124, "", f"SSM Command timed out after {timeout_sec} seconds (ID: {command_id})"


def execute_ssh_command(
    host: str,
    user: str,
    key_path: str,
    command: str,
    timeout_sec: int = 600
) -> Tuple[int, str, str]:
    """Executes a command on the remote instance via SSH."""
    cmd = ["ssh"]
    if key_path:
        cmd.extend(["-i", key_path])
    cmd.extend([
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{user}@{host}",
        command
    ])
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"SSH command timed out after {timeout_sec}s"
    except Exception as e:
        return 1, "", str(e)


def open_gui_tunnel(instance_id: Optional[str] = None, region: Optional[str] = None, port: int = 6080):
    """
    Opens an encrypted AWS SSM port-forwarding session to port 6080 (noVNC desktop)
    and opens the browser at http://localhost:6080/vnc.html.
    """
    cfg = get_aws_config()
    iid = instance_id or cfg["instance_id"]
    reg = region or cfg["region"]
    if not iid:
        print("[RF Suite AWS] Error: No AWS_INSTANCE_ID configured.")
        return

    # Check status
    st = check_instance_status(iid, reg)
    if st != "running":
        print(f"[RF Suite AWS] Instance is currently '{st}'. Starting instance first...")
        if not start_instance(iid, reg):
            return

    print("======================================================================")
    print(f"  Starting AWS SSM Port Forwarding Tunnel to {iid} (Port {port})...")
    print(f"  Web GUI URL: http://localhost:{port}/vnc.html")
    print("  Press Ctrl+C in this terminal to terminate the GUI tunnel session.")
    print("======================================================================")

    url = f"http://localhost:{port}/vnc.html"
    try:
        webbrowser.open(url)
    except Exception:
        pass

    params = json.dumps({"portNumber": [str(port)], "localPortNumber": [str(port)]})
    tunnel_cmd = [
        "aws", "ssm", "start-session",
        "--target", iid,
        "--region", reg,
        "--document-name", "AWS-StartPortForwardingSession",
        "--parameters", params
    ]
    subprocess.run(tunnel_cmd)


def run_remote_command(command_args: List[str], verbose: bool = True) -> int:
    """
    Full workflow runner:
    1. Verify instance is running (starts it if stopped)
    2. Sync local workspace projects to AWS
    3. Execute command inside the remote rf-suite container
    4. Sync deliverables back to local workspace
    5. Return command exit code
    """
    cfg = get_aws_config()
    iid = cfg["instance_id"]
    reg = cfg["region"]

    if not iid and not cfg["ssh_host"]:
        print("[RF Suite AWS] Error: AWS_INSTANCE_ID or AWS_SSH_HOST must be set in .env or environment.")
        return 1

    # 1. Check EC2 instance status
    if iid:
        status = check_instance_status(iid, reg)
        if status == "aws_cli_missing":
            print("[RF Suite AWS] Error: 'aws' CLI command not found in PATH.")
            return 1
        elif status == "stopped":
            print(f"[RF Suite AWS] Instance {iid} is currently stopped.")
            if not start_instance(iid, reg):
                return 1
        elif status != "running":
            print(f"[RF Suite AWS] Instance {iid} status: '{status}'. Waiting for running state...")
            if not start_instance(iid, reg):
                return 1

    # 2. Sync local workspace to AWS
    if verbose:
        print("[RF Suite AWS] Synchronizing local workspace to AWS host...")
    sync_workspace_to_aws(verbose=verbose)

    # 3. Formulate container command on the remote host
    escaped_args = shlex.join(command_args)
    container_exec = (
        f"cd {cfg['compose_dir']} && "
        f"docker compose exec -T rf-suite {escaped_args}"
    )

    if verbose:
        print(f"[RF Suite AWS] Executing inside remote container on {iid or cfg['ssh_host']}:")
        print(f"  $ {escaped_args}")

    # 4. Dispatch command
    exit_code = 1
    stdout_txt = ""
    stderr_txt = ""

    if cfg["remote_method"] == "ssm" and iid:
        exit_code, stdout_txt, stderr_txt = execute_ssm_command(
            iid,
            [container_exec],
            region=reg,
            wait=True
        )
    else:
        exit_code, stdout_txt, stderr_txt = execute_ssh_command(
            cfg["ssh_host"],
            cfg["ssh_user"],
            cfg["ssh_key"],
            container_exec
        )

    # Print output
    if stdout_txt:
        print(stdout_txt, flush=True)
    if stderr_txt:
        print(stderr_txt, file=sys.stderr, flush=True)

    # 5. Sync results back to local machine
    if verbose:
        print("[RF Suite AWS] Synchronizing generated deliverables from AWS to local...")
    sync_workspace_from_aws(verbose=verbose)

    return exit_code


def main():
    parser = argparse.ArgumentParser(description="RF Suite AWS CLI & Remote Execution Tool")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # Action: run
    run_parser = subparsers.add_parser("run", help="Run a command inside the remote AWS container")
    run_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run inside the container")

    # Action: status
    subparsers.add_parser("status", help="Check EC2 instance status")

    # Action: start
    subparsers.add_parser("start", help="Start the AWS EC2 instance")

    # Action: stop
    subparsers.add_parser("stop", help="Stop the AWS EC2 instance to save costs")

    # Action: gui
    gui_parser = subparsers.add_parser("gui", help="Open noVNC web desktop tunnel")
    gui_parser.add_argument("--port", type=int, default=6080, help="Local port for tunnel (default 6080)")

    # Action: sync-up
    subparsers.add_parser("sync-up", help="Sync local projects directory to AWS")

    # Action: sync-down
    subparsers.add_parser("sync-down", help="Sync remote projects directory from AWS to local")

    # Action: host-logs
    logs_parser = subparsers.add_parser("host-logs", help="View cloud-init and container startup logs on EC2")
    logs_parser.add_argument("--lines", type=int, default=40, help="Number of log lines to show (default 40)")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(0)

    cfg = get_aws_config()

    if args.action == "status":
        status = check_instance_status()
        print(f"RF Suite AWS Instance ({cfg.get('instance_id', 'Not Set')} in {cfg.get('region')}): {status}")

    elif args.action == "start":
        start_instance()

    elif args.action == "stop":
        stop_instance()

    elif args.action == "gui":
        open_gui_tunnel(port=args.port)

    elif args.action == "sync-up":
        sync_workspace_to_aws(verbose=True)

    elif args.action == "sync-down":
        sync_workspace_from_aws(verbose=True)

    elif args.action == "host-logs":
        code, out, err = execute_ssm_command(
            cfg["instance_id"],
            [f"tail -n {args.lines} /var/log/cloud-init-output.log"],
            region=cfg["region"],
            wait=True
        )
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)

    elif args.action == "run":
        if not args.cmd:
            print("Error: No command specified for run.")
            sys.exit(1)
        code = run_remote_command(args.cmd)
        sys.exit(code)


if __name__ == "__main__":
    main()
