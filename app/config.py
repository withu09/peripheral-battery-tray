"""JSON configuration persistence and Windows HKCU Run autostart management."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import winreg

from .models import AppConfig

APP_NAME = "PeripheralBatteryTray"
RUN_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_config_path() -> Path:
    # Store config cleanly in project root (portable) if writable, else AppData
    local_path = get_project_root() / "config.json"
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if local_path.exists():
            return local_path
        # Test writability
        with open(local_path, "a", encoding="utf-8"):
            pass
        if local_path.stat().st_size == 0:
            local_path.unlink(missing_ok=True)
        return local_path
    except OSError:
        appdata = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata / "config.json"


def _get_autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    py_dir = Path(sys.executable).resolve().parent
    pythonw = py_dir / "pythonw.exe"
    exe = pythonw if pythonw.exists() else Path(sys.executable).resolve()
    launcher = get_project_root() / "run.pyw"
    return f'"{exe}" "{launcher}"'


def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_autostart(enabled: bool) -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_REG_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def load_config() -> AppConfig:
    path = get_config_path()
    cfg = AppConfig()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = AppConfig.from_dict(json.load(f))
        except Exception:
            cfg = AppConfig()
    cfg.autostart = is_autostart_enabled()
    return cfg


def save_config(cfg: AppConfig) -> None:
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg.to_dict(), f, ensure_ascii=False, indent=2)
    except OSError:
        pass
