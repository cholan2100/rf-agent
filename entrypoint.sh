#!/bin/bash
set -e

# Ensure python aliases to python3 if missing
if ! command -v python >/dev/null 2>&1; then
    ln -sf "$(command -v python3)" /usr/local/bin/python 2>/dev/null || true
fi

# Default resolution if not provided
RESOLUTION="${RESOLUTION:-1920x1080}"
DISPLAY="${DISPLAY:-:99}"
export DISPLAY

# Setup Openbox configs
mkdir -p /root/.config/openbox
if [ -f /opt/rf-linux-env/config/openbox-menu.xml ]; then
    cp /opt/rf-linux-env/config/openbox-menu.xml /root/.config/openbox/menu.xml
fi
if [ -f /opt/rf-linux-env/config/openbox-rc.xml ]; then
    cp /opt/rf-linux-env/config/openbox-rc.xml /root/.config/openbox/rc.xml
fi

# Function to start virtual display server
start_xvfb() {
    # Remove stale X lock files from ungraceful shutdowns or restarts
    local disp_num="${DISPLAY#:}"
    rm -f "/tmp/.X${disp_num}-lock" "/tmp/.X11-unix/X${disp_num}" 2>/dev/null || true

    if ! pgrep -x "Xvfb" > /dev/null; then
        echo "[Entrypoint] Starting Xvfb on ${DISPLAY} (${RESOLUTION}x24)..."
        Xvfb "${DISPLAY}" -screen 0 "${RESOLUTION}x24" -ac +extension GLX +render -noreset &
        sleep 2
    fi
}

# Function to start desktop environment and VNC services
start_desktop() {
    start_xvfb

    if ! pgrep -x "openbox" > /dev/null; then
        echo "[Entrypoint] Starting Openbox Window Manager..."
        openbox-session &
        sleep 1
    fi

    # Setup VNC password
    VNC_AUTH_OPT="-nopw"
    if [ -n "${VNC_PASSWORD:-}" ] && [ "${VNC_PASSWORD}" != "none" ]; then
        mkdir -p /root/.vnc
        x11vnc -storepasswd "${VNC_PASSWORD}" /root/.vnc/passwd
        VNC_AUTH_OPT="-rfbauth /root/.vnc/passwd"
    fi

    if ! pgrep -x "x11vnc" > /dev/null; then
        echo "[Entrypoint] Starting x11vnc server on port 5900..."
        x11vnc -display "${DISPLAY}" -forever -shared -bg ${VNC_AUTH_OPT} -rfbport 5900 -quiet
    fi

    if ! pgrep -f "websockify" > /dev/null; then
        echo "[Entrypoint] Starting noVNC web server on port 6080..."
        # Point directly to vnc.html so navigating to http://localhost:6080 immediately opens the desktop
        websockify --web /usr/share/novnc 6080 localhost:5900 &
    fi

    echo "======================================================================"
    echo "  RF Workbench Container is Ready!"
    echo "  - Web GUI (noVNC): http://localhost:6080/vnc.html"
    echo "  - Direct VNC:      localhost:5900"
    echo "  - Workspace:       /workspace"
    echo "======================================================================"
}

# If arguments are passed, evaluate mode
if [ $# -gt 0 ]; then
    # Headless script or command execution mode
    start_xvfb
    exec "$@"
else
    # Default desktop daemon mode
    start_desktop
    # Keep container alive
    tail -f /dev/null
fi
