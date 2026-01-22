#!/bin/bash
# Build script for WannaTapThat macOS app

set -e

echo "=== WannaTapThat Build Script ==="
echo ""

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check if Nuitka is available
if ! python -c "import nuitka" 2>/dev/null; then
    echo "Installing Nuitka..."
    pip install -q nuitka
fi

echo ""
echo "Building app bundle with Nuitka..."
echo "This may take several minutes on first build..."
echo ""

# Clean previous builds
rm -rf dist/WannaTapThat.app dist/WannaTapThat.build dist/WannaTapThat.dist

# Build with Nuitka
python -m nuitka \
    --standalone \
    --onefile \
    --macos-create-app-bundle \
    --macos-app-name="WannaTapThat" \
    --include-data-dir=resources=resources \
    --output-dir=dist \
    --remove-output \
    --assume-yes-for-downloads \
    gui.py

echo ""
echo "=== Build Complete ==="
echo ""

if [ -d "dist/WannaTapThat.app" ]; then
    echo "App bundle created: dist/WannaTapThat.app"
    echo ""
    echo "To create a DMG for distribution:"
    echo "  brew install create-dmg"
    echo "  ./create-dmg.sh"
else
    echo "Note: App bundle may be at dist/gui.app"
    echo "Rename it: mv dist/gui.app dist/WannaTapThat.app"
fi

echo ""
echo "To test without building, run:"
echo "  python gui.py"
