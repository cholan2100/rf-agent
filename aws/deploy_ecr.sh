#!/usr/bin/env bash
# ==============================================================================
# Build and Push RF Suite Container Image to AWS ECR
# ==============================================================================
set -e

AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO_NAME="${ECR_REPO_NAME:-rf-suite}"

echo "[RF Suite AWS] Fetching AWS Account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "[RF Suite AWS] Ensuring ECR repository exists: ${ECR_REPO_NAME}..."
aws ecr describe-repositories --repository-names "${ECR_REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1 || \
aws ecr create-repository --repository-name "${ECR_REPO_NAME}" --region "${AWS_REGION}" >/dev/null

echo "[RF Suite AWS] Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${SCRIPT_DIR}/rf-suite"

echo "[RF Suite AWS] Building rf-suite:latest..."
docker build -t rf-suite:latest .

echo "[RF Suite AWS] Tagging image as ${ECR_URI}:latest..."
docker tag rf-suite:latest "${ECR_URI}:latest"

echo "[RF Suite AWS] Pushing to ECR: ${ECR_URI}:latest..."
docker push "${ECR_URI}:latest"

echo "======================================================================"
echo "✔ RF Suite image successfully pushed to AWS ECR!"
echo "  URI: ${ECR_URI}:latest"
echo "======================================================================"
