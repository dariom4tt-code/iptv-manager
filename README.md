# IPTV Manager

Gestione personale di una playlist M3U per Samsung Tizen (M3U IPTV): validazione, controllo flussi, EPG, backup/ripristino e pubblicazione sul Gist fisso.

```
Repo GitHub -> Python -> GitHub Actions -> Gist (URL fisso) -> Samsung M5
```
- Gist di produzione: `19eaabb7e385b1e6d1e2f98b011feb41`, file `tv-italia-38.m3u` (nome stabile).
  Raw senza hash: `https://gist.githubusercontent.com/dariom4tt-code/19eaabb7e385b1e6d1e2f98b011feb41/raw/tv-italia-38.m3u` (verificato: HTTP 200, `cache-control: max-age=300`, quindi aggiornamenti visibili entro ~5 min lato GitHub; la cache dell'app Samsung non e' verificata).
- `playlists/production.m3u` = copia del Gist al 22/11/2026 (92 canali). La fonte autorevole resta il Gist.

## Comandi (solo libreria standard + ffprobe)
```bash
python -m unittest discover -s tests
python -m iptv_manager validate [file]
python -m iptv_manager check [--only "PL -"] [--no-deep]   # report in reports/
python -m iptv_manager epg
python -m iptv_manager publish playlists/production.m3u            # dry-run
GIST_TOKEN=... python -m iptv_manager publish FILE --confirm       # solo con approvazione
python -m iptv_manager restore backups/<file>.m3u --confirm        # ripristino immediato
```
## Sicurezza
- Il daily-check non modifica MAI il Gist. Aggiunte/eliminazioni/sostituzioni sono solo proposte (`reports/proposals.json`, soglia 5 fallimenti consecutivi).
- Stati: STREAM_OK (ffprobe), REACHABLE_ONLY, NO_AUDIO, RESTRICTED (401/403/451: non e' prova di morte), UNREACHABLE. "Funziona sul Samsung" solo da `config/device_results.json` (manuale).
- Token: Actions Secret `GIST_TOKEN` (Gist PAT con solo scope `gist`), environment `production` con revisore richiesto. Mai nel codice.
- Backup: `backups/` (baseline del Gist gia' presente; ogni publish salva la versione online).

## Stato / limiti
- Fonti EPG estere: `config/epg_sources.json` le elenca come candidate disabilitate, NON ancora verificate. L'EPG italiana IT1 non e' stata toccata.
- Non ancora fatto: selezione/test di nuove emittenti (ES/PE/UK/US/FR), creazione repo su GitHub, secrets, ricerca di sorgenti alternative. Vedi docs/PLUTO_DIAGNOSIS.md.
