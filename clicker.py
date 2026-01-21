"""WannaTapThat - Core clicker functions for iPhone Mirroring automation."""

import os
import sys
import time
import subprocess

import cv2
import numpy as np
from PIL import Image
import Quartz
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    CGWindowListCreateImage,
    CGRectNull,
    kCGWindowListOptionIncludingWindow,
    kCGWindowImageBoundsIgnoreFraming,
    CGEventCreateMouseEvent,
    CGEventPost,
    kCGEventMouseMoved,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGHIDEventTap,
)
from Quartz.CoreGraphics import CGPointMake
from AppKit import NSWorkspace, NSApplicationActivateIgnoringOtherApps


def get_resource_path(filename):
    """Get path to resource file, works for both dev and bundled app."""
    # List of paths to check in order
    paths_to_check = []

    if getattr(sys, 'frozen', False):
        # Running as compiled PyInstaller app
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller onefile mode
            paths_to_check.append(os.path.join(sys._MEIPASS, 'resources', filename))

        # PyInstaller onedir mode - check relative to executable
        exe_dir = os.path.dirname(sys.executable)
        paths_to_check.append(os.path.join(exe_dir, 'resources', filename))

        # macOS app bundle - Resources folder
        if '.app' in exe_dir:
            # exe is in .app/Contents/MacOS/, resources in .app/Contents/Resources/
            app_contents = os.path.dirname(exe_dir)
            paths_to_check.append(os.path.join(app_contents, 'Resources', 'resources', filename))

    # Running as script - check relative to this file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths_to_check.append(os.path.join(script_dir, 'resources', filename))

    # Return first path that exists
    for path in paths_to_check:
        if os.path.exists(path):
            return path

    # Return the script-relative path as fallback (will error with clear message)
    return os.path.join(script_dir, 'resources', filename)


def activate_app(owner_name):
    """Bring an app to the front by its owner name."""
    workspace = NSWorkspace.sharedWorkspace()
    apps = workspace.runningApplications()
    for app in apps:
        if owner_name.lower() in app.localizedName().lower():
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            time.sleep(0.1)
            return True
    return False


def find_iphone_window():
    """Find the iPhone Mirroring window and return its info."""
    windows = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    )

    for window in windows:
        owner = window.get("kCGWindowOwnerName", "")
        name = window.get("kCGWindowName", "")

        # iPhone Mirroring window
        if "iPhone" in owner or "iPhone" in name:
            bounds = window.get("kCGWindowBounds", {})
            return {
                "id": window.get("kCGWindowNumber"),
                "x": int(bounds.get("X", 0)),
                "y": int(bounds.get("Y", 0)),
                "width": int(bounds.get("Width", 0)),
                "height": int(bounds.get("Height", 0)),
                "owner": owner,
                "name": name,
            }

    return None


