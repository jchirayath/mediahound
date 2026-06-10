# Examples

The fastest way to see MediaHound without any photos or API keys:

```bash
mediahound init demo
mediahound build --config demo/config.toml --mock
cd demo && python3 -m http.server 8080
```

`--mock` writes a small sample catalog (a handful of well-known films + one "unidentified" item)
with generated placeholder posters, so every part of the UI — search, filters, sorting, the detail
modal, mark-as-seen, the export round-trips, and the identify page — is demoable offline.

To try the real **zero-key** pipeline, drop a few cover photos into `demo/RawImages/` and run
`mediahound build --config demo/config.toml` (uses Tesseract OCR + Wikidata).
