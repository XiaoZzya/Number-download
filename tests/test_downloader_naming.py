from pathlib import Path

import pytest

from streamgrab.downloader import Downloader, build_command
from streamgrab.errors import DownloaderError
from streamgrab.models import DownloadRequest
from streamgrab.naming import numbered_name, safe_filename, safe_title_filename
from streamgrab.redact import redact_command, redact_url


def test_safe_filename_blocks_path_and_shell_characters():
    value = safe_filename("IPX-850", '../bad <title> "quoted" | $HOME')
    assert "/" not in value
    assert "\\" not in value
    assert "<" not in value
    assert value.startswith("IPX-850")


def test_numbered_name(tmp_path: Path):
    (tmp_path / "IPX-850 title.mp4").write_bytes(b"x")
    assert numbered_name(tmp_path, "IPX-850 title") == "IPX-850 title (2)"
    assert numbered_name(tmp_path, "IPX-850 new title", force=True) == "IPX-850 new title (2)"


def test_title_filename_does_not_prepend_media_id_twice():
    assert safe_title_filename("SONE-266 测试标题", "SONE-266") == "SONE-266 测试标题"


def test_command_is_argument_list_and_dry_run(tmp_path: Path):
    request = DownloadRequest(
        "https://cdn.example/master.m3u8?token=secret",
        tmp_path,
        'IPX-850 "title"',
        Path("N_m3u8DL-RE"),
        {"Referer": "https://jable.tv/x"},
    )
    command = build_command(request)
    assert command[1].endswith("token=secret")
    assert command[5] == 'IPX-850 "title"'
    assert "-sa" in command and "best" in command
    assert "-ss" in command and "all" in command
    assert command[command.index("--thread-count") + 1] == "8"
    assert command[command.index("--del-after-done") + 1] == "false"
    result = Downloader().run(request, dry_run=True)
    assert result.exit_code == 0
    assert "secret" not in redact_command(result.command)


def test_header_injection_is_rejected(tmp_path: Path):
    request = DownloadRequest("https://x/y.m3u8", tmp_path, "x", Path("tool"), {"X": "ok\nBad: yes"})
    with pytest.raises(DownloaderError):
        build_command(request)


def test_downloader_nonzero_exit_is_reported(tmp_path: Path, monkeypatch):
    request = DownloadRequest("https://x/y.m3u8", tmp_path, "x", Path("tool"))

    class Completed:
        returncode = 9

    monkeypatch.setattr("streamgrab.downloader.subprocess.run", lambda *args, **kwargs: Completed())
    with pytest.raises(DownloaderError, match="退出码 9"):
        Downloader().run(request)


def test_redact_url():
    assert redact_url("https://x/y.m3u8?a=secret") == "https://x/y.m3u8?<已隐藏>"