def capture_window(window_id):
    """Capture a screenshot of the specified window. Returns PIL Image."""
    try:
        print(f"  capture_window: Attempting CGWindowListCreateImage for window {window_id}")
        cg_image = CGWindowListCreateImage(
            CGRectNull,
            kCGWindowListOptionIncludingWindow,
            window_id,
            kCGWindowImageBoundsIgnoreFraming,
        )
        print(f"  capture_window: CGWindowListCreateImage returned: {cg_image}")

        if not cg_image:
            print("  capture_window: cg_image is None/falsy!")
            return None

        width = Quartz.CGImageGetWidth(cg_image)
        height = Quartz.CGImageGetHeight(cg_image)
        bytes_per_row = Quartz.CGImageGetBytesPerRow(cg_image)
        print(f"  capture_window: Image dimensions: {width}x{height}, bytes_per_row={bytes_per_row}")

        pixel_data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(cg_image))

        # Convert to numpy array (BGRA format)
        arr = np.frombuffer(pixel_data, dtype=np.uint8)
        arr = arr.reshape((height, bytes_per_row // 4, 4))
        arr = arr[:, :width, :]  # Trim padding

        # BGRA to RGB
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGRA2RGB)
        return Image.fromarray(rgb)
    except Exception as e:
        print(f"  capture_window: EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return None


def find_icon(image, template_filename, threshold=0.8, topmost=False, return_best_match=False):
    """
    Find the icon in the image using template matching.
    Returns (x, y, confidence) center point in image coordinates, or None if not found.

    If topmost=True, returns the highest match on screen (smallest Y) when multiple found.
    If return_best_match=True, returns the best match even if below threshold (for debugging).
    """
    template_path = get_resource_path(template_filename)

    # Load template
    template = cv2.imread(template_path)
    if template is None:
        raise FileNotFoundError(f"Could not load template: {template_path}")

    # Convert image to cv2 format
    img_arr = np.array(image)
    img_bgr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)

    h, w = template.shape[:2]

    # Use grayscale matching (most reliable)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    result = cv2.matchTemplate(img_gray, template_gray, cv2.TM_CCOEFF_NORMED)

    # Always get the best match for logging
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if topmost:
        # Find ALL matches above threshold
        locations = np.where(result >= threshold)
        matches = list(zip(locations[1], locations[0]))  # (x, y)

        if not matches:
            # No matches above threshold - return best match info if requested
            if return_best_match:
                cx = max_loc[0] + w // 2
                cy = max_loc[1] + h // 2
                return (cx, cy, float(max_val))
            return None

        # Return topmost (smallest Y)
        best = min(matches, key=lambda p: p[1])
        confidence = result[best[1], best[0]]
        return (best[0] + w // 2, best[1] + h // 2, float(confidence))
    else:
        # Original behavior - best match
        if max_val >= threshold:
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2
            return (cx, cy, float(max_val))

        # Return best match info if requested (even if below threshold)
        if return_best_match:
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2
            return (cx, cy, float(max_val))

        return None


def image_to_screen_coords(img_x, img_y, window_info, retina_scale=2):
    """
    Convert image coordinates to screen coordinates.
    Account for window position and Retina scaling.
    """
    screen_x = window_info["x"] + (img_x / retina_scale)
    screen_y = window_info["y"] + (img_y / retina_scale)
    return (screen_x, screen_y)


def click_at(img_x, img_y, window):
    """Click at the specified image coordinates (converts to screen coords)."""
    # Convert from 2x Retina image coords to screen coords
    screen_x, screen_y = image_to_screen_coords(img_x, img_y, window)

    # Activate the target window first
    if window.get("owner"):
        activate_app(window["owner"])

    point = CGPointMake(float(screen_x), float(screen_y))

    # Move mouse to position
    move_event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, point, 0)
    CGEventPost(kCGHIDEventTap, move_event)
    time.sleep(0.1)

    # Mouse down
    down_event = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, 0)
    CGEventPost(kCGHIDEventTap, down_event)
    time.sleep(0.05)

    # Mouse up
    up_event = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, 0)
    CGEventPost(kCGHIDEventTap, up_event)


def type_text(text):
    """Type text using AppleScript (most reliable method on macOS)."""
    # Escape special characters for AppleScript
    escaped = text.replace('\\', '\\\\').replace('"', '\\"')

    # Use AppleScript to type - most reliable method
    subprocess.run([
        'osascript', '-e',
        f'tell application "System Events" to keystroke "{escaped}"'
    ], check=True)


def human_type(text, activate_window=None, should_stop=None):
    """Type text word-by-word with human-like random delays.

    Args:
        text: The text to type
        activate_window: Optional window name to activate first
        should_stop: Optional callable that returns True if typing should stop

    Returns:
        True if completed, False if stopped early
    """
    import random

    if activate_window:
        activate_app(activate_window)
        time.sleep(0.1)

    # Split into words but keep spaces
    words = text.split(' ')

    for i, word in enumerate(words):
        # Check if we should stop BEFORE each word
        if should_stop and should_stop():
            return False

        # Add space before word (except first)
        if i > 0:
            word = ' ' + word

        # Escape for AppleScript
        escaped = word.replace('\\', '\\\\').replace('"', '\\"')

        subprocess.run([
            'osascript', '-e',
            f'tell application "System Events" to keystroke "{escaped}"'
        ], check=True)

        # Check again after typing
        if should_stop and should_stop():
            return False

        # Random delay between words (like thinking)
        delay = random.uniform(0.08, 0.25)

        # Longer pause after punctuation
        if word and word[-1] in '.!?,':
            delay += random.uniform(0.15, 0.4)

        time.sleep(delay)

    return True


def random_delay(min_sec, max_sec, should_stop=None):
    """Sleep for a random duration between min and max seconds.

    Args:
        min_sec: Minimum sleep time
        max_sec: Maximum sleep time
        should_stop: Optional callable that returns True to stop early

    Returns:
        True if completed, False if stopped early
    """
    import random
    total_delay = random.uniform(min_sec, max_sec)

    # Sleep in small increments so we can check should_stop
    elapsed = 0
    increment = 0.05  # Check every 50ms

    while elapsed < total_delay:
        if should_stop and should_stop():
            return False
        time.sleep(min(increment, total_delay - elapsed))
        elapsed += increment

    return True


def press_key(key_code):
    """Press a key using AppleScript key code."""
    subprocess.run([
        'osascript', '-e',
        f'tell application "System Events" to key code {key_code}'
    ], check=True)


def press_return():
    """Press the return/enter key."""
    press_key(36)  # Return key code
