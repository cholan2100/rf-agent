terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ----------------------------------------------------------------------------
# Networking: Dedicated VPC & Subnet
# ----------------------------------------------------------------------------
resource "aws_vpc" "rf_suite_vpc" {
  cidr_block           = "10.10.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = {
    Name = "rf-suite-vpc"
  }
}

resource "aws_internet_gateway" "rf_suite_igw" {
  vpc_id = aws_vpc.rf_suite_vpc.id
  tags = {
    Name = "rf-suite-igw"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_subnet" "rf_suite_public_subnet" {
  vpc_id                  = aws_vpc.rf_suite_vpc.id
  cidr_block              = "10.10.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available.names[0]
  tags = {
    Name = "rf-suite-subnet"
  }
}

resource "aws_route_table" "rf_suite_public_rt" {
  vpc_id = aws_vpc.rf_suite_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.rf_suite_igw.id
  }

  tags = {
    Name = "rf-suite-public-rt"
  }
}

resource "aws_route_table_association" "rf_suite_rta" {
  subnet_id      = aws_subnet.rf_suite_public_subnet.id
  route_table_id = aws_route_table.rf_suite_public_rt.id
}

# ----------------------------------------------------------------------------
# Security Group (No public ingress needed! AWS SSM manages secure access)
# ----------------------------------------------------------------------------
resource "aws_security_group" "rf_suite_sg" {
  name        = "rf-suite-sg"
  description = "RF Suite Security Group - All outbound allowed for package updates & SSM"
  vpc_id      = aws_vpc.rf_suite_vpc.id

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "rf-suite-sg"
  }
}

# ----------------------------------------------------------------------------
# S3 Workspace & Artifact Bucket
# ----------------------------------------------------------------------------
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "rf_workspace_bucket" {
  bucket        = "rf-suite-workspace-${random_id" . "bucket_suffix.hex}"
  force_destroy = true
  tags = {
    Name = "rf-suite-workspace"
  }
}

resource "aws_s3_bucket_public_access_block" "rf_workspace_block" {
  bucket = aws_s3_bucket.rf_workspace_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ----------------------------------------------------------------------------
# IAM Role & Instance Profile for Systems Manager (SSM)
# ----------------------------------------------------------------------------
resource "aws_iam_role" "rf_instance_role" {
  name = "rf-suite-instance-role-${random_id" . "bucket_suffix.hex}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.rf_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "s3_access" {
  name = "rf-suite-s3-policy"
  role = aws_iam_role.rf_instance_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.rf_workspace_bucket.arn,
          "${aws_s3_bucket.rf_workspace_bucket.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:StopInstances"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "rf_profile" {
  name = "rf-suite-instance-profile-${random_id" . "bucket_suffix.hex}"
  role = aws_iam_role.rf_instance_role.name
}

# ----------------------------------------------------------------------------
# Ubuntu 22.04 LTS AMI Data Source
# ----------------------------------------------------------------------------
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ----------------------------------------------------------------------------
# EC2 Instance
# ----------------------------------------------------------------------------
resource "aws_instance" "rf_suite_host" {
  ami                  = data.aws_ami.ubuntu.id
  instance_type        = var.instance_type
  subnet_id            = aws_subnet.rf_suite_public_subnet.id
  vpc_security_group_ids = [aws_security_group.rf_suite_sg.id]
  iam_instance_profile = aws_iam_instance_profile.rf_profile.name

  root_block_device {
    volume_size           = var.volume_size_gb
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = <<-EOF
    #!/bin/bash
    set -ex
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y ca-certificates curl gnupg lsb-release git unzip jq bc

    # Install Docker CE & Docker Compose Plugin
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Install AWS CLI v2
    curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip

    # Clone rf-suite repository
    mkdir -p /opt/rf-agent-host
    cd /opt/rf-agent-host
    git clone --recursive https://github.com/cholan2100/rf-suite.git rf-suite || true
    mkdir -p /opt/rf-agent-host/workspace/projects

    cat << 'ENVFILE' > /opt/rf-agent-host/rf-suite/.env
    PROJECT_PATH=/opt/rf-agent-host/workspace
    RESOLUTION=1920x1080
    VNC_PASSWORD=rfworkbench
    ENVFILE

    cat << 'SERVICE' > /etc/systemd/system/rf-suite.service
    [Unit]
    Description=RF Suite Docker Container Service
    Requires=docker.service
    After=docker.service network-online.target

    [Service]
    Type=oneshot
    RemainAfterExit=yes
    WorkingDirectory=/opt/rf-agent-host/rf-suite
    ExecStart=/usr/bin/docker compose up -d
    ExecStop=/usr/bin/docker compose down
    TimeoutStartSec=0

    [Install]
    WantedBy=multi-user.target
    SERVICE

    systemctl daemon-reload
    systemctl enable rf-suite.service

    cd /opt/rf-agent-host/rf-suite
    docker compose build || true
    docker compose up -d

    # Setup Idle Auto-Shutdown
    cat << 'IDLE' > /usr/local/bin/rf-idle-monitor.sh
    #!/bin/bash
    THRESHOLD=3.0
    MAX_IDLE_MINS=${var.auto_stop_idle_minutes}
    IDLE_COUNT_FILE="/tmp/rf_idle_counter"
    [ ! -f "$IDLE_COUNT_FILE" ] && echo "0" > "$IDLE_COUNT_FILE"
    CPU_IDLE=$(top -bn2 -d 1 | grep "Cpu(s)" | tail -n 1 | awk '{print $8}')
    CPU_USAGE=$(echo "100 - $CPU_IDLE" | bc 2>/dev/null || echo "100")
    CONTAINER_CPU=$(docker stats --no-stream --format "{{.CPUPerc}}" 2>/dev/null | sed 's/%//g' | awk '{s+=$1} END {print s+0}')
    if (( $(echo "$CPU_USAGE < $THRESHOLD" | bc -l) )) && (( $(echo "$CONTAINER_CPU < $THRESHOLD" | bc -l) )); then
        COUNT=$(cat "$IDLE_COUNT_FILE")
        COUNT=$((COUNT + 5))
        echo "$COUNT" > "$IDLE_COUNT_FILE"
        if [ "$COUNT" -ge "$MAX_IDLE_MINS" ]; then
            INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
            REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
            aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
        fi
    else
        echo "0" > "$IDLE_COUNT_FILE"
    fi
    IDLE
    chmod +x /usr/local/bin/rf-idle-monitor.sh
    (crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/rf-idle-monitor.sh >> /var/log/rf-idle-monitor.log 2>&1") | crontab -
  EOF

  tags = {
    Name        = "rf-suite-host"
    Application = "rf-agent"
  }
}
