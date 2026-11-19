"""Aggregates, deduplicates, and prioritizes battery telemetry across all providers."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from ..models import AppConfig, ConnectionType, DeviceBattery
from .bluetooth_pnp import scan_bluetooth_batteries
from .hid_24g import scan_hid_24g_batteries
from .system_battery import scan_system_battery
from .xinput_battery import scan_xinput_batteries


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", name.lower())


class BatteryManager:
    """Runs all enabled battery providers and maintains deduplicated device snapshots."""

    def __init__(self) -> None:
        self._last_devices: List[DeviceBattery] = []

    def scan_all(self, cfg: AppConfig) -> List[DeviceBattery]:
        raw: List[DeviceBattery] = []
        try:
            raw.extend(scan_hid_24g_batteries())
        except Exception:
            pass
        try:
            raw.extend(scan_bluetooth_batteries())
        except Exception:
            pass
        try:
            raw.extend(scan_xinput_batteries())
        except Exception:
            pass
        if cfg.show_system_battery:
            try:
                raw.extend(scan_system_battery())
            except Exception:
                pass

        # Deduplicate devices that appear on both 2.4G and offline Bluetooth
        by_norm: Dict[str, DeviceBattery] = {}
        for dev in raw:
            key = _norm_name(dev.name) or dev.device_id
            existing = by_norm.get(key)
            if existing is None:
                by_norm[key] = dev
            else:
                # Prefer online over offline, and 2.4G over Bluetooth when both online
                if dev.online and not existing.online:
                    by_norm[key] = dev
                elif dev.online == existing.online:
                    if dev.connection == ConnectionType.WIRELESS_24G and existing.connection != ConnectionType.WIRELESS_24G:
                        by_norm[key] = dev

        devices = list(by_norm.values())
        if not cfg.show_offline_devices:
            devices = [d for d in devices if d.online]

        devices.sort(key=lambda d: d.sort_key)
        self._last_devices = devices
        return devices

    @staticmethod
    def select_primary(devices: List[DeviceBattery], cfg: AppConfig) -> Optional[DeviceBattery]:
        """Select which peripheral's battery is shown directly on the system tray icon."""
        if not devices:
            return None
        if cfg.pinned_device_id:
            for d in devices:
                if d.device_id == cfg.pinned_device_id:
                    return d
        # Auto mode: prefer online non-system peripherals with lowest battery percentage
        online_periph = [
            d for d in devices
            if d.online and d.connection != ConnectionType.SYSTEM and d.percentage is not None
        ]
        if online_periph:
            return min(online_periph, key=lambda d: d.percentage if d.percentage is not None else 101)
        online_any = [d for d in devices if d.online]
        if online_any:
            return online_any[0]
        # Fallback to first cached/offline device with a valid percentage
        with_pct = [d for d in devices if d.percentage is not None]
        return with_pct[0] if with_pct else devices[0]
