# tools/

Standalone helper scripts (not part of the `mediahound` pip package).

## Music library → MediaHound CSV

Convert a folder of music files into a CSV you can import (admin → **➕ Add → Import CSV**,
or `mediahound import`).

- **`music_to_mediahound_csv_clean.py`** — *recommended.* Walks a library, reads ID3/Vorbis/MP4
  tags via `mutagen`, groups files into albums, and emits a cleaned CSV. Layer-A cleanup: balanced
  title brackets, global artist canonicalization, genre normalization, audiobook/spoken-word routed
  to a separate review file, and placeholder albums collapsed to per-artist "Singles".
  ```bash
  pip install mutagen
  python tools/music_to_mediahound_csv_clean.py "/path/to/Music" mediahound-music.clean.csv
  # writes mediahound-music.clean.csv (import this) + mediahound-music.review.csv (eyeball)
  ```
- **`music_to_mediahound_csv.py`** — the original, simpler version (kept for reference).
