"""Diagnosi dettagliata di singoli flussi: catena di redirect, packaging HLS, codec (ffprobe).

Serve a capire PERCHE' un flusso non parte/non si sente su Tizen, confrontandolo con flussi
che sul televisore funzionano. Non sostituisce la prova sul dispositivo.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request

from . import checker, m3u


class _Chain(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.chain = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append((code, re.sub(r"(jwt|hdnts|token)=[^&~]+", r"\1=<R>", newurl)[:140]))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _get(url: str):
    h = _Chain()
    op = urllib.request.build_opener(h)
    try:
        with op.open(urllib.request.Request(url, headers={"User-Agent": checker.UA}), timeout=25) as r:
            return r.status, r.geturl(), r.headers.get("Content-Type", ""), r.read(300000).decode("utf-8", "replace"), h.chain
    except Exception as e:  # noqa: BLE001
        return 0, url, "", f"{type(e).__name__}: {e}", h.chain


def features(text: str) -> dict:
    return {
        "version": (re.search(r"#EXT-X-VERSION:(\d+)", text) or [None, None])[1],
        "master": "#EXT-X-STREAM-INF" in text,
        "codecs": sorted(set(re.findall(r'CODECS="([^"]+)"', text)))[:4],
        "resolutions": sorted(set(re.findall(r"RESOLUTION=(\d+x\d+)", text)))[:6],
        "audio_groups": re.findall(r"#EXT-X-MEDIA:[^\n]*TYPE=AUDIO[^\n]*", text)[:2],
        "subtitles": "TYPE=SUBTITLES" in text or "TYPE=CLOSED-CAPTIONS" in text,
        "fmp4_init": "#EXT-X-MAP" in text,
        "ext_x_define": "#EXT-X-DEFINE" in text,
        "encrypted": re.findall(r"METHOD=([A-Z0-9-]+)", text)[:1],
        "video_range": sorted(set(re.findall(r"VIDEO-RANGE=(\w+)", text))),
        "first_lines": [l[:110] for l in text.splitlines()[:6]],
    }


def probe(url: str) -> list[dict]:
    if not shutil.which("ffprobe"):
        return []
    cmd = ["ffprobe", "-v", "error", "-user_agent", checker.UA, "-allowed_extensions", "ALL", "-show_entries",
           "stream=codec_type,codec_name,profile,level,pix_fmt,width,height,avg_frame_rate,sample_rate,channels,channel_layout,bit_rate",
           "-of", "json", url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        return json.loads(p.stdout or "{}").get("streams", [])[:6]
    except Exception:  # noqa: BLE001
        return []


def diagnose(url: str) -> dict:
    code, final, ctype, body, chain = _get(url)
    out = {"http": code, "redirects": chain, "final_host": re.sub(r"^https?://([^/]+).*", r"\1", final), "content_type": ctype}
    if code != 200:
        out["error"] = body[:200]
        return out
    out["manifest"] = features(body)
    out["streams"] = probe(url)
    return out


def run(playlist: str, needles: list[str]) -> dict:
    pl = m3u.parse(open(playlist, encoding="utf-8").read())
    res = {}
    for c in pl.channels:
        if any(n.lower() in c.title.lower() for n in needles):
            res[c.title] = {"url": re.sub(r"(hdnts|jwt)=[^&]+", r"\1=<R>", c.url)[:200], **diagnose(c.url)}
    return res
