from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import InputError
from .provider import normalize_media_id


@dataclass(frozen=True, slots=True)
class DirectoryUsage:
    files: int
    bytes: int


def directory_usage(path: Path) -> DirectoryUsage:
    files = size = 0
    if not path.exists():
        return DirectoryUsage(0, 0)
    for root, _, names in os.walk(path, followlinks=False):
        for name in names:
            item = Path(root) / name
            if not item.is_symlink():
                files += 1
                try:
                    size += item.stat().st_size
                except OSError:
                    pass
    return DirectoryUsage(files, size)


def validate_task_directory(
    temp_root: Path,
    media_id: str,
    task_dir: Path,
    *,
    require_safe_rmtree: bool = True,
) -> Path:
    normalized = normalize_media_id(media_id)
    root = temp_root.resolve(strict=True)
    if temp_root.is_symlink() or task_dir.is_symlink():
        raise InputError("拒绝清理符号链接目录")
    target = task_dir.resolve(strict=True)
    if target == root or target.parent != root or target.name != normalized:
        raise InputError("清理目标不是当前番号的受控任务目录")
    if os.path.ismount(target):
        raise InputError("拒绝清理挂载点")
    for current, directories, files in os.walk(target, followlinks=False):
        current_path = Path(current)
        for name in (*directories, *files):
            item = current_path / name
            if item.is_symlink():
                raise InputError(f"任务目录包含符号链接，拒绝清理：{item}")
            if item.is_dir() and os.path.ismount(item):
                raise InputError(f"任务目录包含嵌套挂载点，拒绝清理：{item}")
    if require_safe_rmtree and not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
        raise InputError("当前 Python 平台不支持防符号链接攻击的安全目录清理")
    return target


def prepare_task_directory(temp_root: Path, media_id: str) -> Path:
    normalized = normalize_media_id(media_id)
    if temp_root.is_symlink():
        raise InputError("临时根目录不能是符号链接")
    temp_root.mkdir(parents=True, exist_ok=True)
    task_dir = temp_root / normalized
    if task_dir.is_symlink():
        raise InputError("当前任务目录不能是符号链接")
    task_dir.mkdir(parents=False, exist_ok=True)
    return validate_task_directory(temp_root, normalized, task_dir, require_safe_rmtree=False)


def remove_verified_task_directory(temp_root: Path, media_id: str, task_dir: Path) -> None:
    target = validate_task_directory(temp_root, media_id, task_dir)
    shutil.rmtree(target)
