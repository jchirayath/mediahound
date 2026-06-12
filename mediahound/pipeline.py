"""Orchestration: scan input, identify → enrich → value → write, incrementally."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import requests

from .config import Config
from .identify import get_identifier
from .identify.base import Identification
from .imaging import make_placeholder_poster, prepared_jpeg, save_thumbnail
from .intro import make_intro
from .links import hear_links as _hear_links
from .links import listen_links as _listen_links
from .links import play_links as _play_links
from .links import read_links as _read_links
from .metadata import get_metadata_provider
from .metadata.base import AudiobookMeta, BookMeta, GameMeta, MovieMeta, MusicMeta
from .resale import estimate
from .store import Store, list_media_images, sha256_file

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_STOP = {"the", "a", "an", "of", "and", "vol", "volume", "part", "complete", "season",
         "collection", "edition", "special", "disc", "set", "series", "to", "in"}

# The bundled static app shell (HTML/JS/CSS/icons). Lives next to this package.
_WEB_TEMPLATE = Path(__file__).resolve().parent / "web"


def sync_web_assets(cfg: Config, log=lambda *_: None) -> None:
    """Refresh the static app shell (index.html, identify.html, favicon, assets/) in a library
    from the **installed package** template, so upgrading MediaHound updates the UI of an existing
    library. Only the app shell is overwritten — `data/`, `posters/`, `originals/`, `RawImages/`,
    `config.toml` and `netlify.toml` are never touched (the template doesn't contain them)."""
    import shutil
    out = cfg.output_dir
    if not _WEB_TEMPLATE.is_dir():
        return
    out.mkdir(parents=True, exist_ok=True)
    for item in _WEB_TEMPLATE.iterdir():
        target = out / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
        except OSError as exc:                       # never let a copy error break a build
            log(f"  web sync: couldn't update {item.name}: {exc}")


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
    return datetime.now(UTC).isoformat(timespec="seconds")


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
        r = requests.get(url, timeout=45, headers={"User-Agent": "MediaHound/0.1"})
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return True
    except requests.RequestException:
        return False


def _find_raw_image(input_dir: Path, name: str) -> Path | None:
    """Locate a source cover photo by basename under RawImages (root or a media subfolder)."""
    if not name:
        return None
    for cand in (input_dir / name, input_dir / "video" / name, input_dir / "audio" / name,
                 input_dir / "movies" / name, input_dir / "music" / name, input_dir / "books" / name):
        if cand.is_file():
            return cand
    return None


# RawImages subfolder that holds each media type's source photos.
_TYPE_FOLDER = {"movie": "video", "music": "audio", "book": "books", "game": "games",
                "audiobook": "audiobooks"}


def _sync_source_folder(cfg: Config, store: Store, m: dict, new_type: str, log) -> None:
    """Keep an item's source cover photo(s) in the RawImages subfolder that matches its media
    type (video → movies, audio → music, books → book). Idempotent: a photo already in place is left
    alone, so a reclassified title is correct *at the source* too — it won't snap back if
    corrections.json is ever cleared. Only moves files that stay inside RawImages."""
    sub = _TYPE_FOLDER.get(new_type, "video")
    dest_dir = (cfg.input_dir / sub).resolve()
    names = set()
    if m.get("source_image"):
        names.add(m["source_image"])
    for rec in store.manifest.values():
        if rec.get("movie_id") == m["id"] and rec.get("file"):
            names.add(rec["file"])
    for name in names:
        if "/" in name or "\\" in name:          # basenames only — never traverse
            continue
        cur = _find_raw_image(cfg.input_dir, name)
        if cur is None or cur.resolve().parent == dest_dir:
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / name
        if target.exists():
            log(f"  correction: source photo {name} already in RawImages/{sub}/ (kept)")
            continue
        try:
            cur.rename(target)
            log(f"  correction: moved source photo {name} → RawImages/{sub}/")
        except OSError as exc:
            log(f"  correction: could not move {name}: {exc}")


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

# Sample music releases for --mock (curated; generated placeholder art, no copyrighted sleeves).
_MOCK_MUSIC = [
    dict(title="The Dark Side of the Moon", cover_url="https://coverartarchive.org/release-group/f5093c06-23e3-404f-aeaa-40f72885ee3a/front", artist="Pink Floyd", year=1973, format="Vinyl",
         label="Harvest", genres=["Progressive Rock"], rating=9.2, color=(18, 18, 22),
         tracklist=["Speak to Me", "Breathe (In the Air)", "On the Run", "Time", "Money",
                    "Us and Them", "Brain Damage", "Eclipse"],
         intro="A seamless suite on madness and time — heard best on vinyl, end to end."),
    dict(title="Rumours", cover_url="https://is1-ssl.mzstatic.com/image/thumb/Music124/v4/4d/13/ba/4d13bac3-d3d5-7581-2c74-034219eadf2b/081227970949.jpg/600x600bb.jpg", artist="Fleetwood Mac", year=1977, format="Vinyl",
         label="Warner Bros.", genres=["Soft Rock", "Pop Rock"], rating=8.9, color=(74, 54, 32),
         tracklist=["Second Hand News", "Dreams", "Never Going Back Again", "Go Your Own Way",
                    "The Chain", "Gold Dust Woman"],
         intro="Heartbreak turned into immaculate harmonies — a band falling apart, beautifully."),
    dict(title="Thriller", cover_url="https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/32/4f/fd/324ffda2-9e51-8f6a-0c2d-c6fd2b41ac55/074643811224.jpg/600x600bb.jpg", artist="Michael Jackson", year=1982, format="Cassette",
         label="Epic", genres=["Pop", "Funk", "R&B"], rating=9.0, color=(40, 20, 24),
         tracklist=["Wanna Be Startin' Somethin'", "Thriller", "Beat It", "Billie Jean",
                    "Human Nature", "P.Y.T."],
         intro="The best-selling album ever made — pop, funk and a werewolf, on one tape."),
    dict(title="Kind of Blue", cover_url="https://is1-ssl.mzstatic.com/image/thumb/Music/7f/9f/d6/mzi.vtnaewef.jpg/600x600bb.jpg", artist="Miles Davis", year=1959, format="Vinyl",
         label="Columbia", genres=["Jazz", "Modal Jazz"], rating=9.4, color=(20, 32, 52),
         tracklist=["So What", "Freddie Freeloader", "Blue in Green", "All Blues", "Flamenco Sketches"],
         intro="Modal jazz at its most serene — the record almost every collection starts with."),
    dict(title="Nevermind", cover_url="https://coverartarchive.org/release-group/1b022e01-4da6-387b-8658-8678046e4cef/front", artist="Nirvana", year=1991, format="CD",
         label="DGC", genres=["Grunge", "Alternative Rock"], rating=8.7, color=(20, 48, 60),
         tracklist=["Smells Like Teen Spirit", "In Bloom", "Come as You Are", "Lithium",
                    "Polly", "Drain You"],
         intro="The CD that dragged the underground overground — louder, quieter, louder."),
    dict(title="The Miseducation of Lauryn Hill", cover_url="https://is1-ssl.mzstatic.com/image/thumb/Music125/v4/09/6b/55/096b55c4-ee8f-23bd-df8f-0ca0821f3028/886446727189.jpg/600x600bb.jpg", artist="Lauryn Hill", year=1998, format="CD",
         label="Ruffhouse / Columbia", genres=["Neo Soul", "Hip Hop", "R&B"], rating=9.1,
         color=(34, 52, 30),
         tracklist=["Lost Ones", "Ex-Factor", "To Zion", "Doo Wop (That Thing)",
                    "Everything Is Everything"],
         intro="Soul, hip-hop and gospel fused into one of the finest debuts ever pressed."),
]

# Sample books for --mock (generated placeholder covers; no copyrighted jackets stored).
_OL_COVER = "https://covers.openlibrary.org/b/isbn/{}-L.jpg"      # real book covers, hotlinked (CC)
_STEAM_CAP = "https://cdn.cloudflare.steamstatic.com/steam/apps/{}/library_600x900.jpg"  # game box art

_MOCK_BOOKS = [
    dict(title="Dune", author="Frank Herbert", year=1965, format="Paperback", publisher="Ace",
         genres=["Science Fiction"], rating=8.7, page_count=688, isbn="9780441013593",
         cover_url=_OL_COVER.format("9780441013593"), color=(54, 38, 18),
         intro="Spice, sandworms and prophecy — the desert epic that defined a genre."),
    dict(title="The Left Hand of Darkness", author="Ursula K. Le Guin", year=1969, format="Paperback",
         publisher="Ace", genres=["Science Fiction"], rating=8.4, page_count=304, isbn="9780441478125",
         cover_url=_OL_COVER.format("9780441478125"), color=(28, 40, 58),
         intro="A lone envoy on a frozen world where gender is fluid — quietly revolutionary."),
    dict(title="Pride and Prejudice", author="Jane Austen", year=1813, format="Hardcover",
         publisher="T. Egerton", genres=["Classic", "Romance"], rating=8.6, page_count=432,
         isbn="9780141439518", cover_url=_OL_COVER.format("9780141439518"), color=(64, 44, 30),
         intro="Wit, manners and Mr. Darcy — the comedy of misjudgement that never ages."),
]

_MOCK_GAMES = [
    dict(title="The Witcher 3: Wild Hunt", year=2015, format="PC",
         developer="CD Projekt Red", publisher="CD Projekt", genres=["RPG"],
         platforms=["PC", "PS5", "Xbox"], players="1", esrb="M", rating=9.3,
         cover_url=_STEAM_CAP.format("292030"), color=(40, 20, 18),
         intro="A vast, story-rich hunt across a war-torn world — choices that actually bite."),
    dict(title="Hades", year=2020, format="Switch",
         developer="Supergiant Games", publisher="Supergiant Games", genres=["Roguelike"],
         platforms=["Switch", "PC", "PS5", "Xbox"], players="1", esrb="T", rating=9.3,
         cover_url=_STEAM_CAP.format("1145360"), color=(28, 18, 40),
         intro="Fight out of hell, die, learn, repeat — a roguelike where the story keeps going."),
    dict(title="Stardew Valley", year=2016, format="PS4",
         developer="ConcernedApe", publisher="ConcernedApe", genres=["Simulation", "RPG"],
         platforms=["PC", "Switch", "PS4", "Xbox"], players="1-4", esrb="E10+", rating=8.9,
         cover_url=_STEAM_CAP.format("413150"), color=(26, 44, 30),
         intro="Inherit a run-down farm and quietly fall in love with small-town life."),
]

_MOCK_AUDIOBOOKS = [
    dict(title="Project Hail Mary", author="Andy Weir", narrator="Ray Porter", year=2021,
         format="Audible", duration=970, publisher="Audible Studios", genres=["Science Fiction"],
         rating=8.9, isbn="9780593135204", cover_url=_OL_COVER.format("9780593135204"),
         color=(20, 36, 52),
         intro="A lone astronaut, an amnesiac mystery, and a buddy comedy across the stars."),
    dict(title="Born a Crime", author="Trevor Noah", narrator="Trevor Noah", year=2016,
         format="Audible", duration=534, publisher="Audible Studios", genres=["Memoir"],
         rating=9.1, isbn="9780399588174", cover_url=_OL_COVER.format("9780399588174"),
         color=(48, 30, 18),
         intro="Read by the author — funnier and sharper for it; a childhood under apartheid."),
    dict(title="Becoming", author="Michelle Obama", narrator="Michelle Obama", year=2018,
         format="CD", duration=1140, publisher="Random House Audio", genres=["Memoir"],
         rating=8.8, isbn="9781524763138", cover_url=_OL_COVER.format("9781524763138"),
         color=(60, 44, 30),
         intro="The former First Lady reads her own story — intimate, and better for her voice."),
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
    sync_web_assets(cfg, log)          # keep an existing library's UI current with the installed version
    store = Store(cfg.data_dir)
    stats = Stats()

    if mock:
        return _build_mock(cfg, store, stats, log)

    # A forced full rebuild re-adds every item; silence the change log so it doesn't record
    # thousands of spurious "add" events for items that already existed.
    store.events.enabled = not force
    if force:
        # full reprocess → rebuild the collection from scratch so stale fields (e.g. old
        # image paths) don't accumulate. seen/identify/corrections files are untouched.
        store.collection = []
        store._collection_by_id = {}
        store.unidentified = []

    images = list_media_images(cfg.input_dir)
    stats.scanned = len(images)
    n_audio = sum(1 for _, mt in images if mt == "music")
    n_book = sum(1 for _, mt in images if mt == "book")
    n_game = sum(1 for _, mt in images if mt == "game")
    n_abook = sum(1 for _, mt in images if mt == "audiobook")
    log(f"Scanning {cfg.input_dir} → {len(images)} image(s) "
        f"({len(images) - n_audio - n_book - n_game - n_abook} video, {n_audio} audio, "
        f"{n_book} books, {n_game} games, {n_abook} audiobooks)")

    providers = None
    if images:
        if online:
            movie_meta = _CachedMetadata(get_metadata_provider(cfg), cfg.data_dir / ".metadata-cache.json")
            providers = {"movie": movie_meta,
                         "music": get_metadata_provider(cfg, "music") if n_audio else _NullMetadata(),
                         "book": get_metadata_provider(cfg, "book") if n_book else _NullMetadata(),
                         "game": get_metadata_provider(cfg, "game") if n_game else _NullMetadata(),
                         "audiobook": get_metadata_provider(cfg, "audiobook") if n_abook else _NullMetadata()}
            log(f"Metadata: {movie_meta.name} (movies) + "
                f"{providers['music'].name if n_audio else 'none'} (music) + "
                f"{providers['book'].name if n_book else 'none'} (books) + "
                f"{providers['game'].name if n_game else 'none'} (games) + "
                f"{providers['audiobook'].name if n_abook else 'none'} (audiobooks), online + cached")
        else:
            providers = {"movie": _NullMetadata(), "music": _NullMetadata(),
                         "book": _NullMetadata(), "game": _NullMetadata(),
                         "audiobook": _NullMetadata()}
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
    for idx, (img, mtype) in enumerate(images, 1):
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
            ok = _process_one(cfg, store, img, h, get_ident, providers, threshold, mtype, online)
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

    if providers and hasattr(providers["movie"], "save"):
        providers["movie"].save()         # persist the movie metadata cache
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
    _providers: dict = {}

    def _meta_provider(mt: str):
        if mt not in _providers:
            _providers[mt] = get_metadata_provider(cfg, mt)
        return _providers[mt]

    # per-type fields, cleared when an item switches to a *different* type
    _TYPE_ONLY = {
        "movie": ("director", "actors", "runtime", "studio", "distributor", "tagline",
                  "spoken_languages", "streaming"),
        "music": ("artist", "label", "tracklist", "disc_count", "barcode", "catalog_no", "listen"),
        "book": ("author", "publisher", "page_count", "isbn", "series", "read"),
        "game": ("developer", "publisher", "platforms", "players", "esrb", "play"),
        "audiobook": ("author", "narrator", "duration", "publisher", "isbn", "listen"),
    }
    # valid formats per type — an incompatible format is normalised when a title switches type.
    # For games the "format" dimension is the platform; for audiobooks it's the medium.
    _FORMATS = {"movie": ("DVD", "VHS", "Blu-ray", "VideoCD", "Unknown"),
                "music": ("CD", "Vinyl", "Cassette", "Unknown"),
                "book": ("Hardcover", "Paperback", "Mass Market", "eBook", "Audiobook", "Unknown"),
                "game": ("Switch", "PS5", "PS4", "Xbox", "PC", "Retro", "Unknown"),
                "audiobook": ("Audible", "CD", "MP3-CD", "Cassette", "Digital", "Unknown")}
    tld = cfg.resale.get("ebay_tld", "com")
    requery_consumed = False

    for mid, c in list(corr.items()):
        if c.get("delete"):
            if store.delete_movie(mid):
                store.events.add("remove", mid)
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
        # move a title between Movies / Music / Books (clears the *other* types' stale fields)
        if c.get("media_type") in _FORMATS:
            new = c["media_type"]
            if new != m.get("media_type", "movie"):
                m["media_type"] = new
                keep = set(_TYPE_ONLY.get(new, ()))      # fields the new type also uses (e.g. publisher)
                for t, fields in _TYPE_ONLY.items():
                    if t != new:
                        for f in fields:
                            if f not in keep:
                                m.pop(f, None)
                log(f"  correction: moved {mid} → {new}")
            # a format that doesn't belong to the new type (e.g. DVD on a book) is normalised
            # (idempotent; runs even if the type already matches, to repair earlier moves)
            if m.get("format") and m["format"] not in _FORMATS[new]:
                m["format"] = _FORMATS[new][0]
            # keep the source photo in the matching RawImages/<video|audio|books> folder (idempotent)
            _sync_source_folder(cfg, store, m, new, log)
        if "artist" in c:
            m["artist"] = c["artist"] or None
        if "label" in c:
            m["label"] = c["label"] or None
        if "author" in c:
            m["author"] = c["author"] or None
        if "publisher" in c:
            m["publisher"] = c["publisher"] or None
        if "developer" in c:
            m["developer"] = c["developer"] or None
        if "narrator" in c:
            m["narrator"] = c["narrator"] or None
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
        if c.get("requery") and need_meta:
            mt = m.get("media_type", "movie")
            prov = _meta_provider(mt)
            try:
                if mt == "music":
                    nm = prov.lookup(m["title"], artist=m.get("artist"))
                elif mt == "book":
                    nm = prov.lookup(m["title"], author=m.get("author"))
                elif mt == "audiobook":
                    nm = prov.lookup(m["title"], author=m.get("author"), narrator=m.get("narrator"))
                elif mt == "game":
                    nm = prov.lookup(m["title"], year=m.get("year"))
                else:
                    nm = prov.lookup(m["title"], m.get("year"))
            except Exception as exc:
                log(f"  correction: re-query failed for {mid}: {exc}")
                nm = None
            if nm and getattr(nm, "matched", False) and _plausible_title(m["title"], nm.title):
                {"music": _apply_meta_to_music, "book": _apply_meta_to_book,
                 "game": _apply_meta_to_game, "audiobook": _apply_meta_to_audiobook}.get(
                     mt, _apply_meta_to_movie)(cfg, m, nm)
                c["requery"] = False  # consumed → don't re-query every build
                requery_consumed = True
                log(f"  correction: re-queried {mid} ({mt}) → {nm.title} ({nm.source})")
            elif nm and getattr(nm, "matched", False):
                # a different title came back — keep the trusted data, don't corrupt it
                c["requery"] = False
                requery_consumed = True
                log(f"  correction: re-query for {mid} kept existing data (implausible: {nm.title!r})")
        # manual studio/distributor edits win over any re-query (movies only)
        if m.get("media_type", "movie") == "movie":
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


def _apply_meta_to_music(cfg: Config, m: dict, meta: MusicMeta) -> None:
    """Overwrite a music item's enrichment fields from a fresh music lookup."""
    m["title"] = meta.title or m["title"]
    m["artist"] = meta.artist or m.get("artist")
    m["year"] = meta.year or m.get("year")
    m["label"] = meta.label
    m["genres"] = meta.genres
    m["rating"] = meta.rating
    m["tracklist"] = meta.tracklist
    m["disc_count"] = meta.disc_count
    m["barcode"] = meta.barcode
    m["catalog_no"] = meta.catalog_no
    m["overview"] = meta.overview
    m["listen"] = _listen_links(m.get("artist") or "", m["title"])
    m["source"] = {"name": meta.source, "url": meta.source_url}
    if meta.cover_url:
        dest = cfg.posters_dir / f"{_slug(m['id'])}.jpg"
        if _download_poster(meta.cover_url, dest):
            m["poster"] = f"posters/{dest.name}"


def _apply_meta_to_book(cfg: Config, m: dict, meta: BookMeta) -> None:
    """Overwrite a book's enrichment fields from a fresh Open Library lookup."""
    m["title"] = meta.title or m["title"]
    m["author"] = meta.author or m.get("author")
    m["year"] = meta.year or m.get("year")
    m["publisher"] = meta.publisher
    m["genres"] = meta.genres
    m["rating"] = meta.rating
    m["page_count"] = meta.page_count
    m["isbn"] = meta.isbn
    m["series"] = meta.series
    m["overview"] = meta.overview
    m["read"] = _read_links(m.get("author") or "", m["title"])
    m["source"] = {"name": meta.source, "url": meta.source_url}
    if meta.cover_url:
        dest = cfg.posters_dir / f"{_slug(m['id'])}.jpg"
        if _download_poster(meta.cover_url, dest):
            m["poster"] = f"posters/{dest.name}"


def _apply_meta_to_audiobook(cfg: Config, m: dict, meta: AudiobookMeta) -> None:
    """Overwrite an audiobook's enrichment fields from a fresh Open Library + LibriVox lookup."""
    m["title"] = meta.title or m["title"]
    m["author"] = meta.author or m.get("author")
    m["narrator"] = meta.narrator or m.get("narrator")
    m["year"] = meta.year or m.get("year")
    m["publisher"] = meta.publisher or m.get("publisher")
    m["genres"] = meta.genres
    m["rating"] = meta.rating
    m["isbn"] = meta.isbn or m.get("isbn")
    m["duration"] = meta.duration or m.get("duration")
    m["overview"] = meta.overview or m.get("overview")
    m["listen"] = _hear_links(m.get("author") or "", m["title"])
    m["source"] = {"name": meta.source, "url": meta.source_url}
    if meta.cover_url:
        dest = cfg.posters_dir / f"{_slug(m['id'])}.jpg"
        if _download_poster(meta.cover_url, dest):
            m["poster"] = f"posters/{dest.name}"


def _apply_meta_to_game(cfg: Config, m: dict, meta: GameMeta) -> None:
    """Overwrite a game's enrichment fields from a fresh Wikidata lookup."""
    m["title"] = meta.title or m["title"]
    m["developer"] = meta.developer or m.get("developer")
    m["publisher"] = meta.publisher or m.get("publisher")
    m["year"] = meta.year or m.get("year")
    m["genres"] = meta.genres
    m["platforms"] = meta.platforms
    m["players"] = meta.players
    m["esrb"] = meta.esrb
    m["rating"] = meta.rating
    m["overview"] = meta.overview
    m["play"] = _play_links(m["title"], m.get("format"))
    m["source"] = {"name": meta.source, "url": meta.source_url}
    if meta.cover_url:
        dest = cfg.posters_dir / f"{_slug(m['id'])}.jpg"
        if _download_poster(meta.cover_url, dest):
            m["poster"] = f"posters/{dest.name}"


def _enrich_streaming(cfg: Config, store: Store, log, refresh: bool = False) -> None:
    """Fill each movie's 'streaming' (where-to-watch) via JustWatch. Skips already-checked
    titles unless refresh=True. Disabled with [streaming] enabled=false."""
    if not cfg.streaming.get("enabled", True):
        return
    pending = [m for m in store.collection if refresh or not m.get("streaming")]
    if not pending:
        return
    import requests

    from . import streaming as sx
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

# Personal/admin-only fields that must NEVER appear in the published catalog. Stripped from
# collection.json + bundle.js at build time; rendered only in the admin view (applied there
# client-side from corrections.json / loans.json, which `publish.py` also excludes). See
# docs/design/04-personal-catalog.md and PRIVACY.md.
PRIVATE_FIELDS = ("my_rating", "my_note", "tags", "loan")


def _public_item(m: dict) -> dict:
    """A copy of a catalog item with personal fields removed (safe to publish)."""
    return {k: v for k, v in m.items() if k not in PRIVATE_FIELDS}


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

    # Public catalog: strip personal/admin-only fields so they can never leak into a
    # published site (bundle.js + collection.json are both deployed). The admin view applies
    # ratings/notes/tags/loans client-side from the (publish-excluded) corrections/loans files.
    public_collection = [_public_item(m) for m in store.collection]
    (cfg.data_dir / "collection.json").write_text(
        json.dumps(public_collection, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also emit a JS bundle so index.html works when opened directly (file://),
    # where browsers block fetch() of local JSON. The page prefers this global and
    # falls back to fetching the JSON when served over http(s).
    view = json.loads((cfg.data_dir / "view-config.json").read_text(encoding="utf-8"))
    payload = {"site": site, "collection": public_collection,
               "unidentified": store.unidentified, "view": view}
    bundle = "window.MEDIAHOUND_DATA = " + json.dumps(payload, ensure_ascii=False) + ";"
    (cfg.data_dir / "bundle.js").write_text(bundle, encoding="utf-8")

    # Syndication feeds (JSON Feed + RSS) of recently-added items — published with the site so
    # anyone can subscribe. Off with [feeds] enabled = false. Uses public items only.
    if cfg.feeds.get("enabled", True):
        _write_feeds(cfg, site, public_collection)

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

    # PWA: stamp the same content version into the service worker so its cache name changes on a
    # rebuild — the browser then activates the new SW, drops the old cache, and the app updates.
    sw = cfg.output_dir / "sw.js"
    if sw.is_file():
        text = re.sub(r'const VERSION = "[^"]*"', f'const VERSION = "{ver}"',
                      sw.read_text(encoding="utf-8"))
        sw.write_text(text, encoding="utf-8")


def _write_feeds(cfg: Config, site: dict, collection: list, limit: int = 30) -> None:
    """Emit feed.json (JSON Feed 1.1) and feed.xml (RSS 2.0) of the most recently-added items."""
    import json
    from email.utils import format_datetime
    from xml.sax.saxutils import escape

    base = str(cfg.feeds.get("site_url", "") or "").rstrip("/")
    recent = sorted(collection, key=lambda m: str(m.get("added_at") or ""), reverse=True)[:limit]
    title = site.get("title") or "My Media Collection"

    def _line(m: dict) -> str:
        mt = m.get("media_type")
        who = (m.get("artist") if mt == "music" else m.get("author") if mt in ("book", "audiobook")
               else m.get("developer") if mt == "game" else m.get("director"))
        bits = [str(m.get("year")) if m.get("year") else None, m.get("format"), who]
        return " · ".join(b for b in bits if b)

    items = [{
        "id": base + "/#" + str(m.get("id")) if base else str(m.get("id")),
        "title": m.get("title") or "Untitled",
        "content_text": (m.get("intro") or m.get("overview") or _line(m) or "").strip(),
        "image": (base + "/" + m["poster"]) if (base and m.get("poster") and not str(m["poster"]).startswith("http")) else m.get("poster"),
        "date_published": m.get("added_at"),
        "_summary": _line(m),
    } for m in recent]

    feed_json = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": title,
        "description": site.get("subtitle") or "",
        "home_page_url": base or None,
        "feed_url": (base + "/data/feed.json") if base else None,
        "items": [{k: v for k, v in it.items() if not k.startswith("_") and v is not None}
                  for it in items],
    }
    (cfg.data_dir / "feed.json").write_text(
        json.dumps(feed_json, indent=2, ensure_ascii=False), encoding="utf-8")

    def _rss_item(it: dict) -> str:
        desc = it["content_text"] or it.get("_summary") or ""
        when = ""
        if it.get("date_published"):
            try:
                when = f"<pubDate>{format_datetime(datetime.fromisoformat(it['date_published']))}</pubDate>"
            except ValueError:
                when = ""
        return (f"    <item><title>{escape(it['title'])}</title>"
                f"<guid isPermaLink=\"false\">{escape(it['id'])}</guid>"
                f"<description>{escape(desc)}</description>{when}</item>")

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>\n'
        f"  <title>{escape(title)}</title>\n"
        f"  <link>{escape(base or 'about:blank')}</link>\n"
        f"  <description>{escape(site.get('subtitle') or '')}</description>\n"
        + "\n".join(_rss_item(it) for it in items)
        + "\n</channel></rss>\n"
    )
    (cfg.data_dir / "feed.xml").write_text(rss, encoding="utf-8")


def _finalize_media(cfg, store, img, h, ident, item, cover_url, is_manual, portrait=True) -> bool:
    """Shared tail for music/book/game records (the same poster/original/upsert/record dance for
    every non-movie type). Downloads the online cover, else falls back to the cover photo, keeps an
    orientation-corrected original, attaches the common fields, then upserts + records."""
    mid = item["id"]
    poster_rel = None
    poster_dest = cfg.posters_dir / f"{_slug(mid)}.jpg"
    if cover_url and _download_poster(cover_url, poster_dest):
        poster_rel = f"posters/{poster_dest.name}"
    else:
        try:
            save_thumbnail(img, poster_dest, max_edge=600)                  # fall back to the photo
            poster_rel = f"posters/{poster_dest.name}"
        except Exception:
            pass

    original_rel = None
    original_dest = cfg.output_dir / "originals" / f"{_slug(mid)}-{h[:8]}.jpg"
    try:
        save_thumbnail(img, original_dest, max_edge=900, portrait=portrait)
        original_rel = f"originals/{original_dest.name}"
    except Exception:
        pass

    images = [poster_rel] if poster_rel else []
    if original_rel and original_rel not in images:
        images.append(original_rel)
    item["poster"] = poster_rel
    item["images"] = images
    item["source_image"] = img.name
    item["confidence"] = round(ident.confidence, 3)
    item.setdefault("seen", False)
    item.setdefault("date_seen", None)
    item["added_at"] = _now()
    existed = store.find_movie(mid) is not None
    store.upsert_movie(item)
    if is_manual:
        store.remove_unidentified_by_hash(h)
    store.record(h, img.name, "identified", mid, _now())
    store.events.add("change" if existed else "add", mid)
    return True


def _process_music(cfg, store, img, h, ident, provider, is_manual) -> bool:
    """Enrich an audio cover (CD/vinyl/cassette) via the music provider and write a music record."""
    meta = provider.lookup(ident.title, artist=ident.artist)
    if not getattr(meta, "matched", False) and not is_manual:
        return _record_unidentified(cfg, store, img, h, ident, reason="no music match")
    if not getattr(meta, "matched", False):
        meta = MusicMeta(True, source="manual", title=ident.title, artist=ident.artist)

    title = meta.title or ident.title
    artist = meta.artist
    mid = _slug(f"{artist or ''}-{title}-{meta.year or ident.year or h[:6]}")
    fmt = ident.format if ident.format and ident.format != "Unknown" else (meta.format or "CD")
    year = meta.year or ident.year
    genre = meta.genres[0].lower() if meta.genres else None
    intro = (f"A {year // 10 * 10}s {genre} record worth spinning." if (year and genre)
             else (f"{artist} — {title}." if artist else title))

    item = {
        "id": mid, "media_type": "music", "title": title, "artist": artist,
        "year": year, "format": fmt, "label": meta.label, "genres": meta.genres,
        "rating": meta.rating, "tracklist": meta.tracklist, "disc_count": meta.disc_count,
        "barcode": meta.barcode, "catalog_no": meta.catalog_no, "intro": intro,
        "overview": meta.overview,
        "listen": _listen_links(artist or "", title),
        "source": {"name": meta.source, "url": meta.source_url},
        "resale": estimate(f"{artist or ''} {title}".strip(), year, fmt, meta.rating,
                           cfg.resale.get("ebay_tld", "com")),
    }
    return _finalize_media(cfg, store, img, h, ident, item, meta.cover_url, is_manual, portrait=False)


def _process_book(cfg, store, img, h, ident, provider, is_manual) -> bool:
    """Enrich a book cover via the book provider (Open Library) and write a book record."""
    meta = provider.lookup(ident.title, author=ident.artist)
    if not getattr(meta, "matched", False) and not is_manual:
        return _record_unidentified(cfg, store, img, h, ident, reason="no book match")
    if not getattr(meta, "matched", False):
        meta = BookMeta(True, source="manual", title=ident.title, author=ident.artist)

    title = meta.title or ident.title
    author = meta.author
    mid = _slug(f"{author or ''}-{title}-{meta.year or ident.year or h[:6]}")
    fmt = ident.format if ident.format and ident.format != "Unknown" else (meta.format or "Paperback")
    year = meta.year or ident.year
    genre = meta.genres[0].lower() if meta.genres else None
    intro = (f"A {genre} book worth a read." if genre
             else (f"{author} — {title}." if author else title))

    item = {
        "id": mid, "media_type": "book", "title": title, "author": author,
        "year": year, "format": fmt, "publisher": meta.publisher, "genres": meta.genres,
        "rating": meta.rating, "page_count": meta.page_count, "isbn": meta.isbn,
        "series": meta.series, "intro": intro, "overview": meta.overview,
        "read": _read_links(author or "", title),
        "source": {"name": meta.source, "url": meta.source_url},
        "resale": estimate(f"{author or ''} {title}".strip(), year, fmt, meta.rating,
                           cfg.resale.get("ebay_tld", "com")),
    }
    return _finalize_media(cfg, store, img, h, ident, item, meta.cover_url, is_manual, portrait=True)


def _process_game(cfg, store, img, h, ident, provider, is_manual) -> bool:
    """Enrich a game cover/box via the game provider (Wikidata) and write a game record.
    Platform is the game's `format` dimension (Switch | PS5 | Xbox | PC | Retro …)."""
    meta = provider.lookup(ident.title, year=ident.year)
    if not getattr(meta, "matched", False) and not is_manual:
        return _record_unidentified(cfg, store, img, h, ident, reason="no game match")
    if not getattr(meta, "matched", False):
        meta = GameMeta(True, source="manual", title=ident.title)

    title = meta.title or ident.title
    mid = _slug(f"{title}-{meta.year or ident.year or h[:6]}")
    # the box's platform (from OCR) wins; else the provider's primary platform; else PC
    fmt = ident.format if ident.format and ident.format != "Unknown" else (meta.format or "PC")
    year = meta.year or ident.year
    genre = meta.genres[0].lower() if meta.genres else None
    dev = meta.developer
    intro = (f"A {genre} game worth a playthrough." if genre
             else (f"{dev} — {title}." if dev else title))

    item = {
        "id": mid, "media_type": "game", "title": title, "developer": dev,
        "publisher": meta.publisher, "year": year, "format": fmt, "genres": meta.genres,
        "platforms": meta.platforms, "players": meta.players, "esrb": meta.esrb,
        "rating": meta.rating, "intro": intro, "overview": meta.overview,
        "play": _play_links(title, fmt),
        "source": {"name": meta.source, "url": meta.source_url},
        "resale": estimate(title, year, fmt, meta.rating, cfg.resale.get("ebay_tld", "com"),
                           media_type="game"),
    }
    return _finalize_media(cfg, store, img, h, ident, item, meta.cover_url, is_manual, portrait=True)


def _process_audiobook(cfg, store, img, h, ident, provider, is_manual) -> bool:
    """Enrich an audiobook cover via the audiobook provider (Open Library + LibriVox)."""
    meta = provider.lookup(ident.title, author=ident.artist)
    if not getattr(meta, "matched", False) and not is_manual:
        return _record_unidentified(cfg, store, img, h, ident, reason="no audiobook match")
    if not getattr(meta, "matched", False):
        meta = AudiobookMeta(True, source="manual", title=ident.title, author=ident.artist)

    title = meta.title or ident.title
    author = meta.author
    mid = _slug(f"{author or ''}-{title}-{meta.year or ident.year or h[:6]}")
    fmt = ident.format if ident.format and ident.format != "Unknown" else (meta.format or "Audible")
    year = meta.year or ident.year
    hrs = f"{meta.duration // 60}h {meta.duration % 60}m" if meta.duration else None
    intro = (f"An audiobook{f' read by {meta.narrator}' if meta.narrator else ''}"
             f"{f' — {hrs}' if hrs else ''}." if (meta.narrator or hrs)
             else (f"{author} — {title}." if author else title))

    item = {
        "id": mid, "media_type": "audiobook", "title": title, "author": author,
        "narrator": meta.narrator, "year": year, "format": fmt, "duration": meta.duration,
        "publisher": meta.publisher, "genres": meta.genres, "rating": meta.rating,
        "isbn": meta.isbn, "intro": intro, "overview": meta.overview,
        "listen": _hear_links(author or "", title),
        "source": {"name": meta.source, "url": meta.source_url},
        "resale": estimate(f"{author or ''} {title}".strip(), year, fmt, meta.rating,
                           cfg.resale.get("ebay_tld", "com")),
    }
    return _finalize_media(cfg, store, img, h, ident, item, meta.cover_url, is_manual, portrait=True)


class _FixedProvider:
    """One-shot provider that returns an already-resolved meta (used when a barcode/ISBN has pinned
    the exact release/edition, so we skip the fuzzy title search entirely)."""
    name = "barcode"

    def __init__(self, meta):
        self.meta = meta

    def lookup(self, title, year=None, **kw):
        return self.meta


def _process_one(cfg, store, img, h, get_ident, providers, threshold, media_type="movie",
                 online=False) -> bool:
    queued = store.queued_identity(h)
    # discard: the user deleted this item in manual identification
    if queued and queued.get("delete"):
        store.remove_unidentified_by_hash(h)
        rec = store.manifest.get(h)
        if rec and rec.get("movie_id") and store.delete_movie(rec["movie_id"]):
            store.events.add("remove", rec["movie_id"])
        store.record(h, img.name, "deleted", None, _now())
        return None
    is_manual = bool(queued)
    if queued:
        ident = Identification(
            True, queued.get("title"), queued.get("year"),
            queued.get("format", "Unknown"), queued.get("language"),
            0.99, queued.get("intro"), queued.get("artist"))
    else:
        # Barcode first (exact > fuzzy OCR): decode locally, resolve online. Music barcodes pin
        # the exact release — write it straight away, skipping OCR and the plausibility guard.
        bm = _try_barcode(cfg, img, media_type) if online else None
        # An ISBN (978/979) self-identifies as a book even in a mixed folder.
        bm_type = bm["media_type"] if bm else media_type
        if bm and bm_type == "music":
            ident = Identification(True, bm["title"], bm["year"], "Unknown", None, 0.99,
                                   None, bm["artist"])
            return _process_music(cfg, store, img, h, ident, _FixedProvider(bm["meta"]), True)
        if bm and bm_type == "book":
            ident = Identification(True, bm["title"], bm["year"], "Unknown", None, 0.99,
                                   None, bm.get("author"))
            return _process_book(cfg, store, img, h, ident, _FixedProvider(bm["meta"]), True)
        if bm and bm_type == "game":            # game: trust the UPC product title, then enrich
            is_manual = True
            ident = Identification(True, bm["title"], bm.get("year"), "Unknown", None, 0.99)
            return _process_game(cfg, store, img, h, ident, providers["game"], is_manual)
        if bm:                                  # movie: trust the UPC product title, then enrich
            is_manual = True
            ident = Identification(True, bm["title"], bm.get("year"), "Unknown", None, 0.99)
        else:
            jpeg = prepared_jpeg(img)
            ident = get_ident().identify(img, jpeg)

    if not ident.identified or ident.confidence < threshold:
        return _record_unidentified(cfg, store, img, h, ident)

    if media_type == "music":
        return _process_music(cfg, store, img, h, ident, providers["music"], is_manual)
    if media_type == "book":
        return _process_book(cfg, store, img, h, ident, providers["book"], is_manual)
    if media_type == "game":
        return _process_game(cfg, store, img, h, ident, providers["game"], is_manual)
    if media_type == "audiobook":
        return _process_audiobook(cfg, store, img, h, ident, providers["audiobook"], is_manual)

    metadata = providers["movie"]
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
        "media_type": "movie",
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
    existed = store.find_movie(mid) is not None
    store.upsert_movie(movie)
    if is_manual:
        store.remove_unidentified_by_hash(h)  # named via manual identification → no longer unidentified
    store.record(h, img.name, "identified", mid, _now())
    store.events.add("change" if existed else "add", mid)
    return True


def _try_barcode(cfg: Config, img: Path, media_type: str) -> dict | None:
    """Decode a barcode from the cover photo and resolve it (music release / movie product).
    Returns None on no barcode / no match / decoder unavailable — never raises."""
    from . import barcode
    try:
        for upc in barcode.decode_image(img):
            match = barcode.lookup(cfg, upc, media_type)
            if match:
                return match
    except Exception:                                    # noqa: BLE001 - never break a build
        return None
    return None


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
            "id": mid, "media_type": "movie", "title": title, "year": year, "format": fmt, "category": "Film",
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

    # --- music releases (CDs / vinyl / cassettes) ------------------------------------
    for i, mk in enumerate(_MOCK_MUSIC):
        title, artist, year, fmt = mk["title"], mk["artist"], mk["year"], mk["format"]
        mid = f"{_slug(artist)}-{_slug(title)}-{year}"
        # real album art hotlinked from Cover Art Archive (no copyrighted files in the repo);
        # falls back to a generated square placeholder if a cover_url isn't set.
        if mk.get("cover_url"):
            images = [mk["cover_url"]]
        else:
            cover = cfg.posters_dir / f"{mid}.jpg"
            make_placeholder_poster(f"{artist} — {title}", cover, color=mk.get("color", (30, 30, 36)),
                                    subtitle=fmt, shape="square")
            images = [f"posters/{cover.name}"]
        played = (i % 3 == 0)
        item = {
            "id": mid, "media_type": "music", "title": title, "artist": artist,
            "year": year, "format": fmt, "label": mk.get("label"), "genres": mk["genres"],
            "rating": mk["rating"], "tracklist": mk.get("tracklist", []),
            "disc_count": 1, "intro": mk["intro"], "overview": mk["intro"],
            "poster": images[0], "images": images,
            "listen": _listen_links(artist, title),
            "source": {"name": "mock", "url": None},
            "resale": estimate(f"{artist} {title}", year, fmt, mk["rating"], tld),
            "source_image": f"(demo) {artist} — {title}", "confidence": 0.99,
            "seen": played, "date_seen": ("2024-03-01" if played else None), "added_at": _now(),
        }
        store.upsert_movie(item)
        store.record(f"mock-{mid}", item["source_image"], "identified", mid, _now())
        stats.new += 1
        stats.identified += 1

    # --- books -----------------------------------------------------------------------
    for i, mk in enumerate(_MOCK_BOOKS):
        title, author, year, fmt = mk["title"], mk["author"], mk["year"], mk["format"]
        mid = f"{_slug(author)}-{_slug(title)}-{year}"
        # real cover hotlinked from Open Library (no copyrighted files in the repo); falls back to
        # a generated placeholder if no cover_url is set.
        if mk.get("cover_url"):
            images = [mk["cover_url"]]
        else:
            cover = cfg.posters_dir / f"{mid}.jpg"
            make_placeholder_poster(f"{title}", cover, color=mk.get("color", (40, 36, 28)),
                                    subtitle=author)
            images = [f"posters/{cover.name}"]
        read = (i % 2 == 0)
        item = {
            "id": mid, "media_type": "book", "title": title, "author": author,
            "year": year, "format": fmt, "publisher": mk.get("publisher"), "genres": mk["genres"],
            "rating": mk["rating"], "page_count": mk.get("page_count"), "isbn": mk.get("isbn"),
            "intro": mk["intro"], "overview": mk["intro"],
            "poster": images[0], "images": images,
            "read": _read_links(author, title),
            "source": {"name": "mock", "url": None},
            "resale": estimate(f"{author} {title}", year, fmt, mk["rating"], tld),
            "source_image": f"(demo) {author} — {title}", "confidence": 0.99,
            "seen": read, "date_seen": ("2024-04-01" if read else None), "added_at": _now(),
        }
        store.upsert_movie(item)
        store.record(f"mock-{mid}", item["source_image"], "identified", mid, _now())
        stats.new += 1
        stats.identified += 1

    # --- video games -----------------------------------------------------------------
    for i, mk in enumerate(_MOCK_GAMES):
        title, year, fmt = mk["title"], mk["year"], mk["format"]
        mid = f"{_slug(title)}-{year}"
        # real box art hotlinked from the Steam capsule CDN (no copyrighted files in the repo);
        # falls back to a generated placeholder if no cover_url is set.
        if mk.get("cover_url"):
            images = [mk["cover_url"]]
        else:
            cover = cfg.posters_dir / f"{mid}.jpg"
            make_placeholder_poster(f"{title}", cover, color=mk.get("color", (24, 28, 40)),
                                    subtitle=fmt)
            images = [f"posters/{cover.name}"]
        played = (i % 2 == 0)
        item = {
            "id": mid, "media_type": "game", "title": title, "developer": mk.get("developer"),
            "publisher": mk.get("publisher"), "year": year, "format": fmt, "genres": mk["genres"],
            "platforms": mk.get("platforms", [fmt]), "players": mk.get("players"),
            "esrb": mk.get("esrb"), "rating": mk["rating"],
            "intro": mk["intro"], "overview": mk["intro"],
            "poster": images[0], "images": images,
            "play": _play_links(title, fmt),
            "source": {"name": "mock", "url": None},
            "resale": estimate(title, year, fmt, mk["rating"], tld, media_type="game"),
            "source_image": f"(demo) {title}", "confidence": 0.99,
            "seen": played, "date_seen": ("2024-05-01" if played else None), "added_at": _now(),
        }
        store.upsert_movie(item)
        store.record(f"mock-{mid}", item["source_image"], "identified", mid, _now())
        stats.new += 1
        stats.identified += 1

    # --- audiobooks ------------------------------------------------------------------
    for i, mk in enumerate(_MOCK_AUDIOBOOKS):
        title, author, year, fmt = mk["title"], mk["author"], mk["year"], mk["format"]
        mid = f"{_slug(author)}-{_slug(title)}-{year}"
        # real cover hotlinked from Open Library (no copyrighted files in the repo); falls back to
        # a generated placeholder if no cover_url is set.
        if mk.get("cover_url"):
            images = [mk["cover_url"]]
        else:
            cover = cfg.posters_dir / f"{mid}.jpg"
            make_placeholder_poster(f"{title}", cover, color=mk.get("color", (22, 34, 44)),
                                    subtitle=f"🎧 {mk.get('narrator') or author}")
            images = [f"posters/{cover.name}"]
        heard = (i % 2 == 0)
        item = {
            "id": mid, "media_type": "audiobook", "title": title, "author": author,
            "narrator": mk.get("narrator"), "year": year, "format": fmt,
            "duration": mk.get("duration"), "publisher": mk.get("publisher"), "genres": mk["genres"],
            "isbn": mk.get("isbn"), "rating": mk["rating"], "intro": mk["intro"], "overview": mk["intro"],
            "poster": images[0], "images": images,
            "listen": _hear_links(author, title),
            "source": {"name": "mock", "url": None},
            "resale": estimate(f"{author} {title}", year, fmt, mk["rating"], tld),
            "source_image": f"(demo) {title}", "confidence": 0.99,
            "seen": heard, "date_seen": ("2024-06-01" if heard else None), "added_at": _now(),
        }
        store.upsert_movie(item)
        store.record(f"mock-{mid}", item["source_image"], "identified", mid, _now())
        stats.new += 1
        stats.identified += 1

    # a couple of sample unidentified items so that flow is demoable too — with generated
    # placeholder thumbnails so they look intentional (not a broken/blank image).
    for n, fmt in [("unreadable cover", "VHS"), ("blank tape", "VHS")]:
        thumb = cfg.posters_dir / f"unid-mock-{_slug(n)}.jpg"
        make_placeholder_poster(f"? {n}", thumb, color=(46, 48, 58), subtitle="needs identifying")
        store.add_unidentified({
            "hash": f"mock-unidentified-{_slug(n)}",
            "source_image": f"(demo) {n}", "thumbnail": f"posters/{thumb.name}",
            "guess_title": None, "guess_year": None, "guess_format": fmt,
            "reason": "low confidence", "added_at": _now(),
        })
        stats.unidentified += 1
    store.save()
    _write_site(cfg, store)
    log(f"Done (mock). {stats}")
    return stats
