"""IPTV Manager - riga di comando.

  python -m iptv_manager validate [file]
  python -m iptv_manager check [file] [--only SUBSTR] [--no-deep]
  python -m iptv_manager epg [file]
  python -m iptv_manager report
  python -m iptv_manager publish [file] [--confirm]
  python -m iptv_manager restore BACKUP [--confirm]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import pathlib
import sys

from . import checker, epg, m3u, publish

ROOT = publish.ROOT
REPORTS = ROOT / "reports"
HISTORY = REPORTS / "history.jsonl"
DEVICE = ROOT / "config" / "device_results.json"


def load(path: str | None) -> m3u.Playlist:
    p = pathlib.Path(path) if path else ROOT / "playlists" / "production.m3u"
    return m3u.parse(p.read_text(encoding="utf-8"))


def cmd_validate(a) -> int:
    pl = load(a.file)
    errors, warnings = m3u.validate(pl)
    print(f"{len(pl.channels)} canali")
    for w in warnings:
        print("AVVISO:", w)
    for e in errors:
        print("ERRORE:", e)
    return 2 if errors else 0


def _history_fail_counts() -> dict[str, int]:
    """Fallimenti CONSECUTIVI per URL, dagli ultimi controlli."""
    counts: dict[str, int] = {}
    if HISTORY.exists():
        for line in HISTORY.read_text().splitlines():
            r = json.loads(line)
            for url, st in r["states"].items():
                counts[url] = counts.get(url, 0) + 1 if st in ("UNREACHABLE", "NO_AUDIO") else 0
    return counts


def cmd_check(a) -> int:
    pl = load(a.file)
    chans = [c for c in pl.channels if not a.only or a.only.lower() in c.title.lower()]
    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda c: checker.check_channel(c.url, deep=not a.no_deep), chans))
    prev = _history_fail_counts()
    device = json.loads(DEVICE.read_text()) if DEVICE.exists() else {}
    rows, states = [], {}
    for c, r in zip(chans, results):
        states[c.url] = r["state"]
        fails = prev.get(c.url, 0) + (1 if r["state"] in ("UNREACHABLE", "NO_AUDIO") else 0)
        rows.append({"title": c.title, "chno": c.chno, "url": c.url, "device": device.get(c.title, "NON_TESTATO_SU_SAMSUNG"),
                     "consecutive_failures": fails, **r})
    REPORTS.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with HISTORY.open("a") as f:
        f.write(json.dumps({"ts": now, "states": states}) + "\n")
    (REPORTS / "latest-check.json").write_text(json.dumps({"ts": now, "channels": rows}, indent=1, ensure_ascii=False))
    # Proposte: MAI applicate automaticamente (eliminazioni = approvazione utente)
    th = json.loads((ROOT / "config" / "settings.json").read_text())["removal_proposal_after_failures"]
    props = [{"title": r["title"], "reason": f"{r['consecutive_failures']} controlli consecutivi falliti",
              "action": "PROPOSTA eliminazione/sostituzione - richiede approvazione"} for r in rows if r["consecutive_failures"] >= th]
    (REPORTS / "proposals.json").write_text(json.dumps(props, indent=1, ensure_ascii=False))
    write_markdown(rows, props, now)
    tally: dict[str, int] = {}
    for r in rows:
        tally[r["state"]] = tally.get(r["state"], 0) + 1
    print(tally)
    return 0


def write_markdown(rows, props, now) -> None:
    groups = {"STREAM_OK": "Integri (video+audio visti da ffprobe), NON verificati sul Samsung",
              "REACHABLE_ONLY": "Raggiungibili ma non verificati", "NO_AUDIO": "Video senza audio",
              "RESTRICTED": "Soggetti a restrizioni (401/403/451, possibile geoblocco)", "UNREACHABLE": "Non raggiungibili"}
    out = [f"# Report controllo flussi\n\nGenerato: {now} (rete GitHub/USA: i geoblocchi italiani possono dare falsi negativi)\n"]
    for st, title in groups.items():
        sel = [r for r in rows if r["state"] == st]
        out.append(f"\n## {title} ({len(sel)})\n")
        out += [f"- {r['chno']} {r['title']} - Samsung: {r['device']}" for r in sel]
    out.append(f"\n## Da controllare manualmente / proposte ({len(props)})\n")
    out += [f"- {p['title']}: {p['reason']}" for p in props]
    (REPORTS / "latest-report.md").write_text("\n".join(out) + "\n")


def cmd_epg(a) -> int:
    pl = load(a.file)
    srcs = json.loads((ROOT / "config" / "epg_sources.json").read_text())
    loaded = {s["name"]: epg.load_channels(s["url"]) for s in srcs if s.get("enabled", True)}
    for n, s in loaded.items():
        print(f"{n}: {'OK' if s['ok'] else 'ERRORE ' + s['error']} - {len(s['ids'])} canali")
    rep = epg.reconcile(pl.channels, {n: s for n, s in loaded.items() if s["ok"]})
    (REPORTS / "latest-epg.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    tally: dict[str, int] = {}
    for r in rep:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    print(tally)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="iptv_manager")
    sp = p.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "check", "epg", "publish"):
        s = sp.add_parser(name)
        s.add_argument("file", nargs="?")
        if name == "check":
            s.add_argument("--only")
            s.add_argument("--no-deep", action="store_true")
        if name == "publish":
            s.add_argument("--confirm", action="store_true")
    s = sp.add_parser("restore")
    s.add_argument("file")
    s.add_argument("--confirm", action="store_true")
    a = p.parse_args(argv)
    if a.cmd == "publish":
        return publish.publish(pathlib.Path(a.file or ROOT / "playlists" / "production.m3u"), a.confirm)
    if a.cmd == "restore":
        return publish.publish(pathlib.Path(a.file), a.confirm)
    return {"validate": cmd_validate, "check": cmd_check, "epg": cmd_epg}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
