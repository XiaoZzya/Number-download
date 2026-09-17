from __future__ import annotations

import argparse
import os
from pathlib import Path


def _validate_tree(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise ValueError(f"{label}不能是符号链接：{path}")
    resolved = path.resolve()
    forbidden = {Path("/"), Path.home().resolve(), Path("/opt"), Path("/usr"), Path("/home"), Path("/root")}
    if resolved in forbidden or len(resolved.parts) < 3:
        raise ValueError(f"拒绝删除危险的{label}：{resolved}")
    if resolved.exists() and os.path.ismount(resolved):
        raise ValueError(f"拒绝删除挂载点：{resolved}")
    return resolved


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    root = _validate_tree(path, label="目录")
    for current, directories, files in os.walk(root, topdown=False, followlinks=False):
        current_path = Path(current)
        for name in files:
            (current_path / name).unlink()
        for name in directories:
            child = current_path / name
            if child.is_symlink():
                child.unlink()
            else:
                child.rmdir()
    root.rmdir()


def uninstall(install_root: Path, output_root: Path, command_path: Path, *, purge: bool) -> None:
    install_root = _validate_tree(install_root, label="安装目录")
    output_root = _validate_tree(output_root, label="下载目录")
    allowed_command_parents = {Path("/usr/local/bin"), (Path.home() / ".local" / "bin").resolve()}
    if command_path.parent.resolve() not in allowed_command_parents:
        raise ValueError(f"命令入口不在允许目录：{command_path}")
    if command_path.exists() or command_path.is_symlink():
        command_path.unlink()

    if purge:
        _remove_tree(output_root)
        _remove_tree(install_root)
        return

    for name in ("app", "venv", "tools", "diagnostics", "source"):
        _remove_tree(install_root / name)
    for name in ("update.sh",):
        target = install_root / name
        if target.exists() or target.is_symlink():
            target.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--command-path", type=Path, required=True)
    parser.add_argument("--purge", action="store_true")
    args = parser.parse_args()
    uninstall(args.install_root, args.output_root, args.command_path, purge=args.purge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
