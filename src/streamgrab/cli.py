from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .config import Config, config_path, load_config, save_config
from .cleanup import directory_usage, prepare_task_directory, remove_verified_task_directory
from .downloader import Downloader, find_binary
from .donate import show_donation
from .errors import InputError, NoPublicStreamError, StreamGrabError
from .history import HistoryStore
from .hls import HlsInspector, choose_variant
from .locking import TaskLock
from .media import existing_media, find_finished_file, probe_media
from .models import BrowserConfig, DownloadRequest, MediaInfo, SearchResult, Variant
from .naming import numbered_name, safe_title_filename
from .paths import data_dir
from .provider import PlaywrightJableProvider, normalize_media_id, try_normalize_media_id
from .redact import redact_command
from .tools import fetch_latest_release, find_ffmpeg, install_release, should_check


def _print_error(message: str) -> None:
    print(f"错误：{message}", file=sys.stderr)


def _confirm(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    answer = input(prompt + suffix).strip().lower()
    return answer in {"y", "yes", "是"} if answer else default


def _download_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nd", description="解析公开 HLS 地址并调用 N_m3u8DL-RE")
    parser.add_argument("target", help="番号、搜索关键字或受支持的作品页 HTTPS 地址")
    parser.add_argument("--output", type=Path, help="保存目录")
    parser.add_argument("--quality", help="best、worst、720p、1080p 等")
    parser.add_argument("--threads", type=int, help="分片下载并发数（默认读取配置，初始为 8）")
    parser.add_argument("--downloader", type=Path, help="N_m3u8DL-RE 可执行文件")
    parser.add_argument("--extractor-proxy", help="仅用于解析器的 HTTP/HTTPS 代理")
    parser.add_argument("--cleanup", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--diagnose", action="store_true", help="失败时显示诊断文件位置")
    parser.add_argument("--dry-run", action="store_true", help="解析并显示脱敏命令，但不下载")
    parser.add_argument("--no-history", action="store_true", help="不写入本地历史")
    parser.add_argument("--version", action="version", version=f"ND {__version__}")
    return parser


def _management_parser(command: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"nd {command}")
    if command == "history":
        parser.add_argument("--limit", type=int, default=20)
    return parser


def _choose_search_result(results: list[SearchResult]) -> SearchResult:
    if not results:
        raise NoPublicStreamError("没有找到匹配的公开作品页面")
    print("\n搜索结果：")
    for index, result in enumerate(results, 1):
        print(f"  {index}. {result.title}\n     {result.page_url}")
    while True:
        answer = input("请选择结果（输入序号，q 取消）：").strip().lower()
        if answer == "q":
            raise KeyboardInterrupt
        try:
            return results[int(answer) - 1]
        except (ValueError, IndexError):
            print("请输入有效序号。")


def _manual_media(target: str, title: str, page_url: str, url: str) -> MediaInfo:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise InputError("手动直链必须是有效的 HTTPS m3u8 地址")
    headers = {"Referer": page_url} if page_url.startswith("https://") else {}
    return MediaInfo("manual", normalize_media_id(target), title, page_url, url.strip(), headers)


def _validate_proxy(proxy: str | None) -> str | None:
    if not proxy:
        return None
    parsed = urlparse(proxy)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InputError("解析器代理必须是有效的 HTTP/HTTPS URL")
    if parsed.username or parsed.password:
        raise InputError("为避免凭据进入配置或进程信息，代理 URL 不允许包含用户名或密码")
    return proxy


def _resolve_media(provider: PlaywrightJableProvider, target: str) -> MediaInfo:
    try:
        if target.lower().startswith("https://"):
            selected = provider.result_from_url(target)
        else:
            media_id = try_normalize_media_id(target)
            direct_result = getattr(provider, "direct_result", None)
            selected = direct_result(media_id) if media_id and direct_result else None
            if selected is None:
                selected = _choose_search_result(provider.search(target))
    except InputError:
        raise
    except StreamGrabError as exc:
        print(f"公开搜索失败：{exc}")
        if not sys.stdin.isatty() or not _confirm("是否粘贴你合法取得的 m3u8 直链？"):
            raise
        media_id = normalize_media_id(target)
        url = input("m3u8 HTTPS 地址：").strip()
        return _manual_media(media_id, media_id, "", url)
    print(f"\n已选择：{selected.media_id}  {selected.title}")
    try:
        return provider.resolve(selected)
    except StreamGrabError as exc:
        print(f"自动解析失败：{exc}")
        if not sys.stdin.isatty() or not _confirm("是否粘贴你合法取得的 m3u8 直链？"):
            raise
        url = input("m3u8 HTTPS 地址：").strip()
        return _manual_media(selected.media_id, selected.title, selected.page_url, url)


def _variant_label(item: Variant) -> str:
    resolution = item.resolution or "未知分辨率"
    bandwidth = f"{item.bandwidth / 1_000_000:.2f} Mbps" if item.bandwidth else "未知码率"
    return f"{resolution} / {bandwidth}"


def _select_variant(variants: list[Variant], quality: str | None) -> Variant:
    if quality:
        return choose_variant(variants, quality)
    if len(variants) == 1:
        print("播放列表只包含一个视频流。")
        return variants[0]
    print("\n可用清晰度：")
    ranked = sorted(variants, key=lambda item: (item.height, item.bandwidth or 0), reverse=True)
    for index, item in enumerate(ranked, 1):
        print(f"  {index}. {_variant_label(item)}")
    while True:
        answer = input("请选择清晰度（默认 1）：").strip() or "1"
        try:
            return ranked[int(answer) - 1]
        except (ValueError, IndexError):
            print("请输入有效序号。")


def _video_selector(variant: Variant) -> str:
    if variant.height:
        return f'res=".*x{variant.height}":for=best'
    return "best"


def _choose_output(argument: Path | None, config: Config) -> Path:
    if argument:
        output = argument.expanduser()
    else:
        output = Path(config.default_output or str(Path.home() / "Downloads")).expanduser()
    if output.exists() and not output.is_dir():
        raise InputError("保存路径不是目录")
    output.mkdir(parents=True, exist_ok=True)
    return output.resolve()


def _check_duplicate(output: Path, media_id: str) -> bool:
    matches = existing_media(output, media_id)
    if not matches:
        return False
    print("\n发现同番号成品：")
    for path in matches:
        print(f"  {path}")
    if sys.stdin.isatty() and not _confirm("是否生成带序号的新文件并继续？"):
        raise InputError("已存在同番号成品，本次未下载")
    return True


def _handle_collision(output: Path, save_name: str) -> str:
    existing = [output / f"{save_name}{ext}" for ext in (".mp4", ".mkv", ".ts")]
    if not any(path.exists() for path in existing):
        return save_name
    print("目标目录中已存在同名媒体文件。")
    while True:
        answer = input("选择 [c]取消、[o]覆盖、[r]自动改名：").strip().lower()
        if answer in {"c", "cancel", "取消"}:
            raise KeyboardInterrupt
        if answer in {"o", "overwrite", "覆盖"}:
            return save_name
        if answer in {"r", "rename", "改名"}:
            return numbered_name(output, save_name)
        print("请输入 c、o 或 r。")


def _browser_config(config: Config, proxy: str | None) -> BrowserConfig:
    return BrowserConfig(
        chromium_path=Path(config.chromium_path),
        profile_dir=Path(config.browser_profile),
        diagnostics_dir=Path(config.diagnostics_dir),
        locale=config.locale,
        page_timeout_ms=config.page_timeout_ms,
        search_wait_ms=config.search_wait_ms,
        capture_timeout_ms=config.capture_timeout_ms,
        preferred_domain=config.m3u8_preferred_domain,
        allow_fallback=config.allow_m3u8_fallback,
        allow_root_no_sandbox=config.allow_root_no_sandbox,
        proxy=proxy,
    )


def _tool_version(binary: Path) -> str:
    try:
        result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=5, check=False)
        return (result.stdout or result.stderr).strip().splitlines()[0][:80] or "unknown"
    except (OSError, subprocess.SubprocessError, IndexError):
        return "unknown"


def _ensure_downloader(config: Config, argument: Path | None, *, dry_run: bool) -> Path:
    binary = find_binary(str(argument) if argument else config.downloader_path)
    if binary:
        return binary
    if dry_run:
        return Path("N_m3u8DL-RE")
    if not sys.stdin.isatty() or not _confirm("未找到 N_m3u8DL-RE，是否从官方 Release 安装到用户目录？"):
        raise InputError("未找到 N_m3u8DL-RE；可用 --downloader 指定路径")
    asset = fetch_latest_release(config.timeout_seconds)
    print(f"将安装官方版本 {asset.version}：{asset.name}")
    if not _confirm("继续下载安装？"):
        raise InputError("已取消工具安装")
    binary = install_release(asset)
    save_config(replace(config, downloader_path=str(binary)))
    print(f"已安装到：{binary}")
    return binary


def _ensure_ffmpeg(*, dry_run: bool) -> None:
    if dry_run or find_ffmpeg():
        return
    if sys.platform == "win32":
        hint = "请安装 ffmpeg 并把其 bin 目录加入当前用户 PATH"
    else:
        hint = "Debian/Ubuntu 可运行：sudo apt install ffmpeg"
    raise InputError(f"未找到 ffmpeg；{hint}，然后运行 nd doctor 检查")


def _weekly_update_notice(config: Config) -> None:
    if not should_check(config.last_update_check):
        return
    updated = config.with_update_check_now()
    try:
        asset = fetch_latest_release(min(config.timeout_seconds, 10))
        print(f"工具版本检查：官方最新版本为 {asset.version}；需要更新时运行 nd update-tools。")
    except StreamGrabError:
        pass
    finally:
        try:
            save_config(updated)
        except OSError:
            pass


def run_download(argv: list[str]) -> int:
    args = _download_parser().parse_args(argv)
    config = load_config()
    thread_count = args.threads if args.threads is not None else config.download_threads
    if not 1 <= thread_count <= 64:
        raise InputError("下载线程数必须在 1 到 64 之间")
    proxy = _validate_proxy(args.extractor_proxy or config.extractor_proxy or None)
    output = _choose_output(args.output, config)
    if os.name != "nt" and os.geteuid() == 0 and config.allow_root_no_sandbox:
        print("警告：Chromium 将以 root + --no-sandbox 运行；这是已明确接受的安全风险。")
    provider = PlaywrightJableProvider(_browser_config(config, proxy))
    inspector = HlsInspector(proxy=proxy, timeout=config.timeout_seconds)
    media_id = try_normalize_media_id(args.target) or "unknown"
    try:
        media = _resolve_media(provider, args.target)
        media_id = media.media_id
        duplicate = _check_duplicate(output, media_id)
        variants = inspector.inspect(media.playlist_url, media.headers)
        variant = _select_variant(variants, args.quality)
        # Jable 标题本身已经以番号开头，不再额外拼接一次番号。
        save_name = safe_title_filename(media.title, media.media_id)
        if duplicate:
            save_name = numbered_name(output, save_name, force=True)
        else:
            save_name = _handle_collision(output, save_name)
        binary = _ensure_downloader(config, args.downloader, dry_run=args.dry_run)
        _ensure_ffmpeg(dry_run=args.dry_run)
        temp_root = Path(config.temp_root)
        task_dir = temp_root / media.media_id
        if not args.dry_run:
            task_dir = prepare_task_directory(temp_root, media.media_id)
            temp_root = temp_root.resolve()
        request = DownloadRequest(
            media.playlist_url, output, save_name, binary, media.headers,
            temp_dir=task_dir, video_selector=_video_selector(variant),
            select_best_audio=True, download_all_subtitles=True,
            subtitle_format="SRT", container="mp4", thread_count=thread_count,
        )
        result = Downloader().run(request, dry_run=args.dry_run)
        if args.dry_run:
            print("\n演练命令（敏感查询参数已隐藏）：")
            print(redact_command(result.command))
            return 0
        output_hint = find_finished_file(output, save_name)
        probe = probe_media(output_hint)
        print(
            f"\n成品验证通过：{probe.video_codec.upper()} {probe.width}x{probe.height} / "
            f"{probe.audio_codec.upper()} / {probe.duration:.1f} 秒 / {probe.size / (1024**3):.2f} GB"
        )
        if not args.no_history:
            HistoryStore().add(media.media_id, media.title, output_hint, "success", _tool_version(binary))
        print(f"下载完成：{output_hint}")
        if task_dir.exists():
            try:
                remove_verified_task_directory(temp_root, media.media_id, task_dir)
                print(f"已清理本次分片：{task_dir}")
            except (OSError, InputError) as exc:
                print(f"警告：成品已保留，但分片清理失败：{exc}", file=sys.stderr)
        return 0
    except StreamGrabError as exc:
        diagnostic_text = Path(config.diagnostics_dir) / "latest.txt"
        if args.diagnose and not diagnostic_text.exists():
            try:
                provider.diagnose_failure("workflow", exc)
            except OSError:
                pass
        if diagnostic_text.exists():
            print(f"诊断文件：{config.diagnostics_dir}/latest.txt 和 latest.png", file=sys.stderr)
        task_dir = Path(config.temp_root) / media_id
        if task_dir.exists():
            usage = directory_usage(task_dir)
            print(f"未完成分片已保留：{task_dir}（{usage.files} 个文件，{usage.bytes / (1024**3):.2f} GB）", file=sys.stderr)
        raise
    finally:
        provider.close()
        inspector.close()


def run_doctor(argv: list[str]) -> int:
    _management_parser("doctor").parse_args(argv)
    config = load_config()
    downloader = find_binary(config.downloader_path)
    ffmpeg = find_ffmpeg()
    chromium = Path(config.chromium_path)
    xvfb = shutil.which("xvfb-run")
    try:
        import playwright  # noqa: F401
        playwright_status = "已安装"
    except ImportError:
        playwright_status = "未安装"
    output = Path(config.default_output)
    free_gb = shutil.disk_usage(output if output.exists() else output.parent).free / (1024**3) if output.parent.exists() else 0
    print(f"ND：{__version__}")
    print(f"Python：{sys.version.split()[0]} ({sys.executable})")
    print(f"配置文件：{config_path()}")
    print(f"数据目录：{data_dir()}")
    print(f"N_m3u8DL-RE：{downloader or '未找到'}")
    print(f"ffmpeg：{ffmpeg or '未找到'}")
    print(f"Chromium：{chromium if chromium.is_file() else '未找到'}")
    print(f"Xvfb：{xvfb or '未找到'}")
    print(f"Playwright：{playwright_status}")
    print(f"浏览器 profile：{config.browser_profile}")
    print(f"目标磁盘可用空间：{free_gb:.2f} GB")
    print(f"root no-sandbox：{'已明确启用（有风险）' if config.allow_root_no_sandbox else '未启用'}")
    return 0 if downloader and ffmpeg and chromium.is_file() and xvfb and playwright_status == "已安装" else 2


def run_update(argv: list[str]) -> int:
    _management_parser("update-tools").parse_args(argv)
    config = load_config()
    asset = fetch_latest_release(config.timeout_seconds)
    print(f"官方最新版本：{asset.version}（{asset.name}）")
    if not _confirm("下载并安装到 ND 工具目录？"):
        print("已取消。")
        return 0
    binary = install_release(asset)
    save_config(replace(config.with_update_check_now(), downloader_path=str(binary)))
    print(f"更新完成：{binary}")
    return 0


def run_self_update(argv: list[str]) -> int:
    _management_parser("update").parse_args(argv)
    updater = data_dir() / "update.sh"
    if not updater.is_file():
        raise InputError(f"找不到更新脚本：{updater}；请使用新版 install.sh 重新安装一次")
    try:
        completed = subprocess.run([str(updater)], check=False)
    except OSError as exc:
        raise InputError(f"无法启动更新脚本：{exc}") from exc
    if completed.returncode != 0:
        raise InputError(f"更新失败（退出码 {completed.returncode}），现有配置和 profile 已保留")
    return 0


def run_history(argv: list[str]) -> int:
    args = _management_parser("history").parse_args(argv)
    if args.limit < 1 or args.limit > 1000:
        raise InputError("--limit 必须在 1 到 1000 之间")
    entries = HistoryStore().list(args.limit)
    if not entries:
        print("暂无下载历史。")
        return 0
    for entry in entries:
        when = entry.created_at.replace("T", " ")[:19]
        print(f"{when}  {entry.status:<8}  {entry.media_id}  {entry.title}\n  {entry.output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments and arguments[0] == "doctor":
            return run_doctor(arguments[1:])
        if arguments and arguments[0] == "update-tools":
            return run_update(arguments[1:])
        if arguments and arguments[0] == "update":
            return run_self_update(arguments[1:])
        if arguments and arguments[0] == "history":
            return run_history(arguments[1:])
        if arguments and arguments[0] == "donate":
            _management_parser("donate").parse_args(arguments[1:])
            show_donation()
            return 0
        if not arguments:
            _download_parser().print_help()
            return 2
        if any(flag in arguments for flag in ("-h", "--help", "--version")):
            return run_download(arguments)
        with TaskLock(data_dir() / "nd.lock"):
            result = run_download(arguments)
        if result == 0 and "--dry-run" not in arguments:
            try:
                _weekly_update_notice(load_config())
            except OSError:
                pass
        return result
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except StreamGrabError as exc:
        _print_error(str(exc))
        return exc.exit_code
    except (OSError, ValueError) as exc:
        _print_error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
