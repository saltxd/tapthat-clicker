"""WannaTapThat - Auto-liker with opener for Hinge via iPhone Mirroring."""

import os
import sys
import platform
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import random
import subprocess
import json
from datetime import datetime
from pathlib import Path

try:
    import fcntl  # POSIX-only; present on macOS (the only supported platform)
except ImportError:
    fcntl = None

APP_NAME = "WannaTapThat"
APP_VERSION = "1.0.1"


def app_support_dir():
    """Return (creating if needed) the per-user app-support directory."""
    d = Path.home() / "Library" / "Application Support" / APP_NAME
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def load_settings():
    """Load saved settings, tolerating a missing or corrupt file."""
    try:
        with open(app_support_dir() / "settings.json") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return {}


def acquire_single_instance_lock():
    """Take an exclusive lock so only one copy drives iPhone Mirroring at a time.

    Returns the open file handle (keep it alive for the process lifetime) or
    None if another instance already holds the lock.
    """
    if fcntl is None:
        return True  # can't lock on this platform; don't block startup
    try:
        fh = open(app_support_dir() / "instance.lock", "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        return None


class DebugLogger:
    """Handles debug logging with timestamped screenshots and log files."""

    def __init__(self, enabled=False):
        self.enabled = enabled
        self.session_dir = None
        self.log_file = None
        self.step_count = 0
        self.attempt_count = 0

    def start_session(self):
        """Create a new debug session directory."""
        if not self.enabled:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = f"/tmp/wtt_debug/session_{timestamp}"
        os.makedirs(self.session_dir, exist_ok=True)

        self.log_file = open(f"{self.session_dir}/debug.log", "w")
        self.step_count = 0
        self.attempt_count = 0
        self.log(f"Debug session started: {timestamp}")
        self.log(f"Session directory: {self.session_dir}")

    def end_session(self):
        """Close the debug session."""
        if self.log_file:
            self.log("Session ended")
            self.log_file.close()
            self.log_file = None

    def new_attempt(self):
        """Start a new like attempt."""
        self.attempt_count += 1
        self.step_count = 0
        self.log(f"\n{'='*50}")
        self.log(f"ATTEMPT {self.attempt_count}")
        self.log(f"{'='*50}")

    def log(self, message):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{timestamp}] {message}"
        print(line)
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()

    def save_screenshot(self, image, step_name):
        """Save a screenshot with descriptive name."""
        if not self.enabled or not self.session_dir or image is None:
            return None

        self.step_count += 1
        filename = f"attempt{self.attempt_count:03d}_step{self.step_count:02d}_{step_name}.png"
        filepath = os.path.join(self.session_dir, filename)
        try:
            image.save(filepath)
            self.log(f"Screenshot saved: {filename}")
            return filepath
        except Exception as e:
            self.log(f"Failed to save screenshot: {e}")
            return None

    def log_match_result(self, template_name, result, threshold, best_match=None):
        """Log template matching result with confidence.

        Args:
            template_name: Name of the template being matched
            result: Match result (x, y, confidence) or None
            threshold: The threshold used
            best_match: Optional (x, y, confidence) of best match even if below threshold
        """
        if result:
            x, y, confidence = result
            status = "FOUND" if confidence >= threshold else "BELOW_THRESHOLD"
            self.log(f"  {template_name}: {status} at ({x}, {y}) "
                     f"confidence={confidence:.3f} threshold={threshold}")
        else:
            if best_match:
                x, y, confidence = best_match
                self.log(f"  {template_name}: NOT_FOUND (best={confidence:.3f}, "
                         f"threshold={threshold}, at ({x}, {y}))")
            else:
                self.log(f"  {template_name}: NOT_FOUND (threshold={threshold})")


# Global debug logger instance
debug_logger = DebugLogger(enabled=False)

# Verified-only tuning
VERIFIED_THRESHOLD = 0.78   # real verified badges match ~0.90-1.0; non-badge regions ~0.65
VERIFIED_REGION_FRAC = 0.45  # badge sits near the name, in the top ~45% of the screen
SKIP_THRESHOLD = 0.70        # X (skip) button match confidence
MAX_CONSECUTIVE_SKIPS = 200  # safety: stop if the deck is essentially all unverified


def is_profile_verified(image, find_icon, threshold=VERIFIED_THRESHOLD,
                        region_frac=VERIFIED_REGION_FRAC):
    """Return (is_verified, best_confidence) for the current Hinge profile.

    The verified badge ("Verified" + purple checkmark) lives next to the name,
    so we only search the top region. This both speeds up matching and avoids
    false positives from unrelated purple UI lower on the profile.
    """
    top = image.crop((0, 0, image.size[0], int(image.size[1] * region_frac)))
    match = find_icon(top, "hinge_verified.png", threshold=threshold)
    if match:
        return True, match[2]
    best = find_icon(top, "hinge_verified.png", threshold=threshold,
                     return_best_match=True)
    return False, (best[2] if best else 0.0)


def run_permission_check(find_iphone_window, capture_window):
    """Debug helper: attempt to find and capture the mirroring window."""
    try:
        print("=" * 50)
        print("DEBUG: Starting permission check")

        window = find_iphone_window()
        print(f"DEBUG: find_iphone_window returned: {window}")

        if window:
            print(f"DEBUG: Attempting capture of window {window['id']}")
            image = capture_window(window['id'])
            print(f"DEBUG: capture_window returned: {image}")
            if image:
                print(f"DEBUG: Image size: {image.size}")
                debug_path = "/tmp/debug_capture.png"
                try:
                    image.save(debug_path)
                    print(f"DEBUG: Saved to {debug_path}")
                except Exception as save_exc:
                    print(f"DEBUG: Failed to save debug capture: {save_exc}")
            else:
                print("DEBUG: Capture returned None!")
        else:
            print("DEBUG: No window found!")
    except Exception as debug_exc:
        print(f"DEBUG: Exception during permission check: {debug_exc}")
        import traceback
        traceback.print_exc()
    finally:
        print("=" * 50)


