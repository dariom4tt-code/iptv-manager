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


def merge(wanted_ids: set[str], sources: list[dict], out_path: str, must_keep: set[str] | None = None) -> dict:
    """Scrive un XMLTV (.xml.gz) con SOLO i canali richiesti, prendendo ogni id dalla prima fonte
    (in ordine di config) che lo contiene con programmi. `must_keep`: id che DEVONO essere presenti
    (la guida italiana oggi funzionante): se mancano, ValueError e il file NON viene scritto."""
    chan_el, prog_el, origin = {}, {}, {}
    report = {"sources": {}, "found": {}, "missing": []}
    for s in sources:
        data = load_raw(s["url"])
        if data is None:
            report["sources"][s["name"]] = "NON RAGGIUNGIBILE"
            continue
        n = 0
        local_ch, local_pr = {}, {}
        try:
            for _, el in ET.iterparse(io.BytesIO(data), events=("end",)):
                if el.tag == "channel" and el.get("id") in wanted_ids and el.get("id") not in chan_el:
                    local_ch[el.get("id")] = ET.fromstring(ET.tostring(el))
                elif el.tag == "programme" and el.get("channel") in wanted_ids and el.get("channel") not in chan_el:
                    local_pr.setdefault(el.get("channel"), []).append(ET.fromstring(ET.tostring(el)))
                if el.tag in ("channel", "programme"):
                    el.clear()
        except ET.ParseError as e:
            report["sources"][s["name"]] = f"XML non valido: {e}"
            continue
        for cid, prs in local_pr.items():
            if cid in local_ch and cid not in chan_el:
                chan_el[cid], prog_el[cid], origin[cid] = local_ch[cid], prs, s["name"]
                n += 1
        report["sources"][s["name"]] = f"OK, {n} canali usati"
    missing_must = sorted((must_keep or set()) - set(chan_el))
    if missing_must:
        raise ValueError(f"id italiani che oggi hanno guida e mancherebbero: {missing_must}")
    root = ET.Element("tv", {"generator-info-name": "iptv-manager"})
    for cid in sorted(chan_el):
        root.append(chan_el[cid])
    for cid in sorted(prog_el):
        root.extend(prog_el[cid])
    with gzip.open(out_path, "wb") as f:
        ET.ElementTree(root).write(f, encoding="utf-8", xml_declaration=True)
    report["found"] = {cid: origin[cid] for cid in sorted(origin)}
    report["missing"] = sorted(wanted_ids - set(origin))
    return report


def load_raw(url: str, timeout: int = 180) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except Exception:  # noqa: BLE001
        return None
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
