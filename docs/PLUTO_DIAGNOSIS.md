# Diagnosi audio Pluto TV su Samsung M5 (S27BM502) - 22/11/2026

## Cosa e' verificato (misurato da questo ambiente) e cosa NO
| Punto | Stato |
|---|---|
| Catena: `jmp2.uk/plu-<id>.m3u8` -> HTTP 302 -> `ipv4.pluto.tv/.../master.m3u8?jwt=...` (token ~24h, cache redirect 5 min) | **verificato** |
| Codec: H.264 High (426x240 ... 1280x720) + **AAC-LC 48 kHz stereo** | **verificato con ffprobe** (tutti e 9 i canali) |
| Audio presente e non silenzioso nel flusso (mean -26,6 dB su 15 s) | **verificato con ffmpeg volumedetect** |
| Audio in **due forme**: (a) rendition separata `EXT-X-MEDIA TYPE=AUDIO DEFAULT=YES` con URI proprio, (b) AAC gia' muxato nei TS di ogni variante video | **verificato** |
| Gruppo `TYPE=SUBTITLES` (en) presente, segmenti **AES-128**, audio separato generato "JIT" (`stream(a)` nell'URL), `DISCONTINUITY-SEQUENCE` attivo (cambi clip/pubblicita') | **verificato** |
| Timestamp A/V: nessun salto in 20 s; audio parte ~28 ms dopo il video (normale) | verificato |
| Riproduzione effettiva sul Samsung | **NON verificabile da qui** |

Evidenze (token redatti): `docs/evidence-pluto-*.m3u8`.

## Conclusione tecnica
**Il codec NON e' il problema**: AAC-LC stereo 48 kHz e' supportato da qualsiasi Tizen, e funziona in VLC. Il flusso Pluto differisce da quelli italiani che funzionano (Rai/Mediaset: audio solo muxato, senza gruppi) per il *packaging*: audio dichiarato come rendition separata di default + gruppo sottotitoli + cifratura AES-128 + discontinuita'.
Ipotesi in ordine di probabilita' (NON provate sul dispositivo):
1. **Il player dell'app seleziona/gestisce male la rendition audio separata** (AVPlay richiede `setSelectTrack()` per tracce audio multiple, Samsung FAQ; l'app non espone il selettore). Il fatto che il video suoni in VLC e non sul Samsung e' coerente con questo.
2. Interazione audio separato + AES-128 + discontinuita' nel motore HLS Tizen.
3. Problema specifico della generazione 2020-2022 (esistono segnalazioni Samsung di "HLS video senza audio" su quei modelli, causa non chiarita; la generazione esatta dell'S27BM502 va confermata).
Non ho trovato nessuna segnalazione documentata specifica "M3U IPTV + Pluto/jmp2.uk": e' un'ipotesi, non un problema noto.

## Soluzioni, per probabilita' di successo / semplicita'
1. **(Zero costo, 2 minuti) Prove nell'app**: cercare nelle impostazioni di M3U IPTV un selettore player/motore e provarlo; durante la riproduzione cercare tasto "audio/lingua". Se compare, scegliere "Italian". Non so se la tua versione lo offre (da verificare, vedi TEST_SAMSUNG.md).
2. **App ufficiale Pluto TV per Samsung** (store Tizen, gratuita): audio e guida nativi. Perde i numeri LCN e la playlist unica, ma e' la via legittima piu' sicura. Non verificata da me sul monitor.
3. **Master "piatto"** (nessuna ricodifica): togliere dal master `EXT-X-MEDIA` audio/sottotitoli cosi' il player usa l'AAC gia' muxato. Provato offline: `iptv_manager/pluto_flatten.py` produce un master che ffprobe legge come H.264+AAC con audio reale. Per usarlo senza PC acceso serve un endpoint: `tools/pluto-worker/worker.js` (Cloudflare Workers, piano gratuito, solo manifest). **Non deployato: serve la tua autorizzazione.** Rischi: token Pluto legato alla sessione/IP (il redirect cache di jmp2 con token di altro client ha funzionato dal mio IP, indizio favorevole ma non prova), termini d'uso Pluto/jmp2, non si sa se risolve finche' non lo provi sul Samsung.
4. **Altra app IPTV Tizen** con EPG: da verificare caso per caso, non ancora testata.
5. **FFmpeg/transcodifica**: NON necessaria (audio gia' AAC-LC stereo 48 kHz) e richiederebbe un server attivo: sconsigliata.
