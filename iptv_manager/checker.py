"""Controllo dei flussi: raggiungibilita', integrita', presenza audio.

Stati (mai equivalenti a "funziona sul Samsung"):
  STREAM_OK      manifest valido + ffprobe vede video E audio decodificabili
  NO_AUDIO       ffprobe vede il video ma nessuna traccia audio
  REACHABLE_ONLY manifest scaricato, ma ffprobe non ha potuto/saputo verificare
  RESTRICTED     HTTP 401/403/451 (possibile geoblocco o token): NON e' una prova di morte
  UNREACHABLE    timeout/DNS/5xx/404
Il test sul Samsung resta SEMPRE manuale: vedi config/device_results.json.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin

UA = "Mozilla/5.0 (SMART-TV; Tizen 6.5) AppleWebKit/537.36 iptv-manager/1.0"


def fetch(url: str, timeout: int = 20, ua: str = UA) -> tuple[int, str, str, str]:
    """(status, url_finale, content_type, body_testo_max_512KB). status 0 = errore di rete."""
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.headers.get("Content-Type", ""), r.read(524288).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, url, "", ""
    except Exception as e:  # noqa: BLE001
        return 0, url, "", f"{type(e).__name__}: {e}"


def analyze_manifest(text: str, base: str) -> dict:
    """Estrae dal manifest HLS le informazioni di packaging rilevanti per i player Samsung."""
    info = {"is_hls": text.lstrip().startswith("#EXTM3U"), "master": "#EXT-X-STREAM-INF" in text,
            "variants": len(re.findall(r"#EXT-X-STREAM-INF", text)),
            "separate_audio": bool(re.search(r"#EXT-X-MEDIA:[^\n]*TYPE=AUDIO[^\n]*URI=", text)),
            "subtitles_group": "TYPE=SUBTITLES" in text,
            "aes128": "METHOD=AES-128" in text,
            "discontinuities": text.count("#EXT-X-DISCONTINUITY\n")}
    info["codecs_attr"] = sorted(set(re.findall(r'CODECS="([^"]+)"', text)))[:3]
    return info


def ffprobe_stream(url: str, timeout: int = 60) -> dict:
    """Esegue ffprobe sul flusso (usa http_proxy se impostato in ambiente)."""
    if not shutil.which("ffprobe"):
        return {"ok": False, "error": "ffprobe non installato"}
    cmd = ["ffprobe", "-v", "error", "-user_agent", UA, "-allowed_extensions", "ALL",
           "-show_entries", "stream=codec_type,codec_name,profile,sample_rate,channels,width,height",
           "-of", "json", url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout ffprobe"}
    try:
        streams = json.loads(p.stdout or "{}").get("streams", [])
    except json.JSONDecodeError:
        streams = []
    return {"ok": bool(streams), "streams": streams, "error": p.stderr.strip()[:200]}


def check_channel(url: str, deep: bool = True) -> dict:
    t0 = time.time()
    status, final, ctype, body = fetch(url)
    res = {"http": status, "final_url": re.sub(r"jwt=[^&]+", "jwt=<REDACTED>", final), "ms": int((time.time() - t0) * 1000)}
    if status in (401, 403, 451):
        res["state"] = "RESTRICTED"
        return res
    if status != 200:
        res["state"] = "UNREACHABLE"
        res["error"] = body if status == 0 else f"HTTP {status}"
        return res
    res["manifest"] = analyze_manifest(body, final)
    if not res["manifest"]["is_hls"]:
        res["state"] = "UNREACHABLE"
        res["error"] = "risposta 200 ma non e' un manifest HLS"
        return res
    res["state"] = "REACHABLE_ONLY"
    if deep:
        probe = ffprobe_stream(url)
        kinds = {s.get("codec_type") for s in probe.get("streams", [])}
        res["ffprobe"] = {"audio": [(s["codec_name"], s.get("profile"), s.get("channels"), s.get("sample_rate"))
                                    for s in probe.get("streams", []) if s.get("codec_type") == "audio"][:1],
                          "video": [(s["codec_name"], s.get("width"), s.get("height"))
                                    for s in probe.get("streams", []) if s.get("codec_type") == "video"][:1],
                          "error": probe.get("error", "")}
        if "video" in kinds and "audio" in kinds:
            res["state"] = "STREAM_OK"
        elif "video" in kinds:
            res["state"] = "NO_AUDIO"
    return res
