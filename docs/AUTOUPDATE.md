# Lista autoaggiornante da fonti pubbliche (22/11/2026)

## Cosa dicono davvero le fonti (verificato scaricandole)
| Fonte | Contenuto | Uso |
|---|---|---|
| worldtvlive Pluto / Samsung TV Plus / Rakuten / wedo / DTT (Kodi) | **110 su 159 (DTT) e il 100% di Pluto/Samsung/Rakuten/wedo sono URL `plugin://plugin.video.wltvhelper/...`: funzionano SOLO dentro Kodi**, non sul Samsung | solo **catalogo** (nomi, loghi, ID canale Pluto) |
| worldtvlive **Sony** (`_sonytv/list.m3u8`) | URL HTTP `.../live?channel=...` che risponde **303** verso lo stream wurl/Titan OS attuale | **flussi veri e autoaggiornanti** (include Cinema Italiano, Totò, Alberto Sordi, Sony One, Top Gear, Mayday, BBC Earth, notizie) |
| iptv-org es/pe/uk/us/fr/de/ch | URL HTTP reali, ma qualita' mista (IP nudi, DASH, mirror, restreamer) | candidati filtrati da `config/policy.json` |
| Nanobuo `lista_nazionali` | URL reali; Rai via *relinker* che richiede user-agent specifico | non usata: i flussi diretti Rai del tuo Gist sono migliori (era il motivo per cui "non si vede la Rai") |

Dalle fonti il **Pluto** si ricava solo l'ID canale: URL = `jmp2.uk/plu-<id>.m3u8` (come gia' fai).

## Come funziona
1. `config/curated.json` = **la lista che approvi tu** (103 voci). Il builder sceglie solo l'URL, mai quali canali esistono.
2. Italia (LCN < 100, 47 canali): copia fedele della produzione, URL invariati; 4 correzioni `tvg-id` verificate per corrispondenza esatta in IT1 (LA7 Cinema, Super!, Sky TG24, Radio Italia TV).
3. Stabilita': l'URL scelto resta finche' e' ancora tra i candidati (`config/selected.json`).
4. Canali `hold` (San Marino, RSI) entrano **solo se il controllo li vede STREAM_OK**: si attivano da soli quando tornano a funzionare.
5. Lo staging e' `build/tv-staging.m3u`. Il workflow `update-playlist` lo ricostruisce ogni giorno, lo committa e **non tocca il Gist** a meno che tu imposti la variabile repo `AUTO_PUBLISH=true`; anche allora pubblica solo se `auto_guard` non vede canali aggiunti/rimossi, LCN cambiati o URL storici (Italia) modificati.

## Risultato staging (127 canali, `python -m iptv_manager build`)
- 47 Italia + canali esteri preservati + 55 nuovi da fonti; 11 rimozioni **proposte** (canali minori: GREAT! Romance, BLAZE, MyTime, FailArmy, FilmRise, Hallmark, Grit Xtra, PBS Kids, TV5 Chefs, TJC, Red TV Shop) e Gusto TV (CA) non riproposto: **da approvare**.
- **Non trovati in forma legittima**: BBC One/Two, Channel 4/5, TF1, France 2/3, M6, franceinfo, BFM, ZDF. Le uniche fonti HLS sono restreamer (`cdn-redge.media`, `iptvnetwork`) senza diritti evidenti: esclusi. Si attivano con `include_grey_new=true` in `config/policy.json`: **decisione tua**. (France 5 gia' nel tuo Gist usa lo stesso host: l'ho preservata e segnalata.)
- **Non trovati affatto**: QVC Spagna, ITV1, ABC/CBS/NBC/FOX nazionali (solo affiliate locali: ho messo 4 esempi: FOX NY, CBS Seattle, ABC Cleveland, PBS KQED), America TV e ATV (Perù), RSI (solo DASH/VPN).
- San Marino RTV: in `hold`.

## EPG (verificata sullo staging con epgshare01)
- Guide esistenti e valide: IT1, ES1, PE1, UK1, US2, US_LOCALS1, FR1, DE1, CH1, RAKUTEN1. Fonte italiana IT1 **invariata**.
- Applicati 20 override `tvg-id` con corrispondenza **esatta** e programmi presenti (es. `Das.Erste.de`, `GB.News.HD.uk`, `LATINA.HD.(Latina.HD).pe`, RK Film Top/Azione/Commedia -> `IT:.…-.Rakuten.TV.be`).
- Senza EPG: **Pluto (19 canali), Sony/Titan (22), Canale 21, TV2000, NBC News NOW, CBS News 24/7, Fox Weather, TVPerú, ST BBC Earth**. epgshare01 non ha Pluto/Samsung. Candidata (da verificare, host non ancora raggiunto): `i.mjh.nz/PlutoTV/it.xml.gz`; la guida di Nanobuo e' su github.com releases. Il workflow la verifichera' in rete libera.
- M3U IPTV: il supporto a piu' fonti EPG va provato sul Samsung (non verificato).

## Non verificato
Nessun flusso nuovo e' stato provato: l'ambiente di sviluppo non raggiunge i CDN dei canali (rete ristretta). Il controllo reale (`build --check`: ffprobe video+audio) gira in GitHub Actions; la riproduzione sul Samsung resta tua.
