"""Native Windows hid.dll 2.4G wireless & USB HID peripheral battery provider."""

from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Set, Tuple

from ..models import ConnectionType, DeviceBattery, DeviceKind, infer_device_kind

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
WAIT_OBJECT_0 = 0x00000000
HIDP_STATUS_SUCCESS = 0x00110000
DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("InterfaceClassGuid", _GUID),
        ("Flags", wt.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class _HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wt.ULONG),
        ("VendorID", wt.USHORT),
        ("ProductID", wt.USHORT),
        ("VersionNumber", wt.USHORT),
    ]


class _HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wt.USHORT),
        ("UsagePage", wt.USHORT),
        ("InputReportByteLength", wt.USHORT),
        ("OutputReportByteLength", wt.USHORT),
        ("FeatureReportByteLength", wt.USHORT),
        ("Reserved", wt.USHORT * 17),
        ("NumberLinkCollectionNodes", wt.USHORT),
        ("NumberInputButtonCaps", wt.USHORT),
        ("NumberInputValueCaps", wt.USHORT),
        ("NumberInputDataIndices", wt.USHORT),
        ("NumberOutputButtonCaps", wt.USHORT),
        ("NumberOutputValueCaps", wt.USHORT),
        ("NumberOutputDataIndices", wt.USHORT),
        ("NumberFeatureButtonCaps", wt.USHORT),
        ("NumberFeatureValueCaps", wt.USHORT),
        ("NumberFeatureDataIndices", wt.USHORT),
    ]


class _HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", wt.USHORT),
        ("ReportID", ctypes.c_ubyte),
        ("IsAlias", ctypes.c_ubyte),
        ("BitField", wt.USHORT),
        ("LinkCollection", wt.USHORT),
        ("LinkUsage", wt.USHORT),
        ("LinkUsagePage", wt.USHORT),
        ("IsRange", ctypes.c_ubyte),
        ("IsStringRange", ctypes.c_ubyte),
        ("IsDesignatorRange", ctypes.c_ubyte),
        ("IsAbsolute", ctypes.c_ubyte),
        ("HasNull", ctypes.c_ubyte),
        ("Reserved", ctypes.c_ubyte),
        ("BitSize", wt.USHORT),
        ("ReportCount", wt.USHORT),
        ("Reserved2", wt.USHORT * 5),
        ("UnitsExp", wt.ULONG),
        ("Units", wt.ULONG),
        ("LogicalMin", ctypes.c_long),
        ("LogicalMax", ctypes.c_long),
        ("PhysicalMin", ctypes.c_long),
        ("PhysicalMax", ctypes.c_long),
        ("UsageMin", wt.USHORT),
        ("UsageMax", wt.USHORT),
        ("StringMin", wt.USHORT),
        ("StringMax", wt.USHORT),
        ("DesignatorMin", wt.USHORT),
        ("DesignatorMax", wt.USHORT),
        ("DataIndexMin", wt.USHORT),
        ("DataIndexMax", wt.USHORT),
    ]


class _OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wt.DWORD),
        ("OffsetHigh", wt.DWORD),
        ("hEvent", wt.HANDLE),
    ]


setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(_GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_GUID), wt.DWORD,
    ctypes.POINTER(_SP_DEVICE_INTERFACE_DATA),
]
setupapi.SetupDiEnumDeviceInterfaces.restype = wt.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(_SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p,
]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wt.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wt.BOOL

kernel32.CreateFileW.argtypes = [
    wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p
]
kernel32.CreateFileW.restype = ctypes.c_void_p
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = wt.BOOL
kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
kernel32.CreateEventW.restype = wt.HANDLE
kernel32.ResetEvent.argtypes = [wt.HANDLE]
kernel32.ResetEvent.restype = wt.BOOL
kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
kernel32.WaitForSingleObject.restype = wt.DWORD
kernel32.GetOverlappedResult.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(_OVERLAPPED), ctypes.POINTER(wt.DWORD), wt.BOOL
]
kernel32.GetOverlappedResult.restype = wt.BOOL
kernel32.CancelIo.argtypes = [ctypes.c_void_p]
kernel32.CancelIo.restype = wt.BOOL
kernel32.WriteFile.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.POINTER(_OVERLAPPED)
]
kernel32.WriteFile.restype = wt.BOOL
kernel32.ReadFile.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.POINTER(_OVERLAPPED)
]
kernel32.ReadFile.restype = wt.BOOL

hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(_GUID)]
hid.HidD_GetHidGuid.restype = None
hid.HidD_GetAttributes.argtypes = [ctypes.c_void_p, ctypes.POINTER(_HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wt.BOOL
hid.HidD_GetProductString.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidD_GetProductString.restype = wt.BOOL
hid.HidD_GetManufacturerString.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidD_GetManufacturerString.restype = wt.BOOL
hid.HidD_GetPreparsedData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wt.BOOL
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = wt.BOOL
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(_HIDP_CAPS)]
hid.HidP_GetCaps.restype = wt.LONG
hid.HidP_GetValueCaps.argtypes = [
    ctypes.c_int, ctypes.POINTER(_HIDP_VALUE_CAPS), ctypes.POINTER(wt.USHORT), ctypes.c_void_p
]
hid.HidP_GetValueCaps.restype = wt.LONG
hid.HidP_GetUsageValue.argtypes = [
    ctypes.c_int, wt.USHORT, wt.USHORT, wt.USHORT, ctypes.POINTER(wt.ULONG),
    ctypes.c_void_p, ctypes.c_void_p, wt.ULONG,
]
hid.HidP_GetUsageValue.restype = wt.LONG
hid.HidD_SetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidD_SetFeature.restype = wt.BOOL
hid.HidD_GetFeature.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidD_GetFeature.restype = wt.BOOL
hid.HidD_FlushQueue.argtypes = [ctypes.c_void_p]
hid.HidD_FlushQueue.restype = wt.BOOL


@dataclass
class HidInterfaceInfo:
    path: str
    vid: int
    pid: int
    version: int
    manufacturer: str
    product: str
    usage_page: int
    usage: int
    in_len: int
    out_len: int
    feat_len: int
    in_rids: Set[int] = field(default_factory=set)
    out_rids: Set[int] = field(default_factory=set)
    feat_rids: Set[int] = field(default_factory=set)
    battery_feat_caps: List[Tuple[int, int, int, int, int]] = field(default_factory=list)
    # (usage_page, usage, report_id, logical_min, logical_max)


def enumerate_hid_interfaces() -> List[HidInterfaceInfo]:
    """Enumerate all currently attached HID collections cleanly via SetupAPI + hid.dll."""
    guid = _GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    hdev = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        return []

    results: List[HidInterfaceInfo] = []
    detail_struct_size = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
    try:
        idx = 0
        while True:
            did = _SP_DEVICE_INTERFACE_DATA()
            did.cbSize = ctypes.sizeof(did)
            if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(guid), idx, ctypes.byref(did)):
                break
            idx += 1

            req = wt.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                hdev, ctypes.byref(did), None, 0, ctypes.byref(req), None
            )
            if req.value <= 4:
                continue
            buf = ctypes.create_string_buffer(req.value)
            ctypes.cast(buf, ctypes.POINTER(wt.DWORD))[0] = detail_struct_size
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                hdev, ctypes.byref(did), buf, req.value, None, None
            ):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)

            h = kernel32.CreateFileW(
                path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
            )
            if not h or h == INVALID_HANDLE_VALUE:
                continue
            try:
                attr = _HIDD_ATTRIBUTES()
                attr.Size = ctypes.sizeof(attr)
                if not hid.HidD_GetAttributes(h, ctypes.byref(attr)):
                    continue
                pbuf = ctypes.create_unicode_buffer(256)
                mbuf = ctypes.create_unicode_buffer(256)
                prod = pbuf.value.strip() if hid.HidD_GetProductString(h, pbuf, 512) else ""
                mfg = mbuf.value.strip() if hid.HidD_GetManufacturerString(h, mbuf, 512) else ""

                pp = ctypes.c_void_p()
                caps = _HIDP_CAPS()
                in_rids: Set[int] = set()
                out_rids: Set[int] = set()
                feat_rids: Set[int] = set()
                bat_caps: List[Tuple[int, int, int, int, int]] = []
                if hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                    try:
                        if hid.HidP_GetCaps(pp, ctypes.byref(caps)) == HIDP_STATUS_SUCCESS:
                            for rtype, cnt, target in (
                                (0, caps.NumberInputValueCaps, in_rids),
                                (1, caps.NumberOutputValueCaps, out_rids),
                                (2, caps.NumberFeatureValueCaps, feat_rids),
                            ):
                                if cnt > 0:
                                    arr = (_HIDP_VALUE_CAPS * cnt)()
                                    ln = wt.USHORT(cnt)
                                    if hid.HidP_GetValueCaps(rtype, arr, ctypes.byref(ln), pp) == HIDP_STATUS_SUCCESS:
                                        for i in range(ln.value):
                                            vc = arr[i]
                                            target.add(int(vc.ReportID))
                                            # Standard HID Battery Strength (0x0006:0x0020)
                                            # or Power/Battery System RemainingCapacity (0x0085:0x0066)
                                            if rtype == 2 and (
                                                (vc.UsagePage == 0x0006 and vc.UsageMin <= 0x0020 <= vc.UsageMax)
                                                or (vc.UsagePage == 0x0085 and vc.UsageMin <= 0x0066 <= vc.UsageMax)
                                            ):
                                                usage_val = 0x0020 if vc.UsagePage == 0x0006 else 0x0066
                                                bat_caps.append(
                                                    (vc.UsagePage, usage_val, int(vc.ReportID), int(vc.LogicalMin), int(vc.LogicalMax))
                                                )
                    finally:
                        hid.HidD_FreePreparsedData(pp)

                results.append(
                    HidInterfaceInfo(
                        path=path,
                        vid=int(attr.VendorID),
                        pid=int(attr.ProductID),
                        version=int(attr.VersionNumber),
                        manufacturer=mfg,
                        product=prod,
                        usage_page=int(caps.UsagePage),
                        usage=int(caps.Usage),
                        in_len=int(caps.InputReportByteLength),
                        out_len=int(caps.OutputReportByteLength),
                        feat_len=int(caps.FeatureReportByteLength),
                        in_rids=in_rids,
                        out_rids=out_rids,
                        feat_rids=feat_rids,
                        battery_feat_caps=bat_caps,
                    )
                )
            finally:
                kernel32.CloseHandle(h)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return results


