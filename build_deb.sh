#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Cleaning previous builds..."
rm -rf deb_dist dist build *.egg-info src/*.egg-info

echo "Generating Debian source tree..."
uv run python3 setup.py --command-packages=stdeb.command sdist_dsc

echo "Patching Debian dependencies..."
cd deb_dist/umik-base-app-*/

# Python 3.12 removed distutils; ensure setuptools is available at build time
sed -i 's/^Build-Depends:.*/Build-Depends: debhelper (>= 9), dh-python, python3-all, python3-setuptools/' debian/control

# Replace ${python3:Depends} with an explicit dep list to prevent vendored packages
# from being expanded as system dependencies by dh_python3
sed -i 's/^Depends:.*/Depends: ${misc:Depends}, python3.12, libportaudio2, libsndfile1, ffmpeg, libzmq3-dev/' debian/control

echo "Fixed debian/control:"
grep -E "^(Package|Depends|Build-Depends):" debian/control

echo "Writing debian/postinst (shebang fix)..."
cat > debian/postinst << 'POSTINST'
#!/bin/sh
set -e
# Vendored C extensions require Python 3.12; patch the auto-generated shebangs
for bin in /usr/bin/audio-tools \
           /usr/bin/umik-calibrate /usr/bin/umik-list-devices \
           /usr/bin/umik-real-time-meter /usr/bin/umik-recorder \
           /usr/bin/umik-metrics-analyzer /usr/bin/umik-metrics-plotter \
           /usr/bin/umik-batch-analyze /usr/bin/umik-enhance-audio \
           /usr/bin/umik-convert; do
    [ -f "$bin" ] && sed -i '1s|^#!/usr/bin/python3$|#!/usr/bin/python3.12|' "$bin" || true
done
#DEBHELPER#
POSTINST
chmod +x debian/postinst

echo "Compiling .deb package..."
PATH="/usr/bin:$PATH" dpkg-buildpackage -uc -us -b

echo "Verifying package integrity..."
cd ../..
DEB_FILE=$(find deb_dist -name "*.deb" -type f | head -1)

dpkg -c "$DEB_FILE" | grep "umik_base_app/" | head -n 1 | grep -q . || {
    echo "Error: umik_base_app package missing from .deb!" >&2
    exit 1
}

echo "Integrity check passed."
echo ""
echo "Build successful: $(realpath "$DEB_FILE")"
