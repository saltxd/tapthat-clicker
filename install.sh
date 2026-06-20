#!/bin/bash
# WannaTapThat one-line installer.
#
#   curl -fsSL https://raw.githubusercontent.com/saltxd/tapthat-clicker/main/install.sh | bash
#
# Downloads the latest release DMG, copies the app to /Applications, removes the
# "downloaded from the internet" quarantine flag (so macOS doesn't block the
# unsigned app), and launches it. No Gatekeeper wall, no System Settings dance.
#
# It only touches /Applications/WannaTapThat.app. Read the script before running
# it if you like — it's short.

set -euo pipefail

APP="WannaTapThat"
DMG_URL="https://github.com/saltxd/tapthat-clicker/releases/latest/download/WannaTapThat.dmg"
DEST="/Applications/${APP}.app"

if [ "$(uname)" != "Darwin" ]; then
    echo "WannaTapThat is macOS only." >&2
    exit 1
fi

TMP="$(mktemp -d)"
MNT="$TMP/mnt"
cleanup() { hdiutil detach "$MNT" >/dev/null 2>&1 || true; rm -rf "$TMP"; }
trap cleanup EXIT

echo "Downloading ${APP}..."
curl -fsSL -o "$TMP/${APP}.dmg" "$DMG_URL"

echo "Installing to /Applications..."
hdiutil attach "$TMP/${APP}.dmg" -nobrowse -mountpoint "$MNT" >/dev/null
rm -rf "$DEST"
cp -R "$MNT/${APP}.app" "$DEST"
hdiutil detach "$MNT" >/dev/null

echo "Clearing the quarantine flag (so macOS won't block it)..."
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true

echo "Launching ${APP}..."
open "$DEST"

cat <<'NOTE'

Installed! One more thing on first run:
  macOS will ask for Screen Recording and Accessibility permissions.
  Grant both (System Settings > Privacy & Security), then start the app.

Enjoy — and remember it's experimental and against Hinge's ToS. Use at your own risk.
NOTE
