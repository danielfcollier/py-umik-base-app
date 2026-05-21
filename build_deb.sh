#!/bin/bash
set -e

SKIP_CHECK=0
for arg in "$@"; do
    [ "$arg" = "--skip" ] && SKIP_CHECK=1
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
PYVER=$(uv run python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$SKIP_CHECK" = "0" ] && compgen -G "deb_dist/*${VERSION}*.deb" > /dev/null 2>&1; then
    printf "\n  Version %s is already built in deb_dist/.\n\n" "$VERSION"
    printf "  Bump the version first:\n"
    printf "    make bump-patch    %s -> next patch\n" "$VERSION"
    printf "    make bump-minor    %s -> next minor\n" "$VERSION"
    printf "    make bump-major    %s -> next major\n" "$VERSION"
    printf "\n  Or rebuild anyway: make build-deb SKIP=1\n\n"
    exit 1
fi

echo "Cleaning previous builds..."
rm -rf deb_dist/umik-base-app-*/ deb_dist/umik-base-app_* deb_dist/tmp_sdist_dsc \
       dist build *.egg-info src/*.egg-info
mkdir -p deb_dist

echo "Generating Debian source tree..."
uv run python3 setup.py --command-packages=stdeb.command sdist_dsc

echo "Patching Debian dependencies..."
cd deb_dist/umik-base-app-*/

# Python 3.12+ removed distutils; ensure setuptools is available at build time
sed -i 's/^Build-Depends:.*/Build-Depends: debhelper (>= 9), dh-python, python3-all, python3-setuptools/' debian/control

# Replace ${python3:Depends} with an explicit dep list to prevent vendored packages
# from being expanded as system dependencies by dh_python3
sed -i "s/^Depends:.*/Depends: \${misc:Depends}, python${PYVER}, libportaudio2, libsndfile1, ffmpeg, libzmq3-dev/" debian/control

# Vendor dir contains arch-specific .so files; replace "all" with "any" so
# dpkg-buildpackage produces the correct arch-specific filename (_amd64 / _arm64).
sed -i 's/^Architecture:.*/Architecture: any/' debian/control

echo "Fixed debian/control:"
grep -E "^(Package|Architecture|Depends|Build-Depends):" debian/control
grep -q "^Architecture: any" debian/control || { echo "ERROR: Architecture patch failed"; exit 1; }

# Disable debhelper steps that break on vendored binary extensions:
# - dh_python3: expects ${python3:Depends} which we replaced with explicit deps
# - dh_shlibdeps: scans .so files for system lib deps we already list explicitly
# - dh_dwz: tries to optimize debug symbols in vendored .so files
cat >> debian/rules << 'RULES_APPEND'

override_dh_python3:

override_dh_shlibdeps:

override_dh_strip:

override_dh_dwz:
RULES_APPEND

echo "Writing debian/postinst (shebang fix)..."
cat > debian/postinst << POSTINST_EOF
#!/bin/sh
set -e
for bin in /usr/bin/audio-tools /usr/bin/audio-tools-calibrate /usr/bin/audio-tools-devices /usr/bin/audio-tools-meter /usr/bin/audio-tools-record /usr/bin/audio-tools-analyze /usr/bin/audio-tools-plot /usr/bin/audio-tools-batch /usr/bin/audio-tools-enhance /usr/bin/audio-tools-convert; do
    [ -f "\$bin" ] && sed -i "1s|^#!/usr/bin/python3\$|#!/usr/bin/python${PYVER}|" "\$bin" || true
done
#DEBHELPER#
POSTINST_EOF
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
