from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .paths import config_dir


@dataclass(frozen=True, slots=True)
class Config:
    default_output: str = "/data/downloads/ss"
    downloader_path: str = ""
    extractor_proxy: str = ""
    timeout_seconds: float = 20.0
    last_update_check: str = ""
    chromium_path: str = "/usr/bin/chromium"
    browser_profile: str = "/data/dd/profile/chromium"
    diagnostics_dir: str = "/data/dd/diagnostics"
    temp_root: str = "/data/downloads/ss/.data"
    locale: str = "zh-CN"
    page_timeout_ms: int = 45_000
    search_wait_ms: int = 5_000
    capture_timeout_ms: int = 30_000
    m3u8_preferred_domain: str = "mushroomtrack.com"
    allow_m3u8_fallback: bool = False
    allow_root_no_sandbox: bool = True
    download_threads: int = 8

    def with_update_check_now(self) -> "Config":
        return replace(self, last_update_check=datetime.now(timezone.utc).isoformat())


def config_path() -> Path:
    return config_dir() / "config.toml"


def load_config(path: Path | None = None) -> Config:
    target = path or config_path()
    if not target.exists():
        return Config()
    with target.open("rb") as handle:
        raw = tomllib.load(handle)
    return Config(
        default_output=str(raw.get("default_output", "/data/downloads/ss")),
        downloader_path=str(raw.get("downloader_path", "")),
        extractor_proxy=str(raw.get("extractor_proxy", "")),
        timeout_seconds=float(raw.get("timeout_seconds", 20)),
        last_update_check=str(raw.get("last_update_check", "")),
        chromium_path=str(raw.get("chromium_path", "/usr/bin/chromium")),
        browser_profile=str(raw.get("browser_profile", "/data/dd/profile/chromium")),
        diagnostics_dir=str(raw.get("diagnostics_dir", "/data/dd/diagnostics")),
        temp_root=str(raw.get("temp_root", "/data/downloads/ss/.data")),
        locale=str(raw.get("locale", "zh-CN")),
        page_timeout_ms=int(raw.get("page_timeout_ms", 45_000)),
        search_wait_ms=int(raw.get("search_wait_ms", 5_000)),
        capture_timeout_ms=int(raw.get("capture_timeout_ms", 30_000)),
        m3u8_preferred_domain=str(raw.get("m3u8_preferred_domain", "mushroomtrack.com")),
        allow_m3u8_fallback=bool(raw.get("allow_m3u8_fallback", False)),
        allow_root_no_sandbox=bool(raw.get("allow_root_no_sandbox", True)),
        download_threads=int(raw.get("download_threads", 8)),
    )


def save_config(config: Config, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "default_output": config.default_output,
        "downloader_path": config.downloader_path,
        "extractor_proxy": config.extractor_proxy,
        "timeout_seconds": config.timeout_seconds,
        "last_update_check": config.last_update_check,
        "chromium_path": config.chromium_path,
        "browser_profile": config.browser_profile,
        "diagnostics_dir": config.diagnostics_dir,
        "temp_root": config.temp_root,
        "locale": config.locale,
        "page_timeout_ms": config.page_timeout_ms,
        "search_wait_ms": config.search_wait_ms,
        "capture_timeout_ms": config.capture_timeout_ms,
        "m3u8_preferred_domain": config.m3u8_preferred_domain,
        "allow_m3u8_fallback": config.allow_m3u8_fallback,
        "allow_root_no_sandbox": config.allow_root_no_sandbox,
        "download_threads": config.download_threads,
    }
    lines = []
    for key, value in values.items():
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        else:
            lines.append(f"{key} = {value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
