import io

import pytest

from streamgrab.cli import _choose_search_result, _ensure_ffmpeg, _manual_media, _resolve_media, _validate_proxy
from streamgrab.errors import InputError, NetworkError
from streamgrab.models import SearchResult


def test_manual_media_keeps_safe_referer_only():
    media = _manual_media("IPX-850", "title", "https://jable.tv/videos/ipx-850/", "https://cdn.example/x.m3u8")
    assert media.headers == {"Referer": "https://jable.tv/videos/ipx-850/"}


def test_proxy_rejects_credentials_and_non_http():
    assert _validate_proxy("http://127.0.0.1:7890") == "http://127.0.0.1:7890"
    with pytest.raises(InputError):
        _validate_proxy("http://user:pass@127.0.0.1:7890")
    with pytest.raises(InputError):
        _validate_proxy("socks5://127.0.0.1:7890")


def test_ffmpeg_check_can_be_skipped_for_dry_run(monkeypatch):
    monkeypatch.setattr("streamgrab.cli.find_ffmpeg", lambda: None)
    _ensure_ffmpeg(dry_run=True)
    with pytest.raises(InputError, match="ffmpeg"):
        _ensure_ffmpeg(dry_run=False)


def test_search_403_can_fall_back_to_manual_m3u8(monkeypatch):
    class Provider:
        def search(self, query):
            raise NetworkError("公开页面拒绝访问（HTTP 403）")

    class Interactive(io.StringIO):
        def isatty(self):
            return True

    answers = iter(["y", "https://cdn.example/manual.m3u8"])
    monkeypatch.setattr("streamgrab.cli.sys.stdin", Interactive())
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    media = _resolve_media(Provider(), "IPX-850")
    assert media.provider == "manual"
    assert media.playlist_url == "https://cdn.example/manual.m3u8"


def test_search_menu_does_not_repeat_media_id(monkeypatch, capsys):
    result = SearchResult("jable", "SONE-266", "SONE-266 测试标题", "https://jable.tv/videos/sone-266/")
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")
    assert _choose_search_result([result]) == result
    output = capsys.readouterr().out
    assert "1. SONE-266 测试标题" in output
    assert "SONE-266  SONE-266" not in output
