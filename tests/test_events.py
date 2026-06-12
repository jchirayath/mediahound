"""Compact change log (events.jsonl) — format/compactness, trimming, wiring, publish-exclusion."""
import json

from mediahound import cli, events, publish
from mediahound.config import load_config
from mediahound.events import EventLog
from mediahound.store import Store


def test_event_format_is_compact(tmp_path):
    log = EventLog(tmp_path)
    log.add("add", "dune-1965", ts=1718150400)
    log.add("change", "dune-1965", fields=["year", "title"], ts=1718150401)
    log.add("seen", "dune-1965", value=1, ts=1718150402)
    raw = (tmp_path / "events.jsonl").read_text().splitlines()
    # single-char op, integer timestamp, short keys, sorted field names, no whitespace padding
    assert raw[0] == '{"t":1718150400,"o":"+","id":"dune-1965"}'
    assert json.loads(raw[1])["f"] == ["title", "year"]      # sorted, deduped
    assert json.loads(raw[1])["o"] == "~"
    assert json.loads(raw[2]) == {"t": 1718150402, "o": "s", "id": "dune-1965", "v": 1}
    # change records field NAMES only — never the values (compact + privacy-safe)
    assert "title" in raw[1] and "Dune" not in raw[1]


def test_event_disabled_is_noop(tmp_path):
    log = EventLog(tmp_path, enabled=False)
    log.add("add", "x")
    assert not (tmp_path / "events.jsonl").exists()
    assert log.recent() == []


def test_event_recent_returns_newest_last(tmp_path):
    log = EventLog(tmp_path)
    for i in range(5):
        log.add("add", f"id-{i}", ts=1700000000 + i)
    got = log.recent(3)
    assert [e["id"] for e in got] == ["id-2", "id-3", "id-4"]


def test_event_log_self_trims(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "MAX_EVENTS", 10)
    monkeypatch.setattr(events, "_TRIM_BYTES", 200)          # force a trim almost immediately
    log = EventLog(tmp_path)
    for i in range(200):
        log.add("add", f"id-{i}", ts=1700000000 + i)
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert len(lines) <= 10                                  # capped to the most recent MAX_EVENTS
    assert json.loads(lines[-1])["id"] == "id-199"           # newest kept


def test_csv_import_logs_add_and_import(tmp_path):
    from mediahound.csvio import import_csv
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    csv_path = tmp_path / "c.csv"
    csv_path.write_text("media_type,title,year,format\nmovie,Heat,1995,DVD\n")
    import_csv(cfg, store, csv_path, online=False, log=lambda *_: None)
    ops = [e["o"] for e in EventLog(cfg.data_dir).recent()]
    assert "+" in ops and "i" in ops                         # an add + a bulk-import summary


def test_correction_delete_logs_remove(tmp_path):
    from mediahound import pipeline
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")
    store = Store(cfg.data_dir)
    victim = store.collection[0]["id"]
    store.corrections = {victim: {"delete": True}}
    pipeline._apply_corrections(cfg, store, lambda *_: None, online=False)
    events_seen = EventLog(cfg.data_dir).recent()
    assert any(e["o"] == "-" and e["id"] == victim for e in events_seen)


def test_publish_excludes_events_log(tmp_path):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cli.main(["build", "--config", str(site / "config.toml"), "--mock"])
    cfg = load_config(site / "config.toml")
    EventLog(cfg.data_dir).add("add", "x")
    assert (cfg.data_dir / "events.jsonl").is_file()
    files = publish._site_files(cfg.output_dir)
    assert not any(p.name == "events.jsonl" for p in files.values())


def test_cli_log_command_runs(tmp_path, capsys):
    site = tmp_path / "site"
    cli.main(["init", str(site)])
    cfg = load_config(site / "config.toml")
    EventLog(cfg.data_dir).add("add", "dune-1965", ts=1718150400)
    cli.main(["log", "--config", str(site / "config.toml")])
    out = capsys.readouterr().out
    assert "dune-1965" in out and "add" in out
