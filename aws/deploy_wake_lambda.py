"""
Deployer for RF Suite Serverless Wake-on-Request Lambda Function.
Deploys or updates the Lambda function, attaches IAM permissions, and configures a public Function URL.
"""

import os
import sys
import io
import time
import zipfile
import json
import urllib.request
from pathlib import Path
from typing import Dict, Any

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Error: boto3 is required. Install via pip install boto3")
    sys.exit(1)


def get_aws_credentials():
    env_path = Path(__file__).parent.parent / ".env"
    creds = {
        "region": os.getenv("AWS_DEFAULT_REGION", "ap-south-2"),
        "access_key": os.getenv("AWS_ACCESS_KEY_ID", ""),
        "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "instance_id": os.getenv("AWS_INSTANCE_ID", "i-0df21d2667a88c7bc"),
        "eip": os.getenv("AWS_EIP", "16.113.67.200"),
        "domain_url": os.getenv("RF_SAAS_URL", "http://rf.nakedcircuits.com:8000")
    }

    # Load from .env if present
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k == "AWS_ACCESS_KEY_ID" and not creds["access_key"]:
                            creds["access_key"] = v
                        elif k == "AWS_SECRET_ACCESS_KEY" and not creds["secret_key"]:
                            creds["secret_key"] = v
        except Exception:
            pass

    return creds


def create_lambda_zip() -> bytes:
    """Packages aws/lambda_wake.py into a zip file in-memory."""
    script_path = Path(__file__).parent / "lambda_wake.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Missing {script_path}")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(script_path, arcname="lambda_wake.py")
    buffer.seek(0)
    return buffer.read()


def ensure_iam_role(iam_client) -> str:
    """Creates or verifies the IAM execution role for the wake Lambda."""
    role_name = "rf-suite-wake-lambda-role"
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }

    ec2_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeInstances",
                    "ec2:DescribeInstanceStatus",
                    "ec2:StartInstances"
                ],
                "Resource": "*"
            }
        ]
    }

    try:
        resp = iam_client.get_role(RoleName=role_name)
        role_arn = resp["Role"]["Arn"]
        print(f"✔ Using existing IAM Role: {role_arn}")
    except ClientError as e:
        if "NoSuchEntity" in str(e):
            print(f"Creating IAM execution role '{role_name}'...")
            resp = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                Description="Execution role for RF Suite Serverless Wake Lambda"
            )
            role_arn = resp["Role"]["Arn"]
            print(f"✔ Created IAM Role: {role_arn}")

            # Attach AWSLambdaBasicExecutionRole
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            )
            time.sleep(5)  # Wait for IAM role propagation
        else:
            raise

    # Attach/update inline policy for EC2 start permissions
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="RFWakeEC2Policy",
        PolicyDocument=json.dumps(ec2_policy)
    )
    return role_arn


