## WannaTapThat v1.0.0

A macOS app that automates "liking" profiles on Hinge by driving **iPhone Mirroring** and matching the on-screen UI with OpenCV. It finds the heart button, taps it, types your opener with human-like timing, sends, and moves on with randomized delays.

### Highlights
- Custom opener, with optional randomization across variants (separate with `|`)
- **Like only** mode — skip the opener and just like
- **Verified only** mode — only like profiles showing Hinge's verified badge; automatically X-skips the rest
- **Browse profile before liking** — scrolls through and pauses as if reading, for more human-like behavior
- Speed presets (Fast / Normal / Slow) + inter-profile delay randomization
- Stop after 10 / 25 / 50 / a custom count, or run until you stop
- Live likes-sent counter, skipped-unverified counter, and status
- Settings persist across launches; single-instance lock
- Debug mode (saves screenshots + logs to `/tmp/wtt_debug/`)

### Requirements
- macOS 15 (Sequoia) or later, with **iPhone Mirroring** set up
- An iPhone signed into Hinge
- **Screen Recording** and **Accessibility** permissions granted to the app (System Settings → Privacy & Security)

### Install (important — Gatekeeper)
This build is **not** code-signed with an Apple Developer ID or notarized, so macOS Gatekeeper will block it on first launch ("can't be opened because Apple cannot check it for malicious software," or "is damaged"). To open it anyway:

1. Drag **WannaTapThat.app** to **/Applications**.
2. **Right-click the app → Open → Open** (don't just double-click).

If that still fails, clear the quarantine attribute in Terminal:
```bash
xattr -dr com.apple.quarantine /Applications/WannaTapThat.app
```

Note: because the build isn't signed with a stable Developer ID, a future update gets a new code signature, which **resets the Screen Recording / Accessibility grants** — you'll need to re-grant them after updating.

### ⚠️ Disclaimer — read before using
This is an **experimental / educational** project. Automating Hinge **violates Hinge's Terms of Service** and can get your account **banned or shadowbanned**. It interacts with **real people** who believe a human chose to like them — use it thoughtfully and respectfully. Provided **as-is, with no warranty**; the author is **not responsible** for bans, lost accounts, or any misuse. **Use entirely at your own risk.** Not affiliated with Hinge or Match Group.
