"""Main Win32 system tray host, background poller, hot-plug monitor, and context menu."""

from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import threading
import time
from typing import Any, List, Optional, Set

from ..config import load_config, save_config, set_autostart
from ..models import AppConfig, DeviceBattery
from ..providers.manager import BatteryManager
from ..win32_api import (
    DBT_DEVICEARRIVAL,
    DBT_DEVICEREMOVECOMPLETE,
    DBT_DEVNODES_CHANGED,
    MF_CHECKED,
    MF_GRAYED,
    MF_POPUP,
    MF_SEPARATOR,
    MF_STRING,
    NIF_ICON,
    NIF_INFO,
    NIF_MESSAGE,
    NIF_TIP,
    NIIF_WARNING,
    NIM_ADD,
    NIM_DELETE,
    NIM_MODIFY,
    NOTIFYICONDATAW,
    TPM_BOTTOMALIGN,
    TPM_LEFTALIGN,
    TPM_NONOTIFY,
    TPM_RETURNCMD,
    TPM_RIGHTBUTTON,
    WM_DATA_UPDATED,
    WM_DESTROY,
    WM_DEVICECHANGE,
    WM_LBUTTONUP,
    WM_RBUTTONUP,
    WM_SETTINGCHANGE,
    WM_SHOW_POPUP_REQ,
    WM_TIMER,
    WM_TRAYICON,
    WNDCLASSEXW,
    WNDPROC,
    init_dpi_awareness,
    init_gdiplus,
    kernel32,
    shell32,
    shutdown_gdiplus,
    trim_working_set,
    user32,
)
from .popup_window import PopupWindow
from .tray_icon import create_battery_tray_icon

ERROR_ALREADY_EXISTS = 183
TIMER_DEVICE_DEBOUNCE = 101

# Context menu command IDs
CMD_REFRESH = 1001
CMD_SETTINGS = 1002
CMD_AUTOSTART = 1003
CMD_SHOW_OFFLINE = 1004
CMD_SHOW_SYSTEM = 1005
CMD_AUTO_PIN = 1006
CMD_EXIT = 1099
CMD_INTERVAL_BASE = 1100  # + seconds
CMD_DEVICE_BASE = 2000


