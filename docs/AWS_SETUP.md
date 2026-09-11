# AWS Remote Execution Setup for `rf-suite`

This guide explains how to deploy and operate the compute-intensive **RF Suite** (`KiCad 10`, `FreeCAD 1.0`, `openEMS v0.37` 3D FDTD EM solver, `Qucsator-RF`, `ngspice 44`) on **Amazon Web Services (AWS)** instead of your local machine.

---

## 1. Architectural Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │ LOCAL WORKSTATION (Windows / macOS / Linux)                 │
 │ - rf-agent AI Intellect (agent/workflow.py, agent/spec.py)  │
 │ - Local Project Workspace (projects/<name>/)                │
 │ - Standard Launchers (rf-suite/bin/rf-run.bat, rf-run)      │
 └──────────────────────────────┬──────────────────────────────┘
                                │
               AWS SSM / S3 Bidirectional Sync
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ AWS EC2 COMPUTE HOST (e.g. c6i.2xlarge, Ubuntu 22.04)       │
 │ - AWS SSM Agent (Secure, no open inbound ports or SSH keys) │
 │ - S3 Workspace Bucket (High-speed project artifact sync)    │
 │ - Docker Compose Environment:                               │
 │   ├── KiCad 10.0.4 (pcbnew C++ bindings, 3D raytracer)      │
 │   ├── FreeCAD 1.0.0 (STEP 3D CAD exporter)                  │
 │   ├── openEMS v0.37 (Multi-threaded 3D FDTD EM solver)      │
 │   ├── Qucsator-RF 1.0.3 & ngspice 44.2 (Co-simulation)      │
 │   └── noVNC Web Desktop (Port 6080 via SSM Tunnel)          │
 │ - 30-Minute Idle Auto-Shutdown Monitor (Saves AWS costs)    │
 └─────────────────────────────────────────────────────────────┘
```

### Why Run in AWS?
* **Heavy Compute Offloading**: openEMS 3D FDTD electromagnetic simulations and FreeCAD STEP generation require high CPU core counts and large RAM allocations (`shm_size: 2GB`).
* **Zero Local Storage Burden**: Saves 20+ GB of local disk space needed for KiCad 3D libraries, solvers, and container layers.
* **No Local Docker / WSL Required**: Run `rf-agent` from any lightweight computer.
* **Cost Effective**: The included idle monitor automatically stops the EC2 instance after 30 minutes of inactivity.

---

## 2. Prerequisites

1. **AWS Account**: An active AWS account with permissions to manage EC2, S3, IAM, and VPC.
2. **AWS CLI**: Installed and configured locally:
   ```bash
   aws configure
   # Enter AWS Access Key ID, Secret Access Key, and default region (e.g. us-east-1)
   ```
3. **AWS Session Manager Plugin**: Install the [AWS Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) on your local machine to allow SSM port forwarding and terminal sessions.

---

## 3. Provisioning the AWS Infrastructure

You can deploy the infrastructure using either **CloudFormation** (recommended) or **Terraform**.

### Option A: 1-Click AWS CloudFormation (Recommended)

#### Via AWS CLI:
```bash
aws cloudformation create-stack \
  --stack-name rf-suite-stack \
  --template-body file://aws/cloudformation.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=InstanceType,ParameterValue=c6i.2xlarge \
  --region us-east-1
```

#### Via AWS Web Console:
1. Open **CloudFormation** in the AWS Console.
2. Click **Create Stack** -> **With new resources (standard)**.
3. Upload `aws/cloudformation.yaml`.
4. Choose your instance type (default: `c6i.2xlarge`) and root volume size (default: `60 GB`).
5. Acknowledge IAM resource creation and click **Submit**.
6. When the stack status reaches `CREATE_COMPLETE` (approx. 3-5 minutes), view the **Outputs** tab.

---

### Option B: Terraform Deployment

```bash
cd aws/terraform
terraform init
terraform apply -var="aws_region=us-east-1" -var="instance_type=c6i.2xlarge"
```

---

## 4. Local Configuration

1. Copy `.env.example` to `.env` in the repository root:
   ```bash
   cp .env.example .env
   ```

2. Fill in the values from your CloudFormation / Terraform stack outputs:
   ```env
   RF_BACKEND=aws
   AWS_REGION=us-east-1
   AWS_INSTANCE_ID=i-0123456789abcdef0
   AWS_S3_BUCKET=rf-suite-workspace-xxxxxx
   RF_REMOTE_METHOD=ssm
   ```

---

## 5. Daily Operations & CLI Usage

All standard launchers (`rf-suite\bin\rf-run.bat`, `./rf-suite/bin/rf-run`, `bin\rf-run.bat`) automatically detect `RF_BACKEND=aws` and delegate commands to AWS!

### 5.1 Checking Instance Status & Starting / Stopping
Save cloud costs by starting the instance only when needed:

```bash
# Check status
rf-suite\bin\rf-aws.bat status
# Or on Linux / WSL:
./rf-suite/bin/rf-aws status

