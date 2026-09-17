from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import DownloaderError


MEDIA_EXTENSIONS = (".mp4", ".mkv", ".ts", ".m4v", ".mov")


@dataclass(frozen=True, slots=True)
class MediaProbe:
    path: Path
    duration: float
    size: int
    video_codec: str
    audio_codec: str
    width: int
    height: int


def find_finished_file(output_dir: Path, save_name: str) -> Path:
    matches = [
        path for path in output_dir.iterdir()
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
        and (path.stem == save_name or path.stem.startswith(save_name + "."))
    ]
    if not matches:
        raise DownloaderError("下载器执行成功，但没有找到最终媒体文件")
    return max(matches, key=lambda path: path.stat().st_mtime)


def probe_media(path: Path, ffprobe: str = "ffprobe") -> MediaProbe:
    if not path.is_file() or path.stat().st_size <= 0:
        raise DownloaderError("成品不存在或为空，不能清理分片")
    try:
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration,size",
             "-show_entries", "stream=codec_type,codec_name,width,height", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=60,
        )
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise DownloaderError("ffprobe 无法读取成品，分片已保留") from exc
    duration = float(payload.get("format", {}).get("duration", 0) or 0)
    if duration <= 0:
        raise DownloaderError("成品时长为零，分片已保留")
    video = next((item for item in payload.get("streams", []) if item.get("codec_type") == "video"), None)
    if video is None:
        raise DownloaderError("成品没有可读视频流，分片已保留")
    audio = next((item for item in payload.get("streams", []) if item.get("codec_type") == "audio"), {})
    return MediaProbe(
        path=path, duration=duration, size=path.stat().st_size,
        video_codec=str(video.get("codec_name", "unknown")),
        audio_codec=str(audio.get("codec_name", "unknown")),
        width=int(video.get("width", 0) or 0), height=int(video.get("height", 0) or 0),
    )


def existing_media(output_dir: Path, media_id: str) -> list[Path]:
    if not output_dir.is_dir():
        return []
    prefix = media_id.upper()
    return sorted(
        (path for path in output_dir.iterdir() if path.is_file()
         and path.suffix.lower() in MEDIA_EXTENSIONS and path.stem.upper().startswith(prefix)),
        key=lambda path: path.name,
    )
