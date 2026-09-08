#!/bin/bash
set -euo pipefail

echo "======================================================================"
echo "  Building and Installing openEMS, CSXCAD, and AppCSXCAD"
echo "======================================================================"

INSTALL_DIR="/opt/openEMS"
mkdir -p "$INSTALL_DIR"

echo "[1/4] Installing openEMS specific build dependencies..."
apt-get update
apt-get install -y --no-install-recommends \
    libcgal-dev \
    libvtk7-qt-dev \
    python3-setuptools-scm \
    gengetopt \
    help2man \
    groff \
    libepoxy-dev

BUILD_DIR="/tmp/openEMS-build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "[2/4] Cloning openEMS-Project repository..."
git clone --recursive --depth 1 https://github.com/thliebig/openEMS-Project.git .

echo "[3/4] Running update_openEMS.sh with Python bindings..."
export CC=gcc
export CXX=g++
./update_openEMS.sh "$INSTALL_DIR" --python --skip-dep-check --verbose

echo "[4/4] Setting up dynamic linker, PATH, and Python modules..."
# Add openEMS libraries to dynamic linker first
echo "$INSTALL_DIR/lib" > /etc/ld.so.conf.d/openEMS.conf
ldconfig

# Copy compiled python modules into system python3 site-packages
PYTHON_SITE_PKG=$(python3 -c "import site; print(site.getsitepackages()[0])")
if [ -d "$INSTALL_DIR/venv" ]; then
    echo "Copying openEMS venv modules to $PYTHON_SITE_PKG..."
    cp -rn $INSTALL_DIR/venv/lib/python*/site-packages/* "$PYTHON_SITE_PKG/" || true
fi

# Create binary symlinks
for bin in openEMS AppCSXCAD nf2ff; do
    if [ -f "$INSTALL_DIR/bin/$bin" ]; then
        ln -sf "$INSTALL_DIR/bin/$bin" "/usr/local/bin/$bin"
    fi
done

# Clean up build directory
rm -rf "$BUILD_DIR"

echo "openEMS installation completed successfully!"
openEMS || true
python3 -c "import CSXCAD; print('CSXCAD Python module OK')"
python3 -c "import openEMS; print('openEMS Python module OK')"
