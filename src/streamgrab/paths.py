from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "streamgrab"


def config_dir() -> Path:
    configured = os.environ.get("STREAMGRAB_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "StreamGrab"
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / APP_NAME


def data_dir() -> Path:
    configured = os.environ.get("STREAMGRAB_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "StreamGrab"
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / APP_NAME


def tool_dir() -> Path:
    return data_dir() / "tools"
