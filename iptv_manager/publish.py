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


def online_text() -> str:
    """Versione attualmente online (Raw senza hash, URL pubblico)."""
    cfg = settings()["gist"]
    url = f"https://gist.githubusercontent.com/{cfg['owner']}/{cfg['id']}/raw/{cfg['filename']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "iptv-manager"}), timeout=30) as r:
        return r.read().decode("utf-8")


def auto_guard(new_text: str, old_text: str) -> list[str]:
    """Motivi per cui l'aggiornamento NON puo' essere automatico (richiede approvazione).

    Automatico solo se: stessi canali (per titolo), stesso LCN/gruppo, e nessun canale
    'storico' (LCN < 100, i canali italiani) cambia URL. Cambi di URL su altri canali e correzioni
    di tvg-id sono considerati aggiornamenti tecnici.
    """
    new, old = m3u.parse(new_text), m3u.parse(old_text)
    n, o = {c.title: c for c in new.channels}, {c.title: c for c in old.channels}
    why = []
    for t in sorted(set(n) - set(o)):
        why.append(f"canale AGGIUNTO: {t}")
    for t in sorted(set(o) - set(n)):
        why.append(f"canale RIMOSSO: {t}")
    for t in sorted(set(n) & set(o)):
        if (n[t].chno, n[t].group) != (o[t].chno, o[t].group):
            why.append(f"LCN/gruppo cambiato: {t}")
        if (o[t].chno or 999) < 100 and n[t].url != o[t].url:
            why.append(f"URL di canale storico cambiato: {t}")
    return why


def publish(path: pathlib.Path, confirm: bool = False, auto: bool = False) -> int:
    text = path.read_text(encoding="utf-8")
    errors, warnings = m3u.validate(m3u.parse(text))
    for w in warnings:
        print("AVVISO:", w)
    if errors:
        print("PUBBLICAZIONE BLOCCATA:\n  " + "\n  ".join(errors))
        return 2
    fname = settings()["gist"]["filename"]
    if auto:
        why = auto_guard(text, online_text())
        if why:
            print("AGGIORNAMENTO AUTOMATICO SOSPESO: serve approvazione.\n  " + "\n  ".join(why))
            return 0  # non e' un errore: resta in staging
        print("auto_guard OK: solo correzioni tecniche")
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
