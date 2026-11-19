"""Dynamic DPI-aware & taskbar-theme-aware system tray HICON generator (pure CPU GDI+)."""

from __future__ import annotations

import ctypes
from typing import Optional

from ..models import DeviceBattery
from ..win32_api import (
    BI_RGB,
    BITMAPINFO,
    DIB_RGB_COLORS,
    ICONINFO,
    gdi32,
    get_system_dpi,
    is_light_taskbar,
    user32,
)
from .gdiplus_draw import Canvas, argb, battery_accent_color, hex_color


def create_battery_tray_icon(
    device: Optional[DeviceBattery],
    dpi: Optional[int] = None,
    light_taskbar: Optional[bool] = None,
) -> int:
    """Render crisp percentage digits + bottom battery bar into a 32-bit ARGB HICON."""
    if dpi is None:
        dpi = get_system_dpi()
    if light_taskbar is None:
        light_taskbar = is_light_taskbar()

    # Crisp oversampled icon size matching DPI (32px at 100%, 48px at 150%, 64px at 200%)
    size = max(32, min(64, int(round(32 * dpi / 96.0))))

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(bmi.bmiHeader)
    bmi.bmiHeader.biWidth = size
    bmi.bmiHeader.biHeight = -size  # top-down DIB
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    bits_ptr = ctypes.c_void_p()
    mem_dc = gdi32.CreateCompatibleDC(None)
    hbm_color = gdi32.CreateDIBSection(
        mem_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits_ptr), None, 0
    )
    old_bmp = gdi32.SelectObject(mem_dc, hbm_color)

    # Clear transparent background
    ctypes.memset(bits_ptr, 0, size * size * 4)

    try:
        pct = device.percentage if device else None
        charging = device.charging if device else False
        online = device.online if device else False

        bar_color = battery_accent_color(pct, charging=charging, online=online)

        if light_taskbar:
            text_color = hex_color("#18181B")
            track_color = argb(65, 24, 24, 27)
        else:
            text_color = hex_color("#FFFFFF")
            track_color = argb(72, 255, 255, 255)

        if pct is not None and pct <= 20 and online and not charging:
            text_color = hex_color("#FF4D4F") if not light_taskbar else hex_color("#DC2626")
        elif device and not online:
            text_color = hex_color("#CBD5E1") if not light_taskbar else hex_color("#64748B")

        with Canvas(mem_dc, cleartype=False) as cv:
            # Top area: crisp percentage digits
            if device is None:
                label = "--"
                font_px = size * 0.56
            elif pct is None:
                label = ""
                font_px = size * 0.56
            else:
                label = str(pct)
                if len(label) >= 3:
                    font_px = size * 0.45
                elif len(label) == 2:
                    font_px = size * 0.58
                else:
                    font_px = size * 0.62

            if label:
                cv.draw_text(
                    label,
                    -size * 0.06,
                    -size * 0.04,
                    size * 1.12,
                    size * 0.76,
                    font_px,
                    text_color,
                    bold=True,
                    align="center",
                    valign="center",
                    family="Segoe UI",
                    ellipsis=False,
                )
            elif charging:
                cv.draw_bolt(size * 0.5, size * 0.36, size * 0.52, bar_color)

            # Bottom rounded battery bar
            pad_x = max(2.0, size * 0.06)
            bar_h = max(4.0, size * 0.19)
            bar_y = size - bar_h - max(1.0, size * 0.05)
            bar_w = size - pad_x * 2
            radius = bar_h * 0.48

            cv.fill_round_rect(pad_x, bar_y, bar_w, bar_h, radius, track_color)

            fill_ratio = 0.0
            if pct is not None:
                fill_ratio = max(0.08, min(1.0, pct / 100.0))
            elif charging:
                fill_ratio = 1.0

            if fill_ratio > 0:
                fill_w = max(bar_h, bar_w * fill_ratio)
                cv.fill_round_rect(pad_x, bar_y, fill_w, bar_h, radius, bar_color)

            # Subtle charging dot in top-right when both pct and charging are present
            if charging and label:
                dot = max(4.0, size * 0.18)
                cv.fill_ellipse(size - dot - 1.0, 1.0, dot, dot, hex_color("#38BDF8"))

        # Monochrome mask (all zeros -> Windows uses 32-bit alpha channel of hbm_color)
        hbm_mask = gdi32.CreateBitmap(size, size, 1, 1, None)
        ii = ICONINFO()
        ii.fIcon = True
        ii.xHotspot = 0
        ii.yHotspot = 0
        ii.hbmMask = hbm_mask
        ii.hbmColor = hbm_color
        hicon = user32.CreateIconIndirect(ctypes.byref(ii))
        gdi32.DeleteObject(hbm_mask)
        return hicon
    finally:
        gdi32.SelectObject(mem_dc, old_bmp)
        gdi32.DeleteObject(hbm_color)
        gdi32.DeleteDC(mem_dc)
