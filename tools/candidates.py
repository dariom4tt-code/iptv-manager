"""Genera l'elenco dei canali candidati incrociando tutte le fonti, con i filtri di qualita'.
Uso: python tools/candidates.py DIR_FONTI PLAYLIST_ATTUALE  -> stampa markdown."""
import re, sys, collections
from urllib.parse import urlparse
BAD = ('stmify','jsdelivr','github.io/','githubusercontent','ignac16','antik.sk','hopslan','iptvnetwork','freem3u','aynaott','aynascope','tinyurl','bit.ly','bantel-cdn','iptvperu','youtube.com','pluto.tv','plutotv','jmp2.uk/plu-','cdn-redge')
REJECTED = r"mr\.? bean|real wild|pbs nature|dateline|law ?& ?crime|stadium|espn8|red bull|fifa\+|sky news|euronews|al jazeera|cbs news 24|inter 24|tennis\+|guardia costiera|squadra speciale"
CAT = {
 'Notizie': r'\b(bbc news|cnn|bloomberg|cnbc|nhk world|france ?24|dw |sky news|reuters|newsnation|livenow|scripps|abc news|nbc news|cbs news|fox news|fox business|newsmax|cgtn|arirang|trt world|wion|cna\b|euronews|al jazeera|weathernation|accuweather|cheddar|cspan|c-span|24 ?horas|24h|noticias|tagesschau)',
 'Intrattenimento, game show e late show': r"(price is right|family feud|jeopardy|wheel of fortune|press your luck|match game|let.s make a deal|deal or no deal|buzzr|game show|gordon ramsay|kitchen nightmares|hell.s kitchen|bar rescue|baywatch|cops\b|judge judy|jerry springer|maury|dr\.? phil|cheers|frasier|seinfeld|bob ross|antiques roadshow|this old house|impractical jokers|whose line|just for laughs|stand.?up|comedy|funny|late night|tonight show|kimmel|colbert|daily show|gutfeld|conan|jay leno|talk ?show|reality|big brother|survivor|love island|geordie shore|storage wars|pawn stars|american pickers|ancient aliens|mythbusters|unsolved mysteries|forensic files|cold case|csi|law & order|ncis|star trek|doctor who|bake off|masterchef|come dine|grand designs|top gear|homes under|tastemade|bon app|food network|tlc\b|hgtv|a&e|crime|true crime|sitcom|classic tv|retro|nostalg|telenovela|novelas|cine ?(mexicano|clasico|latino)|hola|trece|telecinco|antena 3|cuatro|la ?sexta|mega\b|caracol|rcn|estrella|telemundo|univision|azteca|imagen|multimedios)",
 'Sport': r'(sport|espn|bein|fifa|nfl|nba|mlb|nhl|ufc|wwe|golf|tennis|fight|boxing|poker|motorsport|motogp|formula|racing|f1|real madrid|barça|barca|liga|soccer|futbol|fútbol|cricket|rugby|olympic|eurosport|dazn|fubo|willow|racer|pickleball|horse)',
 'Cartoni e ragazzi': r"(cartoon|nickelodeon|nick ?jr|spongebob|looney|tom (and|&) jerry|garfield|peppa|paw patrol|pok[eé]mon|sonic|care bears|strawberry|rugrats|hey arnold|ninja turtles|powerpuff|adventure time|boomerang|smurfs|bluey|clan\b|disney|sesame|teletubbies|barney|toon|kids|kidz|baby shark|masha|super ?mario|lego|transformers|thomas|bob the builder|pocoyo|cocomelon|ryan)",
 'Documentari e natura': r"(documentar|nature|wild|planet|earth|discovery|nat ?geo|national geographic|history|smithsonian|nova\b|science|space|ocean|animal|dog|cat\b|pets?\b|travel|explor|adventure|outdoor|curiosity|docurama|real wild|bbc earth)",
 'Film e serie': r"(movie|movies|film|cine\b|cinema|thriller|western|horror|sci-?fi|action|drama|series|serie|mystery|crime|hallmark|amc\b|mgm|lionsgate|filmrise|screen|kino)",
}
def norm(n):
    n = re.sub(r'\([^)]*\)|\[[^\]]*\]|[Ⓢ Ⓣ Ⓨ ⓖ]', '', n).lower()
    n = re.sub(r'\b(hd|sd|fhd|uhd|tv|channel|canal|international|usa|us|uk|en|es|east|west)\b', ' ', n)
    return re.sub(r'[^a-z0-9]', '', n)
def load(path, src):
    out, cur = [], None
    for l in open(path, encoding='utf-8', errors='replace'):
        l = l.rstrip()
        if l.startswith('#EXTINF'): cur = (l.rpartition(',')[2].strip(), dict(re.findall(r'([\w-]+)="([^"]*)"', l)))
        elif cur and l.startswith('http'):
            out.append((cur[0], cur[1].get('group-title', ''), l, src)); cur = None
    return out
def ok(t, u):
    h = urlparse(u).hostname or ''
    if not u.startswith('https://') or re.match(r'^\d+\.\d+\.\d+\.\d+$', h): return False
    if not ('.m3u8' in u or 'jmp2.uk/stvp-' in u or '/live?channel=' in u): return False
    if any(b in u for b in BAD) and 'jmp2.uk/stvp-' not in u: return False
    return not re.search(r'geo|not 24/7', t, re.I)
d, cur_pl = sys.argv[1], sys.argv[2]
have = {norm(re.sub(r'^[A-Z]{2} - ', '', x.rpartition(',')[2].strip())) for x in open(cur_pl, encoding='utf-8') if x.startswith('#EXTINF')}
rows = []
for f, s in [('tdt.m3u','TDTChannels'),('stvp_us.m3u','SamsungTV+ US'),('stvp_gb.m3u','SamsungTV+ UK'),('stvp_ca.m3u','SamsungTV+ CA'),('stvp_es.m3u','SamsungTV+ ES'),('iptvorg.m3u','iptv-org'),('freetv.m3u','Free-TV'),('sony.m3u','Sony/Titan IT')]:
    rows += load(f"{d}/{f}", s)
seen, cand = set(), []
for t, g, u, s in rows:
    k = norm(t)
    if not k or k in seen or k in have or not ok(t, u) or re.search(REJECTED, t, re.I): continue
    seen.add(k); cand.append((t, g, u, s))
res = collections.defaultdict(list)
for t, g, u, s in cand:
    for c, p in CAT.items():
        if re.search(p, t, re.I): res[c].append((t, s, urlparse(u).hostname[:26])); break
for c, items in res.items():
    print(f"\n## {c} ({len(items)})")
    for t, s, h in items[:int(sys.argv[3]) if len(sys.argv) > 3 else 40]: print(f"- {t[:46]} | {s} | {h}")
print("\nTOTALE candidati filtrati:", len(cand))