# ---------------------------------------------------------------------------
# Low-level Overlapped HID I/O Helpers
# ---------------------------------------------------------------------------
def _open_hid_rw(path: str, overlapped: bool = True) -> Optional[int]:
    flags = FILE_FLAG_OVERLAPPED if overlapped else 0
    h = kernel32.CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        flags,
        None,
    )
    if not h or h == INVALID_HANDLE_VALUE:
        return None
    return h


def _hid_write_read(
    path: str,
    payload: bytes,
    out_len: int,
    in_len: int,
    timeout_ms: int = 220,
    max_reads: int = 3,
    matcher=None,
) -> Optional[bytes]:
    h = _open_hid_rw(path, overlapped=True)
    if not h:
        return None
    ev = kernel32.CreateEventW(None, True, False, None)
    try:
        hid.HidD_FlushQueue(h)
        wbuf = (ctypes.c_ubyte * out_len)()
        for i, b in enumerate(payload[:out_len]):
            wbuf[i] = b
        ov = _OVERLAPPED()
        ov.hEvent = ev
        written = wt.DWORD(0)
        ok_w = kernel32.WriteFile(h, wbuf, out_len, ctypes.byref(written), ctypes.byref(ov))
        if not ok_w:
            if kernel32.WaitForSingleObject(ev, timeout_ms) != WAIT_OBJECT_0:
                kernel32.CancelIo(h)
                return None
            if not kernel32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(written), False):
                return None

        for _ in range(max_reads):
            kernel32.ResetEvent(ev)
            rbuf = (ctypes.c_ubyte * in_len)()
            rd = wt.DWORD(0)
            ok_r = kernel32.ReadFile(h, rbuf, in_len, ctypes.byref(rd), ctypes.byref(ov))
            if not ok_r:
                if kernel32.WaitForSingleObject(ev, timeout_ms) != WAIT_OBJECT_0:
                    kernel32.CancelIo(h)
                    return None
                if not kernel32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(rd), False):
                    return None
            if rd.value > 0:
                data = bytes(rbuf[: rd.value])
                if matcher is None or matcher(data):
                    return data
        return None
    finally:
        if ev:
            kernel32.CloseHandle(ev)
        kernel32.CloseHandle(h)


def _hid_feature_exchange(
    path: str,
    send_payload: bytes,
    feat_len: int,
    get_rid: int,
    delay_s: float = 0.04,
) -> Optional[bytes]:
    h = _open_hid_rw(path, overlapped=False)
    if not h:
        return None
    try:
        sbuf = (ctypes.c_ubyte * feat_len)()
        for i, b in enumerate(send_payload[:feat_len]):
            sbuf[i] = b
        if not hid.HidD_SetFeature(h, sbuf, feat_len):
            return None
        if delay_s > 0:
            time.sleep(delay_s)
        rbuf = (ctypes.c_ubyte * feat_len)()
        rbuf[0] = get_rid & 0xFF
        if not hid.HidD_GetFeature(h, rbuf, feat_len):
            return None
        return bytes(rbuf)
    finally:
        kernel32.CloseHandle(h)


