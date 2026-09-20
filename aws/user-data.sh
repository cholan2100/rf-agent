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
cat << 'IDLE' > /usr/local/bin/rf-idle-monitor.py
#!/usr/bin/env python3
import os, sys, time, subprocess, urllib.request, datetime
THRESHOLD = 3.0
MAX_IDLE_MINS = 30
COUNTER_FILE = "/tmp/rf_idle_counter"
LOG_FILE = "/var/log/rf-idle-monitor.log"

def log(msg):
    now = datetime.datetime.utcnow().strftime("%a %b %d %H:%M:%S UTC %Y")
    line = f"{now}: {msg}\n"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception:
        pass

def get_cpu_usage():
    try:
        with open("/proc/stat", "r") as f:
            f1 = [float(x) for x in f.readline().strip().split()[1:]]
        time.sleep(1.0)
        with open("/proc/stat", "r") as f:
            f2 = [float(x) for x in f.readline().strip().split()[1:]]
        delta_idle = (f2[3] + f2[4]) - (f1[3] + f1[4])
        delta_total = sum(f2) - sum(f1)
        return round((1.0 - delta_idle / delta_total) * 100.0, 2) if delta_total > 0 else 0.0
    except Exception as e:
        log(f"Error reading /proc/stat: {e}")
        return 0.0

def get_container_cpu():
    try:
        res = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}"], capture_output=True, text=True, timeout=10)
        total = sum(float(x.replace("%", "").strip()) for x in res.stdout.strip().split("\n") if x.replace("%", "").strip())
        return round(total, 2)
    except Exception:
        return 0.0

def stop_instance():
    try:
        req = urllib.request.Request("http://169.254.169.254/latest/api/token", headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"}, method="PUT")
        token = urllib.request.urlopen(req, timeout=3).read().decode().strip()
        req = urllib.request.Request("http://169.254.169.254/latest/meta-data/instance-id", headers={"X-aws-ec2-metadata-token": token})
        instance_id = urllib.request.urlopen(req, timeout=3).read().decode().strip()
        req = urllib.request.Request("http://169.254.169.254/latest/meta-data/placement/availability-zone", headers={"X-aws-ec2-metadata-token": token})
        az = urllib.request.urlopen(req, timeout=3).read().decode().strip()
        region = az[:-1] if az[-1].isalpha() else az
        log(f"Stopping instance {instance_id} in {region} due to idle timeout...")
        subprocess.run(["aws", "ec2", "stop-instances", "--instance-ids", instance_id, "--region", region], check=True)
    except Exception as e:
        log(f"Error in stop_instance: {e}")

def main():
    cpu = get_cpu_usage()
    container_cpu = get_container_cpu()
    count = 0
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                content = f.read().strip()
                count = int(content) if content.isdigit() else 0
        except Exception:
            count = 0
    if cpu < THRESHOLD and container_cpu < THRESHOLD:
        count += 5
        try:
            with open(COUNTER_FILE, "w") as f:
                f.write(str(count))
        except Exception:
            pass
        log(f"Idle count: {count} / {MAX_IDLE_MINS} minutes (Host CPU: {cpu}%, Container CPU: {container_cpu}%)")
        if count >= MAX_IDLE_MINS:
            log(f"Idle limit reached ({count} >= {MAX_IDLE_MINS} min). Stopping instance...")
            stop_instance()
    else:
        try:
            with open(COUNTER_FILE, "w") as f:
                f.write("0")
        except Exception:
            pass
        log(f"Active workload (Host CPU: {cpu}%, Container CPU: {container_cpu}%). Reset counter to 0.")

if __name__ == "__main__":
    main()
IDLE

chmod +x /usr/local/bin/rf-idle-monitor.py
cat << 'WRAPPER' > /usr/local/bin/rf-idle-monitor.sh
#!/bin/bash
/usr/bin/python3 /usr/local/bin/rf-idle-monitor.py >> /var/log/rf-idle-monitor.log 2>&1
WRAPPER
chmod +x /usr/local/bin/rf-idle-monitor.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/rf-idle-monitor.sh") | crontab -

echo "RF Suite EC2 Provisioning Complete!"
