import httpx
import pytest

from streamgrab.errors import InputError, NoPublicStreamError
from streamgrab.hls import HlsInspector, choose_variant, parse_master_playlist


MASTER = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,CODECS="avc1"
low/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=4000000,RESOLUTION=1920x1080,CODECS="avc1"
https://cdn.example/high/index.m3u8?token=x
"""


def test_parse_master_and_choose_quality():
    variants = parse_master_playlist(MASTER, "https://cdn.example/master.m3u8?token=x")
    assert variants[0].url == "https://cdn.example/low/index.m3u8"
    assert choose_variant(variants, "best").height == 1080
    assert choose_variant(variants, "worst").height == 360
    assert choose_variant(variants, "1080p").bandwidth == 4_000_000


def test_media_playlist_becomes_single_variant():
    variants = parse_master_playlist("#EXTM3U\n#EXTINF:10,\nseg.ts", "https://cdn.example/media.m3u8")
    assert len(variants) == 1
    assert variants[0].url.endswith("media.m3u8")


def test_invalid_playlist_and_quality():
    with pytest.raises(NoPublicStreamError):
        parse_master_playlist("not hls", "https://cdn.example/x.m3u8")
    with pytest.raises(InputError):
        choose_variant(parse_master_playlist(MASTER, "https://cdn.example/x.m3u8"), "720p")


def test_inspector_rejects_non_https():
    inspector = HlsInspector(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=MASTER)))
    with pytest.raises(InputError):
        inspector.inspect("file:///tmp/x.m3u8")
    inspector.close()

