from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "<已隐藏>", "")) if parts.query else url
    except ValueError:
        return "<无效地址>"


def redact_command(command: tuple[str, ...] | list[str]) -> str:
    result: list[str] = []
    for item in command:
        if item.startswith("https://"):
            result.append(redact_url(item))
        elif item.lower().startswith(("cookie:", "authorization:")):
            result.append(item.split(":", 1)[0] + ": <已隐藏>")
        else:
            result.append(item)
    return " ".join(f'"{item}"' if " " in item else item for item in result)