class TrayBatteryApp:
    """Zero-GPU, minimal-RAM native Win32 peripheral battery tray application."""

    HOST_CLASS_NAME = "PeripheralBatteryTrayHost"
    MUTEX_NAME = "Local\\PeripheralBatteryTray_SingleInstance_v1"

    def __init__(self) -> None:
        self._cfg: AppConfig = load_config()
        self._manager = BatteryManager()
        self._lock = threading.Lock()
        self._devices: List[DeviceBattery] = []
        self._last_updated: float = 0.0
        self._is_refreshing: bool = False
        self._low_notified: Set[str] = set()

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None

        self._hwnd: int = 0
        self._hicon: int = 0
        self._mutex: int = 0
        self._popup: Optional[PopupWindow] = None
        self._wm_taskbar_created: int = user32.RegisterWindowMessageW("TaskbarCreated")
        self._wndproc = WNDPROC(self._proc)

    def _acquire_single_instance(self) -> bool:
        self._mutex = kernel32.CreateMutexW(None, False, self.MUTEX_NAME)
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            existing = user32.FindWindowW(self.HOST_CLASS_NAME, None)
            if existing:
                user32.PostMessageW(existing, WM_SHOW_POPUP_REQ, 0, 0)
            if self._mutex:
                kernel32.CloseHandle(self._mutex)
                self._mutex = 0
            return False
        return True

    def run(self) -> int:
        init_dpi_awareness()
        if not self._acquire_single_instance():
            return 0

        init_gdiplus()
        try:
            self._create_host_window()
            self._popup = PopupWindow(
                on_refresh=self.request_refresh,
                on_pin_device=self._on_pin_device,
                on_update_config=self._on_update_config,
            )
            self._add_tray_icon()
            self._start_poller()

            # Initial trim once initialized
            trim_working_set()

            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            return 0
        finally:
            self._cleanup()
            shutdown_gdiplus()
            if self._mutex:
                kernel32.CloseHandle(self._mutex)
                self._mutex = 0

    def _create_host_window(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = self.HOST_CLASS_NAME
        user32.RegisterClassExW(ctypes.byref(wc))

        # Top-level invisible window (receives WM_DEVICECHANGE, WM_SETTINGCHANGE, TaskbarCreated)
        self._hwnd = user32.CreateWindowExW(
            0, self.HOST_CLASS_NAME, "PeripheralBatteryTray", 0,
            0, 0, 0, 0, None, None, hinst, None,
        )

    def _build_tooltip(self, devices: List[DeviceBattery]) -> str:
        if not devices:
            return "外设电量监控\n暂未检测到外设电量"
        lines = ["外设电量监控"]
        for d in devices[:4]:
            if d.status_note:
                tag = f" ({d.status_note})"
            else:
                tag = "" if d.online else " (离线)"
            chg = " ⚡" if d.charging else ""
            lines.append(f"{d.name}: {d.display_percentage}{chg}{tag}")
        if len(devices) > 4:
            lines.append(f"… 共 {len(devices)} 个外设")
        text = "\n".join(lines)
        return text[:127]

    def _make_nid(self, flags: int) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = flags
        nid.uCallbackMessage = WM_TRAYICON
        return nid

    def _add_tray_icon(self) -> None:
        primary = self._manager.select_primary(self._devices, self._cfg)
        new_icon = create_battery_tray_icon(primary)
        nid = self._make_nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        nid.hIcon = new_icon
        nid.szTip = self._build_tooltip(self._devices)
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        if self._hicon:
            user32.DestroyIcon(self._hicon)
        self._hicon = new_icon

    def _update_tray_icon(self) -> None:
        primary = self._manager.select_primary(self._devices, self._cfg)
        new_icon = create_battery_tray_icon(primary)
        nid = self._make_nid(NIF_ICON | NIF_TIP)
        nid.hIcon = new_icon
        nid.szTip = self._build_tooltip(self._devices)
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        if self._hicon:
            user32.DestroyIcon(self._hicon)
        self._hicon = new_icon

    def _show_balloon(self, title: str, message: str) -> None:
        nid = self._make_nid(NIF_INFO)
        nid.szInfoTitle = title[:63]
        nid.szInfo = message[:255]
        nid.dwInfoFlags = NIIF_WARNING
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def _check_low_battery_alerts(self, devices: List[DeviceBattery]) -> None:
        if not self._cfg.low_battery_notify:
            return
        threshold = self._cfg.low_battery_threshold
        for d in devices:
            if not d.online or d.charging or d.percentage is None:
                continue
            if d.percentage <= threshold:
                if d.device_id not in self._low_notified:
                    self._low_notified.add(d.device_id)
                    self._show_balloon(
                        "外设低电量提醒",
                        f"{d.name} 当前电量仅剩 {d.percentage}%，请及时充电。",
                    )
            elif d.percentage >= threshold + 5:
                self._low_notified.discard(d.device_id)

    # -----------------------------------------------------------------------
    # Background Poller (0% CPU while sleeping)
    # -----------------------------------------------------------------------
    def _start_poller(self) -> None:
        self._poll_thread = threading.Thread(target=self._poll_loop, name="BatteryPoller", daemon=True)
        self._poll_thread.start()

    def request_refresh(self) -> None:
        self._is_refreshing = True
        if self._popup:
            self._popup.update_state(self._devices, self._cfg, self._last_updated, is_refreshing=True)
        self._wake_event.set()

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            self._wake_event.clear()
            with self._lock:
                cfg_copy = AppConfig.from_dict(self._cfg.to_dict())
            devices = self._manager.scan_all(cfg_copy)
            now = time.time()
            with self._lock:
                self._devices = devices
                self._last_updated = now
                self._is_refreshing = False
            if self._hwnd:
                user32.PostMessageW(self._hwnd, WM_DATA_UPDATED, 0, 0)

            interval = max(10, int(cfg_copy.refresh_interval))
            self._wake_event.wait(timeout=interval)

    # -----------------------------------------------------------------------
    # UI & Config Callbacks
    # -----------------------------------------------------------------------
    def _on_pin_device(self, device_id: str) -> None:
        with self._lock:
            if self._cfg.pinned_device_id == device_id:
                self._cfg.pinned_device_id = ""
            else:
                self._cfg.pinned_device_id = device_id
            save_config(self._cfg)
        self._update_tray_icon()
        if self._popup:
            self._popup.update_state(self._devices, self._cfg, self._last_updated, self._is_refreshing)

    def _on_update_config(self, key: str, value: Any) -> None:
        need_rescan = False
        with self._lock:
            if key == "autostart":
                ok = set_autostart(bool(value))
                self._cfg.autostart = bool(value) if ok else self._cfg.autostart
            else:
                setattr(self._cfg, key, value)
                if key in ("show_offline_devices", "show_system_battery"):
                    need_rescan = True
                if key == "low_battery_threshold":
                    self._low_notified.clear()
            save_config(self._cfg)

        if key == "refresh_interval":
            self._wake_event.set()
        elif need_rescan:
            self.request_refresh()
        else:
            self._update_tray_icon()
            if self._popup:
                self._popup.update_state(self._devices, self._cfg, self._last_updated, self._is_refreshing)

    # -----------------------------------------------------------------------
    # Native Win32 Right-Click Context Menu
    # -----------------------------------------------------------------------
    def _show_context_menu(self) -> None:
        if self._popup and self._popup.is_visible():
            self._popup.hide()

        hmenu = user32.CreatePopupMenu()
        sub_interval = user32.CreatePopupMenu()
        try:
            with self._lock:
                devices = list(self._devices)
                cfg = self._cfg

            if devices:
                for idx, dev in enumerate(devices[:10]):
                    flags = MF_STRING
                    if cfg.pinned_device_id == dev.device_id:
                        flags |= MF_CHECKED
                    suffix = "" if dev.online else " [离线]"
                    chg = " ⚡" if dev.charging else ""
                    label = f"{dev.name}  ({dev.display_percentage}{chg}){suffix}"
                    user32.AppendMenuW(hmenu, flags, CMD_DEVICE_BASE + idx, label)
                if cfg.pinned_device_id:
                    user32.AppendMenuW(hmenu, MF_STRING, CMD_AUTO_PIN, "恢复自动选择托盘主外设")
            else:
                user32.AppendMenuW(hmenu, MF_STRING | MF_GRAYED, 0, "暂未检测到外设电量")

            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, CMD_REFRESH, "立即刷新")
            user32.AppendMenuW(hmenu, MF_STRING, CMD_SETTINGS, "偏好设置...")

            for sec, title in ((15, "每 15 秒"), (30, "每 30 秒"), (60, "每 60 秒"), (120, "每 2 分钟")):
                f = MF_STRING | (MF_CHECKED if cfg.refresh_interval == sec else 0)
                user32.AppendMenuW(sub_interval, f, CMD_INTERVAL_BASE + sec, title)
            user32.AppendMenuW(hmenu, MF_POPUP, sub_interval, "自动刷新间隔")

            user32.AppendMenuW(
                hmenu,
                MF_STRING | (MF_CHECKED if cfg.show_offline_devices else 0),
                CMD_SHOW_OFFLINE,
                "显示离线蓝牙缓存",
            )
            user32.AppendMenuW(
                hmenu,
                MF_STRING | (MF_CHECKED if cfg.show_system_battery else 0),
                CMD_SHOW_SYSTEM,
                "显示本机电池",
            )
            user32.AppendMenuW(
                hmenu,
                MF_STRING | (MF_CHECKED if cfg.autostart else 0),
                CMD_AUTOSTART,
                "开机自动启动",
            )
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, CMD_EXIT, "退出")

            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(self._hwnd)
            cmd = user32.TrackPopupMenu(
                hmenu,
                TPM_LEFTALIGN | TPM_BOTTOMALIGN | TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                pt.x, pt.y, 0, self._hwnd, None,
            )
            if cmd:
                self._handle_menu_cmd(int(cmd), devices)
        finally:
            user32.DestroyMenu(hmenu)

    def _handle_menu_cmd(self, cmd: int, devices: List[DeviceBattery]) -> None:
        if cmd == CMD_REFRESH:
            self.request_refresh()
        elif cmd == CMD_SETTINGS:
            if self._popup:
                self._popup.update_state(self._devices, self._cfg, self._last_updated, self._is_refreshing)
                self._popup.show_settings()
        elif cmd == CMD_AUTOSTART:
            self._on_update_config("autostart", not self._cfg.autostart)
        elif cmd == CMD_SHOW_OFFLINE:
            self._on_update_config("show_offline_devices", not self._cfg.show_offline_devices)
        elif cmd == CMD_SHOW_SYSTEM:
            self._on_update_config("show_system_battery", not self._cfg.show_system_battery)
        elif cmd == CMD_AUTO_PIN:
            self._on_update_config("pinned_device_id", "")
        elif cmd == CMD_EXIT:
            user32.PostQuitMessage(0)
        elif CMD_INTERVAL_BASE < cmd <= CMD_INTERVAL_BASE + 600:
            self._on_update_config("refresh_interval", cmd - CMD_INTERVAL_BASE)
        elif CMD_DEVICE_BASE <= cmd < CMD_DEVICE_BASE + len(devices):
            self._on_pin_device(devices[cmd - CMD_DEVICE_BASE].device_id)

    # -----------------------------------------------------------------------
    # Host Window Procedure
    # -----------------------------------------------------------------------
    def _proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == self._wm_taskbar_created and self._wm_taskbar_created != 0:
            self._add_tray_icon()
            return 0
        if msg == WM_TRAYICON:
            ev = lparam & 0xFFFF
            if ev == WM_LBUTTONUP:
                if self._popup:
                    self._popup.update_state(
                        self._devices, self._cfg, self._last_updated, self._is_refreshing
                    )
                    self._popup.toggle()
            elif ev == WM_RBUTTONUP:
                self._show_context_menu()
            return 0
        if msg == WM_DATA_UPDATED:
            with self._lock:
                devices = list(self._devices)
                ts = self._last_updated
            self._update_tray_icon()
            self._check_low_battery_alerts(devices)
            if self._popup:
                self._popup.update_state(devices, self._cfg, ts, is_refreshing=False)
            if not (self._popup and self._popup.is_visible()):
                trim_working_set()
            return 0
        if msg == WM_SHOW_POPUP_REQ:
            if self._popup:
                self._popup.update_state(self._devices, self._cfg, self._last_updated, self._is_refreshing)
                self._popup.show(force=True)
            return 0
        if msg == WM_DEVICECHANGE:
            if wparam in (DBT_DEVNODES_CHANGED, DBT_DEVICEARRIVAL, DBT_DEVICEREMOVECOMPLETE):
                user32.SetTimer(hwnd, TIMER_DEVICE_DEBOUNCE, 1500, None)
            return 1
        if msg == WM_TIMER and wparam == TIMER_DEVICE_DEBOUNCE:
            user32.KillTimer(hwnd, TIMER_DEVICE_DEBOUNCE)
            self.request_refresh()
            return 0
        if msg == WM_SETTINGCHANGE:
            # Taskbar or system light/dark theme changed
            self._update_tray_icon()
            if self._popup and self._popup.is_visible():
                self._popup.show(force=True)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _cleanup(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._hwnd:
            nid = self._make_nid(0)
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        if self._hicon:
            user32.DestroyIcon(self._hicon)
            self._hicon = 0
        if self._popup:
            self._popup.destroy()
            self._popup = None
        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
            self._hwnd = 0
