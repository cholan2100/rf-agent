#!/bin/bash
# ==============================================================================
# RF Suite EC2 Cloud-Init / User-Data Boot Script
# Installs Docker, AWS CLI, SSM Agent, clones rf-suite, starts container service
# ==============================================================================
set -ex

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release git unzip jq bc

# 1. Install Docker CE & Docker Compose Plugin
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 2. Install AWS CLI v2
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install
rm -rf aws awscliv2.zip

# 3. Setup RF Suite Workspace & Host Repo
mkdir -p /opt/rf-agent-host
cd /opt/rf-agent-host
git clone --recursive https://github.com/cholan2100/rf-suite.git rf-suite || true
chmod +x /opt/rf-agent-host/rf-suite/entrypoint.sh
mkdir -p /opt/rf-agent-host/workspace/projects

cat << 'ENVFILE' > /opt/rf-agent-host/rf-suite/.env
PROJECT_PATH=/opt/rf-agent-host/workspace
RESOLUTION=1920x1080
VNC_PASSWORD=rfworkbench
ENVFILE

# 4. Create Systemd Service for RF Suite
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

# 5. Build & Launch Container
cd /opt/rf-agent-host/rf-suite
docker compose build || true
docker compose up -d

# 6. Idle Auto-Shutdown (Stops EC2 after 30 min of inactivity to save costs)
cat << 'IDLE' > /usr/local/bin/rf-idle-monitor.sh
#!/bin/bash
THRESHOLD=3.0
MAX_IDLE_MINS=30
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

echo "RF Suite EC2 Provisioning Complete!"
