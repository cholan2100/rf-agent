"""
Serverless Wake-on-Request Lambda Function for RF Suite Microservice.
Checks EC2 instance status and wakes the containerized EDA solvers on demand.
"""

import json
import os
import time
import urllib.request
import urllib.error
import boto3

INSTANCE_ID = os.environ.get("INSTANCE_ID", "")
REGION = os.environ.get("REGION", "ap-south-2")
EIP = os.environ.get("EIP", "")
PORT = os.environ.get("PORT", "8000")
DOMAIN_URL = os.environ.get("DOMAIN_URL", "http://rf.nakedcircuits.com:8000")

ec2 = boto3.client("ec2", region_name=REGION)


def check_health(url: str, timeout: int = 3) -> bool:
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/health", headers={"User-Agent": "rf-wake-lambda/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "healthy"
    except Exception:
        return False
    return False


def handler(event, context):
    start_time = time.time()
    
    # Handle CORS preflight OPTIONS request
    http_method = (
        event.get("requestContext", {}).get("http", {}).get("method") or
        event.get("httpMethod", "GET")
    ).upper()

    cors_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key"
    }

    if http_method == "OPTIONS":
        return {"statusCode": 204, "headers": cors_headers, "body": ""}

    if not INSTANCE_ID:
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "INSTANCE_ID environment variable not set"})
        }

    # 1. Check current instance state
    try:
        resp = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
        instance = resp["Reservations"][0]["Instances"][0]
        state = instance["State"]["Name"]
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": f"Failed to describe EC2 instance: {str(e)}"})
        }

    eip_url = f"http://{EIP}:{PORT}" if EIP else DOMAIN_URL

    # 2. If already running, verify health
    if state == "running":
        if check_health(eip_url, timeout=3) or check_health(DOMAIN_URL, timeout=3):
            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps({
                    "status": "ready",
                    "instance_id": INSTANCE_ID,
                    "instance_state": "running",
                    "saas_url": DOMAIN_URL,
                    "elapsed_seconds": round(time.time() - start_time, 2),
                    "message": "RF Suite SaaS microservice is already online and healthy."
                })
            }

    # 3. If stopping, wait for it to stop before starting
    if state == "stopping":
        for _ in range(20):
            time.sleep(3)
            resp = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
            state = resp["Reservations"][0]["Instances"][0]["State"]["Name"]
            if state == "stopped":
                break

    # 4. If stopped, start it
    if state == "stopped":
        print(f"Starting EC2 instance {INSTANCE_ID}...")
        ec2.start_instances(InstanceIds=[INSTANCE_ID])

    # 5. Wait for instance to become running and health check to pass
    max_wait_seconds = 100
    is_healthy = False

    while (time.time() - start_time) < max_wait_seconds:
        time.sleep(3)
        try:
            resp = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
            state = resp["Reservations"][0]["Instances"][0]["State"]["Name"]
        except Exception:
            continue

        if state == "running":
            if check_health(eip_url, timeout=3) or check_health(DOMAIN_URL, timeout=3):
                is_healthy = True
                break

    elapsed = round(time.time() - start_time, 2)
    if is_healthy:
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps({
                "status": "ready",
                "instance_id": INSTANCE_ID,
                "instance_state": "running",
                "saas_url": DOMAIN_URL,
                "elapsed_seconds": elapsed,
                "message": f"Successfully woke RF Suite SaaS microservice in {elapsed}s."
            })
        }
    else:
        return {
            "statusCode": 504,
            "headers": cors_headers,
            "body": json.dumps({
                "status": "starting",
                "instance_id": INSTANCE_ID,
                "instance_state": state,
                "saas_url": DOMAIN_URL,
                "elapsed_seconds": elapsed,
                "message": f"Instance {INSTANCE_ID} is starting (state: {state}), but service is still initializing. Please retry in 15 seconds."
            })
        }
