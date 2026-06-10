"""Orchestration: scan input, identify → enrich → value → write, incrementally."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import Config
from .identify import get_identifier
from .identify.base import Identification
from .imaging import make_placeholder_poster, prepared_jpeg, save_thumbnail
from .intro import make_intro
from .metadata import get_metadata_provider
from .metadata.base import MovieMeta
from .resale import estimate
from .store import Store, list_images, sha256_file

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_STOP = {"the", "a", "an", "of", "and", "vol", "volume", "part", "complete", "season",
         "collection", "edition", "special", "disc", "set", "series", "to", "in"}


def _sig_tokens(s: str) -> set:
    return {t for t in _SLUG_RE.split((s or "").lower()) if t and t not in _STOP}


def _plausible_title(claude: str, provider: str) -> bool:
    """True if the provider's returned title plausibly matches what we identified — guards
    against fuzzy search returning a different film and corrupting the name/data."""
    ct, cp = _sig_tokens(claude), _sig_tokens(provider)
    if not ct or not cp:
        return False
    shorter = ct if len(ct) <= len(cp) else cp
    longer = cp if shorter is ct else ct
    return len(shorter & longer) / len(shorter) >= 0.6


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "").lower()).strip("-") or "item"


def _movie_id(meta: MovieMeta, ident: Identification, file_hash: str) -> str:
    if meta.matched and meta.source_id:
        return f"{meta.source}-{meta.source_id}"
    base = _slug(meta.title or ident.title or "item")
    return f"{base}-{(meta.year or ident.year or file_hash[:6])}"


def _download_poster(url: str, dest: Path) -> bool:
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        return False  # only fetch over http(s)
    try:
        r = requests.get(url, timeout=45, headers={"User-Agent": "ReelShelf/0.1"})
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return True
    except requests.RequestException:
        return False


# Sample data used only by --mock so the site can be demoed with no providers/keys.
_STREAM_URL = {"Netflix": "https://www.netflix.com/", "Hulu": "https://www.hulu.com/",
               "Amazon Prime Video": "https://www.amazon.com/Prime-Video/b?node=2676882011"}
_MOCK = [
    dict(title="Serenity", poster_url="https://m.media-amazon.com/images/M/MV5BZWYwN2M1NWItMWI0YS00ZmJjLTk1Y2QtZjIxYmNhNGZkZDcwXkEyXkFqcGc@._V1_SX300.jpg", year=2005, format="DVD", genres=["Science Fiction", "Adventure"],
         language="English", rating=7.8, runtime=119, director="Joss Whedon", color=(40, 44, 64),
         actors=["Nathan Fillion", "Gina Torres", "Alan Tudyk", "Summer Glau"],
         studio="Universal Pictures", stream=["Netflix", "Amazon Prime Video"], photos=3,
         intro="Take my love, take my land — one last desperate run to the edge of the 'verse."),
    dict(title="The Princess Bride", poster_url="https://m.media-amazon.com/images/M/MV5BMjFiOTEyNGMtN2E4MC00ZjZlLTk3ZDQtNTU1ZGNiZTA1MzJlXkEyXkFqcGc@._V1_SX300.jpg", year=1987, format="VHS", genres=["Adventure", "Fantasy", "Romance"],
         language="English", rating=8.0, runtime=98, director="Rob Reiner", color=(74, 52, 40),
         actors=["Cary Elwes", "Robin Wright", "Mandy Patinkin", "Wallace Shawn"],
         studio="20th Century Studios", stream=["Hulu"],
         intro="Fencing, fighting, true love, giants — a bedtime story that never grows up."),
    dict(title="Blade Runner", poster_url="https://m.media-amazon.com/images/M/MV5BOWQ4YTBmNTQtMDYxMC00NGFjLTkwOGQtNzdhNmY1Nzc1MzUxXkEyXkFqcGc@._V1_SX300.jpg", year=1982, format="Blu-ray", genres=["Science Fiction", "Thriller"],
         language="English", rating=8.1, runtime=117, director="Ridley Scott", color=(28, 40, 58), gallery=True,
         actors=["Harrison Ford", "Rutger Hauer", "Sean Young"], studio="Warner Bros.",
         stream=["Amazon Prime Video"], photos=2,
         intro="Neon rain, electric souls, and the question of what makes us human."),
    dict(title="Spirited Away", poster_url="https://m.media-amazon.com/images/M/MV5BNTEyNmEwOWUtYzkyOC00ZTQ4LTllZmUtMjk0Y2YwOGUzYjRiXkEyXkFqcGc@._V1_QL75_UX380_CR0,0,380,562_.jpg", year=2001, format="DVD", genres=["Animation", "Fantasy", "Family"],
         language="Japanese", rating=8.6, runtime=125, director="Hayao Miyazaki", color=(36, 62, 52),
         actors=["Rumi Hiiragi", "Miyu Irino", "Mari Natsuki"], studio="Studio Ghibli", stream=["Netflix"],
         intro="Step through the tunnel into a bathhouse of spirits where nothing is what it seems."),
    dict(title="Pulp Fiction", poster_url="https://m.media-amazon.com/images/M/MV5BYTViYTE3ZGQtNDBlMC00ZTAyLTkyODMtZGRiZDg0MjA2YThkXkEyXkFqcGc@._V1_QL75_UY562_CR3,0,380,562_.jpg", year=1994, format="VHS", genres=["Crime", "Drama"],
         language="English", rating=8.5, runtime=154, director="Quentin Tarantino", color=(64, 38, 38),
         actors=["John Travolta", "Samuel L. Jackson", "Uma Thurman", "Bruce Willis"],
         studio="Miramax", stream=[],
         intro="Hitmen, a briefcase, and a diner — time bends and everyone talks too cool to die."),
    dict(title="Amélie", poster_url="https://m.media-amazon.com/images/M/MV5BOTNmYzY0MWQtZGZmNy00Y2Y4LWFmMDQtMTZjYTdiYzEwZGQ2XkEyXkFqcGc@._V1_QL75_UX380_CR0,4,380,562_.jpg", year=2001, format="DVD", genres=["Comedy", "Romance"],
         language="French", rating=8.3, runtime=122, director="Jean-Pierre Jeunet", color=(64, 56, 26),
         actors=["Audrey Tautou", "Mathieu Kassovitz"], studio="UGC", stream=["Hulu", "Amazon Prime Video"],
         intro="A shy Parisian waitress quietly engineers tiny miracles for everyone but herself."),
    dict(title="Lagaan", poster_url="https://m.media-amazon.com/images/M/MV5BM2FmODM4OTktOTRjOS00ZTIzLWIzZjAtMDBhOGEzYThkNzMzXkEyXkFqcGc@._V1_SX300.jpg", year=2001, format="DVD", genres=["Drama", "Musical", "Sport"],
         language="Hindi", rating=8.1, runtime=224, director="Ashutosh Gowariker", color=(74, 48, 24),
         actors=["Aamir Khan", "Gracy Singh", "Rachel Shelley"], studio="Aamir Khan Productions",
         stream=["Netflix"],
         intro="A drought-struck village stakes everything on one impossible cricket match against the Raj."),
    dict(title="The Matrix", poster_url="https://m.media-amazon.com/images/M/MV5BN2NmN2VhMTQtMDNiOS00NDlhLTliMjgtODE2ZTY0ODQyNDRhXkEyXkFqcGc@._V1_QL75_UX380_CR0,4,380,562_.jpg", year=1999, format="Blu-ray", genres=["Science Fiction", "Action"],
         language="English", rating=8.7, runtime=136, director="The Wachowskis", color=(20, 46, 30),
         actors=["Keanu Reeves", "Laurence Fishburne", "Carrie-Anne Moss"], studio="Warner Bros.",
         stream=["Amazon Prime Video"], photos=2,
         intro="A hacker learns the world is a lie — and that the rules can be bent like rubber."),
    dict(title="Cinema Paradiso", poster_url="https://m.media-amazon.com/images/M/MV5BMTljNzc4YWEtYTZlMS00ODMyLWIwMTAtNWQxY2VkMDEwYTk5XkEyXkFqcGc@._V1_QL75_UX380_CR0,0,380,562_.jpg", year=1988, format="VHS", genres=["Drama", "Romance"],
         language="Italian", rating=8.5, runtime=155, director="Giuseppe Tornatore", color=(54, 44, 62),
         actors=["Philippe Noiret", "Salvatore Cascio"], studio="Miramax", stream=[],
         intro="A boy, a small-town projectionist, and a love letter to the movies themselves."),
    dict(title="Coco", poster_url="https://m.media-amazon.com/images/M/MV5BMDIyM2E2NTAtMzlhNy00ZGUxLWI1NjgtZDY5MzhiMDc5NGU3XkEyXkFqcGc@._V1_QL75_UY562_CR7,0,380,562_.jpg", year=2017, format="DVD", genres=["Animation", "Family", "Adventure"],
         language="Spanish", rating=8.4, runtime=105, director="Lee Unkrich", color=(78, 40, 52),
         actors=["Anthony Gonzalez", "Gael García Bernal"], studio="Pixar", stream=["Netflix", "Hulu"], photos=2,
         intro="On the Day of the Dead, a boy crosses into the afterlife to reclaim his family's song."),
]


class _NullMetadata:
    """Offline stand-in — never touches the network; every title becomes a manual entry."""
    name = "offline"

    def lookup(self, title, year=None):
        return MovieMeta(False)

    def save(self):
        pass


class _CachedMetadata:
    """Wraps a metadata provider with a persistent on-disk cache so repeated builds never
    re-query the network for a title already looked up (protects rate-limited free keys)."""

    def __init__(self, provider, cache_path):
        import json
        self.provider = provider
        self.name = provider.name
        self.cache_path = cache_path
        self.cache = json.loads(cache_path.read_text()) if cache_path.is_file() else {}
        self.dirty = False

    def _key(self, title, year):
        return f"{self.name}|{(title or '').strip().lower()}|{year or ''}"

    def lookup(self, title, year=None):
        key = self._key(title, year)
        if key in self.cache:
            return MovieMeta(**self.cache[key])
        meta = self.provider.lookup(title, year)
        if meta.matched:  # only cache hits, so misses retry once the quota resets
            from dataclasses import asdict
            self.cache[key] = asdict(meta)
            self.dirty = True
        return meta

    def save(self):
        if self.dirty:
            import json
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False))


class Stats:
    def __init__(self):
        self.scanned = self.new = self.identified = self.unidentified = self.skipped = 0

    def __str__(self):
        return (f"scanned={self.scanned} new={self.new} identified={self.identified} "
                f"unidentified={self.unidentified} skipped(existing)={self.skipped}")


def build(cfg: Config, mock: bool = False, force: bool = False,
          reidentify: str | None = None, limit: int | None = None,
          refresh_streaming: bool = False, online: bool = False, log=print) -> Stats:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.posters_dir.mkdir(parents=True, exist_ok=True)
    store = Store(cfg.data_dir)
    stats = Stats()

    if mock:
        return _build_mock(cfg, store, stats, log)

    if force:
        # full reprocess → rebuild the collection from scratch so stale fields (e.g. old
        # image paths) don't accumulate. seen/identify/corrections files are untouched.
        store.collection = []
        store._collection_by_id = {}
        store.unidentified = []

    images = list_images(cfg.input_dir)
    stats.scanned = len(images)
    log(f"Scanning {cfg.input_dir} → {len(images)} image(s)")

    metadata = None
    if images:
        if online:
            metadata = _CachedMetadata(get_metadata_provider(cfg), cfg.data_dir / ".metadata-cache.json")
            log(f"Metadata: {metadata.name} (online, cached)")
        else:
            metadata = _NullMetadata()
            log("OFFLINE mode — not contacting any online databases (use --online to enable).")

    # The identifier is built lazily — only when a NON-queued image actually needs it.
    # This lets a fully pre-identified run (e.g. an identify-queue produced by hand or by
    # Claude Code) work with no identifier credentials at all.
    _ident_box = {}

    def get_ident():
        if "i" not in _ident_box:
            _ident_box["i"] = get_identifier(cfg)
            log(f"Identifier: {_ident_box['i'].name}")
        return _ident_box["i"]

    threshold = float(cfg.identify.get("confidence_threshold", 0.55))
    processed = 0
    for idx, img in enumerate(images, 1):
        if limit and processed >= limit:
            break
        h = sha256_file(img)
        queued = store.identify_queue.get(h)
        skip = (not force) and store.is_processed(h) and reidentify != h
        if skip and queued:
            status = store.manifest.get(h, {}).get("status")
            # reprocess a queued item if it's still unidentified, marked for delete, or
            # we're online (to (re)discover with the corrected name)
            if queued.get("delete") or status in ("unidentified", "error") or online:
                skip = False
        if skip:
            stats.skipped += 1
            continue
        stats.new += 1
        processed += 1
        log(f"[{idx}/{len(images)}] {img.name} …")
        try:
            ok = _process_one(cfg, store, img, h, get_ident, metadata, threshold)
            if ok is None:
                pass  # discarded
            elif ok:
                stats.identified += 1
            else:
                stats.unidentified += 1
        except Exception as exc:  # one bad image shouldn't kill the whole run
            log(f"    ! error: {exc}")
            store.record(h, img.name, "error", None, _now())

    _apply_corrections(cfg, store, log, online=online)
    if online:
        _enrich_streaming(cfg, store, log, refresh=refresh_streaming)

    if metadata is not None:
        metadata.save()
    store.save()
    _write_site(cfg, store)
    log(f"Done. {stats}")
    log(f"Catalog: {store.collection_path}   Unidentified: {len(store.unidentified)}")
    return stats


def _apply_corrections(cfg: Config, store: Store, log, online: bool = False) -> None:
    """Apply user edits from data/corrections.json: rename, delete, format, rotate, set-default.
    Re-query (a network call) only happens when online=True."""
    import json
    corr = store.corrections
    if not corr:
        return
    need_meta = online and any(c.get("requery") for c in corr.values())
    meta_provider = get_metadata_provider(cfg) if need_meta else None
    tld = cfg.resale.get("ebay_tld", "com")
    requery_consumed = False

    for mid, c in list(corr.items()):
        if c.get("delete"):
            if store.delete_movie(mid):
                log(f"  correction: deleted {mid}")
            continue
        m = store.find_movie(mid)
        if not m:
            continue
        if c.get("title") and c["title"] != m.get("title"):
            m["title"] = c["title"]
            m.pop("streaming", None)  # title changed → re-check where-to-watch
        if c.get("year"):
            m["year"] = c["year"]
        if c.get("format"):
            m["format"] = c["format"]
        removed = set(c.get("removed_images") or [])
        if removed:
            m["images"] = [im for im in m.get("images", []) if im not in removed]
            if m.get("poster") in removed:
                m["poster"] = m["images"][0] if m.get("images") else None
        if c.get("default_image") and c["default_image"] not in removed:
            m["poster"] = c["default_image"]  # user chose a different cover as the default
        rotations = c.get("rotations") or {}
        if rotations:
            from .imaging import rotate_file
            base = cfg.output_dir.resolve()
            for rel, deg in list(rotations.items()):
                # guard against path traversal — only rotate image files inside the site's
                # own posters/ or originals/ folders (corrections.json is imported input).
                target = (cfg.output_dir / rel).resolve()
                ok = (target.is_file()
                      and base in target.parents
                      and target.parent.name in ("posters", "originals"))
                if ok and rotate_file(target, int(deg)):
                    log(f"  correction: rotated {rel} by {deg}°")
                elif not ok:
                    log(f"  correction: skipped unsafe rotation path {rel!r}")
            c["rotations"] = {}      # consumed (baked into the files)
            requery_consumed = True  # triggers corrections.json rewrite below
        if c.get("requery") and meta_provider:
            try:
                nm = meta_provider.lookup(m["title"], m.get("year"))
            except Exception as exc:
                log(f"  correction: re-query failed for {mid}: {exc}")
                nm = None
            if nm and nm.matched:
                _apply_meta_to_movie(cfg, m, nm)
                c["requery"] = False  # consumed → don't re-query every build
                requery_consumed = True
                log(f"  correction: re-queried {mid} → {nm.title} ({nm.source})")
        # manual studio/distributor edits win over any re-query
        for fld in ("studio", "distributor"):
            if fld in c and c[fld] is not None:
                m[fld] = c[fld] or None
        # keep the resale link in sync with the (possibly) new title/year/format
        m["resale"] = estimate(m["title"], m.get("year"), m.get("format", "DVD"),
                               m.get("rating"), tld)

    if requery_consumed:
        store.corrections_path.write_text(
            json.dumps(corr, indent=2, ensure_ascii=False), encoding="utf-8")


def _apply_meta_to_movie(cfg: Config, m: dict, meta: MovieMeta) -> None:
    """Overwrite a movie's enrichment fields from a fresh metadata lookup."""
    m["title"] = meta.title or m["title"]
    m["year"] = meta.year or m.get("year")
    m["genres"] = meta.genres
    m["language"] = meta.language or m.get("language")
    m["spoken_languages"] = meta.spoken_languages
    m["runtime"] = meta.runtime
    m["rating"] = meta.rating
    m["director"] = meta.director
    m["actors"] = meta.actors
    m["studio"] = meta.studio
    m["distributor"] = meta.distributor
    m["overview"] = meta.overview
    m["tagline"] = meta.tagline
    m["source"] = {"name": meta.source, "url": meta.source_url}
    m["intro"] = make_intro(Identification(True, meta.title, meta.year), meta)
    if meta.poster_url:
        dest = cfg.posters_dir / f"{_slug(m['id'])}.jpg"
        if _download_poster(meta.poster_url, dest):
            m["poster"] = f"posters/{dest.name}"


