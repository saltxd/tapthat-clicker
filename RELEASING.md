# Releasing WannaTapThat

Maintainer guide for cutting a public release of **WannaTapThat** — building the
`.app`, (optionally) signing + notarizing it so users don't fight Gatekeeper,
packaging the DMG, and publishing a GitHub Release.

This is the document you (the maintainer) follow. It is **not** the user-facing
README. Read it top to bottom the first time; after that you mostly just run
`./build.sh` then `./notarize.sh`.

---

## 0. The honest disclaimer (must ship in every release)

Whatever you publish — the README, the GitHub Release notes, the X/Twitter post
— **must** carry this framing, verbatim or close to it. Do not soften it, do not
bury it, do not contradict it elsewhere.

> **WannaTapThat is an experimental, educational project. Provided as-is, with
> no warranty.**
>
> - Automating Hinge **violates Hinge's Terms of Service**. Using this can get
>   your account **banned or shadowbanned**. There is no "safe amount."
> - It interacts with **real people** who believe a human chose to like them.
>   Use it thoughtfully and respectfully, or don't use it.
> - It is **not** ToS-compliant, **not** undetectable, and **not** risk-free.
>   Anyone who tells you otherwise is wrong.
> - The author is **not responsible** for bans, shadowbans, lost matches, hurt
>   feelings, or any other consequence of using or misusing this software.

Paste this into the GitHub Release body and keep the README's disclaimer section
in sync. The X announcement must keep the "experimental / against ToS / use at
your own risk" framing — playful is fine, deceptive is not.

---

## 1. Prerequisites

### Always needed (to build)

- **macOS 15 (Sequoia) or newer** — iPhone Mirroring (and therefore this app)
  requires it. Build on the oldest macOS you intend to support.
- **Xcode Command Line Tools** — provides `codesign`, `xcrun`, `notarytool`,
  `stapler`, `spctl`:
  ```bash
  xcode-select --install
  ```
- **Python 3** (the `build.sh` script creates its own `venv` and installs
  `requirements.txt`, which includes PyInstaller, into it).
- **`create-dmg`** (Homebrew) for packaging:
  ```bash
  brew install create-dmg
  ```

### Only needed for the FRIENDLY (signed + notarized) path

- A **paid Apple Developer account** ($99/year).
- A **"Developer ID Application"** certificate in your login keychain. Create it
  in Xcode (Settings → Accounts → Manage Certificates → "+" → *Developer ID
  Application*) or via the Apple Developer portal, then download/install it.
  Confirm it's present:
  ```bash
  security find-identity -v -p codesigning
  ```
  You're looking for a line like:
  ```
  1) ABCD1234... "Developer ID Application: Your Name (TEAMID)"
  ```
  Copy that full quoted string — it's your `CODESIGN_IDENTITY`. The 10-character
  `TEAMID` in the parentheses is your `TEAM_ID`.
- An **app-specific password** for notarization, OR (recommended) a saved
  **notarytool keychain profile**. See §5.2.

> **Without** the Developer account you can still ship — see §4 (the unsigned
> path). Users just have to do one extra click or run one command. Be honest
> about that in the release notes.

---

## 2. Build the `.app` (PyInstaller)

```bash
./build.sh
```

This:
1. creates/uses `venv/`, installs deps (including PyInstaller),
2. runs `pyinstaller WannaTapThat.spec` (version + bundle id come from the spec),
3. bundles `resources/` (the OpenCV templates + `icon.icns`),
4. writes **`dist/WannaTapThat.app`**.

The first build takes a couple of minutes. Sanity-check it launched correctly:

```bash
./dist/WannaTapThat.app/Contents/MacOS/WannaTapThat --version
./dist/WannaTapThat.app/Contents/MacOS/WannaTapThat --diagnostics
```

`--diagnostics` prints the runtime/window-lookup info and tries a screen
capture (writes `/tmp/debug_capture.png` on success). Run it on the build
machine after granting Screen Recording to confirm capture works.

### Optional: sign during the build

`build.sh` codesigns the bundle as its last step **if** you export a
`CODESIGN_IDENTITY` (using `entitlements.plist`). Convenient for testing signing
in isolation, but **`notarize.sh` re-signs anyway**, so it's not required — the
authoritative sign happens in `notarize.sh`.

---

## 3. Two distribution paths — pick one

| | Unsigned (§4) | Signed + Notarized (§5) |
|---|---|---|
| Apple Developer account | not needed | **required ($99/yr)** |
| What the user sees | Gatekeeper block; needs a workaround | Opens with a normal "downloaded from the internet" prompt |
| Effort per release | zero extra | run `./notarize.sh` (~2–10 min wait) |
| Recommended for public download | tolerable | **yes** |

You can ship unsigned today and switch to notarized once you have the
Developer account — the build is identical, only the post-processing differs.

---

## 4. UNSIGNED distribution path

