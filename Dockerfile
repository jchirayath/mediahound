# MediaHound — self-host the live server/editor (e.g. on a NAS via Docker).
# Build:  docker build -t mediahound .
# Run:    docker run -p 8765:8765 -v /path/to/library:/library mediahound
FROM python:3.12-slim

# Tesseract lets MediaHound OCR-identify newly added cover photos (the [ocr] extra).
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir ".[ocr]"

# Your library (config.toml, data/, RawImages/, posters/, originals/) mounts here.
VOLUME ["/library"]
EXPOSE 8765

# Serve the catalog on the LAN with the admin console enabled. The write API stays
# origin/token-gated (see docs/self-host.md); for adding photos over the network use
# phone mode.  ⚠ LAN-only — do NOT expose to the public internet without a reverse
# proxy + real auth in front of it.
CMD ["mediahound", "serve", "--host", "0.0.0.0", "--port", "8765", "--admin", "--config", "/library/config.toml"]
