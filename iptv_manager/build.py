"""Costruisce la playlist AUTOAGGIORNANTE a partire da fonti pubbliche + selezione curata.

Principi:
 * Italia (tvg-chno < 100) = copia fedele della produzione (URL funzionanti preservati), con
   le sole correzioni EPG verificate (config/epg_fixes.json).
 * Il resto e' definito in config/curated.json (approvato da te): il builder sceglie solo l'URL.
 * URL stabili: se l'URL scelto in precedenza e' ancora tra i candidati e non fallisce, NON si cambia.
 * Policy di qualita' (config/policy.json): solo HTTPS+HLS, niente IP nudi/mirror/restreamer noti.
 * Il builder scrive SOLO in build/ e reports/: la pubblicazione sul Gist e' un passo separato.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import re
import urllib.request
from urllib.parse import urlparse

from . import checker, m3u

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = "iptv-manager/1.0"


def _json(name):
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def url_allowed(url: str, policy: dict) -> tuple[bool, str]:
    if policy["require_https"] and not url.startswith("https://"):
        return False, "non https"
    if policy["require_hls"] and ".m3u8" not in url:
        return False, "non HLS"
    host = urlparse(url).hostname or ""
    if policy["block_raw_ip_hosts"] and re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        return False, "IP nudo"
    for b in policy["block_url_substrings"]:
        if b in url:
            return False, f"host bloccato ({b})"
    return True, ""


def is_grey(url: str, policy: dict) -> bool:
    return any(g in url for g in policy["grey_url_substrings"])


def load_sources(fetch=fetch_text) -> tuple[dict, dict]:
    pls, errors = {}, {}
    for s in _json("sources.json")["sources"]:
        try:
            pls[s["id"]] = m3u.parse(fetch(s["url"]))
        except Exception as e:  # noqa: BLE001  una fonte giù non deve bloccare la build
            errors[s["id"]] = f"{type(e).__name__}: {e}"
    return pls, errors


def _pluto_id(c: m3u.Channel) -> str | None:
    m = re.search(r"/channels/([0-9a-f]{24})/", c.attrs.get("tvg-logo", ""))
    return m.group(1) if m else None


def build(production_text: str, sources: dict, prev_selected: dict | None = None, check: bool = False) -> dict:
    policy, curated, fixes = _json("policy.json"), _json("curated.json"), _json("epg_fixes.json")
    prev_selected = prev_selected or {}
    prod = m3u.parse(production_text)
    by_title = {c.title: c for c in prod.channels}
    out: list[m3u.Channel] = []
    rep = {"epg_fixed": [], "new": [], "held": [], "not_found": [], "proposed_removal": [], "excluded": [], "selected": {}, "dropped_from_prod": []}

    for c in prod.channels:  # Italia: fedele alla produzione
        if c.chno is not None and c.chno < 100:
            fix = fixes["fixes"].get(c.attrs.get("tvg-name", ""))
            if fix and fix != c.tvg_id:
                rep["epg_fixed"].append(f"{c.title}: {c.tvg_id} -> {fix}")
                c = m3u.Channel({**c.attrs, "tvg-id": fix}, c.title, c.url, c.extra, [])
            else:
                c = m3u.Channel(dict(c.attrs), c.title, c.url, c.extra, [])
            out.append(c)

    def finish(e, attrs, url, extra=None):
        if e.get("epg_id"):  # override verificato (corrispondenza esatta in una fonte XMLTV)
            attrs["tvg-id"] = e["epg_id"]
        attrs["tvg-chno"] = str(e.get("chno", attrs.get("tvg-chno", "")))
        attrs["group-title"] = e.get("group", attrs.get("group-title", ""))
        attrs["tvg-name"] = e.get("name", attrs.get("tvg-name", ""))
        return m3u.Channel(attrs, e.get("name") or e.get("from_title") or attrs["tvg-name"], url, extra or [], [])

    kept_titles = set()
    for e in curated["entries"]:
        key, t = e.get("name") or e.get("from_title"), e["type"]
        ch = None
        if t == "pinned":
            src = by_title.get(e["from_title"])
            kept_titles.add(e["from_title"])
            if src is None:
                rep["not_found"].append(f"{key}: non piu' presente in produzione")
            elif e.get("proposed_removal"):
                rep["proposed_removal"].append(e["from_title"])
            else:
                ch = finish(e, dict(src.attrs), src.url, list(src.extra))
        elif t == "pluto":
            cat = {c.attrs.get("tvg-name"): c for c in sources.get("wltv-pluto", m3u.Playlist("", [])).channels}.get(e["catalog_name"])
            pid = _pluto_id(cat) if cat else None
            if not pid:
                rep["not_found"].append(f"{key}: non nel catalogo Pluto")
            else:
                ch = finish(e, {"tvg-id": pid, "tvg-logo": cat.attrs.get("tvg-logo", "")}, policy["pluto_base"].format(id=pid))
        elif t == "redirector":
            cat = {c.attrs.get("tvg-name"): c for c in sources.get(e["source"], m3u.Playlist("", [])).channels}.get(e["catalog_name"])
            if not cat or not cat.url.startswith("http"):
                rep["not_found"].append(f"{key}: non nel redirector")
            else:
                ch = finish(e, {"tvg-id": cat.tvg_id, "tvg-logo": cat.attrs.get("tvg-logo", "")}, cat.url)
        elif t == "streams":
            pl = sources.get(e["source"])
            cands = []
            for c in (pl.channels if pl else []):
                ids = e.get("tvg_ids")
                if ids is not None and c.tvg_id not in ids:
                    continue
                if e.get("catalog_name") and c.attrs.get("tvg-name") != e["catalog_name"]:
                    continue
                if any(tag in c.title for tag in policy["skip_title_tags"]):
                    continue
                ok, why = url_allowed(c.url, policy)
                if not ok:
                    rep["excluded"].append(f"{key}: {c.url[:60]}... ({why})")
                    continue
                if is_grey(c.url, policy) and not policy["include_grey_new"]:
                    rep["excluded"].append(f"{key}: host grigio, serve include_grey_new ({urlparse(c.url).hostname})")
                    continue
                cands.append(c)
            if e.get("tvg_ids"):
                cands.sort(key=lambda c: e["tvg_ids"].index(c.tvg_id))
            if not cands:
                rep["not_found"].append(f"{key}: nessun candidato valido in {e['source']}")
            else:
                prev = prev_selected.get(key)
                pick = next((c for c in cands if c.url == prev), cands[0])
                ch = finish(e, {"tvg-id": pick.tvg_id, "tvg-logo": pick.attrs.get("tvg-logo", "")}, pick.url)
                rep["selected"][key] = {"url": pick.url, "alternatives": len(cands) - 1}
        if ch is None:
            continue
        if e.get("hold"):
            rep["held"].append(key)  # incluso solo se il controllo lo vede STREAM_OK
            ch.attrs["x-hold"] = "1"
        if t != "pinned":
            rep["new"].append(key)
        out.append(ch)

    out_titles = {c.title for c in out}
    for c in prod.channels:  # canali di produzione non piu' nella selezione
        if (c.chno is None or c.chno >= 100) and c.title not in kept_titles and c.title not in out_titles:
            rep["dropped_from_prod"].append(c.title)

    if check:
        with cf.ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda c: checker.check_channel(c.url), out))
        out = [c for c, r in zip(out, res) if not (c.attrs.get("x-hold") and r["state"] != "STREAM_OK")]
        rep["check"] = {c.title: r["state"] for c, r in zip(out, res)}
    for c in out:
        c.attrs.pop("x-hold", None)
    # LCN duplicati: l'ultimo viene spostato in coda (mai silenzioso)
    seen = set()
    for c in out:
        if c.chno in seen:
            rep.setdefault("chno_conflicts", []).append(f"{c.title} (LCN {c.chno})")
        seen.add(c.chno)
    out.sort(key=lambda c: (c.chno is None, c.chno or 0))
    header = prod.header
    return {"playlist": m3u.Playlist(header, out), "report": rep}
