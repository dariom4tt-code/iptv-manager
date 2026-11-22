// Cloudflare Worker (piano gratuito) - NON ANCORA DEPLOYATO, richiede approvazione dell'utente.
// GET /pluto/<channelId>.m3u8  ->  master Pluto senza gruppi audio/sottotitoli separati.
// Passa solo il piccolo manifest; i segmenti video/audio li scarica direttamente il Samsung da Pluto.
export default {
  async fetch(request) {
    const m = new URL(request.url).pathname.match(/^\/pluto\/([0-9a-f]{24})\.m3u8$/);
    if (!m) return new Response("not found", { status: 404 });
    const upstream = await fetch(`https://jmp2.uk/plu-${m[1]}.m3u8`, { redirect: "follow" });
    if (!upstream.ok) return new Response("upstream " + upstream.status, { status: 502 });
    const base = upstream.url;
    const out = (await upstream.text()).split(/\r?\n/).flatMap((line) => {
      if (line.startsWith("#EXT-X-MEDIA:") && /TYPE=(AUDIO|SUBTITLES)/.test(line)) return [];
      if (line.startsWith("#EXT-X-STREAM-INF:")) return [line.replace(/,(AUDIO|SUBTITLES|CLOSED-CAPTIONS)="[^"]*"/g, "")];
      if (line && !line.startsWith("#")) return [new URL(line, base).toString()];
      return [line];
    });
    return new Response(out.join("\n"), {
      headers: { "content-type": "application/vnd.apple.mpegurl", "cache-control": "no-store" },
    });
  },
};