# ---- Theme ----------------------------------------------------------------
# Dark UI with a Hinge-ish purple accent. Uses the ttk "clam" theme as the base
# because (unlike macOS "aqua") it actually honors custom colors on every widget.
BG = "#1c1c1e"        # window background
SURFACE = "#2c2c2e"   # entries / opener box
SURFACE_HI = "#3a3a3c"  # hover / borders
TEXT = "#f2f2f7"      # primary text
MUTED = "#8e8e93"     # secondary text
ACCENT = "#bf5af2"    # purple accent
ACCENT_HI = "#cf83f5"  # accent hover
ACCENT_DIM = "#7d3a9e"  # accent pressed
DANGER = "#ff453a"    # stop button


def setup_theme(root):
    """Apply the dark + purple theme to the whole app. Call before build_ui."""
    root.configure(bg=BG)
    style = ttk.Style()
    if 'clam' in style.theme_names():
        style.theme_use('clam')

    style.configure('.', background=BG, foreground=TEXT,
                    font=('Helvetica', 11), focuscolor=TEXT)
    style.configure('TFrame', background=BG)
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('Header.TLabel', font=('Helvetica', 26, 'bold'), foreground=TEXT)
    style.configure('Sub.TLabel', font=('Helvetica', 10), foreground=MUTED)
    style.configure('Section.TLabel', font=('Helvetica', 11, 'bold'), foreground=ACCENT)
    style.configure('Muted.TLabel', font=('Helvetica', 10), foreground=MUTED)
    style.configure('Counter.TLabel', font=('Helvetica', 34, 'bold'), foreground=TEXT)
    style.configure('Caption.TLabel', font=('Helvetica', 9, 'bold'), foreground=MUTED)
    style.configure('Skip.TLabel', font=('Helvetica', 12), foreground=ACCENT)
    style.configure('Error.TLabel', font=('Helvetica', 10), foreground=DANGER)

    for widget in ('TCheckbutton', 'TRadiobutton'):
        style.configure(widget, background=BG, foreground=TEXT,
                        indicatorbackground=SURFACE, indicatorforeground=TEXT)
        style.map(widget,
                  background=[('active', BG)],
                  foreground=[('disabled', MUTED)],
                  indicatorbackground=[('selected', ACCENT), ('pressed', ACCENT)],
                  indicatorcolor=[('selected', ACCENT), ('!selected', SURFACE)])

    style.configure('TEntry', fieldbackground=SURFACE, foreground=TEXT,
                    insertcolor=TEXT, bordercolor=SURFACE_HI, relief='flat', padding=4)
    style.configure('TSeparator', background=SURFACE_HI)

    style.configure('Accent.TButton', background=ACCENT, foreground='#ffffff',
                    font=('Helvetica', 12, 'bold'), borderwidth=0, relief='flat',
                    padding=(10, 9), focuscolor='#ffffff')
    style.map('Accent.TButton',
              background=[('disabled', SURFACE), ('pressed', ACCENT_DIM), ('active', ACCENT_HI)],
              foreground=[('disabled', MUTED)])

    style.configure('Ghost.TButton', background=SURFACE, foreground=TEXT,
                    font=('Helvetica', 12, 'bold'), borderwidth=0, relief='flat',
                    padding=(10, 9), focuscolor=SURFACE)
    style.map('Ghost.TButton',
              background=[('disabled', BG), ('pressed', SURFACE), ('active', SURFACE_HI)],
              foreground=[('disabled', '#5a5a5e'), ('active', DANGER)])
    return style


class WannaTapThatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WannaTapThat")
        self.root.geometry("400x900")
        self.root.resizable(False, False)
        self.running = False

        # Dock icon is handled by the .app bundle (Info.plist / .icns).
        self._saved = load_settings()  # persisted opener + options
        self._config_widgets = []  # controls locked while a run is active

        self.build_ui()

    def build_ui(self):
        PAD = 22  # outer horizontal padding
        IND = PAD + 4  # indent for grouped controls

        # ---- Header ------------------------------------------------------
        header = ttk.Frame(self.root)
        header.pack(fill='x', pady=(22, 2))
        ttk.Label(header, text="WannaTapThat", style='Header.TLabel').pack()
        ttk.Label(header, text="Auto-liker with opener for Hinge",
                  style='Sub.TLabel').pack()

        # ---- Opener ------------------------------------------------------
        ttk.Label(self.root, text="YOUR OPENER", style='Section.TLabel').pack(
            anchor='w', padx=PAD, pady=(20, 6))

        self.opener_text = tk.Text(
            self.root, height=3, font=('Helvetica', 12), wrap='word',
            fg=MUTED, bg=SURFACE, insertbackground=TEXT, relief='flat',
            highlightthickness=1, highlightbackground=SURFACE_HI,
            highlightcolor=ACCENT, padx=8, pady=6,
        )
        self.opener_text.pack(padx=PAD, fill='x')
        self.placeholder = "Type your opener here..."
        self.opener_text.insert('1.0', self.placeholder)
        saved_opener = self._saved.get('opener', '')
        if saved_opener:
            self.opener_text.delete('1.0', 'end')
            self.opener_text.insert('1.0', saved_opener)
            self.opener_text.config(fg=TEXT)
        self.opener_text.bind('<FocusIn>', self._on_opener_focus_in)
        self.opener_text.bind('<FocusOut>', self._on_opener_focus_out)

        # ---- Options -----------------------------------------------------
        ttk.Label(self.root, text="OPTIONS", style='Section.TLabel').pack(
            anchor='w', padx=PAD, pady=(16, 4))

        s = self._saved
        self.randomize_var = tk.BooleanVar(value=s.get('randomize', False))
        self.skip_opener_var = tk.BooleanVar(value=s.get('skip_opener', False))
        self.verified_only_var = tk.BooleanVar(value=s.get('verified_only', False))
        self.browse_var = tk.BooleanVar(value=s.get('browse', False))
        self.debug_mode_var = tk.BooleanVar(value=s.get('debug', False))

        for text, var in [
            ("Randomize (separate openers with |)", self.randomize_var),
            ("Like only (skip opener)", self.skip_opener_var),
            ("Verified only (skip unverified)", self.verified_only_var),
            ("Browse profile before liking", self.browse_var),
            ("Debug mode (screenshots to /tmp/wtt_debug/)", self.debug_mode_var),
        ]:
            cb = ttk.Checkbutton(self.root, text=text, variable=var)
            cb.pack(anchor='w', padx=IND, pady=1)
            self._config_widgets.append(cb)

        # ---- Speed -------------------------------------------------------
        ttk.Separator(self.root).pack(fill='x', padx=PAD, pady=(14, 0))
        ttk.Label(self.root, text="SPEED", style='Section.TLabel').pack(
            anchor='w', padx=PAD, pady=(12, 4))

        self.speed_var = tk.StringVar(value=s.get('speed', 'normal'))
        for text, value in [
            ("Fast (2-3 sec between likes)", "fast"),
            ("Normal (3-5 sec)", "normal"),
            ("Slow (5-8 sec)", "slow"),
        ]:
            rb = ttk.Radiobutton(self.root, text=text, variable=self.speed_var,
                                 value=value)
            rb.pack(anchor='w', padx=IND, pady=1)
            self._config_widgets.append(rb)

        # ---- Stop after --------------------------------------------------
        ttk.Separator(self.root).pack(fill='x', padx=PAD, pady=(14, 0))
        ttk.Label(self.root, text="STOP AFTER", style='Section.TLabel').pack(
            anchor='w', padx=PAD, pady=(12, 4))

        self.stop_var = tk.StringVar(value=s.get('stop', '25'))
        for text, value in [("10 likes", "10"), ("25 likes", "25"), ("50 likes", "50")]:
            rb = ttk.Radiobutton(self.root, text=text, variable=self.stop_var,
                                 value=value)
            rb.pack(anchor='w', padx=IND, pady=1)
            self._config_widgets.append(rb)

        custom_frame = ttk.Frame(self.root)
        custom_frame.pack(anchor='w', padx=IND, pady=1)
        rb = ttk.Radiobutton(custom_frame, text="Custom:", variable=self.stop_var,
                             value="custom")
        rb.pack(side='left')
        self._config_widgets.append(rb)
        # Only allow digits in the custom-count field
        vcmd = (self.root.register(lambda p: p == '' or p.isdigit()), '%P')
        self.custom_count = ttk.Entry(custom_frame, width=6, validate='key',
                                      validatecommand=vcmd)
        self.custom_count.pack(side='left', padx=6)
        self.custom_count.insert(0, s.get('custom_count', '100') or '100')
        self._config_widgets.append(self.custom_count)

        rb = ttk.Radiobutton(self.root, text="Until I stop", variable=self.stop_var,
                             value="unlimited")
        rb.pack(anchor='w', padx=IND, pady=1)
        self._config_widgets.append(rb)

        # ---- Buttons -----------------------------------------------------
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=(20, 4))
        self.start_btn = ttk.Button(btn_frame, text="START", command=self.start,
                                    width=13, style='Accent.TButton')
        self.start_btn.grid(row=0, column=0, padx=8)
        self.stop_btn = ttk.Button(btn_frame, text="STOP", command=self.stop,
                                   width=13, style='Ghost.TButton', state='disabled')
        self.stop_btn.grid(row=0, column=1, padx=8)

        # ---- Status ------------------------------------------------------
        status_frame = ttk.Frame(self.root)
        status_frame.pack(pady=(8, 16))
        self.count_var = tk.StringVar(value="0")
        ttk.Label(status_frame, textvariable=self.count_var,
                  style='Counter.TLabel').pack()
        ttk.Label(status_frame, text="LIKES SENT", style='Caption.TLabel').pack()
        self.skipped_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self.skipped_var,
                  style='Skip.TLabel').pack(pady=(4, 0))
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                      style='Muted.TLabel')
        self.status_label.pack(pady=(2, 0))
        # Keep the idle counter's denominator in sync with the STOP AFTER choice
        self.stop_var.trace_add('write', lambda *_: self._sync_idle_counter())
        self.custom_count.bind('<KeyRelease>', lambda *_: self._sync_idle_counter())
        self._sync_idle_counter()

    def _on_opener_focus_in(self, event):
        """Clear placeholder when user clicks in opener field."""
        if self.opener_text.get('1.0', 'end').strip() == self.placeholder:
            self.opener_text.delete('1.0', 'end')
            self.opener_text.config(fg=TEXT)

    def _on_opener_focus_out(self, event):
        """Restore placeholder if field is empty."""
        if not self.opener_text.get('1.0', 'end').strip():
            self.opener_text.insert('1.0', self.placeholder)
            self.opener_text.config(fg=MUTED)

    def _sync_idle_counter(self):
        """Keep the big counter's denominator matching STOP AFTER while idle."""
        if self.running:
            return
        target = self.get_max_likes()
        self.count_var.set("0" if target < 0 else f"0 / {target}")

    def _set_config_state(self, state):
        """Enable/disable all run-config controls (locked during a run)."""
        for w in self._config_widgets:
            try:
                w.config(state=state)
            except tk.TclError:
                pass

    def save_settings(self):
        """Persist opener + options so they survive a relaunch."""
        opener = self.opener_text.get('1.0', 'end').strip()
        if opener == self.placeholder:
            opener = ''
        data = {
            'opener': opener,
            'randomize': self.randomize_var.get(),
            'skip_opener': self.skip_opener_var.get(),
            'verified_only': self.verified_only_var.get(),
            'browse': self.browse_var.get(),
            'debug': self.debug_mode_var.get(),
            'speed': self.speed_var.get(),
            'stop': self.stop_var.get(),
            'custom_count': self.custom_count.get().strip(),
        }
        try:
            with open(app_support_dir() / "settings.json", 'w') as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def get_opener(self) -> str:
        """Get opener text, randomized if enabled."""
        text = self.opener_text.get('1.0', 'end').strip()

        # Don't return placeholder as opener
        if text == self.placeholder:
            return ""

        if self.randomize_var.get() and '|' in text:
            openers = [o.strip() for o in text.split('|') if o.strip()]
            return random.choice(openers) if openers else text

        return text

    def get_delay(self) -> float:
        """Get delay based on speed setting."""
        speed = self.speed_var.get()
        delays = {
            'fast': (2, 3),
            'normal': (3, 5),
            'slow': (5, 8),
        }
        min_d, max_d = delays.get(speed, (3, 5))
        return random.uniform(min_d, max_d)

    def get_max_likes(self) -> int:
        """Get max likes, -1 for unlimited. Custom <= 0 / invalid falls back to 25."""
        stop = self.stop_var.get()
        if stop == 'unlimited':
            return -1
        if stop == 'custom':
            try:
                n = int(self.custom_count.get())
            except ValueError:
                return 25  # Fallback
            return n if n > 0 else 25  # never let <=0 reach the unlimited path
        return int(stop)

    def start(self):
        """Start the auto-liker."""
        try:
            from clicker import find_iphone_window, capture_window
        except ImportError as e:
            messagebox.showerror("Error", f"Failed to import clicker module:\n{e}")
            self.root.lift()
            self.root.focus_force()
            return

        # Validate opener (unless "Like only" is checked)
        if not self.skip_opener_var.get():
            opener = self.opener_text.get('1.0', 'end').strip()
            if not opener or opener == self.placeholder:
                messagebox.showerror("Error", "Please enter an opener message")
                self.root.lift()
                self.root.focus_force()
                return

        # Validate the custom stop count (must be a whole number > 0)
        if self.stop_var.get() == 'custom':
            raw = self.custom_count.get().strip()
            if not raw.isdigit() or int(raw) <= 0:
                messagebox.showerror(
                    "Invalid count",
                    "Custom stop count must be a whole number greater than 0."
                )
                self.root.lift()
                self.root.focus_force()
                return

        # Check for iPhone window
        window = find_iphone_window()
        if not window:
            messagebox.showerror(
                "iPhone Not Found",
                "Can't find iPhone Mirroring window.\n\n"
                "Make sure:\n"
                "1. iPhone Mirroring is open\n"
                "2. Screen Recording permission is granted\n\n"
                "Go to System Settings > Privacy & Security > Screen Recording"
            )
            self.root.lift()
            self.root.focus_force()
            return

        # Try to capture - this will fail if no Screen Recording permission
        try:
            test_capture = capture_window(window['id'])
            if test_capture is None:
                raise Exception("Capture returned None")
        except Exception:
            messagebox.showerror(
                "Permission Required",
                "Can't capture screen.\n\n"
                "Grant Screen Recording permission:\n"
                "System Settings > Privacy & Security > Screen Recording\n\n"
                "Then restart the app."
            )
            self.root.lift()
            self.root.focus_force()
            return

        self.save_settings()  # remember this configuration for next launch

        self.running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.opener_text.config(state='disabled')
        self._set_config_state('disabled')  # freeze config to match the running loop

        thread = threading.Thread(target=self.run_liker, daemon=True)
        thread.start()

    def stop(self):
        """Stop the auto-liker."""
        self.running = False
        self.stop_btn.config(state='disabled')  # acknowledge the click immediately
        self.status_var.set("Stopping...")

    def update_status(self, message, is_error=False):
        """Thread-safe status update; is_error renders it in the danger color."""
        style = 'Error.TLabel' if is_error else 'Muted.TLabel'

        def apply():
            self.status_var.set(message)
            self.status_label.configure(style=style)
        self.root.after(0, apply)

    def update_count(self, text):
        """Thread-safe count update."""
        self.root.after(0, lambda: self.count_var.set(text))

    def update_skipped(self, n):
        """Thread-safe skipped-count update (verified-only mode)."""
        text = f"Skipped {n} unverified" if n > 0 else ""
        self.root.after(0, lambda: self.skipped_var.set(text))

    def run_liker(self):
        """Main liker loop - runs in background thread."""
        global debug_logger

        from clicker import (
            find_iphone_window,
            capture_window,
            find_icon,
            click_at,
            scroll_at,
            type_text,
            human_type,
            random_delay,
            get_resource_path,
            press_return,
        )
        import os

        # Set up debug logging
        debug_logger.enabled = self.debug_mode_var.get()
        debug_logger.start_session()

        # Debug: log resource paths
        debug_logger.log("WannaTapThat Debug Info")
        debug_logger.log("=" * 50)
        for template in ['heart.png', 'add_comment.png', 'send_priority_like.png']:
            path = get_resource_path(template)
            exists = os.path.exists(path)
            debug_logger.log(f"  {template}: {path} -> {'EXISTS' if exists else 'MISSING'}")
        debug_logger.log("=" * 50)

        max_likes = self.get_max_likes()
        verified_only = self.verified_only_var.get()
        browse = self.browse_var.get()
        sent = 0
        skipped = 0  # unverified profiles skipped (verified-only mode)
        consecutive_skips = 0  # safety: bail if the whole deck is unverified
        consecutive_failures = 0
        capture_failures = 0
        max_failures = 5
        dot_cycle = 0
        typed_on_current_profile = False  # Track if we've already typed opener
        self.update_skipped(0)  # clear any count from a previous run

        if verified_only:
            debug_logger.log("Verified-only mode ON: unverified profiles will be skipped")

        while self.running:
            # Check if we've hit the limit
            if max_likes > 0 and sent >= max_likes:
                break

            # Too many failures in a row
            if consecutive_failures >= max_failures:
                self.update_status("Stopped: too many failures", is_error=True)
                break

            # If capture keeps failing, it's likely a permission issue - stop immediately
            if capture_failures >= 2:
                self.update_status("Screen Recording permission needed", is_error=True)
                break

            # Update display with animated dots
            count_text = f"{sent}" if max_likes < 0 else f"{sent} / {max_likes}"
            self.update_count(count_text)
            dots = "." * (dot_cycle % 3 + 1)
            self.update_status(f"Cooking{dots}")
            dot_cycle += 1

            try:
                debug_logger.new_attempt()
                debug_logger.log(f"Starting attempt (sent so far: {sent})")

                window = find_iphone_window()
                if not window:
                    debug_logger.log("FAIL: No iPhone window found")
                    self.update_status("Lost iPhone Mirroring window!", is_error=True)
                    consecutive_failures += 1
                    time.sleep(1)
                    continue

                debug_logger.log(f"Window found: {window['owner']} (id={window['id']})")

                image = capture_window(window["id"])
                if image is None:
                    debug_logger.log("FAIL: Could not capture window (permission issue?)")
                    self.update_status("Capture failed", is_error=True)
                    consecutive_failures += 1
                    capture_failures += 1
                    time.sleep(0.5)
                    continue

                debug_logger.log(f"Captured window: {image.size}")
                debug_logger.save_screenshot(image, "01_initial_capture")

                # 1. Find and click topmost heart (with retry)
                debug_logger.log("Searching for heart...")
                heart_threshold = 0.65  # Back to 0.65 - 0.60 caused false positives
                send_threshold = 0.60   # Lowered from 0.65 - was getting 0.645 misses
                # Heart button is always on the RIGHT side and LOWER portion of screen
                # This prevents false positives from top dropdowns (Dating Intentions, etc.)
                # and left-side UI elements. Pass constraints directly to find_icon.
                min_heart_x = 400   # Right side only (image coords)
                min_heart_y = 400   # Lower portion only - avoids top dropdowns/filters
                heart_pos = None
                for heart_retry in range(3):
                    # Pass min_x/min_y to filter at search level, not after
                    candidate = find_icon(image, "heart.png", threshold=heart_threshold, topmost=True,
                                         min_x=min_heart_x, min_y=min_heart_y)
                    if candidate:
                        heart_pos = candidate
                        debug_logger.log_match_result(f"heart.png (try {heart_retry+1})", heart_pos, heart_threshold)
                        break
                    else:
                        # Get best match anywhere for debugging
                        best_heart = find_icon(image, "heart.png", threshold=heart_threshold, topmost=True, return_best_match=True)
                        debug_logger.log_match_result(f"heart.png (try {heart_retry+1})", None, heart_threshold, best_match=best_heart)
                    if heart_retry < 2:
                        debug_logger.log(f"Heart retry {heart_retry+1} - recapturing...")
                        time.sleep(0.3)
                        image = capture_window(window["id"])
                        if image is None:
                            debug_logger.log("Capture failed during heart retry")
                            break

                # Send button must be in lower portion of screen (not top dropdowns)
                min_send_y = 800

                if not heart_pos:
                    debug_logger.save_screenshot(image, "02_heart_not_found")
                    # No heart - maybe comment box is already open?
                    if not self.skip_opener_var.get():
                        # Check if send button is visible (we already typed)
                        send_recovery = find_icon(image, "send_priority_like.png", threshold=0.60)
                        if send_recovery and send_recovery[1] >= min_send_y and typed_on_current_profile:
                            debug_logger.log("No heart but send found - clicking send (already typed)")
                            click_at(send_recovery[0], send_recovery[1], window)
                            sent += 1
                            consecutive_failures = 0
                            typed_on_current_profile = False  # Reset for next profile
                            debug_logger.log(f"SUCCESS (send recovery)! Total: {sent}")
                            self.update_status("Waiting...")
                            continue
                        elif send_recovery and send_recovery[1] < min_send_y:
                            debug_logger.log(f"  send.png (recovery): REJECTED - y={send_recovery[1]} < {min_send_y} (top area false positive)")

                        textbox_recovery = find_icon(image, "add_comment.png", threshold=0.35)
                        debug_logger.log_match_result("textbox.png (recovery)", textbox_recovery, 0.35)
                        if textbox_recovery and not typed_on_current_profile:
                            debug_logger.log("No heart but textbox found - attempting recovery")
                            self.update_status("Typing...")
                            click_at(textbox_recovery[0], textbox_recovery[1], window)
                            random_delay(0.3, 0.5, should_stop=lambda: not self.running)

                            opener = self.get_opener()
                            debug_logger.log(f"Typing opener: {opener[:50]}...")
                            typing_completed = human_type(opener, should_stop=lambda: not self.running)
                            if not typing_completed:
                                debug_logger.log("Typing interrupted by stop")
                                break
                            typed_on_current_profile = True  # Mark that we've typed

                            # Press Done to dismiss keyboard
                            debug_logger.log("Pressing Done to dismiss keyboard")
                            press_return()
                            random_delay(0.5, 0.8, should_stop=lambda: not self.running)

                            image = capture_window(window["id"])
                            debug_logger.save_screenshot(image, "recovery_after_typing")
                            send_pos = find_icon(image, "send_priority_like.png", threshold=0.60)
                            debug_logger.log_match_result("send.png (recovery)", send_pos, 0.60)
                            if send_pos and send_pos[1] >= min_send_y:
                                click_at(send_pos[0], send_pos[1], window)
                                sent += 1
                                consecutive_failures = 0
                                typed_on_current_profile = False  # Reset for next profile
                                debug_logger.log(f"SUCCESS (recovered)! Total: {sent}")
                                self.update_status("Waiting...")
                                continue
                            elif send_pos and send_pos[1] < min_send_y:
                                debug_logger.log(f"  send.png: REJECTED - y={send_pos[1]} < {min_send_y} (top area false positive)")
                        elif textbox_recovery and typed_on_current_profile:
                            debug_logger.log("Textbox found but already typed - skipping re-type, looking for send")
                            # Already typed, just need to find send
                            image = capture_window(window["id"])
                            send_pos = find_icon(image, "send_priority_like.png", threshold=0.60)
                            if send_pos and send_pos[1] >= min_send_y:
                                click_at(send_pos[0], send_pos[1], window)
                                sent += 1
                                consecutive_failures = 0
                                typed_on_current_profile = False
                                debug_logger.log(f"SUCCESS (skipped re-type)! Total: {sent}")
                                self.update_status("Waiting...")
                                continue
                            elif send_pos and send_pos[1] < min_send_y:
                                debug_logger.log(f"  send.png: REJECTED - y={send_pos[1]} < {min_send_y} (top area false positive)")

                    debug_logger.log("FAIL: Heart not found, no recovery possible")
                    self.update_status("No heart found", is_error=True)
                    consecutive_failures += 1
                    time.sleep(1)
                    continue
                # Verified-only gate: heart found means we're on a profile, so
                # check for the verified badge before liking. If absent, tap the
                # X (skip) button and move on instead.
                if verified_only:
                    is_verified, v_conf = is_profile_verified(image, find_icon)
                    if is_verified:
                        debug_logger.log(f"Verified badge found (conf={v_conf:.3f}) - liking")
                        consecutive_skips = 0
                    else:
                        debug_logger.log(f"No verified badge (best conf={v_conf:.3f} < "
                                         f"{VERIFIED_THRESHOLD}) - skipping profile")
                        skip_pos = find_icon(image, "skip.png", threshold=SKIP_THRESHOLD,
                                             min_y=int(image.size[1] * 0.80))
                        if not skip_pos:
                            best_skip = find_icon(image, "skip.png", threshold=SKIP_THRESHOLD,
                                                  min_y=int(image.size[1] * 0.80),
                                                  return_best_match=True)
                            debug_logger.log_match_result("skip.png", None, SKIP_THRESHOLD,
                                                          best_match=best_skip)
                            debug_logger.save_screenshot(image, "skip_button_not_found")
                            self.update_status("Skip button not found", is_error=True)
                            consecutive_failures += 1
                            time.sleep(1)
                            continue
                        sox = random.randint(-15, 15)
                        soy = random.randint(-15, 15)
                        click_at(skip_pos[0] + sox, skip_pos[1] + soy, window)
                        skipped += 1
                        consecutive_skips += 1
                        consecutive_failures = 0
                        typed_on_current_profile = False
                        debug_logger.log(f"Skipped unverified profile. Total skipped: {skipped}")
                        self.update_status("Skipped unverified")
                        self.update_skipped(skipped)
                        if consecutive_skips >= MAX_CONSECUTIVE_SKIPS:
                            self.update_status(f"Stopped: {consecutive_skips} unverified in a row")
                            debug_logger.log("Hit consecutive-skip safety cap - stopping")
                            break
                        # Brief wait for the next profile to load, then re-loop
                        random_delay(0.8, 1.5, should_stop=lambda: not self.running)
                        continue

                # Browse: scroll down to "read" the profile, then over-scroll back
                # to the top (iOS rubber-bands, so we land at the exact top again)
                # before liking the first heart. Only runs on profiles we'll like
                # (verified gate above already skipped unverified ones).
                if browse:
                    self.update_status("Browsing...")
                    bcx = image.size[0] // 2
                    bcy = int(image.size[1] * 0.45)
                    down = -random.randint(260, 420)
                    debug_logger.log(f"Browse: scrolling down ({down}) to view profile")
                    scroll_at(bcx, bcy, amount=down, window=window)
                    if not random_delay(1.0, 2.0, should_stop=lambda: not self.running):
                        break
                    # Over-scroll up past the top to guarantee we're back at the start
                    scroll_at(bcx, bcy, amount=abs(down) + 400, window=window)
                    if not random_delay(0.4, 0.7, should_stop=lambda: not self.running):
                        break

                    # Re-find the heart at the (now top) position with retries
                    image = capture_window(window["id"])
                    if image is None:
                        debug_logger.log("Browse: capture failed after scroll-back")
                        consecutive_failures += 1
                        continue
                    debug_logger.save_screenshot(image, "browse_back_at_top")
                    heart_pos = None
                    for _ in range(3):
                        cand = find_icon(image, "heart.png", threshold=heart_threshold,
                                         topmost=True, min_x=min_heart_x, min_y=min_heart_y)
                        if cand:
                            heart_pos = cand
                            break
                        time.sleep(0.3)
                        image = capture_window(window["id"])
                        if image is None:
                            break
                    if not heart_pos:
                        debug_logger.log("Browse: heart not found after scroll-back - skipping like")
                        self.update_status("No heart after browse", is_error=True)
                        consecutive_failures += 1
                        time.sleep(1)
                        continue
                    debug_logger.log(f"Browse complete; heart at ({heart_pos[0]}, {heart_pos[1]})")

                # Random offset in image coords (retina 2x, so /2 for screen px)
                offset_x = random.randint(-20, 20)
                offset_y = random.randint(-8, 8)
                click_at(heart_pos[0] + offset_x, heart_pos[1] + offset_y, window)
                debug_logger.log(f"Clicked heart at ({heart_pos[0]}, {heart_pos[1]})")

                # If "Like only" mode, skip typing but still click send
                if self.skip_opener_var.get():
                    debug_logger.log("Like-only mode - skipping opener")
                    random_delay(0.5, 0.9, should_stop=lambda: not self.running)

                    # Capture screen to find send button
                    image = capture_window(window["id"])
                    if image is None:
                        debug_logger.log("FAIL: Could not capture after heart click")
                        consecutive_failures += 1
                        continue

                    debug_logger.save_screenshot(image, "03_after_heart_click_likeonly")
                    send_pos = find_icon(image, "send_priority_like.png", threshold=0.60)
                    best_send = find_icon(image, "send_priority_like.png", threshold=0.60, return_best_match=True) if not send_pos else None
                    debug_logger.log_match_result("send.png (like only)", send_pos, 0.60, best_match=best_send)

                    if send_pos and send_pos[1] >= min_send_y:
                        random_delay(0.2, 0.4, should_stop=lambda: not self.running)
                        offset_x = random.randint(-30, 30)
                        offset_y = random.randint(-8, 8)
                        click_at(send_pos[0] + offset_x, send_pos[1] + offset_y, window)
                        sent += 1
                        consecutive_failures = 0
                        typed_on_current_profile = False  # Reset for next profile
                        debug_logger.log(f"SUCCESS (like only)! Total sent: {sent}")
                        self.update_status("Waiting...")
                    elif send_pos and send_pos[1] < min_send_y:
                        debug_logger.log(f"  send.png (like only): REJECTED - y={send_pos[1]} < {min_send_y} (top area false positive)")
                        debug_logger.save_screenshot(image, "04_send_rejected_likeonly")
                        self.update_status("Send in wrong area")
                        consecutive_failures += 1
                    else:
                        debug_logger.log("FAIL: Send button not found (like only)")
                        debug_logger.save_screenshot(image, "04_send_not_found_likeonly")
                        self.update_status("Send not found")
                        consecutive_failures += 1
                else:
                    # Type opener mode - wait for comment box to fully appear
                    debug_logger.log("Opener mode - waiting for comment box")
                    random_delay(0.8, 1.2, should_stop=lambda: not self.running)

                    # 2. Find text input and type opener
                    image = capture_window(window["id"])
                    if image is None:
                        debug_logger.log("FAIL: Could not capture after heart click")
                        consecutive_failures += 1
                        continue

                    debug_logger.save_screenshot(image, "03_after_heart_click")

                    # Try to find textbox with retries
                    textbox_pos = None
                    for retry in range(3):
                        textbox_pos = find_icon(image, "add_comment.png", threshold=0.35)
                        debug_logger.log_match_result(f"textbox.png (try {retry+1})", textbox_pos, 0.35)
                        if textbox_pos:
                            break
                        # Wait and recapture
                        debug_logger.log(f"Textbox retry {retry+1} - recapturing...")
                        time.sleep(0.5)
                        image = capture_window(window["id"])
                        if image is None:
                            debug_logger.log("FAIL: Capture failed during textbox retry")
                            break
                        debug_logger.save_screenshot(image, f"03b_textbox_retry_{retry+1}")

                    if not textbox_pos:
                        debug_logger.log("FAIL: Textbox not found after all retries")
                        debug_logger.save_screenshot(image, "04_textbox_not_found")

                    if textbox_pos:
                        offset_x = random.randint(-30, 30)
                        offset_y = random.randint(-8, 8)
                        click_at(textbox_pos[0] + offset_x, textbox_pos[1] + offset_y, window)
                        debug_logger.log(f"Clicked textbox at ({textbox_pos[0]}, {textbox_pos[1]})")
                        random_delay(0.3, 0.6, should_stop=lambda: not self.running)

                        opener = self.get_opener()
                        debug_logger.log(f"Typing opener: {opener[:50]}...")
                        self.update_status("Typing...")
                        typing_completed = human_type(opener, should_stop=lambda: not self.running)
                        if not typing_completed:
                            debug_logger.log("Typing interrupted by stop")
                            break
                        typed_on_current_profile = True  # Mark that we've typed
                        debug_logger.log("Typing completed")

                        # 3. Press Done to dismiss keyboard
                        debug_logger.log("Pressing Done to dismiss keyboard")
                        press_return()
                        random_delay(0.5, 0.8, should_stop=lambda: not self.running)

                        # 4. Find and click Send Priority Like
                        image = capture_window(window["id"])
                        if image is None:
                            debug_logger.log("FAIL: Could not capture after typing")
                            consecutive_failures += 1
                            continue

                        debug_logger.save_screenshot(image, "05_after_typing")
                        send_pos = find_icon(image, "send_priority_like.png", threshold=0.60)
                        best_send = find_icon(image, "send_priority_like.png", threshold=0.60, return_best_match=True) if not send_pos else None
                        debug_logger.log_match_result("send_priority_like.png", send_pos, 0.60, best_match=best_send)

                        if send_pos and send_pos[1] >= min_send_y:
                            random_delay(0.2, 0.5, should_stop=lambda: not self.running)
                            offset_x = random.randint(-30, 30)
                            offset_y = random.randint(-8, 8)
                            click_at(send_pos[0] + offset_x, send_pos[1] + offset_y, window)
                            sent += 1
                            consecutive_failures = 0
                            typed_on_current_profile = False  # Reset for next profile
                            debug_logger.log(f"SUCCESS! Total sent: {sent}")
                            self.update_status("Waiting...")
                        elif send_pos and send_pos[1] < min_send_y:
                            debug_logger.log(f"  send.png: REJECTED - y={send_pos[1]} < {min_send_y} (top area false positive)")
                            debug_logger.save_screenshot(image, "06_send_rejected")
                            self.update_status("Send in wrong area")
                            consecutive_failures += 1
                        else:
                            debug_logger.log("FAIL: Send button not found (will retry)")
                            debug_logger.save_screenshot(image, "06_send_not_found")
                            self.update_status("Send failed - retrying...")
                            # Don't increment consecutive_failures heavily - we might find it next loop
                            consecutive_failures += 1
                    else:
                        debug_logger.log("FAIL: Textbox not found - cannot type opener")
                        self.update_status("No textbox")
                        consecutive_failures += 1

                # 4. Wait before next
                delay = self.get_delay()
                for i in range(int(delay * 10)):
                    if not self.running:
                        break
                    time.sleep(0.1)

            except FileNotFoundError as e:
                debug_logger.log(f"ERROR: Missing template: {e}")
                self.update_status(f"Missing template: {e}", is_error=True)
                consecutive_failures += 1
                time.sleep(2)
            except Exception as e:
                debug_logger.log(f"ERROR: Exception: {e}")
                import traceback
                debug_logger.log(traceback.format_exc())
                self.update_status(f"Error: {str(e)[:50]}", is_error=True)
                consecutive_failures += 1
                time.sleep(1)

        # End debug session
        debug_logger.log(f"Session complete. Total sent: {sent}")
        debug_logger.end_session()

        # Done - update UI from main thread
        def finish():
            count_text = f"{sent}" if max_likes < 0 else f"{sent} / {max_likes}"
            self.count_var.set(count_text)
            self.skipped_var.set(f"Skipped {skipped} unverified" if skipped > 0 else "")
            self.status_var.set("Done!")
            self.status_label.configure(style='Muted.TLabel')
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.opener_text.config(state='normal')
            self._set_config_state('normal')  # unlock config controls
            self.running = False

        self.root.after(0, finish)


