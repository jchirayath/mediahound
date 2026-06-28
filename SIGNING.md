# Code-signing the desktop app

> **Status (this project's official builds):**
> - 🍎 **macOS — signed & notarized.** The Developer ID secrets are configured, so released
>   `MediaHound-macOS.zip` builds are codesigned (`Developer ID Application: Jacob Chirayath
>   (VKUYJ3BS76)`) and **notarized by Apple** — they open with **no Gatekeeper warning**
>   (`spctl` → *accepted / Notarized Developer ID*).
> - 🪟 **Windows — not signed yet.** No Authenticode cert is configured, so `MediaHound-Windows.zip`
>   is **unsigned**: Windows SmartScreen shows a one-time *"Unknown publisher"* prompt
>   (**More info → Run anyway**). The free SignPath OSS plan **declined** us (project too new); a paid
>   cert or a later SignPath re-application would remove it — see the Windows section below.

The desktop builds (`.github/workflows/desktop.yml`) also work **unsigned out of the box** for
anyone forking the project — they just show a one-time Gatekeeper (macOS) / SmartScreen (Windows)
prompt. To ship builds that open with **no warning**, add the signing secrets below to the GitHub
repo (**Settings → Secrets and variables → Actions**). The workflow signs automatically when they're
present and silently skips when they're not — so nothing breaks if you only set up one OS.

## macOS (Developer ID + notarization, via Fastlane) — ✅ configured

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

**Using an App Store Connect API key instead of an app-specific password** (recommended — it's what
the poker_manager setup uses): set `ASC_KEY_ID`, `ASC_ISSUER_ID` and `ASC_KEY_FILE` (path to your
`AuthKey_*.p8`). The lane auto-detects these and notarizes with the key. In CI, provide the key as a
base64 secret `ASC_KEY_P8_BASE64` (plus `ASC_KEY_ID`/`ASC_ISSUER_ID`) and the workflow writes it out.

Already keep a **Fastlane `match`** repo? Set `MATCH_GIT_URL` and the lane fetches the Developer ID
cert with `match(type: "developer_id")` instead of needing it pre-installed in the keychain.

## Windows (Authenticode) — ⬜ not configured yet

There's no free *trusted* CA for Windows (no "Let's Encrypt" equivalent). The build ships **unsigned**
today, so SmartScreen shows a one-time *"Unknown publisher"* prompt (**More info → Run anyway**).
Three paths to remove it — none is wired up yet:

> **Status:** SignPath Foundation (the free OSS option) **declined** this project — its free plan
> requires an established project (sufficient repo history / stars / downloads). Re-apply once
> MediaHound has more traction; until then, either pay for a cert (Options 2–3) or leave it unsigned.

### Option 1 — SignPath Foundation (free, for open-source) — *not eligible yet*

[SignPath Foundation](https://signpath.org/) provides **free code signing for qualifying open-source
projects**, but it requires a project with enough history/users (we don't qualify yet — reapply
later). The workflow's SignPath steps **self-skip** until you configure it. When eligible:

1. Apply for the **Foundation (OSS) plan** at <https://signpath.org/> with this repo.
2. In SignPath, create:
   - a **Project** with slug `mediahound` (must match `project-slug` in `desktop.yml`),
   - an **Artifact configuration** for a single PE file (`MediaHound.exe`),
   - a **Signing policy** (default slug `release-signing`),
   - a **Trusted Build System** connection to this GitHub repo (so SignPath verifies the build origin).
3. In GitHub → Settings:
   - **Secret** `SIGNPATH_API_TOKEN` (a SignPath CI user token),
   - **Variable** `SIGNPATH_ORGANIZATION_ID` (your SignPath org id),
   - *(optional)* **Variable** `SIGNPATH_POLICY_SLUG` if not `release-signing`.

On the next build, the Windows `MediaHound.exe` is uploaded, signed by SignPath, and swapped back in
before zipping. (The `release-signing` policy may require a one-click approval in SignPath per build;
use a `test-signing` policy for fully automatic signing while you set things up.)

> SignPath gives you a *real* certificate, so "Unknown publisher" goes away. Windows SmartScreen
> *download* reputation can still take a little while to fully clear, but a genuine signature builds it
> far faster (and per-publisher).

### Option 2 — Azure Trusted Signing (~$10/mo) — ⭐ best paid CI path

Microsoft's managed signing service: no hardware token, signs straight from CI. **Caveat:** like
SignPath, public-trust certs need a verifiable identity — an **organization with ≥3 years of history**,
or individual validation — so a brand-new identity may hit the same wall. If eligible, add the
`sign` action / `signtool` against the Trusted Signing account in `desktop.yml` (no `.pfx` to manage).
EV-equivalent trust → SmartScreen clears quickly.

### Option 3 — Buy your own OV/EV certificate (`signtool`)

If you buy a cert from a CA (OV ~$200-400/yr; EV more). The workflow already has a `signtool` step
keyed on these secrets:

| Secret | What it is |
| --- | --- |
| `WINDOWS_CERT_PFX` | Your code-signing cert exported as `.pfx`, **base64-encoded**. |
| `WINDOWS_CERT_PASSWORD` | The `.pfx` password. |

It signs `MediaHound.exe` with `signtool` (SHA-256, RFC-3161 timestamp). **Note:** since 2023, OV/EV
keys must live on a hardware token / cloud HSM, so the plain `.pfx`-in-CI flow only works with a
provider that offers a cloud-key option (e.g. SSL.com eSigner, DigiCert KeyLocker). A new OV cert
builds SmartScreen reputation over time; EV clears it immediately.

### For now

Windows stays **unsigned** — users click **More info → Run anyway** once. This is fine for an early
OSS tool; revisit when SignPath approves (free) or when paid signing is worth it.

## Verifying

- macOS: `spctl -a -vvv -t install MediaHound.app` should say *accepted / Notarized Developer ID*.
- Windows: right-click `MediaHound.exe` → Properties → **Digital Signatures** (shows the SignPath/your publisher).

Keep all of these in GitHub Secrets only — never commit certificates or passwords to the repo.
