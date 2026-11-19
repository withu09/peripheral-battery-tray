"""Pure-CPU GDI+ Windows 11-style floating peripheral battery card popup & inline settings."""

from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
from dataclasses import dataclass
import time
from typing import Any, Callable, List, Optional, Tuple

from ..models import AppConfig, DeviceBattery
from ..win32_api import (
    BI_RGB,
    BITMAPINFO,
    CS_DROPSHADOW,
    CS_HREDRAW,
    CS_VREDRAW,
    DIB_RGB_COLORS,
    IDC_ARROW,
    IDC_HAND,
    MONITOR_DEFAULTTONEAREST,
    MONITORINFO,
    PAINTSTRUCT,
    SRCCOPY,
    SW_HIDE,
    SW_SHOW,
    TME_LEAVE,
    TRACKMOUSEEVENT,
    VK_ESCAPE,
    WA_INACTIVE,
    WM_ACTIVATE,
    WM_ERASEBKGND,
    WM_KEYDOWN,
    WM_LBUTTONUP,
    WM_MOUSELEAVE,
    WM_MOUSEMOVE,
    WM_MOUSEWHEEL,
    WM_PAINT,
    WM_SETCURSOR,
    WNDCLASSEXW,
    WNDPROC,
    WS_CLIPCHILDREN,
    WS_CLIPSIBLINGS,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_POPUP,
    apply_window_dwm_style,
    gdi32,
    get_system_dpi,
    get_window_dpi,
    is_light_apps,
    kernel32,
    trim_working_set,
    user32,
)
from .gdiplus_draw import Canvas, argb, battery_accent_color, hex_color


@dataclass
class _Theme:
    dark: bool
    bg: int
    border: int
    card: int
    card_hover: int
    card_border: int
    card_pinned_border: int
    icon_bg: int
    text_primary: int
    text_secondary: int
    text_muted: int
    pill_bg: int
    pill_active_bg: int
    pill_active_text: int
    track_bg: int
    divider: int
    toggle_off: int
    toggle_on: int
    toggle_knob: int
    btn_hover: int


def _get_theme(mode: str) -> _Theme:
    if mode == "light":
        dark = False
    elif mode == "dark":
        dark = True
    else:
        dark = not is_light_apps()

    if dark:
        return _Theme(
            dark=True,
            bg=hex_color("#1B1F27"),
            border=hex_color("#2E3545"),
            card=hex_color("#242935"),
            card_hover=hex_color("#2C3342"),
            card_border=hex_color("#31394B"),
            card_pinned_border=hex_color("#3B82F6"),
            icon_bg=hex_color("#2F3748"),
            text_primary=hex_color("#F1F5F9"),
            text_secondary=hex_color("#94A3B8"),
            text_muted=hex_color("#64748B"),
            pill_bg=hex_color("#2F3748"),
            pill_active_bg=hex_color("#3B82F6"),
            pill_active_text=hex_color("#FFFFFF"),
            track_bg=hex_color("#334155"),
            divider=hex_color("#2B3240"),
            toggle_off=hex_color("#475569"),
            toggle_on=hex_color("#3B82F6"),
            toggle_knob=hex_color("#FFFFFF"),
            btn_hover=hex_color("#2E3647"),
        )
    return _Theme(
        dark=False,
        bg=hex_color("#F6F8FC"),
        border=hex_color("#D8E0EC"),
        card=hex_color("#FFFFFF"),
        card_hover=hex_color("#F1F5F9"),
        card_border=hex_color("#E2E8F0"),
        card_pinned_border=hex_color("#2563EB"),
        icon_bg=hex_color("#EEF2F8"),
        text_primary=hex_color("#0F172A"),
        text_secondary=hex_color("#475569"),
        text_muted=hex_color("#94A3B8"),
        pill_bg=hex_color("#E8EEF7"),
        pill_active_bg=hex_color("#2563EB"),
        pill_active_text=hex_color("#FFFFFF"),
        track_bg=hex_color("#E2E8F0"),
        divider=hex_color("#E2E8F0"),
        toggle_off=hex_color("#CBD5E1"),
        toggle_on=hex_color("#2563EB"),
        toggle_knob=hex_color("#FFFFFF"),
        btn_hover=hex_color("#E6ECF5"),
    )


