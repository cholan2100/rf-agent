# ==============================================================================
# RF Workbench Dockerfile (Debian 13 Trixie + KiCad 10 Auto)
# Complete containerized RF Engineering & Simulation suite:
# KiCad 10 (CLI raytracer + pcbnew), FreeCAD 1.0 + Microwave Workbench,
# openEMS + CSXCAD FDTD solvers, Qucs-S + qucsator-rf + ngspice 44,
# RF-tools-KiCAD, scikit-rf, and noVNC Web GUI.
# ==============================================================================

FROM ghcr.io/inti-cmnb/kicad10_auto:latest

LABEL maintainer="RF Workbench Team"
LABEL description="Complete containerized RF Engineering & Simulation suite on Debian 13 with KiCad 10"

USER root

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    DISPLAY=:99 \
    RESOLUTION=1920x1080 \
    PYTHONPATH=/opt/openEMS/share/openEMS/matlab:/opt/openEMS/share/CSXCAD/matlab:/opt/kicad-mcp-server/src:/root/.local/share/FreeCAD/Mod/freecad-microwave:/workspace \
    LD_LIBRARY_PATH=/opt/openEMS/lib:/usr/local/lib:$LD_LIBRARY_PATH \
    PATH=/opt/openEMS/bin:/usr/local/bin:$PATH

WORKDIR /opt/rf-linux-env

# ------------------------------------------------------------------------------
# 1. Clean obsolete repo keys & install Base, Build & Desktop Packages
# ------------------------------------------------------------------------------
RUN rm -f /etc/apt/sources.list.d/kicad-10.0-releases.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    locales \
    curl \
    wget \
    git \
    ca-certificates \
    gnupg \
    unzip \
    tar \
    nano \
    build-essential \
    cmake \
    ninja-build \
    pkg-config \
    bison \
    flex \
    gperf \
    patchelf \
    python3-dev \
    python3-pip \
    python3-venv \
    python3-numpy \
    python3-scipy \
    python3-matplotlib \
    python3-h5py \
    python3-setuptools \
    libhdf5-dev \
    libboost-all-dev \
    libtinyxml-dev \
    libtinyxml2-dev \
    libcgal-dev \
    libvtk9-dev \
    libvtk9-qt-dev \
    libepoxy-dev \
    gengetopt \
    help2man \
    groff \
    qtbase5-dev \
    libqt5opengl5-dev \
    libqt5svg5-dev \
    libqt5charts5-dev \
    dos2unix \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    openbox \
    xterm \
    dbus-x11 \
    libgl1-mesa-dri \
    && locale-gen en_US.UTF-8 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# 2. Install Debian Native FreeCAD 1.0 and ngspice 44
# ------------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    freecad \
    freecad-python3 \
    ngspice \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# 3. Install Python Scientific & RF Stack
# ------------------------------------------------------------------------------
COPY requirements.txt /opt/rf-linux-env/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed -r /opt/rf-linux-env/requirements.txt

# ------------------------------------------------------------------------------
# 4. Build and Install openEMS + CSXCAD (FDTD Solver)
# ------------------------------------------------------------------------------
COPY scripts/install_openems.sh /opt/rf-linux-env/scripts/install_openems.sh
RUN chmod +x /opt/rf-linux-env/scripts/install_openems.sh && /opt/rf-linux-env/scripts/install_openems.sh

# ------------------------------------------------------------------------------
# 5. Build and Install qucsator-rf and Qucs-S GUI
# ------------------------------------------------------------------------------
COPY scripts/install_qucs.sh /opt/rf-linux-env/scripts/install_qucs.sh
RUN chmod +x /opt/rf-linux-env/scripts/install_qucs.sh && /opt/rf-linux-env/scripts/install_qucs.sh

# ------------------------------------------------------------------------------
# 6. Setup Plugins, Workbenches & MCP Server
# ------------------------------------------------------------------------------
COPY scripts/setup_plugins.sh /opt/rf-linux-env/scripts/setup_plugins.sh
RUN chmod +x /opt/rf-linux-env/scripts/setup_plugins.sh && /opt/rf-linux-env/scripts/setup_plugins.sh

# ------------------------------------------------------------------------------
# 7. Desktop Configs, Tests, and Entrypoint
# ------------------------------------------------------------------------------
COPY config/ /opt/rf-linux-env/config/
COPY tests/ /opt/rf-linux-env/tests/
COPY entrypoint.sh /opt/rf-linux-env/entrypoint.sh
RUN chmod +x /opt/rf-linux-env/entrypoint.sh /opt/rf-linux-env/tests/verify_environment.py

# Link noVNC vnc.html as index.html so root URL opens desktop directly
RUN ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html || true

# ------------------------------------------------------------------------------
# 8. Final Environment & Workspace Setup
# ------------------------------------------------------------------------------
WORKDIR /workspace
EXPOSE 6080 5900 8000

ENTRYPOINT ["/opt/rf-linux-env/entrypoint.sh"]
