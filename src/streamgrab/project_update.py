from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass

import httpx


VERSION_URL = "https://raw.githubusercontent.com/XiaoZzya/Number-download/main/pyproject.toml"


@dataclass(frozen=True, slots=True)
class ProjectUpdate:
    current: str
    latest: str


def _version_key(value: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", value.strip())
    if not match:
        raise ValueError(f"无效版本号：{value}")
    return tuple(int(part or 0) for part in match.groups())


def check_project_update(current: str, timeout: float = 6.0) -> ProjectUpdate | None:
    try:
        response = httpx.get(VERSION_URL, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        latest = str(tomllib.loads(response.text)["project"]["version"])
        if _version_key(latest) > _version_key(current):
            return ProjectUpdate(current, latest)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError):
        return None
    return None
