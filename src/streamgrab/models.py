from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SearchResult:
    provider: str
    media_id: str
    title: str
    page_url: str


@dataclass(frozen=True, slots=True)
class MediaInfo:
    provider: str
    media_id: str
    title: str
    page_url: str
    playlist_url: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Variant:
    url: str
    resolution: str | None = None
    bandwidth: int | None = None
    codecs: str | None = None

    @property
    def height(self) -> int:
        if self.resolution and "x" in self.resolution.lower():
            try:
                return int(self.resolution.lower().split("x", 1)[1])
            except ValueError:
                return 0
        return 0


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    playlist_url: str
    output_dir: Path
    save_name: str
    downloader_path: Path
    headers: dict[str, str] = field(default_factory=dict)
    temp_dir: Path | None = None
    video_selector: str = "best"
    select_best_audio: bool = True
    download_all_subtitles: bool = True
    subtitle_format: str = "SRT"
    container: str = "mp4"
    thread_count: int = 8


@dataclass(frozen=True, slots=True)
class DownloadResult:
    exit_code: int
    output_dir: Path
    save_name: str
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BrowserConfig:
    chromium_path: Path
    profile_dir: Path
    diagnostics_dir: Path
    locale: str = "zh-CN"
    page_timeout_ms: int = 45_000
    search_wait_ms: int = 5_000
    capture_timeout_ms: int = 30_000
    preferred_domain: str = "mushroomtrack.com"
    allow_fallback: bool = False
    allow_root_no_sandbox: bool = False
    proxy: str | None = None


@dataclass(frozen=True, slots=True)
class CaptureResult:
    media: MediaInfo
    candidates: tuple[str, ...]
    selected_url: str
    page_status: int | None
    elapsed_seconds: float