# Start the instance
rf-suite\bin\rf-aws.bat start

# Stop the instance when done
rf-suite\bin\rf-aws.bat stop
```
*(Note: If you run a command while the instance is stopped, `rf-run` will automatically start it for you!)*

---

### 5.2 Running RF Design & Simulation Workflows

Commands are identical to local execution! The launcher automatically:
1. Verifies the AWS instance is running.
2. Syncs local project input files to AWS.
3. Executes the workflow stage inside the remote container.
4. Syncs the resulting KiCad PCB, 3D renders, `.s2p` Touchstone files, and Gerbers ZIP back to your local `projects/<name>/` folder.

#### Windows
```cmd
:: Task 1: Synthesize Schematic
rf-suite\bin\rf-run.bat python -m agent.workflow --desc "100MHz LC Bandpass Filter" --stages schematic

:: Task 2: Route Controlled-Impedance PCB & DRC
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/bpf_100mhz_lc/spec.json --stages pcb

:: Task 3: 3D Raytracing Visualizations
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/bpf_100mhz_lc/spec.json --stages render

:: Task 5: openEMS 3D FDTD EM Simulation
rf-suite\bin\rf-run.bat python -m agent.workflow --spec-file projects/bpf_100mhz_lc/spec.json --stages em
```

#### Linux / WSL
```bash
# Task 1: Synthesize Schematic
./rf-suite/bin/rf-run python3 -m agent.workflow --desc "100MHz LC Bandpass Filter" --stages schematic

# Task 2: Route Controlled-Impedance PCB & DRC
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/bpf_100mhz_lc/spec.json --stages pcb

# Task 3: 3D Raytracing Visualizations
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/bpf_100mhz_lc/spec.json --stages render

# Task 5: openEMS 3D FDTD EM Simulation
./rf-suite/bin/rf-run python3 -m agent.workflow --spec-file projects/bpf_100mhz_lc/spec.json --stages em
```

---

### 5.3 Opening the Interactive 3D Web Desktop (noVNC)

To inspect KiCad PCB layouts, FreeCAD 3D assemblies, or Qucs-S schematics visually in your local web browser:

```bash
# Windows:
rf-suite\bin\rf-aws.bat gui

# Linux / WSL:
./rf-suite/bin/rf-aws gui
```

This establishes an encrypted AWS Systems Manager port-forwarding tunnel to the EC2 container and automatically opens:
`http://localhost:6080/vnc.html` (Password: `rfworkbench`).

---

## 6. Cost Optimization Features

* **Idle Auto-Shutdown**: The EC2 instance includes a built-in background cron daemon (`/usr/local/bin/rf-idle-monitor.sh`) that checks CPU and container activity every 5 minutes. If both host and container remain idle (< 3% CPU) for 30 consecutive minutes, the instance automatically stops itself (`aws ec2 stop-instances`).
* **Compute Instance Types**:
  * **Default Recommendation**: `c6i.2xlarge` (8 vCPU, 16 GB RAM) - fast openEMS mesh solving and raytracing (~$0.34 / hr).
  * **Budget Alternative**: `t3.xlarge` (4 vCPU, 16 GB RAM) or `c5.xlarge` (4 vCPU, 8 GB RAM) (~$0.16 / hr).
* **Spot Instances**: You can configure the EC2 instance as a Spot Instance in CloudFormation or Terraform to save up to 70-90% on EC2 compute costs.
