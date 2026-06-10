# Contributing to MediaHound

Thanks for helping out! MediaHound is intentionally small and dependency-light.

## Dev setup

```bash
pip install -e ".[ocr,dev]"
mediahound build --config demo/config.toml --mock   # quick smoke test
```

## Architecture

- `mediahound/pipeline.py` — orchestration (scan → identify → enrich → intro → resale → write).
- `mediahound/identify/` — **Identifier** providers (read title/year/format from a cover).
- `mediahound/metadata/` — **MetadataProvider** providers (poster + canonical fields).
- `mediahound/store.py` — the incremental manifest and the JSON the website reads.
- `mediahound/web/` — the static site template copied by `mediahound init`.

## Adding a provider

1. **Identifier:** subclass `identify.base.Identifier`, implement
   `identify(image_path, jpeg_bytes) -> Identification`, and register it in
   `identify/__init__.py:get_identifier`.
2. **Metadata:** subclass `metadata.base.MetadataProvider`, implement
   `lookup(title, year) -> MovieMeta`, and register it in
   `metadata/__init__.py:get_metadata_provider`.

Keep these rules:

- **No secrets in the repo.** Read keys from environment variables only (loaded from a gitignored
  `.env`). Never log a key.
- **Degrade gracefully.** A provider that can't match should return `identified=False` /
  `matched=False`, not raise — one bad cover must not stop the run.
- **Stay key-optional.** The default `tesseract` + `wikidata` path must keep working with zero keys.

## Style

Plain standard-library Python where practical; only `requests` + `Pillow` (+ optional `pytesseract`)
as runtime deps. Frontend is vanilla JS — no build step, no framework.
