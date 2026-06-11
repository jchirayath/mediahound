# Code-signing the desktop app

The desktop builds (`.github/workflows/desktop.yml`) work **unsigned out of the box** — they just
show a one-time Gatekeeper (macOS) / SmartScreen (Windows) prompt the first time a user opens them.

To ship builds that open with **no warning**, add the signing secrets below to the GitHub repo
(**Settings → Secrets and variables → Actions**). The workflow signs automatically when they're
present and silently skips signing when they're not — so nothing breaks if you only set up one OS.

## macOS (Developer ID + notarization, via Fastlane)

> MediaHound's desktop app is a **macOS** app (no iOS target). It's distributed **outside the App
> Store**, so it needs a **Developer ID Application** certificate (not an App Store / iOS cert) — no
> new app record in App Store Connect is required. Signing is done with **Fastlane**
> ([`fastlane/Fastfile`](fastlane/Fastfile)), reusing your existing Apple Developer account.

Requires an Apple Developer account ($99/yr) and a **Developer ID Application** certificate.

| Secret | What it is |
| --- | --- |
| `APPLE_CERTIFICATE_P12` | Your Developer ID Application cert + private key exported as `.p12`, then **base64-encoded** (`base64 -i cert.p12 \| pbcopy`). |
| `APPLE_CERTIFICATE_PASSWORD` | The password you set when exporting the `.p12`. |
| `APPLE_SIGN_IDENTITY` | The identity string, e.g. `Developer ID Application: Your Name (TEAMID)`. |
| `APPLE_ID` | Your Apple ID email (for notarization). |
| `APPLE_TEAM_ID` | Your 10-character Apple Team ID. |
| `APPLE_APP_PASSWORD` | An **app-specific password** for that Apple ID (appleid.apple.com → Sign-In and Security). |

**In CI:** `desktop.yml` imports the cert into a temporary keychain, then runs
`bundle exec fastlane mac sign`, which `codesign`s `MediaHound.app` with the hardened runtime,
notarizes it (`notarize` action → `notarytool`), and staples the ticket.

**Locally** (the same way you sign your other apps):

```bash
bash packaging/build-desktop.sh        # produces dist/MediaHound.app
export MAC_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export APPLE_ID="you@example.com" APPLE_TEAM_ID="XXXXXXXXXX" APPLE_APP_PASSWORD="abcd-efgh-ijkl-mnop"
bundle exec fastlane mac sign
```

Already keep a **Fastlane `match`** repo? Set `MATCH_GIT_URL` and the lane fetches the Developer ID
cert with `match(type: "developer_id")` instead of needing it pre-installed in the keychain.

## Windows (Authenticode)

Requires a code-signing certificate (OV/EV) from a CA.

| Secret | What it is |
| --- | --- |
| `WINDOWS_CERT_PFX` | Your code-signing cert exported as `.pfx`, **base64-encoded**. |
| `WINDOWS_CERT_PASSWORD` | The `.pfx` password. |

The workflow signs `MediaHound.exe` with `signtool` (SHA-256, RFC-3161 timestamp). Note: a brand-new
OV certificate still accrues SmartScreen reputation over time; an **EV** certificate clears SmartScreen
immediately.

## Verifying

- macOS: `spctl -a -vvv -t install MediaHound.app` should say *accepted / Notarized Developer ID*.
- Windows: right-click `MediaHound.exe` → Properties → **Digital Signatures**.

Keep all of these in GitHub Secrets only — never commit certificates or passwords to the repo.