def deploy_lambda():
    creds = get_aws_credentials()
    region = creds["region"]
    func_name = "rf-suite-wake"

    print("═══ DEPLOYING SERVERLESS WAKE-ON-REQUEST LAMBDA ═══")
    print(f"Region:       {region}")
    print(f"Function:     {func_name}")
    print(f"Instance ID:  {creds['instance_id']}")
    print(f"Domain URL:   {creds['domain_url']}")
    print("═" * 52)

    session = boto3.Session(
        aws_access_key_id=creds["access_key"],
        aws_secret_access_key=creds["secret_key"],
        region_name=region
    )

    iam = session.client("iam")
    lam = session.client("lambda")

    role_arn = ensure_iam_role(iam)
    zip_bytes = create_lambda_zip()

    env_vars = {
        "INSTANCE_ID": creds["instance_id"],
        "REGION": region,
        "EIP": creds["eip"],
        "PORT": "8000",
        "DOMAIN_URL": creds["domain_url"]
    }

    # Check if function exists
    func_exists = False
    try:
        lam.get_function(FunctionName=func_name)
        func_exists = True
        print(f"Function '{func_name}' already exists. Updating code and configuration...")
    except ClientError as e:
        if "ResourceNotFoundException" not in str(e):
            raise

    if func_exists:
        lam.update_function_code(
            FunctionName=func_name,
            ZipFile=zip_bytes
        )
        time.sleep(2)
        lam.update_function_configuration(
            FunctionName=func_name,
            Role=role_arn,
            Handler="lambda_wake.handler",
            Runtime="python3.12",
            Timeout=120,
            MemorySize=256,
            Environment={"Variables": env_vars}
        )
        print(f"✔ Lambda code and configuration updated.")
    else:
        print(f"Creating Lambda function '{func_name}'...")
        # IAM role propagation retry
        for attempt in range(6):
            try:
                lam.create_function(
                    FunctionName=func_name,
                    Runtime="python3.12",
                    Role=role_arn,
                    Handler="lambda_wake.handler",
                    Code={"ZipFile": zip_bytes},
                    Timeout=120,
                    MemorySize=256,
                    Environment={"Variables": env_vars},
                    Description="Serverless wake-on-request trigger for RF Suite EC2 microservice"
                )
                print(f"✔ Lambda function created successfully.")
                break
            except ClientError as e:
                if "The role defined for the function cannot be assumed" in str(e) and attempt < 5:
                    print(f"Waiting for IAM role to propagate (attempt {attempt+1}/5)...")
                    time.sleep(5)
                else:
                    raise

    # 4. Configure API Gateway HTTP API (Dedicated Public HTTPS Endpoint)
    print("Configuring API Gateway HTTP API...")
    apg = session.client("apigatewayv2")
    api_name = "rf-suite-wake-api"
    function_arn = lam.get_function(FunctionName=func_name)["Configuration"]["FunctionArn"]

    api_endpoint = None
    try:
        apis = apg.get_apis().get("Items", [])
        for a in apis:
            if a.get("Name") == api_name:
                api_endpoint = a.get("ApiEndpoint")
                api_id = a.get("ApiId")
                print(f"✔ Using existing API Gateway HTTP API: {api_endpoint}")
                break
    except Exception as e:
        print(f"Notice checking APIs: {e}")

    if not api_endpoint:
        api = apg.create_api(
            Name=api_name,
            ProtocolType="HTTP",
            Target=function_arn,
            CorsConfiguration={
                "AllowOrigins": ["*"],
                "AllowMethods": ["GET", "POST", "OPTIONS"],
                "AllowHeaders": ["*"]
            }
        )
        api_id = api["ApiId"]
        api_endpoint = api["ApiEndpoint"]
        print(f"✔ Created API Gateway HTTP API: {api_endpoint}")

        # 5. Grant API Gateway Permission to invoke Lambda
        try:
            account_id = boto3.client("sts", aws_access_key_id=creds["access_key"], aws_secret_access_key=creds["secret_key"]).get_caller_identity()["Account"]
            lam.add_permission(
                FunctionName=func_name,
                StatementId="APIGatewayInvokePermission",
                Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com",
                SourceArn=f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*"
            )
            print("✔ Granted Lambda invoke permissions to API Gateway.")
        except ClientError as e:
            if "ResourceConflictException" in str(e):
                pass
            else:
                print(f"Permission notice: {e}")

    print("\n" + "═" * 52)
    print("🎉 SERVERLESS WAKE-ON-REQUEST ENDPOINT READY!")
    print(f"Wake Endpoint URL: {api_endpoint}")
    print("═" * 52)

    # 6. Update local .env file
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        if "RF_WAKE_URL=" in content:
            import re
            content = re.sub(r"^RF_WAKE_URL=.*$", f"RF_WAKE_URL={api_endpoint}", content, flags=re.MULTILINE)
        else:
            content = content.rstrip() + f"\nRF_WAKE_URL={api_endpoint}\n"
        env_file.write_text(content, encoding="utf-8")
        print(f"✔ Saved RF_WAKE_URL to {env_file}")

    return api_endpoint


if __name__ == "__main__":
    deploy_lambda()
