"""WannaTapThat - Auto-liker with opener for Hinge via iPhone Mirroring."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import random
import subprocess


class WannaTapThatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WannaTapThat")
        self.root.geometry("400x720")
        self.root.resizable(False, False)
        self.running = False

        # Set app icon if available
        try:
            # On macOS, the dock icon is handled by the app bundle
            pass
        except Exception:
            pass

        self.build_ui()

    def build_ui(self):
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill='x', pady=(20, 5))

        ttk.Label(
            header_frame,
            text="WannaTapThat",
            font=('Helvetica', 24, 'bold')
        ).pack()

        ttk.Label(
            header_frame,
            text="Auto-liker with opener for Hinge",
            font=('Helvetica', 10),
            foreground='gray'
        ).pack()

        # Opener section
        ttk.Label(
            self.root,
            text="Your Opener:",
            font=('Helvetica', 11, 'bold')
        ).pack(anchor='w', padx=20, pady=(20, 5))

        self.opener_text = tk.Text(
            self.root,
            height=3,
            width=45,
            font=('Helvetica', 11),
            wrap='word',
            fg='#888888',
            bg='white',
            insertbackground='black'
        )
        self.opener_text.pack(padx=20)
        self.placeholder = "Type your opener here..."
        self.opener_text.insert('1.0', self.placeholder)
        self.opener_text.bind('<FocusIn>', self._on_opener_focus_in)
        self.opener_text.bind('<FocusOut>', self._on_opener_focus_out)

        # Randomize checkbox
        self.randomize_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.root,
            text="Randomize (separate openers with |)",
            variable=self.randomize_var
        ).pack(anchor='w', padx=20, pady=(5, 0))

        # Like only checkbox (skip opener)
        self.skip_opener_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.root,
            text="Like only (skip opener)",
            variable=self.skip_opener_var
        ).pack(anchor='w', padx=20, pady=(0, 5))

        # Separator
        ttk.Separator(self.root).pack(fill='x', padx=20, pady=10)

        # Speed section
        ttk.Label(
            self.root,
            text="Speed:",
            font=('Helvetica', 11, 'bold')
        ).pack(anchor='w', padx=20)

        self.speed_var = tk.StringVar(value="normal")
        speeds = [
            ("Fast (2-3 sec between likes)", "fast"),
            ("Normal (3-5 sec)", "normal"),
            ("Slow (5-8 sec)", "slow")
        ]

        for text, value in speeds:
            ttk.Radiobutton(
                self.root,
                text=text,
                variable=self.speed_var,
                value=value
            ).pack(anchor='w', padx=40)

        # Separator
        ttk.Separator(self.root).pack(fill='x', padx=20, pady=15)

        # Stop after section
        ttk.Label(
            self.root,
            text="Stop after:",
            font=('Helvetica', 11, 'bold')
        ).pack(anchor='w', padx=20)

        self.stop_var = tk.StringVar(value="25")

        # Radio buttons for preset counts
        for text, value in [("10 likes", "10"), ("25 likes", "25"), ("50 likes", "50")]:
            ttk.Radiobutton(
                self.root,
                text=text,
                variable=self.stop_var,
                value=value
            ).pack(anchor='w', padx=40)

        # Custom count option
        custom_frame = ttk.Frame(self.root)
        custom_frame.pack(anchor='w', padx=40, pady=2)

        ttk.Radiobutton(
            custom_frame,
            text="Custom:",
            variable=self.stop_var,
            value="custom"
        ).pack(side='left')

        self.custom_count = ttk.Entry(custom_frame, width=6)
        self.custom_count.pack(side='left', padx=5)
        self.custom_count.insert(0, "100")

        # Unlimited option
        ttk.Radiobutton(
            self.root,
            text="Until I stop",
            variable=self.stop_var,
            value="unlimited"
        ).pack(anchor='w', padx=40)

        # Separator
        ttk.Separator(self.root).pack(fill='x', padx=20, pady=15)

        # Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=20)

        self.start_btn = ttk.Button(
            btn_frame,
            text="START",
            command=self.start,
            width=15
        )
        self.start_btn.grid(row=0, column=0, padx=10)

        self.stop_btn = ttk.Button(
            btn_frame,
            text="STOP",
            command=self.stop,
            width=15,
            state='disabled'
        )
        self.stop_btn.grid(row=0, column=1, padx=10)

        # Status section
        ttk.Separator(self.root).pack(fill='x', padx=20, pady=10)

        status_frame = ttk.Frame(self.root)
        status_frame.pack(pady=10)

        # Big counter
        self.count_var = tk.StringVar(value="0")
        ttk.Label(
            status_frame,
            textvariable=self.count_var,
            font=('Helvetica', 32, 'bold')
        ).pack()

        # Small status below
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=('Helvetica', 10),
            foreground='gray'
        ).pack(pady=(3, 15))

    def _on_opener_focus_in(self, event):
        """Clear placeholder when user clicks in opener field."""
        if self.opener_text.get('1.0', 'end').strip() == self.placeholder:
            self.opener_text.delete('1.0', 'end')
            self.opener_text.config(fg='black', bg='white')

    def _on_opener_focus_out(self, event):
        """Restore placeholder if field is empty."""
        if not self.opener_text.get('1.0', 'end').strip():
            self.opener_text.insert('1.0', self.placeholder)
            self.opener_text.config(fg='#888888', bg='white')

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
        """Get max likes, -1 for unlimited."""
        stop = self.stop_var.get()
        if stop == 'unlimited':
            return -1
        if stop == 'custom':
            try:
                return int(self.custom_count.get())
            except ValueError:
                return 25  # Fallback
        return int(stop)

    def start(self):
        """Start the auto-liker."""
        # Validate opener (unless "Like only" is checked)
        if not self.skip_opener_var.get():
            opener = self.opener_text.get('1.0', 'end').strip()
            if not opener or opener == self.placeholder:
                messagebox.showerror("Error", "Please enter an opener message")
                self.root.lift()
                self.root.focus_force()
                return

        # Check iPhone window
        try:
            from clicker import find_iphone_window
            window = find_iphone_window()
        except ImportError as e:
            messagebox.showerror(
                "Error",
                f"Failed to import clicker module:\n{e}"
            )
            self.root.lift()
            self.root.focus_force()
            return
        except Exception as e:
            # Catch permission errors or other issues
            messagebox.showerror(
                "Permission Required",
                "Screen Recording permission is required.\n\n"
                "Go to System Settings > Privacy & Security > Screen Recording\n"
                "and enable WannaTapThat, then try again."
            )
            self.root.lift()
            self.root.focus_force()
            return

        if not window:
            messagebox.showerror(
                "iPhone Mirroring Not Found",
                "Cannot find iPhone Mirroring window!\n\n"
                "Make sure:\n"
                "1. iPhone Mirroring app is open\n"
                "2. Your iPhone is connected\n"
                "3. Hinge is visible on screen\n\n"
                "If you just granted Screen Recording permission,\n"
                "you may need to restart the app."
            )
            self.root.lift()
            self.root.focus_force()
            return

        self.running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.opener_text.config(state='disabled')

        thread = threading.Thread(target=self.run_liker, daemon=True)
        thread.start()

    def stop(self):
        """Stop the auto-liker."""
        self.running = False
        self.status_var.set("Stopping...")

    def update_status(self, message):
        """Thread-safe status update."""
        self.root.after(0, lambda: self.status_var.set(message))

    def update_count(self, text):
        """Thread-safe count update."""
        self.root.after(0, lambda: self.count_var.set(text))

    def run_liker(self):
        """Main liker loop - runs in background thread."""
        from clicker import (
            find_iphone_window,
            capture_window,
            find_icon,
            click_at,
            type_text,
            human_type,
            random_delay,
            get_resource_path
        )
        import os

        # Debug: log resource paths
        print("=" * 50)
        print("WannaTapThat Debug Info")
        print("=" * 50)
        for template in ['heart.png', 'textbox.png', 'send.png']:
            path = get_resource_path(template)
            exists = os.path.exists(path)
            print(f"  {template}: {path}")
            print(f"    -> {'EXISTS' if exists else 'MISSING'}")
        print("=" * 50)

        max_likes = self.get_max_likes()
        sent = 0
        consecutive_failures = 0
        max_failures = 10
        dot_cycle = 0

        while self.running:
            # Check if we've hit the limit
            if max_likes > 0 and sent >= max_likes:
                break

            # Too many failures in a row
            if consecutive_failures >= max_failures:
                self.update_status(f"Stopped: {max_failures} failures in a row")
                break

            # Update display with animated dots
            count_text = f"{sent}" if max_likes < 0 else f"{sent} / {max_likes}"
            self.update_count(count_text)
            dots = "." * (dot_cycle % 3 + 1)
            self.update_status(f"Cooking{dots}")
            dot_cycle += 1

            try:
                print(f"\n[Attempt {sent+1}] Starting...")

                window = find_iphone_window()
                if not window:
                    print("  FAIL: No iPhone window found")
                    self.update_status("Lost iPhone Mirroring window!")
                    consecutive_failures += 1
                    time.sleep(1)
                    continue

                print(f"  Window found: {window['owner']}")

                image = capture_window(window["id"])
                if image is None:
                    print("  FAIL: Could not capture window")
                    self.update_status("Failed to capture window")
                    consecutive_failures += 1
                    time.sleep(1)
                    continue

                print(f"  Captured: {image.size}")

                # 1. Find and click topmost heart
                heart_pos = find_icon(image, "heart.png", threshold=0.65, topmost=True)
                print(f"  Heart search: {heart_pos}")

                if not heart_pos:
                    # No heart - maybe comment box is already open?
                    if not self.skip_opener_var.get():
                        textbox_recovery = find_icon(image, "textbox.png", threshold=0.45)
                        if textbox_recovery:
                            print("  No heart but textbox found - recovering...")
                            self.update_status("Typing...")
                            click_at(textbox_recovery[0], textbox_recovery[1], window)
                            random_delay(0.3, 0.5, should_stop=lambda: not self.running)

                            opener = self.get_opener()
                            typing_completed = human_type(opener, should_stop=lambda: not self.running)
                            if not typing_completed:
                                break
                            random_delay(0.3, 0.5, should_stop=lambda: not self.running)

                            image = capture_window(window["id"])
                            send_pos = find_icon(image, "send.png", threshold=0.65)
                            if send_pos:
                                click_at(send_pos[0], send_pos[1], window)
                                sent += 1
                                consecutive_failures = 0
                                print(f"  SUCCESS (recovered)! Total: {sent}")
                                self.update_status("Waiting...")
                                continue

                    print("  FAIL: Heart not found")
                    self.update_status("No heart found")
                    consecutive_failures += 1
                    time.sleep(1)
                    continue
                # Add small random offset to click position (more human-like)
                offset_x = random.randint(-5, 5)
                offset_y = random.randint(-5, 5)
                click_at(heart_pos[0] + offset_x, heart_pos[1] + offset_y, window)
                print(f"  Clicked heart at ({heart_pos[0]}, {heart_pos[1]})")

                # If "Like only" mode, skip typing but still click send
                if self.skip_opener_var.get():
                    random_delay(0.5, 0.9, should_stop=lambda: not self.running)

                    # Capture screen to find send button
                    image = capture_window(window["id"])
                    if image is None:
                        print("  FAIL: Could not capture after heart click")
                        consecutive_failures += 1
                        continue

                    send_pos = find_icon(image, "send.png", threshold=0.65)
                    print(f"  Send search (like only): {send_pos}")

                    if send_pos:
                        random_delay(0.2, 0.4, should_stop=lambda: not self.running)
                        offset_x = random.randint(-3, 3)
                        offset_y = random.randint(-3, 3)
                        click_at(send_pos[0] + offset_x, send_pos[1] + offset_y, window)
                        sent += 1
                        consecutive_failures = 0
                        print(f"  SUCCESS (like only)! Total sent: {sent}")
                        self.update_status("Waiting...")
                    else:
                        print("  FAIL: Send button not found (like only)")
                        self.update_status("Send not found")
                        consecutive_failures += 1
                else:
                    # Type opener mode
                    random_delay(0.5, 0.9, should_stop=lambda: not self.running)

                    # 2. Find text input and type opener
                    image = capture_window(window["id"])
                    if image is None:
                        print("  FAIL: Could not capture after heart click")
                        consecutive_failures += 1
                        continue

                    textbox_pos = find_icon(image, "textbox.png", threshold=0.45)
                    print(f"  Textbox search: {textbox_pos}")

                    if textbox_pos:
                        offset_x = random.randint(-3, 3)
                        offset_y = random.randint(-3, 3)
                        click_at(textbox_pos[0] + offset_x, textbox_pos[1] + offset_y, window)
                        print(f"  Clicked textbox at ({textbox_pos[0]}, {textbox_pos[1]})")
                        random_delay(0.3, 0.6, should_stop=lambda: not self.running)

                        opener = self.get_opener()
                        self.update_status("Typing...")
                        typing_completed = human_type(opener, should_stop=lambda: not self.running)
                        if not typing_completed:
                            print("  Typing interrupted by stop")
                            break
                        print(f"  Typed: {opener[:30]}...")
                        random_delay(0.3, 0.7, should_stop=lambda: not self.running)

                        # 3. Find and click send
                        image = capture_window(window["id"])
                        if image is None:
                            print("  FAIL: Could not capture after typing")
                            consecutive_failures += 1
                            continue

                        send_pos = find_icon(image, "send.png", threshold=0.65)
                        print(f"  Send search: {send_pos}")

                        if send_pos:
                            random_delay(0.2, 0.5, should_stop=lambda: not self.running)
                            offset_x = random.randint(-3, 3)
                            offset_y = random.randint(-3, 3)
                            click_at(send_pos[0] + offset_x, send_pos[1] + offset_y, window)
                            sent += 1
                            consecutive_failures = 0
                            print(f"  SUCCESS! Total sent: {sent}")
                            self.update_status("Waiting...")
                        else:
                            print("  FAIL: Send button not found")
                            self.update_status("Send failed")
                            consecutive_failures += 1
                    else:
                        print("  FAIL: Textbox not found")
                        self.update_status("No textbox")
                        consecutive_failures += 1

                # 4. Wait before next
                delay = self.get_delay()
                for i in range(int(delay * 10)):
                    if not self.running:
                        break
                    time.sleep(0.1)

            except FileNotFoundError as e:
                self.update_status(f"Missing template: {e}")
                consecutive_failures += 1
                time.sleep(2)
            except Exception as e:
                self.update_status(f"Error: {str(e)[:50]}")
                consecutive_failures += 1
                time.sleep(1)

        # Done - update UI from main thread
        def finish():
            count_text = f"{sent}" if max_likes < 0 else f"{sent} / {max_likes}"
            self.count_var.set(count_text)
            self.status_var.set("Done!")
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.opener_text.config(state='normal')
            self.running = False

        self.root.after(0, finish)


def main():
    root = tk.Tk()

    # Set a nice style
    style = ttk.Style()
    if 'aqua' in style.theme_names():
        style.theme_use('aqua')  # macOS native look

    app = WannaTapThatApp(root)

    # Handle window close
    def on_closing():
        if app.running:
            if messagebox.askokcancel("Quit", "Liker is running. Stop and quit?"):
                app.running = False
                root.after(500, root.destroy)
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()
