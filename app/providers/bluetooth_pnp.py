"""Ultra-fast native Win32 SetupAPI Bluetooth / BLE / HFP battery provider (~10ms)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import re
import uuid
from typing import Dict, List, Optional

from ..models import ConnectionType, DeviceBattery, infer_device_kind

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wt.ULONG)]


class _SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("ClassGuid", _GUID),
        ("DevInst", wt.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


def _make_guid(guid_str: str) -> _GUID:
    g = _GUID()
    ctypes.memmove(ctypes.byref(g), uuid.UUID(guid_str).bytes_le, 16)
    return g


# Property keys
PKEY_NAME = _DEVPROPKEY(_make_guid("{B725F130-47EF-101A-A5F1-02608C9EEBAC}"), 10)
PKEY_FRIENDLY_NAME = _DEVPROPKEY(_make_guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"), 14)
PKEY_DEVICE_DESC = _DEVPROPKEY(_make_guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"), 2)
PKEY_BLUETOOTH_BATTERY = _DEVPROPKEY(_make_guid("{104EA319-6EE2-4701-BD47-8DDBF425BBE5}"), 2)
PKEY_DEVICE_CONNECTED = _DEVPROPKEY(_make_guid("{83DA6326-97A6-4088-9453-A1923F573B29}"), 15)
PKEY_CONTAINER_ID = _DEVPROPKEY(_make_guid("{8C7ED206-3F8A-4827-B3AB-AE9E1FAEFC6C}"), 2)

DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, wt.HWND, wt.DWORD]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.POINTER(_SP_DEVINFO_DATA)]
setupapi.SetupDiEnumDeviceInfo.restype = wt.BOOL
setupapi.SetupDiGetDevicePropertyW.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(_SP_DEVINFO_DATA),
    ctypes.POINTER(_DEVPROPKEY),
    ctypes.POINTER(wt.ULONG),
    ctypes.c_void_p,
    wt.DWORD,
    ctypes.POINTER(wt.DWORD),
    wt.DWORD,
]
setupapi.SetupDiGetDevicePropertyW.restype = wt.BOOL
setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(_SP_DEVINFO_DATA),
    wt.LPWSTR,
    wt.DWORD,
    ctypes.POINTER(wt.DWORD),
]
setupapi.SetupDiGetDeviceInstanceIdW.restype = wt.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wt.BOOL

_SUFFIX_RE = re.compile(
    r"\s*(?:Hands-Free\s*AG(?:\s*Audio)?|Hands-Free|Avrcp\s*传输|Stereo|Audio)\s*$",
    re.IGNORECASE,
)


def _clean_bt_name(name: str) -> str:
    cleaned = _SUFFIX_RE.sub("", name.strip()).strip()
    return cleaned or name.strip()


def _get_dev_prop(hdev: int, devinfo: _SP_DEVINFO_DATA, key: _DEVPROPKEY):
    prop_type = wt.ULONG(0)
    req_size = wt.DWORD(0)
    setupapi.SetupDiGetDevicePropertyW(
        hdev, ctypes.byref(devinfo), ctypes.byref(key),
        ctypes.byref(prop_type), None, 0, ctypes.byref(req_size), 0,
    )
    if req_size.value == 0:
        return None
    buf = ctypes.create_string_buffer(req_size.value)
    ok = setupapi.SetupDiGetDevicePropertyW(
        hdev, ctypes.byref(devinfo), ctypes.byref(key),
        ctypes.byref(prop_type), buf, req_size.value, None, 0,
    )
    if not ok:
        return None
    pt = prop_type.value
    if pt == 18:  # DEVPROP_TYPE_STRING
        return ctypes.wstring_at(buf)
    if pt == 3:  # DEVPROP_TYPE_BYTE
        return int(buf.raw[0])
    if pt == 17:  # DEVPROP_TYPE_BOOLEAN
        return buf.raw[0] != 0
    if pt == 7:  # DEVPROP_TYPE_UINT32
        return int.from_bytes(buf.raw[:4], "little")
    if pt == 13 and len(buf.raw) >= 16:  # DEVPROP_TYPE_GUID
        return str(uuid.UUID(bytes_le=buf.raw[:16]))
    return None


def scan_bluetooth_batteries() -> List[DeviceBattery]:
    """Read Bluetooth Classic (HFP) & BLE (GATT BAS) battery levels via Windows PnP."""
    hdev = setupapi.SetupDiGetClassDevsW(None, None, None, DIGCF_ALLCLASSES | DIGCF_PRESENT)
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        return []

    container_connected: Dict[str, bool] = {}
    container_best_name: Dict[str, str] = {}
    raw_entries = []

    try:
        idx = 0
        id_buf = ctypes.create_unicode_buffer(512)
        while True:
            did = _SP_DEVINFO_DATA()
            did.cbSize = ctypes.sizeof(did)
            if not setupapi.SetupDiEnumDeviceInfo(hdev, idx, ctypes.byref(did)):
                break
            idx += 1

            inst_id = ""
            if setupapi.SetupDiGetDeviceInstanceIdW(hdev, ctypes.byref(did), id_buf, 512, None):
                inst_id = id_buf.value

            inst_upper = inst_id.upper()
            is_bt_node = (
                inst_upper.startswith("BTHLE\\")
                or inst_upper.startswith("BTHENUM\\")
                or inst_upper.startswith("BTHLEDEVICE\\")
            )
            if not is_bt_node:
                continue

            cid: Optional[str] = _get_dev_prop(hdev, did, PKEY_CONTAINER_ID)
            conn: Optional[bool] = _get_dev_prop(hdev, did, PKEY_DEVICE_CONNECTED)
            name: Optional[str] = (
                _get_dev_prop(hdev, did, PKEY_FRIENDLY_NAME)
                or _get_dev_prop(hdev, did, PKEY_NAME)
                or _get_dev_prop(hdev, did, PKEY_DEVICE_DESC)
            )

            if cid:
                if conn is True:
                    container_connected[cid] = True
                elif cid not in container_connected and conn is False:
                    container_connected[cid] = False
                if name and (inst_upper.startswith("BTHLE\\DEV_") or inst_upper.startswith("BTHENUM\\DEV_")):
                    container_best_name[cid] = _clean_bt_name(name)

            bat = _get_dev_prop(hdev, did, PKEY_BLUETOOTH_BATTERY)
            if isinstance(bat, int) and 0 <= bat <= 100:
                raw_entries.append((cid, name or "蓝牙外设", bat, conn, inst_id))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)

    # Merge entries sharing the same Bluetooth ContainerId
    merged: Dict[str, DeviceBattery] = {}
    for cid, raw_name, pct, conn, inst_id in raw_entries:
        display_name = container_best_name.get(cid, "") if cid else ""
        if not display_name:
            display_name = _clean_bt_name(raw_name)

        online = bool(container_connected.get(cid, conn is True)) if cid else bool(conn is True)
        key = f"bt:{cid}" if cid else f"bt:{inst_id.lower()}"

        hint = raw_name
        kind = infer_device_kind(display_name, hint)
        item = DeviceBattery(
            device_id=key,
            name=display_name,
            percentage=pct,
            connection=ConnectionType.BLUETOOTH,
            kind=kind,
            online=online,
            charging=False,
            source="Windows 蓝牙 PnP",
            raw_id=inst_id,
        )
        prev = merged.get(key)
        if prev is None or (item.online and not prev.online):
            merged[key] = item

    return list(merged.values())
