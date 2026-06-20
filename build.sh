#!/bin/bash
# Build the WannaTapThat macOS .app bundle (PyInstaller).
#
# Usage:
#   ./build.sh                 # build an ad-hoc-signed .app (Gatekeeper-blocked)
#   CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" ./build.sh
#                              # build + sign with a Developer ID (for notarization)
#
# For the full signed + notarized release flow, see RELEASING.md / notarize.sh.

set -euo pipefail

cd "$(dirname "$0")"

echo "=== WannaTapThat Build (PyInstaller) ==="

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found" >&2
    exit 1
fi

# Virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Clean previous build
rm -rf build dist/WannaTapThat.app

echo "Building app bundle..."
pyinstaller WannaTapThat.spec --noconfirm --clean

APP="dist/WannaTapThat.app"
if [ ! -d "$APP" ]; then
    echo "Error: build did not produce $APP" >&2
    exit 1
fi

# Optional: sign with a Developer ID so the bundle can be notarized.
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
    echo "Code-signing with: $CODESIGN_IDENTITY"
    codesign --force --deep --options runtime --timestamp \
        --entitlements entitlements.plist \
        --sign "$CODESIGN_IDENTITY" "$APP"
    codesign --verify --strict --verbose=2 "$APP"
else
    echo "No CODESIGN_IDENTITY set -> ad-hoc signature (Gatekeeper will block it)."
fi

echo ""
echo "=== Build complete: $APP ==="
"$APP/Contents/MacOS/WannaTapThat" --version || true
echo ""
echo "Next: ./create-dmg.sh  (for a clean install, sign + notarize per RELEASING.md)"
