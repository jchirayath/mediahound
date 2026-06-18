"""Store: manifest, image-gallery dedup, seen overrides, delete, unidentified, save."""
import json

from mediahound.store import Store, list_images


def test_upsert_merges_image_gallery_without_dupes(tmp_path):
    s = Store(tmp_path / "data")
    s.upsert_movie({"id": "m1", "title": "A", "images": ["p/a.jpg"], "seen": False})
    s.upsert_movie({"id": "m1", "title": "A", "images": ["p/a.jpg", "p/b.jpg"]})  # dup + new
    assert s.find_movie("m1")["images"] == ["p/a.jpg", "p/b.jpg"]
    assert len(s.collection) == 1


def test_seen_overrides_survive_rebuild(tmp_path):
    s = Store(tmp_path / "data")
    s.seen_overrides = {"m1": {"seen": True, "date_seen": "2020-01-01"}}
    s.upsert_movie({"id": "m1", "title": "A", "images": []})  # upsert honors the override
    assert s.find_movie("m1")["seen"] is True
    assert s.find_movie("m1")["date_seen"] == "2020-01-01"


def test_apply_lists_bakes_per_type_position(tmp_path):
    s = Store(tmp_path / "data")
    s.upsert_movie({"id": "a", "title": "A", "media_type": "movie", "images": []})
    s.upsert_movie({"id": "b", "title": "B", "media_type": "movie", "images": []})
    s.upsert_movie({"id": "c", "title": "C", "media_type": "music", "images": []})
    s.lists = {"movie": ["b", "a"], "music": ["c"]}   # curated order: b before a
    s.apply_lists()
    assert s.find_movie("b")["list_pos"] == 0
    assert s.find_movie("a")["list_pos"] == 1
    assert s.find_movie("c")["list_pos"] == 0
    # an item not on any list gets a null position (not "on the list")
    s.upsert_movie({"id": "d", "title": "D", "media_type": "movie", "images": []})
    s.apply_lists()
    assert s.find_movie("d")["list_pos"] is None
    # save() persists list_pos into collection.json and creates an empty lists.json on first run
    s.save()
    coll = json.loads((tmp_path / "data" / "collection.json").read_text())
    assert {m["id"]: m["list_pos"] for m in coll} == {"a": 1, "b": 0, "c": 0, "d": None}
    assert (tmp_path / "data" / "lists.json").is_file()


def test_delete_movie_marks_manifest_so_it_is_not_readded(tmp_path):
    s = Store(tmp_path / "data")
    s.record("h1", "f.jpg", "ok", "m1", "2020")
    s.upsert_movie({"id": "m1", "title": "A", "images": ["x"]})
    assert s.delete_movie("m1") is True
    assert s.find_movie("m1") is None
    assert s.manifest["h1"]["status"] == "deleted" and s.manifest["h1"]["movie_id"] is None
    assert s.delete_movie("ghost") is False


def test_unidentified_dedup_and_remove(tmp_path):
    s = Store(tmp_path / "data")
    s.add_unidentified({"hash": "h", "id": "u1"})
    s.add_unidentified({"hash": "h", "id": "u1"})  # duplicate ignored
    assert len(s.unidentified) == 1
    s.remove_unidentified_by_hash("h")
    assert s.unidentified == []


def test_save_sorts_by_title_and_creates_roundtrip_files(tmp_path):
    d = tmp_path / "data"
    s = Store(d)
    s.upsert_movie({"id": "b", "title": "Zebra", "images": []})
    s.upsert_movie({"id": "a", "title": "Apple", "images": []})
    s.save()
    col = json.loads((d / "collection.json").read_text())
    assert [m["title"] for m in col] == ["Apple", "Zebra"]
    assert (d / "seen-overrides.json").is_file()
    assert (d / "identify-queue.json").is_file()


def test_is_processed_and_queued_identity(tmp_path):
    s = Store(tmp_path / "data")
    assert s.is_processed("h1") is False
    s.record("h1", "f.jpg", "ok", "m1", "2020")
    assert s.is_processed("h1") is True
    s.identify_queue = {"h2": {"title": "Manual"}}
    assert s.queued_identity("h2")["title"] == "Manual"
    assert s.queued_identity("nope") is None


def test_list_images_filters_and_sorts(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.png").write_bytes(b"x")
    (tmp_path / ".hidden.jpg").write_bytes(b"x")  # dotfile ignored
    (tmp_path / "notes.txt").write_bytes(b"x")    # non-image ignored
    names = [p.name for p in list_images(tmp_path)]
    assert names == ["a.jpg", "b.png"]
    assert list_images(tmp_path / "missing") == []


def test_list_media_images_routes_by_subfolder(tmp_path):
    from mediahound.store import list_media_images
    raw = tmp_path / "RawImages"
    (raw / "video").mkdir(parents=True)
    (raw / "audio").mkdir(parents=True)
    (raw / "root.jpg").write_bytes(b"x")          # root → default (movie)
    (raw / "video" / "m.jpg").write_bytes(b"x")    # video → movie
    (raw / "audio" / "a.png").write_bytes(b"x")    # audio → music
    (raw / "audio" / "notes.txt").write_bytes(b"x")  # non-image ignored
    got = {p.name: mt for p, mt in list_media_images(raw)}
    assert got == {"root.jpg": "movie", "m.jpg": "movie", "a.png": "music"}
