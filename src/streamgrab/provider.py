from __future__ import annotations

import html
import os
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit, urlunsplit

from .errors import InputError, NetworkError, NoPublicStreamError, SiteChangedError
from .models import BrowserConfig, CaptureResult, MediaInfo, SearchResult


CARD_RE = re.compile(r'<a[^>]+href=["\'](?P<url>[^"\']+)["\'][^>]*>(?P<body>.*?)</a>', re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
BLOCKED_M3U8_HINTS = ("preview", "trailer", "advert", "/ads/", "sample")
CHALLENGE_HINTS = (
    "cf-chl-", "verify you are human", "checking your browser", "just a moment",
    "captcha", "安全验证", "驗證您是人類",
)


def try_normalize_media_id(value: str) -> str | None:
    value = value.strip()
    compact = re.sub(r"[\s_]+", "-", value).upper()
    numeric = re.search(r"(?<![A-Z0-9])(\d{4,12}-\d{2,6})(?![A-Z0-9])", compact)
    if numeric:
        return numeric.group(1)
    alpha = re.search(r"(?<![A-Z0-9])([A-Z]{2,10})-?(\d{2,6})(?![A-Z0-9])", compact)
    return f"{alpha.group(1)}-{alpha.group(2)}" if alpha else None


def normalize_media_id(value: str) -> str:
    if not value.strip():
        raise InputError("番号不能为空")
    media_id = try_normalize_media_id(value)
    if media_id is None:
        raise InputError("无法识别番号，请输入类似 IPX-850 或 121914-760 的格式")
    return media_id


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", value))).strip()


def _validate_https_url(url: str, *, allowed_hosts: tuple[str, ...] | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise InputError("只接受有效的 HTTPS 地址")
    host = parsed.hostname.lower()
    if allowed_hosts and not any(host == item or host.endswith("." + item) for item in allowed_hosts):
        raise InputError("页面地址不属于受支持的公开站点")
    return url


def extract_search_results(document: str, query: str, search_url: str, provider: str = "jable") -> list[SearchResult]:
    results_by_url: dict[str, SearchResult] = {}
    query_id = try_normalize_media_id(query)
    needle = query_id.replace("-", "").lower() if query_id else ""
    for match in CARD_RE.finditer(document):
        page_url = urljoin(search_url, html.unescape(match.group("url")))
        parsed = urlparse(page_url)
        if parsed.scheme != "https" or not parsed.hostname or "/videos/" not in parsed.path:
            continue
        title = _clean_text(match.group("body"))
        if needle and needle not in (title + page_url).replace("-", "").lower():
            continue
        media_id = try_normalize_media_id(unquote(parsed.path))
        if media_id is None:
            continue
        candidate = SearchResult(provider, media_id, title or media_id, page_url)
        current = results_by_url.get(page_url)
        if current is None or len(candidate.title) > len(current.title):
            results_by_url[page_url] = candidate
    expected = f"/videos/{query_id.lower()}/" if query_id else ""
    return sorted(results_by_url.values(), key=lambda item: (urlparse(item.page_url).path.lower() != expected, -len(item.title)))


def is_challenge_page(title: str, document: str) -> bool:
    sample = (title + "\n" + document[:100_000]).lower()
    return any(hint in sample for hint in CHALLENGE_HINTS)


def is_candidate_m3u8(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    lower = url.lower()
    return (
        parsed.scheme == "https" and bool(parsed.hostname)
        and ".m3u8" in parsed.path.lower()
        and not any(hint in lower for hint in BLOCKED_M3U8_HINTS)
    )


def rank_m3u8_candidates(candidates: list[str], preferred_domain: str, allow_fallback: bool) -> list[str]:
    unique = list(dict.fromkeys(url for url in candidates if is_candidate_m3u8(url)))
    preferred = [url for url in unique if preferred_domain.lower() in (urlparse(url).hostname or "").lower()]
    return preferred or (unique if allow_fallback else [])


def _redacted_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "<hidden>" if parts.query else "", ""))
    except ValueError:
        return "<invalid-url>"


class Provider(ABC):
    @abstractmethod
    def search(self, query: str) -> list[SearchResult]: ...

    @abstractmethod
    def resolve(self, result: SearchResult) -> MediaInfo: ...

    def close(self) -> None:
        return None


class PlaywrightJableProvider(Provider):
    """Run real Chromium under Xvfb without solving or bypassing challenges."""

    provider_name = "jable"
    allowed_hosts = ("jable.tv",)
    base_url = "https://jable.tv"

    def __init__(self, browser_config: BrowserConfig):
        self.config = browser_config
        self._playwright = None
        self._context = None
        self._page = None
        self.last_capture: CaptureResult | None = None

    def _ensure_browser(self):
        if self._page is not None:
            return self._page
        if os.name != "nt" and os.geteuid() == 0 and not self.config.allow_root_no_sandbox:
            raise InputError("root 运行 Chromium 必须在配置中明确允许 no-sandbox")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise InputError("缺少 Playwright，请重新运行安装器") from exc
        if not self.config.chromium_path.is_file():
            raise InputError(f"找不到 Chromium：{self.config.chromium_path}")
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)
        self.config.profile_dir.chmod(0o700)
        args = ["--disable-dev-shm-usage", "--disable-gpu"]
        if os.name != "nt" and os.geteuid() == 0:
            args.append("--no-sandbox")
        if self.config.proxy:
            args.append(f"--proxy-server={self.config.proxy}")
        try:
            self._playwright = sync_playwright().start()
            self._context = self._playwright.chromium.launch_persistent_context(
                str(self.config.profile_dir), headless=False,
                executable_path=str(self.config.chromium_path),
                viewport={"width": 1365, "height": 768}, locale=self.config.locale, args=args,
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._page.set_default_timeout(self.config.page_timeout_ms)
            return self._page
        except Exception as exc:
            self.close()
            raise NetworkError(f"无法启动 Chromium：{exc.__class__.__name__}") from exc

    def close(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._context = self._page = self._playwright = None

    def diagnose_failure(self, stage: str, error: BaseException) -> tuple[Path, Path]:
        directory = self.config.diagnostics_dir
        directory.mkdir(parents=True, exist_ok=True)
        text_path, image_path = directory / "latest.txt", directory / "latest.png"
        image_path.write_bytes(b"")
        current_url = title = ""
        if self._page is not None:
            try:
                current_url = _redacted_url(self._page.url)
                title = self._page.title()
                self._page.screenshot(path=str(image_path), full_page=False)
            except Exception:
                pass
        text_path.write_text(
            f"stage={stage}\nerror_type={error.__class__.__name__}\n"
            f"message={str(error).replace(chr(10), ' ')[:500]}\nurl={current_url}\n"
            f"title={title[:300]}\ntimestamp={time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n",
            encoding="utf-8",
        )
        return text_path, image_path

    def _goto(self, url: str, stage: str):
        page = self._ensure_browser()
        try:
            return page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_timeout_ms)
        except Exception as exc:
            self.diagnose_failure(stage, exc)
            raise NetworkError(f"浏览器在{stage}阶段等待超时或导航失败") from exc

    def search(self, query: str) -> list[SearchResult]:
        query = query.strip()
        if not query:
            raise InputError("搜索关键字不能为空")
        search_url = f"{self.base_url}/search/{quote(query, safe='')}/"
        response = self._goto(search_url, "search")
        page = self._page
        assert page is not None
        try:
            page.wait_for_timeout(self.config.search_wait_ms)
            status = response.status if response is not None else None
            if status is not None and status != 200:
                raise NetworkError(f"搜索页面访问失败（HTTP {status}）")
            document = page.content()
            if is_challenge_page(page.title(), document):
                raise NetworkError("站点要求人工验证；程序不会绕过验证页")
            results = extract_search_results(document, query, search_url, self.provider_name)
            if not results:
                raise NoPublicStreamError(f"没有找到 {query} 的公开作品页面")
            return results
        except (InputError, NetworkError, NoPublicStreamError, SiteChangedError) as exc:
            self.diagnose_failure("search", exc)
            raise

    def direct_result(self, media_id: str) -> SearchResult | None:
        media_id = normalize_media_id(media_id)
        page_url = f"{self.base_url}/videos/{media_id.lower()}/"
        response = self._goto(page_url, "direct")
        page = self._page
        assert page is not None
        try:
            page.wait_for_timeout(self.config.search_wait_ms)
            status = response.status if response is not None else None
            if status in {404, 410}:
                return None
            if status is not None and status != 200:
                raise NetworkError(f"作品页面访问失败（HTTP {status}）")
            document = page.content()
            if is_challenge_page(page.title(), document):
                raise NetworkError("站点要求人工验证；程序不会绕过验证页")
            expected = f"/videos/{media_id.lower()}/"
            if urlparse(page.url).path.lower() != expected:
                return None
            title = page.title().split(" - Jable.TV", 1)[0].strip() or media_id
            return SearchResult(self.provider_name, media_id, title, page_url)
        except (InputError, NetworkError, SiteChangedError) as exc:
            self.diagnose_failure("direct", exc)
            raise

    def result_from_url(self, url: str) -> SearchResult:
        _validate_https_url(url, allowed_hosts=self.allowed_hosts)
        media_id = normalize_media_id(unquote(urlparse(url).path))
        return SearchResult(self.provider_name, media_id, media_id, url)

    def resolve(self, result: SearchResult) -> MediaInfo:
        page_url = _validate_https_url(result.page_url, allowed_hosts=self.allowed_hosts)
        page = self._ensure_browser()
        candidates: list[str] = []

        def record(item) -> None:
            try:
                url = item.url
            except Exception:
                return
            if is_candidate_m3u8(url) and url not in candidates:
                candidates.append(url)

        page.on("request", record)
        page.on("response", record)
        started = time.monotonic()
        response = self._goto(page_url, "capture")
        try:
            status = response.status if response is not None else None
            if status is not None and status != 200:
                raise NetworkError(f"作品页面访问失败（HTTP {status}）")
            deadline = time.monotonic() + self.config.capture_timeout_ms / 1000
            selected: list[str] = []
            while time.monotonic() < deadline:
                selected = rank_m3u8_candidates(candidates, self.config.preferred_domain, self.config.allow_fallback)
                if selected:
                    break
                page.wait_for_timeout(500)
            document = page.content()
            if is_challenge_page(page.title(), document):
                raise NetworkError("作品页停在人工验证页面；程序不会绕过")
            if not selected:
                raise NoPublicStreamError(f"没有捕获到首选域名 {self.config.preferred_domain} 的主视频 m3u8")
            title = page.title().split(" - Jable.TV", 1)[0].strip() or result.title
            user_agent = page.evaluate("() => navigator.userAgent")
            media = MediaInfo(
                self.provider_name, result.media_id, title, page_url, selected[0],
                {"Referer": page_url, "User-Agent": str(user_agent)},
            )
            self.last_capture = CaptureResult(
                media, tuple(_redacted_url(url) for url in candidates), _redacted_url(selected[0]),
                status, time.monotonic() - started,
            )
            return media
        except (InputError, NetworkError, NoPublicStreamError, SiteChangedError) as exc:
            self.diagnose_failure("capture", exc)
            raise
        finally:
            try:
                page.remove_listener("request", record)
                page.remove_listener("response", record)
            except Exception:
                pass


JableProvider = PlaywrightJableProvider
