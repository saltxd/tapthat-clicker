#!/bin/bash
# notarize.sh — sign, package, notarize, and staple WannaTapThat for public
# distribution. Run AFTER ./build.sh has produced dist/WannaTapThat.app.
#
# What it does:
#   1. Signs the .app with your Developer ID + hardened runtime + entitlements
#   2. Builds the DMG (via ./create-dmg.sh) and signs it
#   3. Submits the DMG to Apple's notary service and waits for the result
#   4. Staples the notarization ticket to the DMG and verifies with spctl
#
# Configure via environment variables (preferred) or edit the defaults below:
#   CODESIGN_IDENTITY  e.g. "Developer ID Application: Your Name (TEAMID)"
#   NOTARY_PROFILE     a notarytool keychain profile name (see store-credentials)
#                      -- OR -- provide APPLE_ID + TEAM_ID + APP_PASSWORD instead.
#
# Set up a keychain profile once (recommended) so you never paste secrets here:
#   xcrun notarytool store-credentials "wtt-notary" \
#     --apple-id "you@example.com" --team-id "TEAMID" --password "app-specific-pw"

set -euo pipefail

# ---- Config (edit or override via env) ------------------------------------
APP_NAME="WannaTapThat"
APP_PATH="dist/${APP_NAME}.app"
DMG_PATH="dist/${APP_NAME}.dmg"
ENTITLEMENTS="entitlements.plist"

CODESIGN_IDENTITY="${CODESIGN_IDENTITY:-}"   # "Developer ID Application: Your Name (TEAMID)"
NOTARY_PROFILE="${NOTARY_PROFILE:-}"         # notarytool keychain profile name
APPLE_ID="${APPLE_ID:-}"                     # fallback if no NOTARY_PROFILE
TEAM_ID="${TEAM_ID:-}"                       # fallback if no NOTARY_PROFILE
APP_PASSWORD="${APP_PASSWORD:-}"             # fallback app-specific password

# ---- Helpers --------------------------------------------------------------
step() { echo ""; echo "==> $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "required tool '$1' not found (install Xcode Command Line Tools)"; }

# ---- Preflight ------------------------------------------------------------
step "Preflight checks"

need_cmd codesign
need_cmd xcrun
need_cmd hdiutil
xcrun notarytool --help >/dev/null 2>&1 || die "'xcrun notarytool' unavailable — update Xcode Command Line Tools (xcode-select --install)"

[ -d "$APP_PATH" ] || die "$APP_PATH not found. Run ./build.sh first."

[ -n "$CODESIGN_IDENTITY" ] || die "CODESIGN_IDENTITY is not set. Export it, e.g.:
  export CODESIGN_IDENTITY=\"Developer ID Application: Your Name (TEAMID)\"
  (find it with: security find-identity -v -p codesigning)"

# Confirm the signing identity actually exists in a keychain.
if ! security find-identity -v -p codesigning | grep -qF "$CODESIGN_IDENTITY"; then
    die "Signing identity not found in keychain:
  $CODESIGN_IDENTITY
List available identities with: security find-identity -v -p codesigning"
fi

# Resolve notarization credentials: keychain profile OR apple-id/team/password.
NOTARY_ARGS=()
if [ -n "$NOTARY_PROFILE" ]; then
    NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
    echo "  Using notarytool keychain profile: $NOTARY_PROFILE"
elif [ -n "$APPLE_ID" ] && [ -n "$TEAM_ID" ] && [ -n "$APP_PASSWORD" ]; then
    NOTARY_ARGS=(--apple-id "$APPLE_ID" --team-id "$TEAM_ID" --password "$APP_PASSWORD")
    echo "  Using Apple ID credentials for: $APPLE_ID (team $TEAM_ID)"
else
    die "No notarization credentials. Either:
  export NOTARY_PROFILE=\"wtt-notary\"   (after 'xcrun notarytool store-credentials')
or export all of: APPLE_ID, TEAM_ID, APP_PASSWORD (an app-specific password)."
fi

echo "  App:      $APP_PATH"
echo "  Identity: $CODESIGN_IDENTITY"

# ---- Entitlements (hardened runtime needs these for the bundled Python) -----
step "Writing $ENTITLEMENTS"
# PyInstaller ships a Python interpreter that loads unsigned .so/.dylib files and
# uses executable memory, so under the hardened runtime notarization needs the
# JIT / unsigned-exec-memory / library-validation relaxations below.
cat > "$ENTITLEMENTS" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key><true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
  <key>com.apple.security.cs.disable-library-validation</key><true/>
</dict>
</plist>
PLIST
echo "  wrote $ENTITLEMENTS"

# ---- 1. Sign the app ------------------------------------------------------
step "Signing $APP_PATH (Developer ID + hardened runtime)"
codesign --force --deep --timestamp --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$CODESIGN_IDENTITY" \
    "$APP_PATH"

echo "  Verifying app signature..."
codesign --verify --strict --verbose=2 "$APP_PATH"
codesign --display --verbose=2 "$APP_PATH" 2>&1 | grep -i "Authority\|flags" || true

# ---- 2. Build + sign the DMG ---------------------------------------------
step "Building DMG"
rm -f "$DMG_PATH"
[ -x ./create-dmg.sh ] || die "./create-dmg.sh not found or not executable."
./create-dmg.sh
[ -f "$DMG_PATH" ] || die "DMG was not created at $DMG_PATH."

step "Signing $DMG_PATH"
codesign --force --timestamp --sign "$CODESIGN_IDENTITY" "$DMG_PATH"

# ---- 3. Notarize ----------------------------------------------------------
step "Submitting to Apple notary service (this can take a few minutes)"
xcrun notarytool submit "$DMG_PATH" "${NOTARY_ARGS[@]}" --wait \
    || die "Notarization submission failed. Fetch details with:
  xcrun notarytool log <SUBMISSION_ID> ${NOTARY_ARGS[*]}"

# ---- 4. Staple + verify ---------------------------------------------------
step "Stapling notarization ticket to the DMG"
xcrun stapler staple "$DMG_PATH"
xcrun stapler validate "$DMG_PATH"

step "Gatekeeper assessment (mounting DMG)"
MOUNT_DIR="$(mktemp -d)"
hdiutil attach "$DMG_PATH" -nobrowse -mountpoint "$MOUNT_DIR" >/dev/null
trap 'hdiutil detach "$MOUNT_DIR" >/dev/null 2>&1 || true; rmdir "$MOUNT_DIR" 2>/dev/null || true' EXIT
if spctl --assess --type execute --verbose=4 "$MOUNT_DIR/${APP_NAME}.app" 2>&1 | tee /dev/stderr | grep -q "accepted"; then
    echo "  Gatekeeper: ACCEPTED"
else
    die "Gatekeeper did NOT accept the app. Check the spctl output above."
fi

step "Done"
echo "Notarized, stapled, Gatekeeper-accepted DMG ready:"
echo "  $DMG_PATH"
echo ""
echo "Attach it to the GitHub Release:"
echo "  gh release create vX.Y.Z \"$DMG_PATH\" --repo saltxd/tapthat-clicker \\"
echo "    --title \"WannaTapThat vX.Y.Z\" --notes-file release-notes.md"