# ---------------------------------------------------------------------------
# Protocol Probes
# ---------------------------------------------------------------------------
_MCHOSE_HEADSET_PIDS: Dict[Tuple[int, int], str] = {
    (0x291D, 0x385D): "MCHOSE V9 PRO",
    (0x3837, 0x600A): "MCHOSE V9 Turbo+",
    (0x3837, 0x6045): "MCHOSE X9",
}
_MCHOSE_V9_PRO_MIN_FW = 8
_MCHOSE_FW_CACHE_TTL = 300.0
_mchose_fw_cache: Dict[str, Tuple[float, Optional[int]]] = {}


def _read_mchose_receiver_fw(ifaces: List[HidInterfaceInfo]) -> Optional[int]:
    """Read MCHOSE 2.4G receiver firmware version via UP=0xFF22 Feature Report 0xAA (cached)."""
    fw_iface = next(
        (
            i for i in ifaces
            if i.usage_page == 0xFF22 and i.feat_len >= 64 and (not i.feat_rids or 0xAA in i.feat_rids)
        ),
        None,
    )
    if not fw_iface:
        return None
    cache_key = fw_iface.path.lower()
    now = time.monotonic()
    cached = _mchose_fw_cache.get(cache_key)
    if cached is not None and (now - cached[0]) < _MCHOSE_FW_CACHE_TTL:
        return cached[1]

    resp = _hid_feature_exchange(
        fw_iface.path,
        bytes([0xAA, 0x01, 0x01]),
        feat_len=fw_iface.feat_len,
        get_rid=0xAA,
        delay_s=0.30,
    )
    fw_ver: Optional[int] = None
    if resp and len(resp) >= 6 and resp[0] == 0xAA and resp[1] == 0x01:
        digits = resp[2:6]
        if all(0 <= b <= 9 for b in digits):
            fw_ver = int("".join(str(b) for b in digits))
    _mchose_fw_cache[cache_key] = (now, fw_ver)
    return fw_ver


def _probe_mchose_headset(ifaces: List[HidInterfaceInfo]) -> Optional[DeviceBattery]:
    """MCHOSE 2.4G Wireless Headset protocol (V9 PRO / V9 Turbo+ / X9, UP=0xFF90, 0x55 0x65 0x01)."""
    target = next(
        (
            i for i in ifaces
            if (i.vid, i.pid) in _MCHOSE_HEADSET_PIDS
            and i.usage_page == 0xFF90
            and i.out_len >= 64
            and i.in_len >= 64
        ),
        None,
    )
    if not target:
        return None

    default_name = _MCHOSE_HEADSET_PIDS[(target.vid, target.pid)]
    name = target.product or default_name
    is_v9_pro = (target.vid, target.pid) == (0x291D, 0x385D)

    # V9 PRO receiver firmware < 0008 does not implement 2.4G battery queries (55 65 01)
    if is_v9_pro:
        fw_ver = _read_mchose_receiver_fw(ifaces)
        if fw_ver is not None and fw_ver < _MCHOSE_V9_PRO_MIN_FW:
            return DeviceBattery(
                device_id=f"hid:{target.vid:04x}:{target.pid:04x}",
                name=name,
                percentage=None,
                connection=ConnectionType.WIRELESS_24G,
                kind=DeviceKind.HEADSET,
                online=False,
                charging=False,
                source=f"2.4G HID (MCHOSE 固件 {fw_ver:04d})",
                raw_id=f"VID_{target.vid:04X}&PID_{target.pid:04X}",
                status_note=f"固件{fw_ver:04d}需升级",
            )

    resp = _hid_write_read(
        target.path,
        bytes([0x55, 0x65, 0x01]),
        out_len=target.out_len,
        in_len=target.in_len,
        timeout_ms=1000,
        max_reads=24,
        matcher=lambda d: len(d) >= 4 and d[0] == 0x55 and d[1] == 0x65,
    )
    if not resp:
        return None

    level = int(resp[2])
    state = int(resp[3])

    # State mapping verified against HeadsetControl & myfinder-device-battery:
    # 0x1A: headset powered off
    # 0x02: online & discharging (level = 0..100%)
    # 0x00 / 0x03: online & external power / charging (percentage frozen in firmware)
    # 0x04 (V9 PRO): online & fully charged (level == 100)
    if state == 0x1A:
        return None

    charging = False
    pct: Optional[int] = None
    if state == 0x02 and 0 <= level <= 100:
        pct = level
    elif state in (0x00, 0x03):
        charging = True
        pct = None
    elif state == 0x04 and is_v9_pro:
        pct = 100 if level == 100 else None
        if pct is None:
            return None
    elif 1 <= level <= 100:
        pct = level
        charging = state == 0x01
    else:
        return None

    return DeviceBattery(
        device_id=f"hid:{target.vid:04x}:{target.pid:04x}",
        name=name,
        percentage=pct,
        connection=ConnectionType.WIRELESS_24G,
        kind=DeviceKind.HEADSET,
        online=True,
        charging=charging,
        source="2.4G HID (MCHOSE)",
        raw_id=f"VID_{target.vid:04X}&PID_{target.pid:04X}",
    )


