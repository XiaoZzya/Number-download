import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from streamgrab.cleanup import directory_usage, prepare_task_directory, remove_verified_task_directory, validate_task_directory
from streamgrab.errors import DownloaderError, InputError
from streamgrab.media import probe_media


def test_probe_media_requires_video_and_positive_duration(tmp_path: Path, monkeypatch):
    media = tmp_path / "IPX-850 title.mp4"
    media.write_bytes(b"media")
    payload = {
        "format": {"duration": "12.5", "size": "5"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }
    monkeypatch.setattr("streamgrab.media.subprocess.run", lambda *a, **k: SimpleNamespace(stdout=json.dumps(payload)))
    result = probe_media(media)
    assert result.duration == 12.5
    assert result.video_codec == "h264"


def test_probe_media_rejects_zero_duration(tmp_path: Path, monkeypatch):
    media = tmp_path / "bad.mp4"
    media.write_bytes(b"x")
    payload = {"format": {"duration": "0"}, "streams": [{"codec_type": "video"}]}
    monkeypatch.setattr("streamgrab.media.subprocess.run", lambda *a, **k: SimpleNamespace(stdout=json.dumps(payload)))
    with pytest.raises(DownloaderError, match="时长为零"):
        probe_media(media)


def test_cleanup_only_exact_current_task(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("streamgrab.cleanup.shutil.rmtree.avoids_symlink_attacks", True, raising=False)
    root = tmp_path / ".data"
    task = root / "IPX-850"
    other = root / "IPX-851"
    task.mkdir(parents=True)
    other.mkdir()
    (task / "seg.ts").write_bytes(b"123")
    (other / "keep.ts").write_bytes(b"456")
    assert validate_task_directory(root, "IPX-850", task) == task.resolve()
    assert directory_usage(task).files == 1
    remove_verified_task_directory(root, "IPX-850", task)
    assert not task.exists()
    assert (other / "keep.ts").exists()


def test_cleanup_rejects_nested_symlink(tmp_path: Path):
    root = tmp_path / ".data"
    task = root / "IPX-850"
    outside = tmp_path / "outside"
    task.mkdir(parents=True)
    outside.mkdir()
    link = task / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(InputError, match="符号链接"):
        validate_task_directory(root, "IPX-850", task)


def test_prepare_task_directory_is_exact_child(tmp_path: Path):
    root = tmp_path / ".data"
    task = prepare_task_directory(root, "ipx850")
    assert task == (root / "IPX-850").resolve()


def test_cleanup_rejects_root_other_task_and_symlink(tmp_path: Path):
    root = tmp_path / ".data"
    task = root / "IPX-850"
    other = root / "IPX-851"
    task.mkdir(parents=True)
    other.mkdir()
    with pytest.raises(InputError):
        validate_task_directory(root, "IPX-850", root)
    with pytest.raises(InputError):
        validate_task_directory(root, "IPX-850", other)
    link = root / "IPX-852"
    try:
        link.symlink_to(task, target_is_directory=True)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(InputError):
        validate_task_directory(root, "IPX-852", link)
