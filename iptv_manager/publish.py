"""Backup, ripristino e pubblicazione sul Gist di produzione.

Sicurezza:
 * il token si legge SOLO da GIST_TOKEN (Actions Secret), mai da file/argomenti;
 * `publish` e' dry-run salvo --confirm; con --confirm esegue prima backup e validazione;
 * il nome del file nel Gist e' fisso (config/settings.json -> gist.filename);
 * `restore` ripubblica un backup locale (stessi controlli).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import shutil
import urllib.request

from . import m3u

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.github.com/gists/"


def settings() -> dict:
    return json.loads((ROOT / "config" / "settings.json").read_text())


def backup(path: pathlib.Path, label: str = "") -> pathlib.Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = ROOT / "backups" / f"playlist-{stamp}{('-' + label) if label else ''}.m3u"
    shutil.copy2(path, dest)
    return dest


def _gist_request(method: str, data: dict | None = None) -> dict:
    token = os.environ.get("GIST_TOKEN")
    if not token:
        raise SystemExit("GIST_TOKEN non impostato (usare GitHub Actions Secrets)")
    gid = settings()["gist"]["id"]
    req = urllib.request.Request(API + gid, method=method, data=json.dumps(data).encode() if data else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json", "User-Agent": "iptv-manager"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def publish(path: pathlib.Path, confirm: bool = False) -> int:
    text = path.read_text(encoding="utf-8")
    errors, warnings = m3u.validate(m3u.parse(text))
    for w in warnings:
        print("AVVISO:", w)
    if errors:
        print("PUBBLICAZIONE BLOCCATA:\n  " + "\n  ".join(errors))
        return 2
    fname = settings()["gist"]["filename"]
    if not confirm:
        print(f"[dry-run] validazione OK ({len(text.splitlines())} righe). Pubblicherebbe su gist file '{fname}'. "
              "Aggiungere --confirm per procedere.")
        return 0
    cur = _gist_request("GET")["files"].get(fname)
    if cur is not None:  # backup della versione ONLINE prima di sovrascriverla
        bk = ROOT / "backups" / f"gist-online-{dt.datetime.now(dt.timezone.utc):%Y%m%d-%H%M%S}.m3u"
        bk.write_text(cur["content"], encoding="utf-8")
        print("backup versione online:", bk.name)
    _gist_request("PATCH", {"files": {fname: {"content": text}}})
    print("pubblicato su", fname)
    return 0
