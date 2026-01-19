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