class PopupWindow:
    """Lightweight floating card popup anchored above the Windows system tray."""

    CLASS_NAME = "PeripheralBatteryPopupWnd"

    def __init__(
        self,
        on_refresh: Callable[[], None],
        on_pin_device: Callable[[str], None],
        on_update_config: Callable[[str, Any], None],
    ) -> None:
        self._on_refresh = on_refresh
        self._on_pin_device = on_pin_device
        self._on_update_config = on_update_config

        self._devices: List[DeviceBattery] = []
        self._cfg: AppConfig = AppConfig()
        self._last_updated: float = 0.0
        self._is_refreshing: bool = False
        self._view: str = "devices"  # "devices" | "settings"
        self._scroll_y: float = 0.0
        self._max_scroll: float = 0.0

        self._hit_zones: List[Tuple[Tuple[float, float, float, float], str, Any]] = []
        self._hover_id: Optional[str] = None
        self._tracking_leave: bool = False
        self._last_hide_time: float = 0.0

        self._dpi: int = get_system_dpi()
        self._width_px: int = self._dp(344)
        self._height_px: int = self._dp(260)

        self._cursor_arrow = user32.LoadCursorW(None, ctypes.c_void_p(IDC_ARROW))
        self._cursor_hand = user32.LoadCursorW(None, ctypes.c_void_p(IDC_HAND))

        self._wndproc = WNDPROC(self._proc)
        self.hwnd = self._create_window()

    def _dp(self, val: float) -> int:
        return int(round(val * self._dpi / 96.0))

    def _f(self, val: float) -> float:
        return float(val) * self._dpi / 96.0

    def _create_window(self) -> int:
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.style = CS_HREDRAW | CS_VREDRAW | CS_DROPSHADOW
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.hCursor = self._cursor_arrow
        wc.lpszClassName = self.CLASS_NAME
        user32.RegisterClassExW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_TOPMOST,
            self.CLASS_NAME,
            "外设电量",
            WS_POPUP | WS_CLIPCHILDREN | WS_CLIPSIBLINGS,
            0, 0, self._width_px, self._height_px,
            None, None, hinst, None,
        )
        theme = _get_theme(self._cfg.theme_mode)
        apply_window_dwm_style(hwnd, dark=theme.dark)
        return hwnd

    def destroy(self) -> None:
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = 0

    def is_visible(self) -> bool:
        return bool(self.hwnd and user32.IsWindowVisible(self.hwnd))

    def update_state(
        self,
        devices: List[DeviceBattery],
        cfg: AppConfig,
        last_updated: float,
        is_refreshing: bool = False,
    ) -> None:
        self._devices = list(devices)
        self._cfg = cfg
        self._last_updated = last_updated
        self._is_refreshing = is_refreshing
        if self.is_visible():
            self._reposition_and_resize(keep_anchor=True)
            self.repaint()

    def show_settings(self) -> None:
        self._view = "settings"
        self._scroll_y = 0.0
        self.show(force=True)

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
            return
        # Guard against hide-then-reopen race when clicking tray icon while popup is open
        if time.monotonic() - self._last_hide_time < 0.25:
            return
        self._view = "devices"
        self._scroll_y = 0.0
        self.show(force=True)

    def show(self, force: bool = False) -> None:
        if not self.hwnd:
            return
        self._dpi = get_window_dpi(self.hwnd)
        theme = _get_theme(self._cfg.theme_mode)
        apply_window_dwm_style(self.hwnd, dark=theme.dark)
        self._reposition_and_resize(keep_anchor=False)
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.SetForegroundWindow(self.hwnd)
        self.repaint()

    def hide(self) -> None:
        if self.is_visible():
            self._last_hide_time = time.monotonic()
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self._hover_id = None
            trim_working_set()

    def repaint(self) -> None:
        if self.hwnd:
            user32.InvalidateRect(self.hwnd, None, False)

    def _compute_desired_size(self) -> Tuple[int, int]:
        w = self._dp(348)
        if self._view == "settings":
            h = self._dp(416)
            return w, h

        header_h = 54
        footer_h = 34
        pad_y = 10
        card_h = 76
        gap = 8
        count = len(self._devices)
        if count == 0:
            body_h = 128
        else:
            body_h = count * card_h + max(0, count - 1) * gap + pad_y * 2
        total_dp = min(500, header_h + body_h + footer_h)
        visible_body_dp = total_dp - header_h - footer_h
        self._max_scroll = max(0.0, self._f(body_h - visible_body_dp))
        self._scroll_y = max(0.0, min(self._scroll_y, self._max_scroll))
        return w, self._dp(total_dp)

    def _reposition_and_resize(self, keep_anchor: bool = False) -> None:
        w, h = self._compute_desired_size()
        self._width_px = w
        self._height_px = h

        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        work = mi.rcWork
        mon = mi.rcMonitor
        margin = self._dp(10)

        if keep_anchor and self.is_visible():
            # Keep bottom-right aligned cleanly inside work area
            x = work.right - w - margin
            y = work.bottom - h - margin
        else:
            # Anchor near cursor horizontally, clamped cleanly into monitor work area
            x = pt.x - w // 2
            x = max(work.left + margin, min(x, work.right - w - margin))
            # Detect taskbar edge
            if work.top > mon.top:  # Taskbar at top
                y = work.top + margin
            elif work.left > mon.left:  # Taskbar at left
                x = work.left + margin
                y = min(max(work.top + margin, pt.y - h // 2), work.bottom - h - margin)
            elif work.right < mon.right:  # Taskbar at right
                x = work.right - w - margin
                y = min(max(work.top + margin, pt.y - h // 2), work.bottom - h - margin)
            else:  # Standard bottom taskbar
                y = work.bottom - h - margin

        # SWP_NOACTIVATE = 0x0010 when resizing while already open
        flags = 0x0010 if keep_anchor else 0x0000
        user32.SetWindowPos(self.hwnd, wt.HWND(-1), x, y, w, h, flags)

    # -----------------------------------------------------------------------
    # Window Procedure
    # -----------------------------------------------------------------------
    def _proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_PAINT:
            self._on_paint(hwnd)
            return 0
        if msg == WM_ACTIVATE:
            if (wparam & 0xFFFF) == WA_INACTIVE:
                self.hide()
            return 0
        if msg == WM_KEYDOWN:
            if wparam == VK_ESCAPE:
                if self._view == "settings":
                    self._view = "devices"
                    self._reposition_and_resize(keep_anchor=True)
                    self.repaint()
                else:
                    self.hide()
                return 0
        if msg == WM_MOUSEMOVE:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            self._on_mouse_move(hwnd, float(x), float(y))
            return 0
        if msg == WM_MOUSELEAVE:
            self._tracking_leave = False
            if self._hover_id is not None:
                self._hover_id = None
                self.repaint()
            return 0
        if msg == WM_SETCURSOR:
            user32.SetCursor(self._cursor_hand if self._hover_id else self._cursor_arrow)
            return 1
        if msg == WM_LBUTTONUP:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            self._on_click(float(x), float(y))
            return 0
        if msg == WM_MOUSEWHEEL:
            if self._view == "devices" and self._max_scroll > 0:
                delta = ctypes.c_short((wparam >> 16) & 0xFFFF).value
                self._scroll_y = max(0.0, min(self._max_scroll, self._scroll_y - delta * 0.35))
                self.repaint()
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _hit_test(self, x: float, y: float) -> Optional[Tuple[str, Any]]:
        for (rx, ry, rw, rh), action, payload in reversed(self._hit_zones):
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return action, payload
        return None

    def _on_mouse_move(self, hwnd: int, x: float, y: float) -> None:
        if not self._tracking_leave:
            tme = TRACKMOUSEEVENT(ctypes.sizeof(TRACKMOUSEEVENT), TME_LEAVE, hwnd, 0)
            user32.TrackMouseEvent(ctypes.byref(tme))
            self._tracking_leave = True
        hit = self._hit_test(x, y)
        new_hover = f"{hit[0]}:{hit[1]}" if hit else None
        if new_hover != self._hover_id:
            self._hover_id = new_hover
            self.repaint()

    def _on_click(self, x: float, y: float) -> None:
        hit = self._hit_test(x, y)
        if not hit:
            return
        action, payload = hit
        if action == "refresh":
            self._on_refresh()
        elif action == "open_settings":
            self._view = "settings"
            self._scroll_y = 0.0
            self._hover_id = None
            self._reposition_and_resize(keep_anchor=True)
            self.repaint()
        elif action == "back":
            self._view = "devices"
            self._scroll_y = 0.0
            self._hover_id = None
            self._reposition_and_resize(keep_anchor=True)
            self.repaint()
        elif action == "pin_device":
            self._on_pin_device(str(payload))
        elif action == "toggle_cfg":
            key = str(payload)
            cur = bool(getattr(self._cfg, key, False))
            self._on_update_config(key, not cur)
        elif action == "set_cfg":
            key, val = payload
            self._on_update_config(key, val)
            if key == "theme_mode":
                theme = _get_theme(str(val))
                apply_window_dwm_style(self.hwnd, dark=theme.dark)
            self.repaint()

    # -----------------------------------------------------------------------
    # Offscreen Double-Buffered GDI+ Rendering (0% GPU)
    # -----------------------------------------------------------------------
    def _on_paint(self, hwnd: int) -> None:
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        rect = wt.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        w = max(1, rect.right - rect.left)
        h = max(1, rect.bottom - rect.top)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(bmi.bmiHeader)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        bits_ptr = ctypes.c_void_p()
        mem_dc = gdi32.CreateCompatibleDC(hdc)
        hbm = gdi32.CreateDIBSection(
            mem_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits_ptr), None, 0
        )
        old_bmp = gdi32.SelectObject(mem_dc, hbm)
        try:
            self._hit_zones.clear()
            theme = _get_theme(self._cfg.theme_mode)
            with Canvas(mem_dc, cleartype=True) as cv:
                cv.clear(theme.bg)
                if self._view == "settings":
                    self._render_settings(cv, float(w), float(h), theme)
                else:
                    self._render_devices(cv, float(w), float(h), theme)
                # Crisp 1px outer frame (great on Windows 10 & subtle polish on Win11)
                cv.stroke_round_rect(0.5, 0.5, w - 1.0, h - 1.0, self._f(8), theme.border, 1.0)

            gdi32.BitBlt(hdc, 0, 0, w, h, mem_dc, 0, 0, SRCCOPY)
        finally:
            gdi32.SelectObject(mem_dc, old_bmp)
            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(mem_dc)
            user32.EndPaint(hwnd, ctypes.byref(ps))

    def _add_hit(self, x: float, y: float, w: float, h: float, action: str, payload: Any = "") -> bool:
        self._hit_zones.append(((x, y, w, h), action, payload))
        return self._hover_id == f"{action}:{payload}"

    def _render_devices(self, cv: Canvas, w: float, h: float, t: _Theme) -> None:
        pad = self._f(14)
        header_h = self._f(52)
        footer_h = self._f(34)

        # ---- Header ----
        cv.draw_text("外设电量", pad, self._f(12), self._f(120), self._f(28), self._f(16), t.text_primary, bold=True)

        online_cnt = sum(1 for d in self._devices if d.online)
        badge_txt = f"{online_cnt} 在线" if online_cnt > 0 else f"{len(self._devices)} 已记录"
        badge_w = self._f(56)
        badge_x = pad + self._f(74)
        badge_y = self._f(16)
        badge_h = self._f(20)
        badge_bg = argb(38, 34, 197, 94) if online_cnt > 0 else t.pill_bg
        badge_fg = hex_color("#22C55E") if online_cnt > 0 else t.text_secondary
        cv.fill_round_rect(badge_x, badge_y, badge_w, badge_h, self._f(10), badge_bg)
        cv.draw_text(badge_txt, badge_x, badge_y, badge_w, badge_h, self._f(11), badge_fg, bold=True, align="center")

        btn_sz = self._f(28)
        btn_y = self._f(12)
        set_x = w - pad - btn_sz
        ref_x = set_x - btn_sz - self._f(6)

        if self._add_hit(ref_x, btn_y, btn_sz, btn_sz, "refresh", ""):
            cv.fill_round_rect(ref_x, btn_y, btn_sz, btn_sz, self._f(7), t.btn_hover)
        cv.draw_refresh_icon(
            ref_x + btn_sz / 2, btn_y + btn_sz / 2, self._f(16),
            hex_color("#38BDF8") if self._is_refreshing else t.text_secondary,
        )

        if self._add_hit(set_x, btn_y, btn_sz, btn_sz, "open_settings", ""):
            cv.fill_round_rect(set_x, btn_y, btn_sz, btn_sz, self._f(7), t.btn_hover)
        cv.draw_gear_icon(set_x + btn_sz / 2, btn_y + btn_sz / 2, self._f(16), t.text_secondary)

        cv.draw_line(pad, header_h, w - pad, header_h, t.divider, 1.0, rounded=False)

        # ---- Device Cards ----
        body_top = header_h + self._f(10)
        body_bottom = h - footer_h - self._f(4)
        card_w = w - pad * 2
        card_h = self._f(76)
        gap = self._f(8)

        if not self._devices:
            ey = body_top + self._f(14)
            cv.fill_round_rect(pad, ey, card_w, self._f(94), self._f(10), t.card)
            cv.stroke_round_rect(pad, ey, card_w, self._f(94), self._f(10), t.card_border, 1.0)
            cv.draw_text(
                "暂未检测到外设电量",
                pad, ey + self._f(20), card_w, self._f(24),
                self._f(14), t.text_primary, bold=True, align="center",
            )
            cv.draw_text(
                "请连接蓝牙鼠标/耳机或 2.4G 接收器后点击刷新",
                pad + self._f(12), ey + self._f(48), card_w - self._f(24), self._f(22),
                self._f(11.5), t.text_secondary, align="center",
            )
        else:
            y = body_top - self._scroll_y
            for dev in self._devices:
                if y + card_h >= header_h and y <= body_bottom:
                    self._render_device_card(cv, dev, pad, y, card_w, card_h, t)
                y += card_h + gap

        # ---- Mask overflow cleanly over header/footer ----
        cv.fill_rect(1.0, h - footer_h, w - 2.0, footer_h - 1.0, t.bg)
        cv.draw_line(pad, h - footer_h, w - pad, h - footer_h, t.divider, 1.0, rounded=False)

        if self._is_refreshing:
            ftxt = "正在刷新外设电量..."
        elif self._last_updated > 0:
            ts = time.strftime("%H:%M:%S", time.localtime(self._last_updated))
            ftxt = f"更新于 {ts}  ·  点击卡片可固定到托盘"
        else:
            ftxt = "点击卡片可固定主显外设到托盘"
        cv.draw_text(
            ftxt, pad, h - footer_h, w - pad * 2, footer_h,
            self._f(11), t.text_muted, align="left",
        )

    def _render_device_card(
        self, cv: Canvas, dev: DeviceBattery, x: float, y: float, w: float, h: float, t: _Theme
    ) -> None:
        is_pinned = bool(self._cfg.pinned_device_id and dev.device_id == self._cfg.pinned_device_id)
        hovered = self._add_hit(x, y, w, h, "pin_device", dev.device_id)

        bg = t.card_hover if hovered else t.card
        border = t.card_pinned_border if is_pinned else t.card_border
        cv.fill_round_rect(x, y, w, h, self._f(10), bg)
        cv.stroke_round_rect(x, y, w, h, self._f(10), border, self._f(1.4 if is_pinned else 1.0))

        accent = battery_accent_color(dev.percentage, charging=dev.charging, online=dev.online)

        # Left vector icon badge
        icon_box = self._f(36)
        ix = x + self._f(12)
        iy = y + self._f(11)
        cv.fill_round_rect(ix, iy, icon_box, icon_box, self._f(9), t.icon_bg)
        cv.draw_device_icon(dev.kind, ix + icon_box / 2, iy + icon_box / 2, self._f(20), accent)

        # Right percentage readout
        pct_w = self._f(68)
        pct_x = x + w - pct_w - self._f(12)
        cv.draw_text(
            dev.display_percentage,
            pct_x, y + self._f(9), pct_w, self._f(26),
            self._f(17 if dev.percentage is not None else 13),
            accent if (dev.online or dev.charging) else t.text_secondary,
            bold=True,
            align="right",
            family="Segoe UI",
        )
        if dev.charging and dev.percentage is not None:
            cv.draw_text(
                "⚡ 充电中",
                pct_x - self._f(10), y + self._f(34), pct_w + self._f(10), self._f(16),
                self._f(10.5), hex_color("#38BDF8"), align="right",
            )
        elif dev.voltage_mv:
            cv.draw_text(
                f"{dev.voltage_mv / 1000.0:.2f}V",
                pct_x, y + self._f(34), pct_w, self._f(16),
                self._f(10.5), t.text_muted, align="right", family="Segoe UI",
            )

        # Middle device name & tags
        tx = ix + icon_box + self._f(10)
        tw = pct_x - tx - self._f(6)
        cv.draw_text(
            dev.name, tx, y + self._f(9), tw, self._f(22),
            self._f(13.5), t.text_primary if dev.online else t.text_secondary, bold=True,
        )

        # Sub-tags row
        tags = [dev.connection.value]
        if dev.status_note:
            tags.append(dev.status_note)
        elif not dev.online:
            tags.append("离线缓存")
        if is_pinned:
            tags.append("★ 托盘主显")
        tag_x = tx
        tag_y = y + self._f(33)
        tag_h = self._f(17)
        for idx_t, tag in enumerate(tags):
            vis_len = sum(10.2 if ord(ch) > 127 else 6.2 for ch in tag)
            tag_w = self._f(14.0 + vis_len)
            if tag_x + tag_w > pct_x:
                break
            if "托盘主显" in tag:
                tbg = argb(40, 59, 130, 246)
                tfg = hex_color("#60A5FA") if t.dark else hex_color("#2563EB")
            elif dev.status_note and tag == dev.status_note:
                tbg = argb(38, 245, 158, 11)
                tfg = hex_color("#FBBF24") if t.dark else hex_color("#D97706")
            elif idx_t == 0:
                tbg = t.pill_bg
                tfg = t.text_secondary
            else:
                tbg = argb(28, 148, 163, 184)
                tfg = t.text_muted
            cv.fill_round_rect(tag_x, tag_y, tag_w, tag_h, self._f(5), tbg)
            cv.draw_text(tag, tag_x, tag_y, tag_w, tag_h, self._f(10), tfg, align="center")
            tag_x += tag_w + self._f(5)

        # Bottom battery progress bar
        bar_x = x + self._f(12)
        bar_y = y + h - self._f(14)
        bar_w = w - self._f(24)
        bar_h = self._f(5.5)
        cv.fill_round_rect(bar_x, bar_y, bar_w, bar_h, bar_h / 2, t.track_bg)
        ratio = (dev.percentage / 100.0) if dev.percentage is not None else (1.0 if dev.charging else 0.0)
        if ratio > 0:
            fw = max(bar_h, bar_w * min(1.0, ratio))
            cv.fill_round_rect(bar_x, bar_y, fw, bar_h, bar_h / 2, accent)

    def _render_settings(self, cv: Canvas, w: float, h: float, t: _Theme) -> None:
        pad = self._f(14)
        header_h = self._f(52)

        # Back button
        btn_sz = self._f(28)
        btn_y = self._f(12)
        if self._add_hit(pad, btn_y, btn_sz, btn_sz, "back", ""):
            cv.fill_round_rect(pad, btn_y, btn_sz, btn_sz, self._f(7), t.btn_hover)
        cv.draw_back_icon(pad + btn_sz / 2, btn_y + btn_sz / 2, self._f(16), t.text_primary)
        cv.draw_text("偏好设置", pad + btn_sz + self._f(8), btn_y, self._f(140), btn_sz, self._f(15.5), t.text_primary, bold=True)
        cv.draw_line(pad, header_h, w - pad, header_h, t.divider, 1.0, rounded=False)

        y = header_h + self._f(12)
        row_h = self._f(38)

        # Toggle rows
        toggles = [
            ("autostart", "开机自动启动"),
            ("show_offline_devices", "显示离线蓝牙缓存电量"),
            ("show_system_battery", "显示本机笔记本电池"),
            ("low_battery_notify", "低电量桌面通知提醒"),
        ]
        for key, label in toggles:
            val = bool(getattr(self._cfg, key, False))
            self._render_toggle_row(cv, pad, y, w - pad * 2, row_h, label, val, key, t)
            y += row_h + self._f(4)

        y += self._f(6)
        # Segmented selectors
        self._render_pill_row(
            cv, pad, y, w - pad * 2, "自动刷新间隔",
            [(15, "15秒"), (30, "30秒"), (60, "60秒"), (120, "2分")],
            self._cfg.refresh_interval, "refresh_interval", t,
        )
        y += self._f(56)
        self._render_pill_row(
            cv, pad, y, w - pad * 2, "低电量提醒阈值",
            [(10, "10%"), (15, "15%"), (20, "20%"), (30, "30%")],
            self._cfg.low_battery_threshold, "low_battery_threshold", t,
        )
        y += self._f(56)
        self._render_pill_row(
            cv, pad, y, w - pad * 2, "浮窗界面主题",
            [("auto", "跟随系统"), ("dark", "深色"), ("light", "浅色")],
            self._cfg.theme_mode, "theme_mode", t,
        )

    def _render_toggle_row(
        self, cv: Canvas, x: float, y: float, w: float, h: float, label: str, on: bool, key: str, t: _Theme
    ) -> None:
        hovered = self._add_hit(x, y, w, h, "toggle_cfg", key)
        if hovered:
            cv.fill_round_rect(x, y, w, h, self._f(8), t.card_hover)
        cv.draw_text(label, x + self._f(8), y, w - self._f(64), h, self._f(13), t.text_primary)

        tw, th = self._f(38), self._f(20)
        tx = x + w - tw - self._f(8)
        ty = y + (h - th) / 2
        cv.fill_round_rect(tx, ty, tw, th, th / 2, t.toggle_on if on else t.toggle_off)
        kd = th - self._f(5)
        kx = (tx + tw - kd - self._f(2.5)) if on else (tx + self._f(2.5))
        cv.fill_ellipse(kx, ty + self._f(2.5), kd, kd, t.toggle_knob)

    def _render_pill_row(
        self,
        cv: Canvas,
        x: float,
        y: float,
        w: float,
        title: str,
        options: List[Tuple[Any, str]],
        current: Any,
        cfg_key: str,
        t: _Theme,
    ) -> None:
        cv.draw_text(title, x + self._f(6), y, w, self._f(18), self._f(12), t.text_secondary)
        py = y + self._f(22)
        ph = self._f(26)
        gap = self._f(6)
        pw = (w - gap * (len(options) - 1)) / len(options)
        for idx_o, (val, label) in enumerate(options):
            px = x + idx_o * (pw + gap)
            active = val == current
            hovered = self._add_hit(px, py, pw, ph, "set_cfg", (cfg_key, val))
            bg = t.pill_active_bg if active else (t.card_hover if hovered else t.pill_bg)
            fg = t.pill_active_text if active else t.text_primary
            cv.fill_round_rect(px, py, pw, ph, self._f(7), bg)
            cv.draw_text(label, px, py, pw, ph, self._f(11.5), fg, bold=active, align="center")
