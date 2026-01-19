#!/bin/bash
# Create DMG for WannaTapThat distribution

set -e

APP_NAME="WannaTapThat"
APP_PATH="dist/${APP_NAME}.app"
DMG_NAME="${APP_NAME}.dmg"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: $APP_PATH not found"
    echo "Run ./build.sh first"
    exit 1
fi

# Check for create-dmg
if ! command -v create-dmg &> /dev/null; then
    echo "Installing create-dmg..."
    brew install create-dmg
fi

# Remove old DMG if exists
rm -f "dist/$DMG_NAME"

echo "Creating DMG..."

create-dmg \
    --volname "$APP_NAME" \
    --window-pos 200 120 \
    --window-size 500 300 \
    --icon-size 100 \
    --icon "$APP_NAME.app" 150 150 \
    --app-drop-link 350 150 \
    --hide-extension "$APP_NAME.app" \
    "dist/$DMG_NAME" \
    "$APP_PATH"

echo ""
echo "=== DMG Created ==="
echo "Output: dist/$DMG_NAME"
echo ""
echo "Users can open the DMG and drag to Applications."
