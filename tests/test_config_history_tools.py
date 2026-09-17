import hashlib
import io
import sqlite3
import zipfile
from pathlib import Path

import pytest

from streamgrab.config import Config, load_config, save_config
from streamgrab.history import HistoryStore
from streamgrab.tools import ReleaseAsset, _extract_binary, select_asset, should_check


def test_config_round_trip(tmp_path: Path):
    path = tmp_path / "config.toml"
    expected = Config("D:\\视频", "C:\\Tools\\N_m3u8DL-RE.exe", "http://127.0.0.1:7890", 12.5, "2026-01-01T00:00:00+00:00")
    save_config(expected, path)
    assert load_config(path) == expected


def test_history_schema_never_has_url_or_headers(tmp_path: Path):
    path = tmp_path / "history.sqlite3"
    store = HistoryStore(path)
    store.add("IPX-850", "标题", tmp_path / "IPX-850 标题.mp4", "success", "v1")
    entry = store.list()[0]
    assert entry.media_id == "IPX-850"
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(downloads)")}
    assert "playlist_url" not in columns
    assert "headers" not in columns


def test_select_asset_for_current_platform(monkeypatch):
    monkeypatch.setattr("streamgrab.tools._platform_tokens", lambda: ("linux", ("x64",)))
    asset = select_asset({
        "tag_name": "v1",
        "assets": [
            {"name": "tool-win-x64.zip", "browser_download_url": "https://x/win"},
            {"name": "tool-linux-x64.tar.gz", "browser_download_url": "https://x/linux", "digest": "sha256:abc"},
        ],
    })
    assert asset.name == "tool-linux-x64.tar.gz"
    assert asset.digest == "sha256:abc"


def test_safe_zip_extracts_only_binary(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("streamgrab.tools.platform.system", lambda: "Windows")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("folder/N_m3u8DL-RE.exe", b"binary")
        archive.writestr("../escape.txt", b"bad")
    result = _extract_binary(buffer.getvalue(), "release.zip", tmp_path)
    assert result.read_bytes() == b"binary"
    assert not (tmp_path.parent / "escape.txt").exists()


def test_update_check_invalid_or_empty_is_due():
    assert should_check("")
    assert should_check("not-a-date")