def _probe_by_tech_ff04_08(ifaces: List[HidInterfaceInfo]) -> Optional[DeviceBattery]:
    """BY-tech 64-byte Report ID 0x08 on UP=0xFF04 (e.g. WU-mouse 372E:10F8 / 372E:10F9).

    Frame format: [0x08, cmd, 0x00, 0x00, data_len, <data>, checksum]
    Checksum: (~sum(frame[:5 + data_len])) & 0xFF
    cmd=0x02 reply payload (4 bytes): [online, state, percentage(0..100), charging(0/1)]
    """
    candidates = [
        i for i in ifaces
        if i.vid == 0x372E
        and i.usage_page == 0xFF04
        and i.in_len >= 64
        and i.out_len >= 64
        and (0x08 in i.out_rids)
        and (0x08 in i.in_rids)
    ]
    for target in candidates:
        req = bytearray(target.out_len)
        req[0] = 0x08
        req[1] = 0x02
        req[4] = 0x01
        req[5] = 0x00
        req[6] = (~sum(req[:6])) & 0xFF  # 0xF4

        resp = _hid_write_read(
            target.path,
            bytes(req),
            out_len=target.out_len,
            in_len=target.in_len,
            timeout_ms=220,
            max_reads=6,
            matcher=lambda d: len(d) >= 10 and d[0] == 0x08 and d[1] == 0x02,
        )
        if not resp:
            continue
        plen = int(resp[4])
        # High bit 0x80 indicates NACK / error frame
        if (plen & 0x80) or plen < 3 or (5 + plen) >= len(resp):
            continue
        expected_chk = (~sum(resp[: 5 + plen])) & 0xFF
        if resp[5 + plen] != expected_chk:
            continue

        online = resp[5] != 0
        if not online:
            return None
        pct = int(resp[7])
        if not (0 <= pct <= 100):
            continue
        charging = plen >= 4 and resp[8] == 1
        name = target.product or f"WU-mouse ({target.vid:04X}:{target.pid:04X})"
        return DeviceBattery(
            device_id=f"hid:{target.vid:04x}:{target.pid:04x}",
            name=name,
            percentage=pct,
            connection=ConnectionType.WIRELESS_24G,
            kind=infer_device_kind(name, "mouse"),
            online=True,
            charging=charging,
            source="2.4G HID (BY-tech 0x08)",
            raw_id=f"VID_{target.vid:04X}&PID_{target.pid:04X}",
        )
    return None


def _probe_by_tech_372e(ifaces: List[HidInterfaceInfo]) -> Optional[DeviceBattery]:
    """BY-Tech / PixArt 372E Feature Report 0x03 protocol (EWEADN S9 Pro / IPI PIX v1)."""
    target = next(
        (
            i for i in ifaces
            if i.vid == 0x372E and i.usage_page == 0xFF00 and i.feat_len >= 16 and (0x03 in i.feat_rids)
        ),
        None,
    )
    if not target:
        return None
    for cmd_bytes in (
        bytes([0x03, 0x20, 0x50, 0x00, 0x00, 0x4F, 0x81]),  # EWEADN S9 Pro
        bytes([0x03, 0x22, 0x50, 0x00, 0x02, 0x4F, 0x81]),  # IPI PIX v1
    ):
        resp = _hid_feature_exchange(
            target.path,
            cmd_bytes,
            feat_len=target.feat_len,
            get_rid=0x03,
            delay_s=0.04,
        )
        if not resp or len(resp) < 7:
            continue
        if resp[0] == 0x03 and resp[1] == 0x50 and resp[2] == 0x00 and resp[5] == 0x01:
            pct = int(resp[6] & 0x7F)
            charging = bool(resp[6] & 0x80)
            if 1 <= pct <= 100:
                name = target.product or f"2.4G 鼠标 ({target.vid:04X}:{target.pid:04X})"
                return DeviceBattery(
                    device_id=f"hid:{target.vid:04x}:{target.pid:04x}",
                    name=name,
                    percentage=pct,
                    connection=ConnectionType.WIRELESS_24G,
                    kind=infer_device_kind(name, "mouse"),
                    online=True,
                    charging=charging,
                    source="2.4G HID (PixArt 372E)",
                    raw_id=f"VID_{target.vid:04X}&PID_{target.pid:04X}",
                )
    return None


