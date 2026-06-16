# Self-hosting MediaHound (NAS / Docker)

Run MediaHound's server on an always-on box (QNAP, Synology, a Pi, any Docker host)
so your catalog lives at `http://<nas-ip>:8765` on your home network — with the
library (photos + data) stored on the NAS.

> **What this is good for:** an always-on **private catalog on your LAN**, plus
> **phone uploads** straight into the library. For a **public, read-only** copy,
> publish the generated static site to Netlify / GitHub Pages / Azure Static Web
> Apps instead — the two complement each other (NAS = editable master, static
> host = published snapshot).

## QNAP — Container Station (recommended)

Docker bundles Python 3.12, so you don't depend on QNAP's system Python.

1. Copy your library onto the NAS, e.g. `/share/MediaHound` (the folder that holds
   `config.toml`, `data/`, `RawImages/`, `posters/`, `originals/`). If you don't
   have one yet, `mediahound init` makes one.
2. In **Container Station → Applications → Create**, paste this (edit the volume path):
   ```yaml
   services:
     mediahound:
       image: ghcr.io/jchirayath/mediahound:latest   # or build: . from this repo
       container_name: mediahound
       restart: unless-stopped
       ports:
         - "8765:8765"
       volumes:
         - /share/MediaHound:/library
   ```
   (No published image yet? Clone this repo on the NAS and use `build: .`, or
   `docker build -t mediahound .` then reference `image: mediahound`.)
3. Start it → open **`http://<nas-ip>:8765`**.

CLI equivalent on any Docker host:
```bash
docker compose up -d        # uses the Dockerfile + docker-compose.yml in this repo
```

## QNAP — native (no Container Station)

Don't want to run Container Station/Docker? MediaHound is pure Python, so you can run it
directly on the NAS with a **relocatable Python** (QNAP ships no usable system Python). This
uses ~150 MB and starts in one process. Everything below assumes you SSH in as an admin user
(`ssh admin@<nas-ip>`) and pick a big data volume — here `/share/CACHEDEV1_DATA` (yours may be
`CACHEDEV2_DATA`/`MD0_DATA`; check with `df -h`).

```sh
BASE=/share/CACHEDEV1_DATA/mediahound      # adjust to your volume
mkdir -p "$BASE" && cd "$BASE"

# 1) Standalone CPython — pick the base x86_64 'gnu' build (runs on QNAP's older glibc).
#    Grab the latest install_only tarball from astral-sh/python-build-standalone releases:
#    https://github.com/astral-sh/python-build-standalone/releases
curl -L -o python.tar.gz \
  "https://github.com/astral-sh/python-build-standalone/releases/download/<TAG>/cpython-3.12.<x>+<TAG>-x86_64-unknown-linux-gnu-install_only.tar.gz"
tar xzf python.tar.gz          # → ./python/

# 2) Install MediaHound into it.
#    Invoke pip via `python -m pip` — the standalone build's `pip` wrapper has a hard-coded
#    shebang from its build host that breaks once the tarball is relocated.
./python/bin/python -m pip install --upgrade pip
./python/bin/python -m pip install mediahound
```

> **Old-glibc NAS?** MediaHound's barcode decoder (`zxing-cpp`) is a core dependency. Current
> wheels need glibc ≥ 2.28; QNAP/Synology boxes often ship something older (e.g. glibc 2.21), so
> pip would try to compile from source and fail. Pin the last version with a glibc-2.17
> (manylinux2014) wheel:
> ```sh
> ./python/bin/python -m pip install 'zxing-cpp==2.2.0'
> ```
> Check your glibc with `./python/bin/python -c 'import platform; print(platform.libc_ver())'`.
> (Everything else still works without it — only photograph-the-barcode decoding needs the wheel.)

Copy your library onto the NAS (the folder holding `config.toml`, `data/`, `RawImages/`,
`posters/`, `originals/`) — from your computer:

```sh
rsync -av --delete /path/to/MediaHound-Library/ admin@<nas-ip>:/share/CACHEDEV1_DATA/mediahound/library/
```

**Run it in combined mode** (view + admin editing + phone uploads), bound to the LAN on a
memorable port:

```sh
cd "$BASE/library"
PYTHONUNBUFFERED=1 "$BASE/python/bin/mediahound" app --phone \
  --host 0.0.0.0 --port 8080 --no-open "$BASE/library"
```

