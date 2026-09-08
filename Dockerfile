# ==============================================================================
# RF Workbench Dockerfile
# All-in-one containerized Linux environment for RF Engineering:
# KiCad 8 + pcbnew, openEMS + CSXCAD, Qucs-S + qucsator-rf + ngspice,
# FreeCAD + Microwave Workbench, RF-tools-KiCAD, scikit-rf, and noVNC Web GUI.
# ==============================================================================

FROM ubuntu:22.04

LABEL maintainer="RF Workbench Team"
LABEL description="Complete containerized RF Engineering & Simulation suite"

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
# 1. Base System, Build Tools, and Desktop/VNC packages
# ------------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
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
    python3 \
    python3-pip \
    python3-dev \
    python3-numpy \
    python3-scipy \
    python3-matplotlib \
    python3-h5py \
    python3-venv \
    cython3 \
    libhdf5-dev \
    libboost-all-dev \
    libtinyxml-dev \
    libtinyxml2-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libqt5svg5-dev \
    libqt5xmlpatterns5-dev \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    openbox \
    xterm \
    dbus-x11 \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    && locale-gen en_US.UTF-8 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Try installing libvtk (version 7 or 9 depending on availability)
RUN apt-get update && (apt-get install -y --no-install-recommends libvtk7-dev || apt-get install -y --no-install-recommends libvtk9-dev) \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# 2. Add PPAs for KiCad 8.0 and FreeCAD
# ------------------------------------------------------------------------------
RUN add-apt-repository --yes ppa:kicad/kicad-8.0-releases && \
    add-apt-repository --yes ppa:freecad-maintainers/freecad-stable && \
    apt-get update

# ------------------------------------------------------------------------------
# 3. Install KiCad 8, FreeCAD, and ngspice
# ------------------------------------------------------------------------------
RUN apt-get install -y --no-install-recommends -o Dpkg::Options::="--force-overwrite" \
    kicad \
    kicad-libraries \
    kicad-symbols \
    kicad-footprints \
    kicad-packages3d \
    freecad \
    freecad-python3 \
    ngspice \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# 4. Install Python Scientific & RF Stack
# ------------------------------------------------------------------------------
COPY requirements.txt /opt/rf-linux-env/requirements.txt
RUN pip3 install --no-cache-dir -r /opt/rf-linux-env/requirements.txt

# ------------------------------------------------------------------------------
# 5. Build and Install openEMS + CSXCAD (FDTD Solver)
# ------------------------------------------------------------------------------
COPY scripts/install_openems.sh /opt/rf-linux-env/scripts/install_openems.sh
RUN chmod +x /opt/rf-linux-env/scripts/install_openems.sh && /opt/rf-linux-env/scripts/install_openems.sh

# ------------------------------------------------------------------------------
# 6. Build and Install qucsator-rf and Solvers
# ------------------------------------------------------------------------------
COPY scripts/install_qucs.sh /opt/rf-linux-env/scripts/install_qucs.sh
RUN chmod +x /opt/rf-linux-env/scripts/install_qucs.sh && /opt/rf-linux-env/scripts/install_qucs.sh

# ------------------------------------------------------------------------------
# 7. Setup Plugins, Workbenches & MCP Server
# ------------------------------------------------------------------------------
COPY scripts/setup_plugins.sh /opt/rf-linux-env/scripts/setup_plugins.sh
RUN chmod +x /opt/rf-linux-env/scripts/setup_plugins.sh && /opt/rf-linux-env/scripts/setup_plugins.sh

# ------------------------------------------------------------------------------
# 8. Desktop Configs, Tests, and Entrypoint
# ------------------------------------------------------------------------------
COPY config/ /opt/rf-linux-env/config/
COPY tests/ /opt/rf-linux-env/tests/
COPY entrypoint.sh /opt/rf-linux-env/entrypoint.sh
RUN chmod +x /opt/rf-linux-env/entrypoint.sh /opt/rf-linux-env/tests/verify_environment.py

# Link noVNC vnc.html as index.html so root URL opens desktop directly
RUN ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html || true

# ------------------------------------------------------------------------------
# 9. Final Environment & Workspace Setup
# ------------------------------------------------------------------------------
WORKDIR /workspace
EXPOSE 6080 5900 8000

ENTRYPOINT ["/opt/rf-linux-env/entrypoint.sh"]