_COMPX_VIDS = {0x3554, 0x373B, 0x25A7, 0x1D57, 0x41E4, 0x248A, 0x3151, 0x372E, 0x1915}


def _probe_compx_08(ifaces: List[HidInterfaceInfo]) -> Optional[DeviceBattery]:
    """CompX / Nordic52 / ATK / VXE / VGN / Zaopin 0x08 17-byte battery protocol."""
    candidates = [
        i for i in ifaces
        if i.vid in _COMPX_VIDS
        and i.usage_page in (0xFF00, 0xFF02, 0xFF04)
        and i.out_len >= 17
        and i.in_len >= 17
        and (0x08 in i.out_rids or 0x08 in i.in_rids)
    ]
    req = bytearray(17)
    req[0] = 0x08
    req[1] = 0x04
    req[16] = 0x49  # (0x55 - (0x08 + 0x04)) & 0xFF

    for iface in candidates:
        resp = _hid_write_read(
            iface.path,
            bytes(req),
            out_len=iface.out_len,
            in_len=iface.in_len,
            timeout_ms=180,
            matcher=lambda d: len(d) >= 17 and d[0] == 0x08 and d[1] == 0x04,
        )
        if not resp or len(resp) < 17:
            continue
        # Strict checksum validation prevents false positives on unrelated 0x08 protocols
        if (sum(resp[:17]) & 0xFF) != 0x55:
            continue
        pct = int(resp[6])
        if not (1 <= pct <= 100):
            continue
        charging = resp[7] == 1
        mv = (resp[8] << 8) | resp[9]
        voltage_mv = mv if 2500 <= mv <= 4600 else None
        name = iface.product or f"2.4G 鼠标 ({iface.vid:04X}:{iface.pid:04X})"
        return DeviceBattery(
            device_id=f"hid:{iface.vid:04x}:{iface.pid:04x}",
            name=name,
            percentage=pct,
            connection=ConnectionType.WIRELESS_24G,
            kind=infer_device_kind(name, "mouse"),
            online=True,
            charging=charging,
            voltage_mv=voltage_mv,
            source="2.4G HID (CompX)",
            raw_id=f"VID_{iface.vid:04X}&PID_{iface.pid:04X}",
        )
    return None


def _probe_logitech_hidpp(ifaces: List[HidInterfaceInfo]) -> List[DeviceBattery]:
    """Logitech Unifying / Bolt / Lightspeed HID++ 2.0 wireless battery probe."""
    short_if = next(
        (i for i in ifaces if i.vid == 0x046D and i.usage_page == 0xFF00 and i.out_len == 7 and i.in_len == 7),
        None,
    )
    long_if = next(
        (i for i in ifaces if i.vid == 0x046D and i.usage_page == 0xFF00 and i.out_len == 20 and i.in_len == 20),
        None,
    )
    iface = long_if or short_if
    if not iface:
        return []

    rep_id = 0x11 if iface.out_len == 20 else 0x10
    sw_id = 0x0A
    found: List[DeviceBattery] = []

    def xfer(dev_idx: int, feat_idx: int, func_idx: int, params: bytes = b"") -> Optional[bytes]:
        pkt = bytearray(iface.out_len)
        pkt[0] = rep_id
        pkt[1] = dev_idx
        pkt[2] = feat_idx
        pkt[3] = ((func_idx & 0x0F) << 4) | (sw_id & 0x0F)
        for k, b in enumerate(params):
            if 4 + k < len(pkt):
                pkt[4 + k] = b
        return _hid_write_read(
            iface.path,
            bytes(pkt),
            out_len=iface.out_len,
            in_len=iface.in_len,
            timeout_ms=140,
            max_reads=3,
            matcher=lambda d: len(d) >= 7 and d[0] in (0x10, 0x11) and d[1] == dev_idx and d[2] != 0x8F,
        )

    # Probe direct device (0xFF) first, then receiver slots 1..6
    slots = [0xFF, 1, 2, 3, 4, 5, 6]
    for slot in slots:
        # Root feature 0x0000, function 0 = GetFeatureIndex
        pct = None
        charging = False
        # Try 0x1004 (Unified Battery)
        r = xfer(slot, 0x00, 0x00, bytes([0x10, 0x04]))
        if r and r[2] == 0x00 and r[4] != 0:
            feat_idx = r[4]
            br = xfer(slot, feat_idx, 0x01)  # get_status
            if br and br[2] == feat_idx and 1 <= br[4] <= 100:
                pct = int(br[4])
                charging = br[6] in (1, 2, 3)
        else:
            # Try 0x1000 (Battery Level Status)
            r = xfer(slot, 0x00, 0x00, bytes([0x10, 0x00]))
            if r and r[2] == 0x00 and r[4] != 0:
                feat_idx = r[4]
                br = xfer(slot, feat_idx, 0x00)
                if br and br[2] == feat_idx and 1 <= br[4] <= 100:
                    pct = int(br[4])
                    charging = br[6] in (1, 2, 3)

        if pct is None:
            continue

        # Try fetching device name via feature 0x0005
        dev_name = iface.product or f"Logitech 设备 #{slot}"
        nr = xfer(slot, 0x00, 0x00, bytes([0x00, 0x05]))
        if nr and nr[2] == 0x00 and nr[4] != 0:
            name_feat = nr[4]
            lr = xfer(slot, name_feat, 0x00)
            if lr and lr[2] == name_feat and 1 <= lr[4] <= 50:
                total_len = lr[4]
                chunks = bytearray()
                while len(chunks) < total_len:
                    cr = xfer(slot, name_feat, 0x01, bytes([len(chunks)]))
                    if not cr or cr[2] != name_feat:
                        break
                    chunks.extend(cr[4:])
                decoded = chunks[:total_len].decode("utf-8", errors="ignore").strip("\x00 ")
                if decoded:
                    dev_name = decoded

        found.append(
            DeviceBattery(
                device_id=f"logi:{iface.pid:04x}:{slot}",
                name=dev_name,
                percentage=pct,
                connection=ConnectionType.WIRELESS_24G,
                kind=infer_device_kind(dev_name),
                online=True,
                charging=charging,
                source="2.4G HID++ 2.0",
                raw_id=f"VID_046D&PID_{iface.pid:04X}&SLOT_{slot}",
            )
        )
        if slot == 0xFF:
            break  # Direct device responded; no need to probe receiver slots
    return found


