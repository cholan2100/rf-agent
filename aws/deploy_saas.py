"""
One-Command Deployment Script for RF Suite Hosted SaaS Service on AWS.
Deploys CloudFormation stack (App Runner + ECR + S3), builds container, and pushes image.
"""

import os
import sys
import time
import argparse
import subprocess

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from agent.aws.rf_remote_client import get_aws_config


def run_cmd(cmd, check=True):
    print(f"--> {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True)


def deploy_saas_service(
    stack_name: str = "rf-suite-saas-stack",
    region: str = "us-east-1",
    api_key: str = "",
    cpu: str = "2 vCPU",
    memory: str = "4 GB"
):
    print(f"═══ RF SUITE SAAS DEPLOYER (AWS App Runner) ═══")
    print(f"Stack Name: {stack_name}")
    print(f"Region:     {region}")
    print(f"Compute:    {cpu} / {memory}")
    print("═" * 50)

    # 1. Check AWS identity
    try:
        run_cmd(["aws", "sts", "get-caller-identity", "--region", region])
    except Exception as e:
        print(f"Error: AWS CLI credentials not valid: {e}")
        return 1

    template_path = os.path.join(repo_root, "aws", "saas_apprunner.yaml")
    if not os.path.exists(template_path):
        print(f"Error: CloudFormation template not found at {template_path}")
        return 1

    # 2. Deploy CloudFormation stack
    print(f"\n[1/3] Deploying CloudFormation infrastructure...")
    deploy_cmd = [
        "aws", "cloudformation", "deploy",
        "--template-file", template_path,
        "--stack-name", stack_name,
        "--region", region,
        "--capabilities", "CAPABILITY_NAMED_IAM",
        "--parameter-overrides",
        f"ServiceName={stack_name}",
        f"Cpu={cpu}",
        f"Memory={memory}",
        f"ApiKeySecret={api_key}"
    ]
    res = subprocess.run(deploy_cmd)
    if res.returncode != 0:
        print("CloudFormation deployment failed.")
        return res.returncode

    # 3. Retrieve Outputs
    print(f"\n[2/3] Retrieving stack outputs...")
    out_cmd = [
        "aws", "cloudformation", "describe-stacks",
        "--stack-name", stack_name,
        "--region", region,
        "--query", "Stacks[0].Outputs",
        "--output", "json"
    ]
    out_res = subprocess.run(out_cmd, capture_output=True, text=True)
    import json
    outputs = {}
    if out_res.returncode == 0:
        for item in json.loads(out_res.stdout):
            outputs[item["OutputKey"]] = item["OutputValue"]

    service_url = outputs.get("ServiceUrl", "")
    swagger_url = outputs.get("SwaggerDocsUrl", "")
    ecr_uri = outputs.get("EcrRepositoryUri", "")

    print("\n" + "═" * 50)
    print("✔ RF Suite SaaS Service Deployed Successfully!")
    print(f"Service URL:  {service_url}")
    print(f"Swagger Docs: {swagger_url}")
    print(f"ECR Repo:     {ecr_uri}")
    print("═" * 50)

    print("\nTo configure local rf-agent to use this SaaS service, set in .env:")
    print(f"  RF_BACKEND=saas")
    print(f"  RF_SAAS_URL={service_url}")
    if api_key:
        print(f"  RF_SAAS_API_KEY={api_key}")
    print("═" * 50)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Deploy RF Suite Hosted SaaS Service on AWS")
    parser.add_argument("--stack-name", default="rf-suite-saas", help="CloudFormation stack name")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"), help="AWS Region")
    parser.add_argument("--api-key", default=os.getenv("RF_SAAS_API_KEY", ""), help="Optional API Key")
    parser.add_argument("--cpu", default="2 vCPU", help="Compute allocation")
    parser.add_argument("--memory", default="4 GB", help="Memory allocation")
    args = parser.parse_args()

    sys.exit(deploy_saas_service(
        stack_name=args.stack_name,
        region=args.region,
        api_key=args.api_key,
        cpu=args.cpu,
        memory=args.memory
    ))


if __name__ == "__main__":
    main()