Open **`http://<nas-ip>:8080`** to view; the log prints the token-gated phone/editor URL
(`http://<nas-ip>:8080/?t=<token>` + a QR).

### Keep it running (reboots + crashes)

QNAP's `nohup`/`setsid` won't survive a reboot. Use a tiny **watchdog cron** that relaunches it
if the port goes quiet (this also recovers from crashes). Create two scripts in `$BASE`:

`start.sh`
```sh
#!/bin/sh
BASE=/share/CACHEDEV1_DATA/mediahound
for p in $(ps | grep 'app --phone' | grep -v grep | awk '{print $1}'); do kill -9 $p 2>/dev/null; done
sleep 2
cd "$BASE/library"
PYTHONUNBUFFERED=1 setsid "$BASE/python/bin/mediahound" app --phone \
  --host 0.0.0.0 --port 8080 --no-open "$BASE/library" > "$BASE/mediahound.log" 2>&1 < /dev/null &
```

`watchdog.sh`
```sh
#!/bin/sh
BASE=/share/CACHEDEV1_DATA/mediahound
netstat -tln 2>/dev/null | grep -q ':8080' || sh "$BASE/start.sh"
```

Then register the cron (QNAP keeps the persistent crontab at `/etc/config/crontab`):
```sh
chmod +x "$BASE/start.sh" "$BASE/watchdog.sh"
grep -q 'mediahound/watchdog.sh' /etc/config/crontab \
  || echo "*/5 * * * * $BASE/watchdog.sh" >> /etc/config/crontab
crontab /etc/config/crontab && /etc/init.d/crond.sh restart
```

> Note: `app` does an offline rebuild on every start (~1 min for a few hundred items), so the
> catalog is briefly unavailable right after a (re)boot until the rebuild finishes and it binds.

## Run modes

**The image default is combined mode** — `mediahound app --phone` runs everything in
one process:
- **view** the catalog at `http://<nas-ip>:8765`,
- **admin console** for editing (regular mode), and
- **phone uploads** — a token-gated QR so you can add items from your phone by photographing
  the **cover** or the **barcode** (UPC/EAN/ISBN); the server decodes the barcode and resolves
  the exact release. (No browser camera permission / HTTPS needed — it uses the OS photo picker's
  *Take Photo*, then identifies server-side. The live in-browser barcode scanner, by contrast,
  needs HTTPS and isn't supported on iOS.)

**Get the phone-pairing QR / URL from the container logs** (Container Station → the
container → Logs, or `docker compose logs mediahound`). The URL looks like
`http://<nas-ip>:8765/?t=<token>` — open it (or scan the QR) to get write access from a
phone/browser. **By default the token rotates each time the server restarts**, so re-grab it
from the logs after a restart.

**Want a stable pairing URL?** Set `MEDIAHOUND_TOKEN` to a long secret and the phone/editor URL
stays the same across restarts (handy for an always-on NAS behind a watchdog). In Docker add it
under `environment:`; for the native QNAP setup, `export MEDIAHOUND_TOKEN=<your-secret>` at the
top of `start.sh`. Treat it like a password — anyone with it can edit on your LAN; unset it to go
back to a fresh random token each run.

Prefer a **view-only** server (no admin writes, no phone)? Override the command:
```yaml
command: ["mediahound", "serve", "--host", "0.0.0.0", "--port", "8765", "--no-open", "--config", "/library/config.toml"]
```

## Security model (read this before exposing it)

MediaHound's **write/admin API is intentionally hardened for local use**:
- Reads (viewing the catalog) are open on whatever interface you bind.
- **Writes require either a loopback (localhost) origin or a token** (phone/LAN mode),
  and cross-origin writes are rejected. So casual editing is smoothest from the NAS's
  own session or via phone mode's token.

**Keep it LAN-only.** Do **not** port-forward `:8765` to the internet or expose it via
myQNAPcloud without putting a reverse proxy with real authentication in front of it.
For remote access, use your NAS's **VPN**, or publish the **static** catalog to a host
(Netlify / Azure SWA) for a public read-only view.

## Provider API keys (optional)

Zero keys are needed for OCR + open-data identification. If you want TMDB/OMDb/Discogs,
put them in a gitignored `.env` next to `config.toml` in the mounted library — the
container reads them from there (the OS-keychain path isn't available in a container).