def _probe_razer_24g(ifaces: List[HidInterfaceInfo]) -> Optional[DeviceBattery]:
    """Razer wireless 90-byte Feature Report battery probe (VID=0x1532)."""
    target = next(
        (i for i in ifaces if i.vid == 0x1532 and i.feat_len in (90, 91)),
        None,
    )
    if not target:
        return None

    def razer_cmd(cmd_class: int, cmd_id: int) -> Optional[bytes]:
        buf = bytearray(target.feat_len)
        offset = 1 if target.feat_len == 91 else 0
        # status=0x00, txid=0x1F, remaining=0x0000, protocol=0x00, data_size=0x02
        buf[offset + 1] = 0x1F
        buf[offset + 5] = 0x02
        buf[offset + 6] = cmd_class
        buf[offset + 7] = cmd_id
        crc = 0
        for b in buf[offset + 2 : offset + 88]:
            crc ^= b
        buf[offset + 88] = crc
        resp = _hid_feature_exchange(target.path, bytes(buf), target.feat_len, get_rid=0x00, delay_s=0.05)
        if not resp or len(resp) < offset + 10:
            return None
        if resp[offset + 0] != 0x02:  # 0x02 = successful reply
            return None
        return resp[offset:]

    rb = razer_cmd(0x07, 0x80)
    if not rb:
        return None
    raw_level = rb[9]
    if raw_level == 0:
        return None
    pct = max(1, min(100, round(raw_level * 100 / 255)))
    rc = razer_cmd(0x07, 0x84)
    charging = bool(rc and rc[9] == 1)
    name = target.product or f"Razer 无线设备 ({target.pid:04X})"
    return DeviceBattery(
        device_id=f"hid:{target.vid:04x}:{target.pid:04x}",
        name=name,
        percentage=pct,
        connection=ConnectionType.WIRELESS_24G,
        kind=infer_device_kind(name, "mouse"),
        online=True,
        charging=charging,
        source="2.4G HID (Razer)",
        raw_id=f"VID_1532&PID_{target.pid:04X}",
    )


