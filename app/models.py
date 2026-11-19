"""Core data models for peripheral battery status and application settings."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import time
from typing import Optional


class ConnectionType(str, Enum):
    BLUETOOTH = "蓝牙"
    WIRELESS_24G = "2.4G"
    USB_HID = "USB"
    GAMEPAD = "手柄"
    SYSTEM = "本机"


class DeviceKind(str, Enum):
    MOUSE = "mouse"
    HEADSET = "headset"
    EARBUDS = "earbuds"
    KEYBOARD = "keyboard"
    GAMEPAD = "gamepad"
    LAPTOP = "laptop"
    OTHER = "other"


@dataclass
class DeviceBattery:
    """Represents a single peripheral's battery telemetry."""

    device_id: str
    name: str
    percentage: Optional[int]  # 0..100, or None if unknown (e.g. charging without pct)
    connection: ConnectionType
    kind: DeviceKind = DeviceKind.OTHER
    online: bool = True
    charging: bool = False
    voltage_mv: Optional[int] = None
    source: str = ""
    raw_id: str = ""
    status_note: str = ""
    updated_at: float = field(default_factory=time.time)

    @property
    def display_percentage(self) -> str:
        if self.percentage is None:
            return "充电中" if self.charging else "--"
        return f"{self.percentage}%"

    @property
    def sort_key(self) -> tuple:
        # Online first, then 2.4G/BT peripherals before system battery, then lower pct first
        pct = self.percentage if self.percentage is not None else 101
        is_sys = 1 if self.connection == ConnectionType.SYSTEM else 0
        return (0 if self.online else 1, is_sys, pct, self.name.lower())


@dataclass
class AppConfig:
    """Persistent user configuration."""

    refresh_interval: int = 30  # seconds: 15, 30, 60, 120
    pinned_device_id: str = ""  # empty = auto select primary device
    show_offline_devices: bool = True
    show_system_battery: bool = False
    low_battery_notify: bool = True
    low_battery_threshold: int = 20  # 10, 15, 20, 30
    autostart: bool = False
    theme_mode: str = "auto"  # "auto", "dark", "light"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        cfg = cls()
        if not isinstance(data, dict):
            return cfg
        for key in cfg.to_dict():
            if key in data:
                setattr(cfg, key, data[key])
        if cfg.refresh_interval not in (15, 30, 60, 120):
            cfg.refresh_interval = max(10, min(600, int(cfg.refresh_interval or 30)))
        if cfg.low_battery_threshold not in (10, 15, 20, 30):
            cfg.low_battery_threshold = max(5, min(50, int(cfg.low_battery_threshold or 20)))
        if cfg.theme_mode not in ("auto", "dark", "light"):
            cfg.theme_mode = "auto"
        return cfg


def infer_device_kind(name: str, hint: str = "") -> DeviceKind:
    """Infer device icon type from name and protocol hint."""
    text = f"{name} {hint}".lower()
    if any(k in text for k in ("tws", "airpods", "buds", "earbud", "air3", "air2", "freebuds", "enco", "pods")):
        return DeviceKind.EARBUDS
    if any(k in text for k in ("headset", "headphone", "v9 pro", "v9 turbo", "mchose", "x9", "g9", "cloud", "barracuda", "blackshark", "hs", "耳机", "耳麦", "hands-free", "audio")):
        return DeviceKind.HEADSET
    if any(k in text for k in ("mouse", "wu-mouse", "wumouse", "鼠标", "atk a9", "a9 ultra", "vxe", "dragonfly", "viper", "deathadder", "superlight", "g pro", "g304", "g502", "mx master", "mx anywhere", "piao", "s9 pro", "zaopin", "incott")):
        return DeviceKind.MOUSE
    if any(k in text for k in ("keyboard", "kbd", "键盘", "rs6", "f75", "f87", "f99", "keychron", "nuphy", "rainy", "aula", "he68", "hero 68")):
        return DeviceKind.KEYBOARD
    if any(k in text for k in ("xbox", "controller", "gamepad", "dualsense", "dualshock", "手柄", "xinput")):
        return DeviceKind.GAMEPAD
    if any(k in text for k in ("本机电池", "laptop", "system battery")):
        return DeviceKind.LAPTOP
    return DeviceKind.OTHER
