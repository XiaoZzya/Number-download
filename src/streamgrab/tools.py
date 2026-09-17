from __future__ import annotations

import hashlib
import io
import json
import platform
import shutil
import stat
import tarfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

import httpx

from .errors import NetworkError
from .paths import tool_dir


RELEASE_API = "https://api.github.com/repos/nilaoda/N_m3u8DL-RE/releases/latest"


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    version: str
    name: str
    url: str
    digest: str | None = None


def should_check(last_check: str, days: int = 7) -> bool:
    if not last_check:
        return True
    try:
        previous = datetime.fromisoformat(last_check)
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - previous >= timedelta(days=days)


def _platform_tokens() -> tuple[str, tuple[str, ...]]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_token = "win" if system == "windows" else "linux" if system == "linux" else "osx"
    if machine in {"x86_64", "amd64"}:
        arch = ("x64", "amd64")
    elif machine in {"aarch64", "arm64"}:
        arch = ("arm64", "aarch64")
    else:
        arch = (machine,)
    return os_token, arch


def select_asset(payload: dict) -> ReleaseAsset:
    os_token, arch_tokens = _platform_tokens()
    candidates = []
    for item in payload.get("assets", []):
        name = str(item.get("name", ""))
        lower = name.lower()
        if os_token in lower and any(token in lower for token in arch_tokens) and lower.endswith((".zip", ".tar.gz")):
            candidates.append(item)
    if not candidates:
        raise NetworkError("官方 Release 中没有适合当前系统架构的安装包")
    item = sorted(candidates, key=lambda value: len(str(value.get("name", ""))))[0]
    return ReleaseAsset(
        version=str(payload.get("tag_name", "unknown")),
        name=str(item["name"]),
        url=str(item["browser_download_url"]),
        digest=str(item.get("digest")) if item.get("digest") else None,
    )


def fetch_latest_release(timeout: float = 20.0, transport=None) -> ReleaseAsset:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, transport=transport) as client:
            response = client.get(RELEASE_API, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            return select_asset(response.json())
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise NetworkError("无法查询 N_m3u8DL-RE 官方 Release") from exc


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts


def _extract_binary(data: bytes, asset_name: str, destination: Path) -> Path:
    executable_name = "N_m3u8DL-RE.exe" if platform.system().lower() == "windows" else "N_m3u8DL-RE"
    found: bytes | None = None
    if asset_name.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                if _safe_member(member.filename) and PurePosixPath(member.filename).name.lower() == executable_name.lower():
                    found = archive.read(member)
                    break
    elif asset_name.lower().endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                if member.isfile() and _safe_member(member.name) and PurePosixPath(member.name).name == executable_name:
                    handle = archive.extractfile(member)
                    found = handle.read() if handle else None
                    break
    if found is None:
        raise NetworkError("官方安装包中未找到 N_m3u8DL-RE 可执行文件")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / executable_name
    temporary = destination / (executable_name + ".new")
    temporary.write_bytes(found)
    temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR)
    temporary.replace(target)
    return target


def install_release(asset: ReleaseAsset, timeout: float = 60.0, transport=None) -> Path:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, transport=transport) as client:
            response = client.get(asset.url)
            response.raise_for_status()
            data = response.content
    except httpx.HTTPError as exc:
        raise NetworkError("下载 N_m3u8DL-RE 官方安装包失败") from exc
    if asset.digest:
        algorithm, _, expected = asset.digest.partition(":")
        if algorithm.lower() != "sha256" or not expected:
            raise NetworkError("官方提供了无法识别的安装包摘要")
        actual = hashlib.sha256(data).hexdigest()
        if actual.lower() != expected.lower():
            raise NetworkError("安装包 SHA-256 校验失败，已停止安装")
    return _extract_binary(data, asset.name, tool_dir())


def find_ffmpeg() -> Path | None:
    located = shutil.which("ffmpeg")
    return Path(located).resolve() if located else None

