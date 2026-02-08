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

1. Finds the iPhone Mirroring window via Quartz APIs
2. Uses OpenCV template matching to find the heart button (bottom 30% of screen)
3. Clicks heart to like the profile
4. Finds the text input field
5. Types your opener message with human-like keystroke delays
6. Clicks send
7. Repeats with randomized delays between profiles

### Template Matching

Uses `TM_CCOEFF_NORMED` with **cropped templates** (15% margin trim) to avoid background-dependent edge artifacts. This was critical for reliability on profiles with bright/white backgrounds where the original full-template approach would fail.

Key parameters:
- Heart threshold: 0.65 (topmost match in bottom 30% of screen)
- Send threshold: 0.60
- Speed delays: fast (2-3s), normal (3-5s), slow (5-8s)

### Anti-Detection
- Random click offsets (+-5px) on each button press
- Variable inter-profile delays
- Long pause injection every 8-15 likes (simulates reading)

## Icon Templates

The `resources/` folder contains template images used for finding UI elements:

- `heart.png` - The heart/like button
- `textbox.png` - The text input field
- `send.png` - The send button

If matching isn't working well, you can capture new templates:
1. Take a screenshot of iPhone Mirroring with Hinge open
2. Crop to just the button/element
3. Replace the PNG in `resources/`

## Shared Module: clicker.py

`clicker.py` is the core automation module shared with TinderTapper. It provides:

| Function | Purpose |
|----------|---------|
| `find_iphone_window()` | Locate iPhone Mirroring window via Quartz |
| `capture_window(wid)` | Screenshot a window by ID (returns PIL Image) |
| `find_icon(image, template, ...)` | Template matching with cropped margins, region filtering, topmost mode |
| `click_at(x, y, window)` | Click at image coordinates (auto-converts to screen coords via 2x Retina) |
| `random_delay(min, max)` | Sleep with optional early-stop callback |
| `type_text(text)` / `human_type(text)` | Keyboard input simulation |
| `press_key(key)` / `press_return()` | Single key press simulation |
| `activate_app(name)` | Bring app to front via NSWorkspace |

## Recent Changes

### 2026-02-07: Cropped Template Matching Fix
- **Problem**: Heart detection failed on profiles with bright/white backgrounds (Nadia, Dina, Lindsay). The heart.png template had dark edge pixels that mismatched against light backgrounds.
- **Fix**: Three changes to `find_icon()` in clicker.py:
  1. Crop templates by 15% margins before matching (removes background-dependent edges)
  2. Peak refinement in topmost matching (5px neighborhood search for highest confidence)
  3. Apply min_x/min_y filtering in non-topmost mode (was only applied in topmost mode)
- **Result**: 23/23 test screenshots pass, minimum confidence 0.815 (+0.165 margin above threshold). Ran 83 consecutive profiles without failure in production.

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

- macOS ties Screen Recording permission to the code signature of the `.app`. PyInstaller uses an ad-hoc signature by default, so every rebuild has a new code hash. After each new build, macOS treats it as a brand-new app. Because of that the System Settings toggle you enabled for the previous build does **not** apply to the new binary and `CGWindowListCreateImage` will return `None`.

  To fix this:

  1. Remove the stale permission entry and re-grant it for the current build:
     ```bash
     tccutil reset ScreenCapture
     tccutil reset Accessibility
     ```
     then re-run the `.app` so macOS prompts again, or manually re-enable it under Privacy & Security.
  2. For a permanent fix, sign the bundle with a consistent code signing identity:
     ```bash
     codesign --force --deep --options runtime \
       --sign "Developer ID Application: YOUR NAME (TEAMID)" \
       dist/WannaTapThat.app
     ```
  3. **Patching in-place** preserves permissions without resetting:
     ```bash
     cp dist/WannaTapThat.app/Contents/MacOS/WannaTapThat /Applications/WannaTapThat.app/Contents/MacOS/WannaTapThat
     rsync -a --delete dist/WannaTapThat.app/Contents/Frameworks/ /Applications/WannaTapThat.app/Contents/Frameworks/
     codesign --force --deep --sign - /Applications/WannaTapThat.app
     ```
