@echo off
setlocal enabledelayedexpansion

if "%AWS_REGION%"=="" set AWS_REGION=us-east-1
if "%ECR_REPO_NAME%"=="" set ECR_REPO_NAME=rf-suite

echo [RF Suite AWS] Fetching AWS Account ID...
for /f "delims=" %%i in ('aws sts get-caller-identity --query Account --output text') do set ACCOUNT_ID=%%i

if "%ACCOUNT_ID%"=="" (
    echo [RF Suite AWS] Error: Failed to obtain AWS Account ID. Make sure AWS CLI is configured.
    exit /b 1
)

set ECR_URI=%ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com/%ECR_REPO_NAME%

echo [RF Suite AWS] Ensuring ECR repository exists: %ECR_REPO_NAME%...
aws ecr describe-repositories --repository-names %ECR_REPO_NAME% --region %AWS_REGION% >nul 2>nul
if errorlevel 1 (
    aws ecr create-repository --repository-name %ECR_REPO_NAME% --region %AWS_REGION% >nul
)

echo [RF Suite AWS] Logging into ECR...
aws ecr get-login-password --region %AWS_REGION% | docker login --username AWS --password-stdin %ACCOUNT_ID%.dkr.ecr.%AWS_REGION%.amazonaws.com

cd /d "%~dp0\..\rf-suite"

echo [RF Suite AWS] Building rf-suite:latest...
docker build -t rf-suite:latest .

echo [RF Suite AWS] Tagging image as %ECR_URI%:latest...
docker tag rf-suite:latest %ECR_URI%:latest

echo [RF Suite AWS] Pushing to ECR: %ECR_URI%:latest...
docker push %ECR_URI%:latest

echo ======================================================================
echo RF Suite image successfully pushed to AWS ECR!
echo URI: %ECR_URI%:latest
echo ======================================================================
