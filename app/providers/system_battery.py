"""Optional Windows system/laptop battery provider via GetSystemPowerStatus."""

from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
from typing import List

from ..models import ConnectionType, DeviceBattery, DeviceKind


class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", wt.DWORD),
        ("BatteryFullLifeTime", wt.DWORD),
    ]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.GetSystemPowerStatus.argtypes = [ctypes.POINTER(_SYSTEM_POWER_STATUS)]
_kernel32.GetSystemPowerStatus.restype = wt.BOOL


def scan_system_battery() -> List[DeviceBattery]:
    st = _SYSTEM_POWER_STATUS()
    if not _kernel32.GetSystemPowerStatus(ctypes.byref(st)):
        return []
    # BatteryFlag 128 = No system battery; 255 = Unknown
    if st.BatteryFlag in (128, 255) or st.BatteryLifePercent > 100:
        return []
    charging = bool(st.BatteryFlag & 8) or (st.ACLineStatus == 1 and st.BatteryLifePercent < 100)
    return [
        DeviceBattery(
            device_id="system:battery",
            name="本机电池",
            percentage=int(st.BatteryLifePercent),
            connection=ConnectionType.SYSTEM,
            kind=DeviceKind.LAPTOP,
            online=True,
            charging=charging,
            source="Windows Power API",
            raw_id="SYSTEM_BATTERY",
        )
    ]