def _enrich_streaming(cfg: Config, store: Store, log, refresh: bool = False) -> None:
    """Fill each movie's 'streaming' (where-to-watch) via JustWatch. Skips already-checked
    titles unless refresh=True. Disabled with [streaming] enabled=false."""
    if not cfg.streaming.get("enabled", True):
        return
    pending = [m for m in store.collection if refresh or not m.get("streaming")]
    if not pending:
        return
    from . import streaming as sx
    import requests
    country = cfg.streaming.get("country", "US")
    log(f"Where-to-watch: checking {len(pending)} title(s) via JustWatch ({country})…")
    session = requests.Session()
    found = 0
    for m in pending:
        info = sx.fetch_offers(m["title"], m.get("year"), country=country, session=session)
        m["streaming"] = info
        if info.get("providers"):
            found += 1
    log(f"Where-to-watch: {found}/{len(pending)} are on a target service.")


_DEFAULT_VIEW = {
    "columns": 5,
    "fields": {  # which fields appear on the (read-only) default view
        "poster": True, "title": True, "meta": True, "genres": True, "people": True,
        "studio": True, "watch": True, "resale": True, "intro": True, "overview": False,
    },
}


def _write_site(cfg: Config, store: Store) -> None:
    import hashlib
    import json
    pw = str(cfg.admin.get("password", "changeme"))
    site = {
        "title": cfg.site.get("title", "My Movie Collection"),
        "subtitle": cfg.site.get("subtitle", ""),
        "generated_at": _now(),
        "count": len(store.collection),
        "unidentified": len(store.unidentified),
        # NOTE: this is NOT password storage in the security sense. The "admin" view is a
        # client-side convenience gate on a *static* site; this hash is intentionally published
        # and protects no server-side resource (the catalog can't change without rebuilding +
        # redeploying). It is compared in-browser via WebCrypto SHA-256. See SECURITY.md.
        "admin_password_sha256": hashlib.sha256(pw.encode("utf-8")).hexdigest(),
    }
    (cfg.data_dir / "site.json").write_text(
        json.dumps(site, indent=2, ensure_ascii=False), encoding="utf-8")

    # view-config.json is admin-owned (field visibility + default columns). Create a default
    # the first time; never overwrite it afterwards so the admin's choices persist.
    view_path = cfg.data_dir / "view-config.json"
    if not view_path.is_file():
        view = dict(_DEFAULT_VIEW)
        view["columns"] = int(cfg.view.get("columns", 4))
        view_path.write_text(json.dumps(view, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also emit a JS bundle so index.html works when opened directly (file://),
    # where browsers block fetch() of local JSON. The page prefers this global and
    # falls back to fetching the JSON when served over http(s).
    view = json.loads((cfg.data_dir / "view-config.json").read_text(encoding="utf-8"))
    payload = {"site": site, "collection": store.collection,
               "unidentified": store.unidentified, "view": view}
    bundle = "window.REELSHELF_DATA = " + json.dumps(payload, ensure_ascii=False) + ";"
    (cfg.data_dir / "bundle.js").write_text(bundle, encoding="utf-8")

    # Cache-bust: stamp a content version onto the asset URLs in the HTML so browsers (and
    # CDNs like GitHub Pages) always fetch the latest data/JS/CSS after a rebuild.
    ver = hashlib.sha256(bundle.encode("utf-8")).hexdigest()[:10]
    asset_re = re.compile(r'(href|src)="(assets/[^"?]+\.(?:css|js)|data/bundle\.js)(?:\?v=[0-9a-f]+)?"')
    for name in ("index.html", "identify.html"):
        page = cfg.output_dir / name
        if page.is_file():
            html = asset_re.sub(lambda m: f'{m.group(1)}="{m.group(2)}?v={ver}"',
                                page.read_text(encoding="utf-8"))
            page.write_text(html, encoding="utf-8")


def _process_one(cfg, store, img, h, get_ident, metadata, threshold) -> bool:
    queued = store.queued_identity(h)
    # discard: the user deleted this item in manual identification
    if queued and queued.get("delete"):
        store.remove_unidentified_by_hash(h)
        rec = store.manifest.get(h)
        if rec and rec.get("movie_id"):
            store.delete_movie(rec["movie_id"])
        store.record(h, img.name, "deleted", None, _now())
        return None
    is_manual = bool(queued)
    if queued:
        ident = Identification(
            True, queued.get("title"), queued.get("year"),
            queued.get("format", "Unknown"), queued.get("language"),
            0.99, queued.get("intro"))
    else:
        jpeg = prepared_jpeg(img)
        ident = get_ident().identify(img, jpeg)

    if not ident.identified or ident.confidence < threshold:
        return _record_unidentified(cfg, store, img, h, ident)

    meta = metadata.lookup(ident.title, ident.year)
    # Reject a fuzzy mis-match: if the provider returned a different film, don't let it
    # overwrite the name/poster/data we trust from identification.
    if is_manual and meta.matched and not _plausible_title(ident.title, meta.title):
        meta = MovieMeta(False)
    if not meta.matched and not is_manual:
        # auto-identified titles that don't resolve go to manual review
        return _record_unidentified(cfg, store, img, h, ident, reason="no metadata match")
    if not meta.matched:
        # a manual / Claude-Code identification we trust — keep it even without a metadata hit
        meta = MovieMeta(True, source="manual", title=ident.title, year=ident.year,
                         language=ident.language)
    elif is_manual:
        # trust our identified name over the provider's canonical title
        meta.title = ident.title

    # Poster: prefer the online poster; if none is found (or the download fails), fall back to the
    # item's own cover photo (orientation auto-corrected via EXIF) so every title still has an image.
    poster_rel = None
    mid = _movie_id(meta, ident, h)
    poster_dest = cfg.posters_dir / f"{_slug(mid)}.jpg"
    if meta.poster_url and _download_poster(meta.poster_url, poster_dest):
        poster_rel = f"posters/{poster_dest.name}"
    else:
        try:
            save_thumbnail(img, poster_dest, max_edge=600)
            poster_rel = f"posters/{poster_dest.name}"
            meta.raw["poster_from_cover"] = True
        except Exception:
            pass

    # Keep a web-viewable copy of THIS cover photo (orientation-corrected). One per source
    # image, so duplicate copies of a title accumulate into a gallery you can flip through.
    original_rel = None
    originals_dir = cfg.output_dir / "originals"
    original_dest = originals_dir / f"{_slug(mid)}-{h[:8]}.jpg"
    try:
        save_thumbnail(img, original_dest, max_edge=900, portrait=True)
        original_rel = f"originals/{original_dest.name}"
    except Exception:
        pass

    fmt = ident.format if ident.format != "Unknown" else "DVD"
    val = estimate(meta.title or ident.title, meta.year or ident.year, fmt,
                   meta.rating, cfg.resale.get("ebay_tld", "com"))

    movie = {
        "id": mid,
        "title": meta.title or ident.title,
        "year": meta.year or ident.year,
        "format": fmt,
        "category": meta.category,
        "genres": meta.genres,
        "language": meta.language or ident.language,
        "spoken_languages": meta.spoken_languages,
        "runtime": meta.runtime,
        "rating": meta.rating,
        "director": meta.director,
        "actors": meta.actors,
        "studio": meta.studio,
        "distributor": meta.distributor,
        "intro": make_intro(ident, meta),
        "tagline": meta.tagline,
        "overview": meta.overview,
        "poster": poster_rel,
        "backdrop": meta.backdrop_url,
        "original_image": original_rel,
        "images": [original_rel] if original_rel else [],
        "source": {"name": meta.source, "url": meta.source_url},
        "resale": val,
        "source_image": img.name,
        "confidence": round(ident.confidence, 3),
        "seen": False,
        "date_seen": None,
        "added_at": _now(),
    }
    store.upsert_movie(movie)
    if is_manual:
        store.remove_unidentified_by_hash(h)  # named via manual identification → no longer unidentified
    store.record(h, img.name, "identified", mid, _now())
    return True


def _record_unidentified(cfg, store, img, h, ident: Identification, reason="low confidence") -> bool:
    thumb = cfg.posters_dir / f"unid-{h[:12]}.jpg"
    try:
        save_thumbnail(img, thumb)
        thumb_rel = f"posters/{thumb.name}"
    except Exception:
        thumb_rel = None
    store.add_unidentified({
        "hash": h,
        "source_image": img.name,
        "thumbnail": thumb_rel,
        "guess_title": ident.title,
        "guess_year": ident.year,
        "guess_format": ident.format,
        "reason": reason,
        "added_at": _now(),
    })
    store.record(h, img.name, "unidentified", None, _now())
    return False


def _build_mock(cfg, store, stats, log) -> Stats:
    """Populate the catalog with sample data so the site can be demoed with no keys."""
    log("Mock mode — generating sample catalog (no providers/keys used).")
    tld = cfg.resale.get("ebay_tld", "com")
    for i, mk in enumerate(_MOCK):
        title, year, fmt = mk["title"], mk["year"], mk["format"]
        mid = f"{_slug(title)}-{year}"
        # The default image is the real movie poster (hotlinked from IMDb/OMDb — no copyrighted
        # files are stored in the repo). Extra gallery photos are generated placeholders that
        # stand in for "your own cover photos", to demo the multi-image gallery (arrows / zoom).
        n_photos = mk.get("photos", 1)
        images = []
        if mk.get("poster_url"):
            images.append(mk["poster_url"])
        else:
            dest = cfg.posters_dir / f"{mid}.jpg"
            make_placeholder_poster(title, dest, color=mk.get("color", (40, 44, 64)), subtitle=str(year))
            images.append(f"posters/{dest.name}")
        extra_labels = ["your cover photo", "back cover", "spine / sleeve"]
        for k in range(1, n_photos):
            dest = cfg.posters_dir / f"{mid}-{k + 1}.jpg"
            make_placeholder_poster(title, dest, color=(52, 52, 60),
                                    subtitle=extra_labels[(k - 1) % len(extra_labels)])
            images.append(f"posters/{dest.name}")
        streaming = None
        if mk.get("stream"):
            streaming = {"checked": True, "justwatch_url": "https://www.justwatch.com/",
                         "providers": [{"name": n, "type": "FLATRATE", "type_label": "Stream",
                                        "url": _STREAM_URL.get(n, "https://www.justwatch.com/")}
                                       for n in mk["stream"]]}
        seen = (i % 4 == 0)
        movie = {
            "id": mid, "title": title, "year": year, "format": fmt, "category": "Film",
            "genres": mk["genres"], "language": mk["language"], "spoken_languages": [mk["language"]],
            "runtime": mk["runtime"], "rating": mk["rating"], "director": mk.get("director"),
            "actors": mk.get("actors", []), "studio": mk.get("studio"), "distributor": None,
            "intro": mk["intro"], "tagline": None, "overview": mk["intro"],
            "poster": images[0], "images": images, "backdrop": None, "streaming": streaming,
            "source": {"name": "mock", "url": None},
            "resale": estimate(title, year, fmt, mk["rating"], tld),
            "source_image": f"(demo) {title}", "confidence": 0.99,
            "seen": seen, "date_seen": ("2024-02-14" if seen else None), "added_at": _now(),
        }
        store.upsert_movie(movie)
        store.record(f"mock-{mid}", movie["source_image"], "identified", mid, _now())
        stats.new += 1
        stats.identified += 1

    # a couple of sample unidentified items so that flow is demoable too
    for n, fmt in [("unreadable cover", "VHS"), ("blank tape", "VHS")]:
        store.add_unidentified({
            "hash": f"mock-unidentified-{_slug(n)}",
            "source_image": f"(demo) {n}", "thumbnail": None,
            "guess_title": None, "guess_year": None, "guess_format": fmt,
            "reason": "low confidence", "added_at": _now(),
        })
        stats.unidentified += 1
    store.save()
    _write_site(cfg, store)
    log(f"Done (mock). {stats}")
    return stats
