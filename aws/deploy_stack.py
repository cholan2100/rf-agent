#!/usr/bin/env python3
"""
Automated AWS CloudFormation stack deployer for RF Suite.
Deploys aws/cloudformation.yaml, tracks progress, and updates .env with stack outputs.
"""

import os
import sys
import time
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


def main():
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / ".env"
    cf_template_path = repo_root / "aws" / "cloudformation.yaml"

    if not env_path.is_file():
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)

    load_dotenv(dotenv_path=env_path)

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    stack_name = os.getenv("AWS_STACK_NAME", "rf-suite-stack")
    instance_type = os.getenv("AWS_INSTANCE_TYPE", "m7i-flex.large")

    print(f"[RF Suite Deploy] Initializing AWS session in region: {region}...")
    try:
        session = boto3.Session(region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"✔ Authenticated as IAM identity: {identity.get('Arn')}")
        print(f"  Account ID: {identity.get('Account')}")
    except Exception as e:
        print(f"Error authenticating with AWS: {e}")
        sys.exit(1)

    ec2 = session.client("ec2")
    cf = session.client("cloudformation")

    # Resolve AMI ID
    print(f"[RF Suite Deploy] Resolving latest Ubuntu 22.04 LTS AMI in {region}...")
    try:
        ami_id = get_latest_ubuntu_ami(ec2)
        print(f"✔ Target AMI: {ami_id}")
    except Exception as e:
        print(f"Error finding AMI: {e}")
        sys.exit(1)

    # Check if stack already exists
    stack_exists = False
    stack_status = None
    try:
        resp = cf.describe_stacks(StackName=stack_name)
        if resp.get("Stacks"):
            stack_exists = True
            stack_status = resp["Stacks"][0]["StackStatus"]
            print(f"[RF Suite Deploy] Stack '{stack_name}' already exists with status: {stack_status}")
    except ClientError as e:
        if "does not exist" not in str(e):
            print(f"Error checking stack: {e}")
            sys.exit(1)

    if not stack_exists:
        print(f"[RF Suite Deploy] Reading template: {cf_template_path}...")
        with open(cf_template_path, "r", encoding="utf-8") as f:
            template_body = f.read()

        print(f"[RF Suite Deploy] Creating CloudFormation stack '{stack_name}' (Instance Type: {instance_type})...")
        try:
            cf.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM"],
                Parameters=[
                    {"ParameterKey": "InstanceType", "ParameterValue": instance_type},
                    {"ParameterKey": "AmiId", "ParameterValue": ami_id},
                    {"ParameterKey": "VolumeSizeGB", "ParameterValue": "60"},
                    {"ParameterKey": "AutoStopIdleMinutes", "ParameterValue": "30"},
                ],
                Tags=[
                    {"Key": "Application", "Value": "rf-agent"},
                    {"Key": "Environment", "Value": "rf-suite"}
                ]
            )
            print("✔ Stack creation initiated. Waiting for resources to be provisioned (approx 3-5 mins)...")
        except Exception as e:
            print(f"Error initiating stack creation: {e}")
            sys.exit(1)

    # Wait for completion
    start_time = time.time()
    last_status = None

    while True:
        try:
            r = cf.describe_stacks(StackName=stack_name)
            st = r["Stacks"][0]["StackStatus"]
            if st != last_status:
                print(f"[RF Suite Deploy] Current Stack Status: {st}")
                last_status = st

            if st in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
                print("✔ CloudFormation stack creation complete!")
                outputs = {o["OutputKey"]: o["OutputValue"] for o in r["Stacks"][0].get("Outputs", [])}
                break
            elif "FAILED" in st or "ROLLBACK" in st:
                print(f"Error: Stack failed with status: {st}")
                # Fetch recent events for diagnostics
                events = cf.describe_stack_events(StackName=stack_name).get("StackEvents", [])
                for ev in reversed(events[:10]):
                    print(f"  {ev.get('LogicalResourceId')}: {ev.get('ResourceStatus')} ({ev.get('ResourceStatusReason', '')})")
                sys.exit(1)
        except Exception as e:
            print(f"Status check note: {e}")

        time.sleep(10)

    # Extract outputs
    instance_id = outputs.get("InstanceId", "")
    bucket_name = outputs.get("WorkspaceBucketName", "")
    aws_region = outputs.get("AwsRegion", region)

    print("\n======================================================================")
    print("  RF Suite AWS Deployment Complete!")
    print(f"  - Instance ID:        {instance_id}")
    print(f"  - Workspace Bucket:   {bucket_name}")
    print(f"  - Region:             {aws_region}")
    print("======================================================================\n")

    # Update .env file safely
    print("[RF Suite Deploy] Updating .env with AWS outputs...")
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated_lines = []
    keys_set = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("RF_BACKEND="):
            updated_lines.append("RF_BACKEND=aws\n")
            keys_set.add("RF_BACKEND")
        elif stripped.startswith("AWS_REGION="):
            updated_lines.append(f"AWS_REGION={aws_region}\n")
            keys_set.add("AWS_REGION")
        elif stripped.startswith("AWS_INSTANCE_ID="):
            updated_lines.append(f"AWS_INSTANCE_ID={instance_id}\n")
            keys_set.add("AWS_INSTANCE_ID")
        elif stripped.startswith("AWS_S3_BUCKET="):
            updated_lines.append(f"AWS_S3_BUCKET={bucket_name}\n")
            keys_set.add("AWS_S3_BUCKET")
        elif stripped.startswith("RF_REMOTE_METHOD="):
            updated_lines.append("RF_REMOTE_METHOD=ssm\n")
            keys_set.add("RF_REMOTE_METHOD")
        else:
            updated_lines.append(line)

    if "RF_BACKEND" not in keys_set:
        updated_lines.append("RF_BACKEND=aws\n")
    if "AWS_REGION" not in keys_set:
        updated_lines.append(f"AWS_REGION={aws_region}\n")
    if "AWS_INSTANCE_ID" not in keys_set:
        updated_lines.append(f"AWS_INSTANCE_ID={instance_id}\n")
    if "AWS_S3_BUCKET" not in keys_set:
        updated_lines.append(f"AWS_S3_BUCKET={bucket_name}\n")
    if "RF_REMOTE_METHOD" not in keys_set:
        updated_lines.append("RF_REMOTE_METHOD=ssm\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    print("✔ .env file updated successfully.")


if __name__ == "__main__":
    main()
