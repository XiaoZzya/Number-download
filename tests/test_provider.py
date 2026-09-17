from pathlib import Path

import pytest

from streamgrab.errors import InputError
from streamgrab.models import BrowserConfig
from streamgrab.provider import (
    PlaywrightJableProvider,
    extract_search_results,
    is_candidate_m3u8,
    is_challenge_page,
    normalize_media_id,
    rank_m3u8_candidates,
)


def browser_config(tmp_path: Path) -> BrowserConfig:
    return BrowserConfig(
        chromium_path=tmp_path / "chromium",
        profile_dir=tmp_path / "profile",
        diagnostics_dir=tmp_path / "diagnostics",
    )


def test_normalize_media_id():
    assert normalize_media_id(" ipx_850 ") == "IPX-850"
    assert normalize_media_id("121914-760") == "121914-760"
    assert normalize_media_id("https://example.test/videos/abc-123/") == "ABC-123"


def test_normalize_media_id_rejects_invalid():
    with pytest.raises(InputError):
        normalize_media_id("not-an-id")


def test_search_results_deduplicate_and_prefer_exact_title():
    document = (
        '<a href="/videos/ipx-718/">IPX-718 unrelated</a>'
        '<a href="/videos/ipx-850/">2:26:25</a>'
        '<h6><a href="/videos/ipx-850/"><span>IPX-850 测试标题</span></a></h6>'
        '<a href="/videos/ipx-850-extra/">IPX-850 compilation</a>'
    )
    results = extract_search_results(document, "IPX-850", "https://jable.tv/search/IPX-850/")
    assert len(results) == 2
    assert results[0].page_url == "https://jable.tv/videos/ipx-850/"
    assert results[0].title == "IPX-850 测试标题"


def test_keyword_search_extracts_each_result_media_id():
    document = '<a href="/videos/sone-266/">河北彩花 SONE-266</a>'
    results = extract_search_results(document, "河北彩花", "https://jable.tv/search/x/")
    assert results[0].media_id == "SONE-266"


def test_challenge_detection():
    assert is_challenge_page("Just a moment...", "checking your browser")
    assert not is_challenge_page("IPX-850", "normal result page")


def test_candidate_ranking_prefers_main_cdn_and_excludes_preview():
    candidates = [
        "https://ads.example/preview.m3u8",
        "https://other.example/main.m3u8",
        "https://cdn.mushroomtrack.com/hls/main.m3u8",
    ]
    assert not is_candidate_m3u8(candidates[0])
    ranked = rank_m3u8_candidates(candidates, "mushroomtrack.com", False)
    assert ranked == ["https://cdn.mushroomtrack.com/hls/main.m3u8"]
    assert rank_m3u8_candidates([candidates[1]], "mushroomtrack.com", False) == []
    assert rank_m3u8_candidates([candidates[1]], "mushroomtrack.com", True) == [candidates[1]]


def test_result_from_url_rejects_other_hosts(tmp_path: Path):
    provider = PlaywrightJableProvider(browser_config(tmp_path))
    with pytest.raises(InputError):
        provider.result_from_url("https://example.com/ipx-850")


def test_diagnostics_redacts_query(tmp_path: Path):
    provider = PlaywrightJableProvider(browser_config(tmp_path))

    class Page:
        url = "https://jable.tv/test?token=secret"

        def title(self):
            return "Verification"

        def screenshot(self, **kwargs):
            Path(kwargs["path"]).write_bytes(b"png")

    provider._page = Page()
    text_path, image_path = provider.diagnose_failure("search", RuntimeError("failed"))
    report = text_path.read_text(encoding="utf-8")
    assert "secret" not in report
    assert "<hidden>" in report
    assert image_path.read_bytes() == b"png"
