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

## The two run modes

- **`serve` (default in the Dockerfile)** — serves the catalog + admin console on the LAN.
- **`app --phone`** — also prints a QR + sets a write token so you can **add cover photos
  from your phone** over the LAN. Override the container command to use it:
  ```yaml
  command: ["mediahound", "app", "--phone", "--host", "0.0.0.0", "--port", "8765", "--config", "/library/config.toml"]
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
