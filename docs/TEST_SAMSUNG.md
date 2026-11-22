# Test di Il Testimone sul Samsung (semplice)

Prima: annota **versione di M3U IPTV** (Impostazioni/Info dell'app) e **anno/firmware** del monitor (Impostazioni > Supporto > Informazioni).

1. Per non toccare la produzione: crea un Gist **di prova** (o un file di staging) con `playlists/pluto-test.m3u` e caricalo in M3U IPTV come playlist separata. (Non sostituire l'URL di produzione.)
2. Apri **C1 Rai 1**: deve avere audio (se no: problema di volume/uscita, non di Pluto). Apri **C2 Rakuten**: segna se ha audio.
3. Apri **T1 Il Testimone**: aspetta 30 secondi. Segna: video SI/NO, audio SI/NO.
4. Durante T1 premi i tasti freccia/Info/menu dell'app: esiste "Audio", "Lingua", "Player" o "Motore video"? Segna cosa appare (foto con il telefono).
5. Prova anche un altro canale Pluto (es. Totò) e Samsung TV Plus (BBC Earth).
6. Scrivi i risultati in `config/device_results.json` (es. `"PL - Il Testimone": "VIDEO_SI_AUDIO_NO"`) oppure mandameli e li inserisco.
7. Solo se autorizzi il Worker, avrai la voce T2 da provare nello stesso modo.

Come interpretare: C1 e C2 con audio + T1 senza = problema del packaging Pluto (ipotesi 1-2). Anche C2 senza audio = problema piu' generale dei flussi FAST/demuxed.
