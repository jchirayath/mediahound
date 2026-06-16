# MediaHound — self-host the live server/editor (e.g. on a NAS via Docker).
# Build:  docker build -t mediahound .
# Run:    docker run -p 8765:8765 -v /path/to/library:/library mediahound
FROM python:3.12-slim

# Tesseract lets MediaHound OCR-identify newly added cover photos (the [ocr] extra).
# Barcode decoding (snap the UPC/EAN/ISBN to add an exact release) ships in the core install
# via the zxing-cpp wheel — no system package needed.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir ".[ocr]"

# Your library (config.toml, data/, RawImages/, posters/, originals/) mounts here.
VOLUME ["/library"]
EXPOSE 8765

# Default = combined mode: `app --phone` serves the catalog (view) + admin console
# (regular editing) + phone uploads (token-gated QR) in one process, bound to the LAN.
# Get the phone-pairing QR/URL from the container logs (it rotates on restart).
# ⚠ LAN-only — do NOT expose to the public internet without a reverse proxy + real auth.
CMD ["mediahound", "app", "--phone", "--host", "0.0.0.0", "--port", "8765", "--no-open", "/library"]
