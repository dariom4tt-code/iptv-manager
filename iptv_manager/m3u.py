"""Parser, serializzatore e validatore M3U (solo libreria standard).

Ogni canale conserva TUTTE le righe che lo precedono (#EXTVLCOPT, commenti
dedicati) in `extra`, e gli attributi nell'ordine originale, cosi' la
serializzazione e' round-trip fedele.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')


@dataclass
class Channel:
    attrs: dict[str, str]
    title: str
    url: str
    extra: list[str] = field(default_factory=list)  # #EXTVLCOPT ecc. tra EXTINF e URL
    section: list[str] = field(default_factory=list)  # commenti/righe vuote prima del canale

    @property
    def tvg_id(self) -> str:
        return self.attrs.get("tvg-id", "")

    @property
    def chno(self) -> int | None:
        v = self.attrs.get("tvg-chno", "")
        return int(v) if v.isdigit() else None

    @property
    def group(self) -> str:
        return self.attrs.get("group-title", "")

    @property
    def prefix(self) -> str | None:
        m = re.match(r"^([A-Z]{2}) - ", self.title)
        return m.group(1) if m else None


@dataclass
class Playlist:
    header: str
    channels: list[Channel]
    trailer: list[str] = field(default_factory=list)


def _split_extinf(line: str) -> tuple[str, str]:
    """Divide '#EXTINF:-1 attrs,titolo' alla prima virgola FUORI dalle virgolette."""
    inq = False
    for i, ch in enumerate(line):
        if ch == '"':
            inq = not inq
        elif ch == "," and not inq:
            return line[:i], line[i + 1:].strip()
    return line, ""


def parse(text: str) -> Playlist:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or not lines[0].startswith("#EXTM3U"):
        raise ValueError("manca l'intestazione #EXTM3U")
    header, channels, pending = lines[0], [], []
    cur: Channel | None = None
    for line in lines[1:]:
        if line.startswith("#EXTINF:"):
            head, title = _split_extinf(line)
            cur = Channel(dict(ATTR_RE.findall(head)), title.strip(), "", [], pending)
            pending = []
        elif cur is not None and line.startswith("#"):
            cur.extra.append(line)
        elif cur is not None and line.strip():
            cur.url = line.strip()
            channels.append(cur)
            cur = None
        else:
            pending.append(line)
    return Playlist(header, channels, [l for l in pending if l.strip()])


def dumps(pl: Playlist) -> str:
    out = [pl.header]
    for c in pl.channels:
        out += c.section
        attrs = " ".join(f'{k}="{v}"' for k, v in c.attrs.items())
        out.append(f"#EXTINF:-1 {attrs},{c.title}")
        out += c.extra
        out.append(c.url)
    out += pl.trailer
    return "\n".join(out).rstrip("\n") + "\n"


def validate(pl: Playlist) -> tuple[list[str], list[str]]:
    """Ritorna (errori, avvisi). Gli errori bloccano la pubblicazione."""
    errors, warnings = [], []
    if not pl.channels:
        errors.append("playlist vuota")
    seen_url: dict[str, str] = {}
    seen_chno: dict[int, str] = {}
    for c in pl.channels:
        if not re.match(r"^https?://\S+$", c.url):
            errors.append(f"URL non valido: {c.title!r}")
        if not c.title:
            errors.append(f"titolo vuoto per {c.url}")
        if c.chno is None:
            warnings.append(f"tvg-chno mancante/non numerico: {c.title}")
        elif c.chno in seen_chno:
            errors.append(f"tvg-chno {c.chno} duplicato: {c.title} / {seen_chno[c.chno]}")
        else:
            seen_chno[c.chno] = c.title
        if c.url in seen_url:
            warnings.append(f"URL duplicato: {c.title} = {seen_url[c.url]}")
        seen_url.setdefault(c.url, c.title)
        if not c.tvg_id:
            warnings.append(f"tvg-id vuoto (nessuna EPG): {c.title}")
        if c.group.startswith("Internazionali") or c.group.startswith("FAST"):
            if c.prefix is None:
                warnings.append(f"prefisso Paese mancante nel nome: {c.title}")
    return errors, warnings
