from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

from .errors import InputError, NetworkError, NoPublicStreamError
from .models import Variant


ATTR_RE = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', re.I)


def _validate_playlist_url(url: str) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise InputError("m3u8 必须是有效的 HTTPS 地址")


def parse_master_playlist(text: str, base_url: str) -> list[Variant]:
    if not text.lstrip().startswith("#EXTM3U"):
        raise NoPublicStreamError("地址返回的内容不是有效的 m3u8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    variants: list[Variant] = []
    for index, line in enumerate(lines):
        if not line.upper().startswith("#EXT-X-STREAM-INF:"):
            continue
        attrs = {key.upper(): value.strip('"') for key, value in ATTR_RE.findall(line.split(":", 1)[1])}
        uri = next((item for item in lines[index + 1 :] if not item.startswith("#")), "")
        if not uri:
            continue
        try:
            bandwidth = int(attrs["BANDWIDTH"]) if attrs.get("BANDWIDTH") else None
        except ValueError:
            bandwidth = None
        variants.append(
            Variant(
                url=urljoin(base_url, uri),
                resolution=attrs.get("RESOLUTION"),
                bandwidth=bandwidth,
                codecs=attrs.get("CODECS"),
            )
        )
    return variants or [Variant(url=base_url)]


class HlsInspector:
    def __init__(self, *, proxy: str | None = None, timeout: float = 20.0, transport=None):
        kwargs: dict[str, object] = {"timeout": timeout, "follow_redirects": True}
        if proxy:
            kwargs["proxy"] = proxy
        if transport is not None:
            kwargs["transport"] = transport
        self.client = httpx.Client(**kwargs)

    def close(self) -> None:
        self.client.close()

    def inspect(self, url: str, headers: dict[str, str] | None = None) -> list[Variant]:
        _validate_playlist_url(url)
        try:
            response = self.client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise NetworkError("读取 m3u8 超时，直链可能已经过期") from exc
        except httpx.HTTPStatusError as exc:
            raise NetworkError(f"读取 m3u8 失败（HTTP {exc.response.status_code}）") from exc
        except httpx.HTTPError as exc:
            raise NetworkError(f"读取 m3u8 失败：{exc.__class__.__name__}") from exc
        return parse_master_playlist(response.text, str(response.url))


def choose_variant(variants: list[Variant], quality: str) -> Variant:
    if not variants:
        raise NoPublicStreamError("没有可选的视频流")
    ranked = sorted(variants, key=lambda item: (item.height, item.bandwidth or 0))
    quality = quality.lower()
    if quality == "best":
        return ranked[-1]
    if quality == "worst":
        return ranked[0]
    match = re.fullmatch(r"(\d{3,4})p", quality)
    if not match:
        raise InputError("清晰度格式应为 best、worst、720p 或 1080p")
    target = int(match.group(1))
    exact = [item for item in ranked if item.height == target]
    if not exact:
        available = ", ".join(str(item.height) + "p" for item in ranked if item.height)
        raise InputError(f"没有 {quality} 清晰度；可用：{available or '未知'}")
    return exact[-1]

