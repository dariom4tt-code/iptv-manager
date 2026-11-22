import pathlib, unittest
from iptv_manager import m3u
ROOT = pathlib.Path(__file__).resolve().parent.parent

class T(unittest.TestCase):
    def test_roundtrip_production(self):
        text = (ROOT / "playlists" / "production.m3u").read_text()
        pl = m3u.parse(text)
        self.assertEqual(len(pl.channels), 92)
        again = m3u.parse(m3u.dumps(pl))
        self.assertEqual([(c.attrs, c.title, c.url, c.extra) for c in pl.channels],
                         [(c.attrs, c.title, c.url, c.extra) for c in again.channels])
    def test_validate_flags_duplicate_chno(self):
        t = '#EXTM3U\n#EXTINF:-1 tvg-id="a" tvg-chno="1",A\nhttp://x/a.m3u8\n#EXTINF:-1 tvg-id="b" tvg-chno="1",B\nhttp://x/b.m3u8\n'
        errors, _ = m3u.validate(m3u.parse(t))
        self.assertTrue(any("duplicato" in e for e in errors))
    def test_comma_inside_attribute(self):
        pl = m3u.parse('#EXTM3U\n#EXTINF:-1 tvg-id="a" tvg-name="X, Y & Co.",Titolo\nhttp://x/a.m3u8\n')
        self.assertEqual(pl.channels[0].attrs["tvg-name"], "X, Y & Co.")
        self.assertEqual(pl.channels[0].title, "Titolo")

if __name__ == "__main__":
    unittest.main()