def main():
    if '--version' in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        print(f"  Python: {platform.python_version()} ({sys.executable})")
        print(f"  Frozen: {getattr(sys, 'frozen', False)}")
        print(f"  argv: {sys.argv}")
        return

    if '--diagnostics' in sys.argv:
        try:
            from clicker import find_iphone_window, capture_window
            run_permission_check(find_iphone_window, capture_window)
        except Exception as exc:
            print(f"Diagnostics failed: {exc}")
            raise SystemExit(1)
        return

    # Only one copy may drive iPhone Mirroring at a time
    instance_lock = acquire_single_instance_lock()
    if instance_lock is None:
        warn = tk.Tk()
        warn.withdraw()
        messagebox.showerror(
            APP_NAME,
            f"{APP_NAME} is already running.\n\n"
            "Only one copy can control iPhone Mirroring at a time."
        )
        warn.destroy()
        return

    root = tk.Tk()
    setup_theme(root)  # dark + purple theme (must run before building widgets)

    app = WannaTapThatApp(root)

    # Surface uncaught callback exceptions instead of swallowing them to stderr
    # (a bundled .app has no visible console).
    def report_exc(exc, val, tb):
        import traceback
        traceback.print_exception(exc, val, tb)
        try:
            messagebox.showerror(APP_NAME, f"Unexpected error:\n{val}")
        except Exception:
            pass
    root.report_callback_exception = report_exc

    # Handle window close (and Cmd-Q, which otherwise bypasses this guard)
    def on_closing():
        if app.running:
            if messagebox.askokcancel("Quit", "Liker is running. Stop and quit?"):
                app.running = False
                app.save_settings()
                root.after(500, root.destroy)
        else:
            app.save_settings()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    try:
        root.createcommand('tk::mac::Quit', on_closing)  # macOS Cmd-Q / dock Quit
    except tk.TclError:
        pass
    root.mainloop()
    # keep a reference so the lock file handle isn't GC'd before mainloop ends
    del instance_lock


if __name__ == '__main__':
    main()
