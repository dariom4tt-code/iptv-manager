"""Verifica fonti XMLTV (.xml / .xml.gz) e riconciliazione dei tvg-id.

Regole: nessuna associazione "fuzzy" automatica. Un tvg-id e' valido solo se
compare ESATTAMENTE come <channel id="..."> in almeno una fonte.
I suggerimenti per nome sono solo informativi (campo `suggestions`).
"""
from __future__ import annotations

import gzip
import io
import re
import urllib.request
import xml.etree.ElementTree as ET
from difflib import get_close_matches

UA = "iptv-manager/1.0"


def load_channels(url: str, timeout: int = 120) -> dict:
    """Scarica la fonte e ritorna {ok, ids:{id:display_name}, programmes:{id:n}, error}."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "ids": {}, "programmes": {}}
    if raw[:2] == b"\x1f\x8b":  # riconoscimento dal contenuto, non dall'estensione
        raw = gzip.decompress(raw)
    ids, progs = {}, {}
    try:
        for _, el in ET.iterparse(io.BytesIO(raw), events=("end",)):
            if el.tag == "channel":
                dn = el.find("display-name")
                ids[el.get("id", "")] = (dn.text or "") if dn is not None else ""
                el.clear()
            elif el.tag == "programme":
                progs[el.get("channel", "")] = progs.get(el.get("channel", ""), 0) + 1
                el.clear()
    except ET.ParseError as e:
        return {"ok": False, "error": f"XML non valido: {e}", "ids": ids, "programmes": progs}
    return {"ok": True, "error": "", "ids": ids, "programmes": progs}


def reconcile(channels, sources: dict[str, dict]) -> list[dict]:
    """channels: lista di m3u.Channel; sources: {nome: risultato load_channels}."""
    index: dict[str, list[str]] = {}
    for name, s in sources.items():
        for cid in s["ids"]:
            index.setdefault(cid, []).append(name)
    all_ids = list(index)
    report = []
    for c in channels:
        row = {"title": c.title, "tvg_id": c.tvg_id}
        if not c.tvg_id:
            row["status"] = "NO_TVG_ID"
        elif c.tvg_id in index:
            n = max(s["programmes"].get(c.tvg_id, 0) for s in sources.values())
            row["status"] = "EPG_OK" if n else "ID_PRESENT_NO_PROGRAMMES"
            row["sources"] = index[c.tvg_id]
            row["programmes"] = n
        else:
            row["status"] = "ID_NOT_FOUND"
            key = re.sub(r"[^a-z0-9]", "", c.attrs.get("tvg-name", c.title).lower())
            row["suggestions"] = get_close_matches(c.tvg_id, all_ids, n=3, cutoff=0.8)  # solo informativo
        report.append(row)
    return report
