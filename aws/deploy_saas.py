#!/usr/bin/env python3
"""
Automated AWS CloudFormation Deployer for Hosted RF Suite SaaS Microservice.
Deploys CloudFormation stack (VPC, Elastic IP, EC2, Security Group for Port 8000 & 6080),
configures .env with RF_BACKEND=aws_saas, and verifies /health endpoint.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError


def get_latest_ubuntu_ami(ec2_client) -> str:
    """Finds the latest official Ubuntu 22.04 LTS AMI in the current region."""
    resp = ec2_client.describe_images(
        Owners=["099720109477"],  # Canonical
        Filters=[
            {"Name": "name", "Values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]},
            {"Name": "state", "Values": ["available"]}
        ]
    )
    images = resp.get("Images", [])
    if not images:
        raise RuntimeError("No Ubuntu 22.04 LTS AMI found in this region.")
    sorted_imgs = sorted(images, key=lambda x: x["CreationDate"], reverse=True)
    return sorted_imgs[0]["ImageId"]


def update_env_file(env_path: Path, new_vars: dict):
    """Updates or adds key-value pairs in the .env file while preserving existing settings."""
    lines = []
    if env_path.is_file():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    keys_set = set()
    updated_lines = []

    for line in lines:
        stripped = line.strip()
        matched = False
        for k, v in new_vars.items():
            if stripped.startswith(f"{k}="):
                updated_lines.append(f"{k}={v}\n")
                keys_set.add(k)
                matched = True
                break
        if not matched:
            # Remove obsolete SSM keys if present
            if any(stripped.startswith(obs) for obs in ["AWS_INSTANCE_ID=", "AWS_S3_BUCKET=", "RF_REMOTE_METHOD="]):
                continue
            updated_lines.append(line)

    for k, v in new_vars.items():
        if k not in keys_set:
            updated_lines.append(f"{k}={v}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)


def wait_for_saas_health(health_url: str, timeout_sec: int = 900) -> bool:
    """Polls the SaaS /health endpoint until it reports healthy."""
    print(f"\n[RF SaaS Deploy] Probing microservice health at {health_url}...")
    print("  (The EC2 host is cloning the repository and building the Docker container on first boot.)")
    print("  (This typically takes ~5-8 minutes. Live polling every 15 seconds...)\n")

    start_time = time.time()
    last_print = 0

    while time.time() - start_time < timeout_sec:
        elapsed = int(time.time() - start_time)
        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "rf-deployer/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    print(f"\n✔ [200 OK] SaaS Microservice is ONLINE and HEALTHY! (Boot took {elapsed}s)")
                    print(f"  Status:   {data.get('status')}")
                    print(f"  Service:  {data.get('service')}")
                    versions = data.get("versions", {})
                    if versions:
                        print("  Toolchain Versions:")
                        for tool, ver in versions.items():
                            print(f"    - {tool}: {ver}")
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionRefusedError):
            pass
        except Exception as e:
            pass

        time_since_print = time.time() - last_print
        if time_since_print >= 30:
            print(f"  ... waiting for container boot ({elapsed}s elapsed, timeout in {timeout_sec - elapsed}s) ...")
            last_print = time.time()

        time.sleep(15)

    print(f"\n⚠ Timeout reached ({timeout_sec}s) waiting for {health_url}.")
    print("  The instance may still be finalizing the Docker build.")
    return False


def main():
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / ".env"
    cf_template_path = repo_root / "aws" / "cloudformation.yaml"

    if not env_path.is_file():
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)

    load_dotenv(dotenv_path=env_path)

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-south-2"
    stack_name = os.getenv("AWS_STACK_NAME", "rf-suite-saas")
    instance_type = os.getenv("AWS_INSTANCE_TYPE", "m7i-flex.large")
    auto_stop = os.getenv("AUTO_STOP_IDLE_MINS", "30")
    api_key = os.getenv("RF_SAAS_API_KEY", "")

    print(f"═══ RF SUITE SAAS MICROSERVICE DEPLOYER (AWS EC2) ═══")
    print(f"Stack Name:    {stack_name}")
    print(f"AWS Region:    {region}")
    print(f"Instance Type: {instance_type}")
    print(f"Template:      {cf_template_path}")
    print("═" * 54)

    # 1. AWS Session & Identity Verification
    try:
        session = boto3.Session(region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"✔ Authenticated AWS Account: {identity.get('Account')} ({identity.get('Arn')})")
    except Exception as e:
        print(f"Error authenticating with AWS: {e}")
        sys.exit(1)

    ec2 = session.client("ec2")
    cf = session.client("cloudformation")

    # 2. Resolve AMI ID
    print(f"[RF SaaS Deploy] Resolving latest Ubuntu 22.04 LTS AMI in {region}...")
    try:
        ami_id = get_latest_ubuntu_ami(ec2)
        print(f"✔ Target AMI: {ami_id}")
    except Exception as e:
        print(f"Error finding AMI: {e}")
        sys.exit(1)

    # 3. Check Stack Status
    stack_exists = False
    try:
        resp = cf.describe_stacks(StackName=stack_name)
        if resp.get("Stacks"):
            st = resp["Stacks"][0]
            stack_status = st["StackStatus"]
            if stack_status not in ("DELETE_COMPLETE", "ROLLBACK_COMPLETE"):
                stack_exists = True
                print(f"[RF SaaS Deploy] Stack '{stack_name}' already exists (Status: {stack_status}).")
    except ClientError as e:
        if "does not exist" not in str(e):
            print(f"Error checking stack: {e}")
            sys.exit(1)

    with open(cf_template_path, "r", encoding="utf-8") as f:
        template_body = f.read()

    parameters = [
        {"ParameterKey": "InstanceType", "ParameterValue": instance_type},
        {"ParameterKey": "AmiId", "ParameterValue": ami_id},
        {"ParameterKey": "VolumeSizeGB", "ParameterValue": "60"},
        {"ParameterKey": "AutoStopIdleMinutes", "ParameterValue": auto_stop},
        {"ParameterKey": "ApiKeySecret", "ParameterValue": api_key},
    ]

    if not stack_exists:
        print(f"\n[1/3] Creating CloudFormation stack '{stack_name}'...")
        try:
            cf.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM"],
                Parameters=parameters,
                Tags=[
                    {"Key": "Environment", "Value": "rf-suite-saas"},
                    {"Key": "Application", "Value": "rf-agent"},
                ]
            )
            print("  Stack creation initiated. Waiting for CREATE_COMPLETE (approx 2 min)...")
            waiter = cf.get_waiter("stack_create_complete")
            waiter.wait(StackName=stack_name)
            print(f"✔ CloudFormation stack '{stack_name}' created successfully!")
        except Exception as e:
            print(f"Error creating stack: {e}")
            sys.exit(1)
    else:
        print(f"\n[1/3] Updating existing stack '{stack_name}'...")
        try:
            cf.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM"],
                Parameters=parameters,
            )
            print("  Stack update initiated. Waiting for UPDATE_COMPLETE...")
            waiter = cf.get_waiter("stack_update_complete")
            waiter.wait(StackName=stack_name)
            print(f"✔ CloudFormation stack '{stack_name}' updated successfully!")
        except ClientError as e:
            if "No updates are to be performed" in str(e):
                print("  Stack is already up to date.")
            else:
                print(f"Error updating stack: {e}")
                sys.exit(1)

    # 4. Extract Stack Outputs
    print(f"\n[2/3] Retrieving SaaS microservice endpoints...")
    resp = cf.describe_stacks(StackName=stack_name)
    outputs = {}
    if resp.get("Stacks"):
        for out in resp["Stacks"][0].get("Outputs", []):
            outputs[out["OutputKey"]] = out["OutputValue"]

    saas_url = outputs.get("SaaSUrl", "")
    health_url = outputs.get("HealthCheckUrl", f"{saas_url}/health")
    swagger_url = outputs.get("SwaggerDocsUrl", f"{saas_url}/docs")
    web_gui_url = outputs.get("WebGuiUrl", "")
    public_ip = outputs.get("PublicIp", "")

    print(f"  Public Static IP:  {public_ip}")
    print(f"  SaaS REST API:     {saas_url}")
    print(f"  Swagger Docs:      {swagger_url}")
    print(f"  noVNC Web Desktop: {web_gui_url}")

    # 5. Update local .env file
    print(f"\n[3/3] Configuring local environment (.env) for RF_BACKEND=aws_saas...")
    update_vars = {
        "RF_BACKEND": "aws_saas",
        "RF_SAAS_URL": saas_url,
    }
    update_env_file(env_path, update_vars)
    rf_suite_env = repo_root / "rf-suite" / ".env"
    if rf_suite_env.is_file():
        update_env_file(rf_suite_env, update_vars)
    print(f"✔ Updated {env_path} with:")
    print(f"    RF_BACKEND=aws_saas")
    print(f"    RF_SAAS_URL={saas_url}")

    # 6. Wait for service health
    wait_for_saas_health(health_url, timeout_sec=900)

    print("\n" + "═" * 54)
    print("🎉 RF Suite AWS SaaS Microservice Deployment Complete!")
    print(f"   Endpoint:    {saas_url}")
    print(f"   Swagger UI:  {swagger_url}")
    print(f"   Backend:     RF_BACKEND=aws_saas")
    print("═" * 54)


if __name__ == "__main__":
    main()
