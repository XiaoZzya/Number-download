from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import DownloaderError
from .models import DownloadRequest, DownloadResult


def find_binary(configured: str = "", name: str = "N_m3u8DL-RE") -> Path | None:
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate.resolve()
    found = shutil.which(name) or (shutil.which(name + ".exe") if not name.endswith(".exe") else None)
    return Path(found).resolve() if found else None


def build_command(request: DownloadRequest) -> list[str]:
    command = [
        str(request.downloader_path),
        request.playlist_url,
        "--save-dir",
        str(request.output_dir),
        "--save-name",
        request.save_name,
    ]
    if request.temp_dir is not None:
        command.extend(["--tmp-dir", str(request.temp_dir)])
    command.extend(["--thread-count", str(request.thread_count)])
    command.extend(["-sv", request.video_selector])
    if request.select_best_audio:
        command.extend(["-sa", "best"])
    if request.download_all_subtitles:
        command.extend(["-ss", "all", "--sub-format", request.subtitle_format])
    command.extend(["--del-after-done", "false", "-M", f"format={request.container}"])
    for key, value in request.headers.items():
        if "\n" in key or "\r" in key or "\n" in value or "\r" in value:
            raise DownloaderError("请求头包含非法换行符")
        command.extend(["-H", f"{key}: {value}"])
    return command


class Downloader:
    def run(self, request: DownloadRequest, *, dry_run: bool = False) -> DownloadResult:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        command = build_command(request)
        if dry_run:
            return DownloadResult(0, request.output_dir, request.save_name, tuple(command))
        try:
            completed = subprocess.run(command, check=False)
        except OSError as exc:
            raise DownloaderError(f"无法启动 N_m3u8DL-RE：{exc}") from exc
        if completed.returncode != 0:
            raise DownloaderError(f"N_m3u8DL-RE 执行失败（退出码 {completed.returncode}）")
        return DownloadResult(completed.returncode, request.output_dir, request.save_name, tuple(command))
