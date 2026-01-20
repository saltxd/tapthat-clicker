# WannaTapThat

Auto-liker with opener for Hinge via iPhone Mirroring.

## Quick Start (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python gui.py
```

## Building a Distributable App

```bash
# Build macOS app bundle
./build.sh

# Create DMG for distribution
./create-dmg.sh
```

## How It Works

1. Finds the iPhone Mirroring window
2. Uses template matching to find the heart button
3. Clicks heart to like the profile
4. Finds the text input field
5. Types your opener message
6. Clicks send

## Icon Templates

The `resources/` folder contains template images used for finding UI elements:

- `heart.png` - The heart/like button
- `textbox.png` - The text input field
- `send.png` - The send button

If matching isn't working well, you can capture new templates:
1. Take a screenshot of iPhone Mirroring with Hinge open
2. Crop to just the button/element
3. Replace the PNG in `resources/`

## Requirements

- macOS 14+ (for iPhone Mirroring)
- iPhone with Hinge installed
- Screen Recording permission for the app

## Permissions

On first run, macOS will ask for:
- **Accessibility** - Required for clicking and typing
- **Screen Recording** - Required for capturing iPhone Mirroring window

Go to System Settings > Privacy & Security to grant these.

### Troubleshooting Screen Recording Permission

- You can now run bundled diagnostics from Terminal without launching the UI:

  ```bash
  ./dist/WannaTapThat.app/Contents/MacOS/WannaTapThat --diagnostics
  ```

  This prints the detected Python/runtime info, window lookup results, and whether `CGWindowListCreateImage` succeeds. The tool also writes `/tmp/debug_capture.png` when capture works.

- macOS ties Screen Recording permission to the code signature of the `.app`. PyInstaller uses an ad-hoc signature by default, so every rebuild has a new code hash. After each new build, macOS treats it as a brand-new app (you can confirm in Console with `log show --predicate 'process == "tccd"'` where the identifier appears as `WannaTapThat-<hash>`). Because of that the System Settings toggle you enabled for the previous build does **not** apply to the new binary and `CGWindowListCreateImage` will return `None`.

  To fix this:

  1. Remove the stale permission entry and re‑grant it for the current build. The quickest way during development is:
     ```bash
     tccutil reset ScreenCapture
     tccutil reset Accessibility
     ```
     then re-run the `.app` so macOS prompts again, or manually re-enable it under Privacy & Security → Screen Recording/Accessibility.
  2. For a permanent fix sign the bundle with a real code signing identity (or a dedicated self-signed Code Signing certificate) so the code requirement is stable across builds:
     ```bash
     codesign --force --deep --options runtime \
       --sign "Developer ID Application: YOUR NAME (TEAMID)" \
       dist/WannaTapThat.app
     ```
     Once the app is signed with a consistent identity, you only need to grant permissions once.