def _probe_generic_hid_battery(ifaces: List[HidInterfaceInfo]) -> Optional[DeviceBattery]:
    """Standard HID Usage Page 0x0006:0x0020 (Battery Strength) / 0x0085:0x0066."""
    for iface in ifaces:
        if not iface.battery_feat_caps or iface.feat_len <= 0:
            continue
        h = _open_hid_rw(iface.path, overlapped=False)
        if not h:
            continue
        try:
            pp = ctypes.c_void_p()
            if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                continue
            try:
                for up, u, rid, lmin, lmax in iface.battery_feat_caps:
                    rbuf = (ctypes.c_ubyte * iface.feat_len)()
                    rbuf[0] = rid & 0xFF
                    if not hid.HidD_GetFeature(h, rbuf, iface.feat_len):
                        continue
                    val = wt.ULONG(0)
                    st = hid.HidP_GetUsageValue(
                        2, up, 0, u, ctypes.byref(val), pp, rbuf, iface.feat_len
                    )
                    if st == HIDP_STATUS_SUCCESS:
                        span = max(1, lmax - lmin)
                        pct = round((int(val.value) - lmin) * 100 / span)
                        if 0 <= pct <= 100:
                            name = iface.product or f"HID 设备 ({iface.vid:04X}:{iface.pid:04X})"
                            conn = (
                                ConnectionType.BLUETOOTH
                                if "bth" in iface.path.lower()
                                else ConnectionType.WIRELESS_24G
                            )
                            return DeviceBattery(
                                device_id=f"hidstd:{iface.vid:04x}:{iface.pid:04x}",
                                name=name,
                                percentage=pct,
                                connection=conn,
                                kind=infer_device_kind(name),
                                online=True,
                                charging=False,
                                source="标准 HID 电量",
                                raw_id=f"VID_{iface.vid:04X}&PID_{iface.pid:04X}",
                            )
            finally:
                hid.HidD_FreePreparsedData(pp)
        finally:
            kernel32.CloseHandle(h)
    return None


def scan_hid_24g_batteries() -> List[DeviceBattery]:
    """Scan all connected 2.4G wireless / USB HID peripherals for battery readings."""
    all_ifaces = enumerate_hid_interfaces()
    by_device: Dict[Tuple[int, int], List[HidInterfaceInfo]] = {}
    for iface in all_ifaces:
        # Skip Bluetooth GATT HID nodes (already handled cleanly by Windows Bluetooth PnP)
        if "bth" in iface.path.lower():
            continue
        by_device.setdefault((iface.vid, iface.pid), []).append(iface)

    results: List[DeviceBattery] = []
    for (vid, pid), group in by_device.items():
        if (vid, pid) in _MCHOSE_HEADSET_PIDS:
            item = _probe_mchose_headset(group)
            if item:
                results.append(item)
                continue
        if vid == 0x046D:
            items = _probe_logitech_hidpp(group)
            if items:
                results.extend(items)
                continue
        if vid == 0x1532:
            item = _probe_razer_24g(group)
            if item:
                results.append(item)
                continue
        if vid == 0x372E:
            item = _probe_by_tech_ff04_08(group) or _probe_by_tech_372e(group)
            if item:
                results.append(item)
                continue
        if vid in _COMPX_VIDS:
            item = _probe_compx_08(group)
            if item:
                results.append(item)
                continue
        # Fallback: standard HID battery usage page
        item = _probe_generic_hid_battery(group)
        if item:
            results.append(item)
    return results


def dump_hid_diagnostics() -> str:
    """Return human-readable summary of vendor HID interfaces for troubleshooting."""
    ifaces = enumerate_hid_interfaces()
    lines = ["=== 已连接的厂商 HID / 2.4G 接口诊断 ==="]
    seen = set()
    by_dev: Dict[Tuple[int, int], List[HidInterfaceInfo]] = {}
    for i in ifaces:
        by_dev.setdefault((i.vid, i.pid), []).append(i)
        if i.usage_page < 0xFF00 and not i.battery_feat_caps:
            continue
        key = (i.vid, i.pid, i.usage_page, i.usage, i.in_len, i.out_len, i.feat_len)
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"VID={i.vid:04X} PID={i.pid:04X} | {i.manufacturer or '-'} / {i.product or '-'} | "
            f"UP={i.usage_page:04X} U={i.usage:04X} IN={i.in_len} OUT={i.out_len} FEAT={i.feat_len} "
            f"RIDs(in={sorted(i.in_rids)}, out={sorted(i.out_rids)}, feat={sorted(i.feat_rids)})"
        )
    for (vid, pid), grp in by_dev.items():
        if (vid, pid) in _MCHOSE_HEADSET_PIDS:
            fw = _read_mchose_receiver_fw(grp)
            if fw is not None:
                hint = (
                    f" (< 0008，需通过 M HUB 升级接收器固件以开启 2.4G 电量上报)"
                    if (vid, pid) == (0x291D, 0x385D) and fw < _MCHOSE_V9_PRO_MIN_FW
                    else " (支持 2.4G 电量查询)"
                )
                lines.append(
                    f"[MCHOSE 接收器固件] {_MCHOSE_HEADSET_PIDS[(vid, pid)]} ({vid:04X}:{pid:04X}) 固件版本: {fw:04d}{hint}"
                )
    if len(lines) == 1:
        lines.append("(未发现厂商自定义 HID 接口)")
    return "\n".join(lines)
