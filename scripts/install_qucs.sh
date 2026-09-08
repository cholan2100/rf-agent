#!/bin/bash
set -euo pipefail

echo "======================================================================"
echo "  Installing Qucs-S, qucsator-rf, and ngspice"
echo "======================================================================"

echo "[1/2] Setting up ngspice compatibility symlinks..."

# Create ngspice_con symlink for compatibility with Windows scripts
ln -sf /usr/bin/ngspice /usr/local/bin/ngspice_con || true
ln -sf /usr/bin/ngspice /usr/bin/ngspice_con || true

echo "[2/2] Building Qucs-S and qucsator-rf from source..."
apt-get update && apt-get install -y --no-install-recommends libqt5charts5-dev dos2unix

BUILD_DIR="/tmp/qucs_s_build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

git clone --recursive --depth 1 --branch 24.4.1 https://github.com/ra3xdh/qucs_s.git .
mkdir -p build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release -DWITH_DOCS=OFF ..
make -j"$(nproc)"
make install

# Ensure qucsator and qucsator_rf are in PATH
ln -sf /usr/local/bin/qucsator_rf /usr/local/bin/qucsator || true
ln -sf /usr/local/bin/qucsator_rf /usr/bin/qucsator_rf || true
ln -sf /usr/local/bin/qucsator_rf /usr/bin/qucsator || true

# Also create symlinks for qucsconv
if [ -f /usr/local/bin/qucsconv ]; then
    ln -sf /usr/local/bin/qucsconv /usr/local/bin/qucsconv_rf || true
    ln -sf /usr/local/bin/qucsconv /usr/bin/qucsconv_rf || true
fi

# Clean up build directory
rm -rf "$BUILD_DIR"

echo "Verifying Qucs / qucsator installation..."
qucsator -v || true
ngspice -v || true
echo "Qucs-S and solvers installed successfully!"
