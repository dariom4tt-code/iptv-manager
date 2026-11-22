"""Trasforma un master HLS Pluto in un master "piatto" per player con problemi sui gruppi audio separati.

Rimuove #EXT-X-MEDIA (AUDIO/SUBTITLES) e gli attributi AUDIO=/SUBTITLES= dalle STREAM-INF,
rende assoluti gli URI delle varianti. Nessuna ricodifica: l'audio AAC-LC e' gia' muxato nei
segmenti TS delle varianti (verificato con ffprobe, vedi docs/PLUTO_DIAGNOSIS.md).
Il Worker Cloudflare in tools/pluto-worker/worker.js implementa la stessa logica.
"""
import re
from urllib.parse import urljoin


def flatten(master: str, base_url: str) -> str:
    out = []
    for line in master.replace("\r\n", "\n").split("\n"):
        if line.startswith("#EXT-X-MEDIA:") and re.search(r"TYPE=(AUDIO|SUBTITLES)", line):
            continue
        if line.startswith("#EXT-X-STREAM-INF:"):
            line = re.sub(r',(AUDIO|SUBTITLES|CLOSED-CAPTIONS)="[^"]*"', "", line)
        elif line and not line.startswith("#"):
            line = urljoin(base_url, line)
        out.append(line)
    return "\n".join(out)
