from __future__ import annotations

import re
from pathlib import Path


INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(media_id: str, title: str, limit: int = 150) -> str:
    value = re.sub(r"\s+", " ", INVALID.sub("_", f"{media_id} {title}")).strip(" ._")
    if not value:
        value = media_id
    if value.upper() in RESERVED:
        value = "_" + value
    return value[:limit].rstrip(" .")


def safe_title_filename(title: str, fallback: str, limit: int = 150) -> str:
    value = re.sub(r"\s+", " ", INVALID.sub("_", title)).strip(" ._") or fallback
    if value.upper() in RESERVED:
        value = "_" + value
    return value[:limit].rstrip(" .")


def numbered_name(
    output_dir: Path,
    save_name: str,
    extensions: tuple[str, ...] = (".mp4", ".mkv", ".ts"),
    *,
    force: bool = False,
) -> str:
    if not force and not any((output_dir / f"{save_name}{ext}").exists() for ext in extensions):
        return save_name
    number = 2
    while any((output_dir / f"{save_name} ({number}){ext}").exists() for ext in extensions):
        number += 1
    return f"{save_name} ({number})"
