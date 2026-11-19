"""XInput wireless controller battery provider (Xbox 360 / One / Series)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
from typing import List

from ..models import ConnectionType, DeviceBattery, DeviceKind

BATTERY_DEVTYPE_GAMEPAD = 0x00
BATTERY_TYPE_DISCONNECTED = 0x00
BATTERY_TYPE_WIRED = 0x01
BATTERY_TYPE_ALKALINE = 0x02
BATTERY_TYPE_NIMH = 0x03

BATTERY_LEVEL_MAP = {
    0: 10,   # EMPTY
    1: 30,   # LOW
    2: 65,   # MEDIUM
    3: 100,  # FULL
}


class _XINPUT_BATTERY_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BatteryType", ctypes.c_ubyte),
        ("BatteryLevel", ctypes.c_ubyte),
    ]


def _load_xinput():
    for dll in ("xinput1_4", "xinput1_3"):
        try:
            lib = ctypes.WinDLL(dll)
            lib.XInputGetBatteryInformation.argtypes = [
                wt.DWORD,
                ctypes.c_ubyte,
                ctypes.POINTER(_XINPUT_BATTERY_INFORMATION),
            ]
            lib.XInputGetBatteryInformation.restype = wt.DWORD
            return lib
        except OSError:
            continue
    return None


_xinput = _load_xinput()


def scan_xinput_batteries() -> List[DeviceBattery]:
    if _xinput is None:
        return []
    results: List[DeviceBattery] = []
    for idx in range(4):
        info = _XINPUT_BATTERY_INFORMATION()
        rc = _xinput.XInputGetBatteryInformation(idx, BATTERY_DEVTYPE_GAMEPAD, ctypes.byref(info))
        if rc != 0:
            continue
        if info.BatteryType in (BATTERY_TYPE_DISCONNECTED, BATTERY_TYPE_WIRED):
            continue
        pct = BATTERY_LEVEL_MAP.get(info.BatteryLevel, 50)
        results.append(
            DeviceBattery(
                device_id=f"xinput:{idx}",
                name=f"Xbox 无线手柄 #{idx + 1}",
                percentage=pct,
                connection=ConnectionType.GAMEPAD,
                kind=DeviceKind.GAMEPAD,
                online=True,
                charging=False,
                source="XInput 1.4",
                raw_id=f"XINPUT_{idx}",
            )
        )
    return results