Build (§2), package the DMG:

```bash
./create-dmg.sh        # -> dist/WannaTapThat.dmg
```

Attach that DMG to the GitHub Release (§6). **Because it's neither signed with a
Developer ID nor notarized, macOS Gatekeeper will block it on first open.** The
user sees one of:

- *"WannaTapThat" can't be opened because Apple cannot check it for malicious
  software.*
- *"WannaTapThat" is damaged and can't be opened. You should move it to the
  Trash.* (Common when the DMG/app carry the `com.apple.quarantine` xattr.)

**Put these workarounds in the release notes, verbatim:**

> This build is not notarized, so macOS will warn you on first launch. Pick one:
>
> **Option A — right-click to open (easiest):**
> 1. Drag **WannaTapThat** to your Applications folder.
> 2. In Applications, **right-click** (or Control-click) the app → **Open**.
> 3. In the dialog, click **Open** again. macOS remembers this choice; future
>    launches are normal.
>
> *(On macOS Sequoia, if right-click → Open doesn't show an Open button, go to
> **System Settings → Privacy & Security**, scroll to the message about
> WannaTapThat being blocked, and click **Open Anyway**.)*
>
> **Option B — clear the quarantine flag (fixes "is damaged"):**
> ```bash
> xattr -dr com.apple.quarantine /Applications/WannaTapThat.app
> ```
> Then open it normally.

Then point users at the README permissions section (Screen Recording +
Accessibility). See §7 for the permission gotcha.

---

## 5. SIGNED + NOTARIZED path (the friendly one)

This is what `notarize.sh` (§8) automates end to end. The manual steps below are
what the script does, documented so you understand and can debug it.

### 5.1 Sign the `.app` with the hardened runtime

The hardened runtime is **required** for notarization. A PyInstaller bundle ships
a Python interpreter plus many unsigned `.so`/`.dylib` files and uses executable
memory, so it needs entitlements that permit JIT / unsigned executable memory and
skip library validation. The repo already includes `entitlements.plist`; sign the
bundle with it:

```bash
codesign --force --deep --timestamp --options runtime \
  --entitlements entitlements.plist \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  dist/WannaTapThat.app

# verify the signature is valid and Developer-ID, with the hardened runtime
codesign --verify --strict --verbose=2 dist/WannaTapThat.app
codesign --display --verbose=4 dist/WannaTapThat.app   # look for "flags=...runtime"
```

> **Nested code.** A PyInstaller `.app` contains many Mach-O files under
> `Contents/Frameworks` and `Contents/MacOS`. `--deep` signs them in one pass,
> which is enough here. If Apple's notary log ever complains about a specific
> unsigned/nested binary, sign that file explicitly (inner-first, outer-last)
> and re-run. `entitlements.plist` only needs to apply to the main executable.

### 5.2 Set up notarytool credentials (once)

Notarization needs your Apple ID, an **app-specific password** (not your real
password — create one at <https://account.apple.com> → Sign-In and Security →
App-Specific Passwords), and your Team ID. Store them once in a keychain
profile so you never paste them again:

```bash
xcrun notarytool store-credentials "wtt-notary" \
  --apple-id "you@example.com" \
  --team-id "TEAMID" \
  --password "abcd-efgh-ijkl-mnop"   # the app-specific password
```

From then on you just reference `--keychain-profile "wtt-notary"`.

### 5.3 Build, sign, and notarize the DMG

Notarize the **DMG** (the artifact users download) so the ticket can be stapled
to it. Build the DMG, sign it, submit, wait, then staple:

```bash
./create-dmg.sh                                   # -> dist/WannaTapThat.dmg

codesign --force --timestamp \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  dist/WannaTapThat.dmg

xcrun notarytool submit dist/WannaTapThat.dmg \
  --keychain-profile "wtt-notary" \
  --wait

xcrun stapler staple dist/WannaTapThat.dmg
```

`--wait` blocks until Apple finishes (usually 1–5 min). On **Invalid**, pull the
log to see exactly what failed:

```bash
xcrun notarytool log <SUBMISSION_ID> --keychain-profile "wtt-notary"
```

(`notarize.sh` notarizes the app-containing DMG; you can also staple the `.app`
itself before packaging — stapling the DMG is sufficient for the download.)

### 5.4 Verify Gatekeeper will accept it

```bash
# DMG staple is valid
xcrun stapler validate dist/WannaTapThat.dmg

# Mount and check the app the way Gatekeeper will
hdiutil attach dist/WannaTapThat.dmg
spctl --assess --type execute --verbose=4 "/Volumes/WannaTapThat/WannaTapThat.app"
#   -> "...: accepted"  and  "source=Notarized Developer ID"
hdiutil detach "/Volumes/WannaTapThat"
```

`source=Notarized Developer ID` + `accepted` means a normal user double-click
will Just Work (one "downloaded from the internet" confirmation, no scary
"unidentified developer" / "damaged" block).

---

## 6. Cut the GitHub Release

Repo: <https://github.com/saltxd/tapthat-clicker>.

1. Bump the version in `gui.py` (`APP_VERSION`) and commit. Tag it:
   ```bash
   git tag -a v1.0.0 -m "WannaTapThat 1.0.0"
   git push origin v1.0.0
   ```
2. Create the release and attach the DMG (use `gh`):
   ```bash
   gh release create v1.0.0 \
     dist/WannaTapThat.dmg \
     --repo saltxd/tapthat-clicker \
     --title "WannaTapThat v1.0.0" \
     --notes-file release-notes.md
   ```
3. `release-notes.md` must contain:
   - the **disclaimer** from §0,
   - **requirements**: macOS 15 Sequoia+, iPhone Mirroring set up, an iPhone
     signed into Hinge, and Screen Recording + Accessibility permissions,
   - **install steps** (drag to Applications), and
   - if unsigned: the **Gatekeeper workarounds** from §4. If notarized, say so
     ("signed & notarized — opens normally") and omit the workaround noise.

> Double-check the attached `.dmg` is the **notarized + stapled** one, not a
> stale unsigned build sitting in `dist/`. `xcrun stapler validate
> dist/WannaTapThat.dmg` right before upload.

---

## 7. The permission-reset-on-update gotcha (tell users!)

macOS ties **Screen Recording** and **Accessibility** grants to the app's
**code signature / bundle identity**. When you ship a new build:

- **Signed with the SAME Developer ID identity every release** → the identity is
  stable, so macOS keeps the existing permission grants across updates. This is
  a real, underrated reason to get the Developer ID and sign consistently.
- **Unsigned / ad-hoc signed** (the default build) → every build has a new code
  hash, so macOS treats each update as a brand-new app and the **permission
  toggles you (or the user) previously enabled no longer apply**. Capture will
  return `None` and the app will report "Screen Recording permission needed."

Put this in the release notes for any update:

> After updating, if liking stops working or you see a permission error, macOS
> may have dropped the old permission. Re-grant it:
> **System Settings → Privacy & Security → Screen Recording** (and
> **Accessibility**) → toggle **WannaTapThat** on (remove and re-add it if it's
> already listed). If needed, reset and re-grant from Terminal:
> ```bash
> tccutil reset ScreenCapture
> tccutil reset Accessibility
> ```
> then relaunch the app so it prompts again.

For your own dev iteration, the in-place patch trick (copy the new binary into
the already-permitted `/Applications/WannaTapThat.app` and ad-hoc re-sign)
preserves permissions without a full reset — see the README's troubleshooting
section. That's a maintainer convenience, **not** something to tell end users.

---

## 8. Helper scripts in this repo

- **`notarize.sh`** — one command to sign the `.app`, build + sign the DMG,
  submit to notarytool (`--wait`), and staple. Edit the placeholders at the top
  (or export the env vars) and run it after `./build.sh`. It is defensive:
  `set -euo pipefail`, checks every required tool and credential, and echoes
  each step.
- **`build.sh`** — codesigns the freshly built bundle **only if**
  `CODESIGN_IDENTITY` is exported (otherwise it produces an ad-hoc bundle), using
  `entitlements.plist`. Lets you get a signed bundle straight from the build;
  `notarize.sh` still owns the authoritative sign + notarize.
- **`entitlements.plist`** — hardened-runtime entitlements used when signing.

Typical release flow once set up:

```bash
export CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export TEAM_ID="TEAMID"
export NOTARY_PROFILE="wtt-notary"        # from `notarytool store-credentials`

./build.sh         # build (optionally signs if CODESIGN_IDENTITY is exported)
./notarize.sh      # sign + DMG + notarize + staple
# verify, then:
gh release create vX.Y.Z dist/WannaTapThat.dmg --repo saltxd/tapthat-clicker ...
```

---

## 9. Quick troubleshooting

| Symptom | Cause / fix |
|---|---|
| `notarytool` → **Invalid** | `xcrun notarytool log <id> --keychain-profile "$NOTARY_PROFILE"`. Usually: missing hardened runtime (re-sign with `--options runtime`), unsigned nested binary (use `--deep`, or rebuild `--standalone` without `--onefile` and sign inner-first), or no secure timestamp (`--timestamp`). |
| `spctl` → **rejected / source=Unnotarized Developer ID** | Notarization didn't complete or the ticket wasn't stapled. Re-run staple; confirm with `stapler validate`. |
| Users still see "is damaged" on a notarized build | They downloaded a cached/old unsigned DMG, or the DMG itself wasn't stapled. Re-staple the DMG and re-upload. |
| `security find-identity` shows no Developer ID | Certificate not installed / expired. Recreate in Xcode → Accounts → Manage Certificates. |
| Capture works in dev but not for users after update | Permission reset on new signature — see §7. |
