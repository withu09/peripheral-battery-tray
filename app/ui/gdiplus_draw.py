"""Zero-GPU, leak-free GDI+ 2D drawing helpers and vector peripheral icons."""

from __future__ import annotations

import ctypes
from typing import Iterable, Tuple

from ..models import DeviceKind
from ..win32_api import PointF, RectF, gdiplus

# GDI+ constants
SMOOTHING_ANTIALIAS = 4
TEXT_HINT_ANTIALIAS_GRIDFIT = 3
TEXT_HINT_CLEARTYPE = 5
PIXEL_OFFSET_HIGH_QUALITY = 2
UNIT_PIXEL = 2
FONT_STYLE_REGULAR = 0
FONT_STYLE_BOLD = 1
LINE_CAP_ROUND = 2
LINE_JOIN_ROUND = 2
STRING_TRIM_ELLIPSIS_CHAR = 3
STRING_FORMAT_NO_WRAP = 0x00001000


def argb(a: int, r: int, g: int, b: int) -> int:
    return ((a & 0xFF) << 24) | ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)


def hex_color(hex_str: str, alpha: int = 255) -> int:
    s = hex_str.lstrip("#")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return argb(alpha, r, g, b)


def battery_accent_color(pct: int | None, charging: bool = False, online: bool = True) -> int:
    if not online:
        return hex_color("#64748B")
    if charging:
        return hex_color("#38BDF8")
    if pct is None:
        return hex_color("#94A3B8")
    if pct <= 20:
        return hex_color("#EF4444")
    if pct <= 50:
        return hex_color("#F59E0B")
    return hex_color("#22C55E")


class Canvas:
    """Thin RAII wrapper over a GDI+ Graphics pointer with zero object leaks."""

    def __init__(self, hdc: int, cleartype: bool = True) -> None:
        self.g = ctypes.c_void_p()
        gdiplus.GdipCreateFromHDC(hdc, ctypes.byref(self.g))
        gdiplus.GdipSetSmoothingMode(self.g, SMOOTHING_ANTIALIAS)
        gdiplus.GdipSetPixelOffsetMode(self.g, PIXEL_OFFSET_HIGH_QUALITY)
        gdiplus.GdipSetTextRenderingHint(
            self.g, TEXT_HINT_CLEARTYPE if cleartype else TEXT_HINT_ANTIALIAS_GRIDFIT
        )

    def __enter__(self) -> "Canvas":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def close(self) -> None:
        if self.g and self.g.value:
            gdiplus.GdipDeleteGraphics(self.g)
            self.g = ctypes.c_void_p()

    def clear(self, color: int) -> None:
        gdiplus.GdipGraphicsClear(self.g, color)

    def _make_round_path(self, x: float, y: float, w: float, h: float, r: float) -> ctypes.c_void_p:
        path = ctypes.c_void_p()
        gdiplus.GdipCreatePath(0, ctypes.byref(path))
        r = max(0.0, min(r, w / 2.0, h / 2.0))
        d = r * 2.0
        if d <= 0.5:
            # Fallback tiny arc
            d = 0.5
        gdiplus.GdipAddPathArc(path, x, y, d, d, 180.0, 90.0)
        gdiplus.GdipAddPathArc(path, x + w - d, y, d, d, 270.0, 90.0)
        gdiplus.GdipAddPathArc(path, x + w - d, y + h - d, d, d, 0.0, 90.0)
        gdiplus.GdipAddPathArc(path, x, y + h - d, d, d, 90.0, 90.0)
        gdiplus.GdipClosePathFigure(path)
        return path

    def fill_round_rect(self, x: float, y: float, w: float, h: float, r: float, color: int) -> None:
        if w <= 0 or h <= 0:
            return
        brush = ctypes.c_void_p()
        gdiplus.GdipCreateSolidFill(color, ctypes.byref(brush))
        path = self._make_round_path(x, y, w, h, r)
        try:
            gdiplus.GdipFillPath(self.g, brush, path)
        finally:
            gdiplus.GdipDeletePath(path)
            gdiplus.GdipDeleteBrush(brush)

    def stroke_round_rect(
        self, x: float, y: float, w: float, h: float, r: float, color: int, width: float = 1.0
    ) -> None:
        if w <= 0 or h <= 0:
            return
        pen = ctypes.c_void_p()
        gdiplus.GdipCreatePen1(color, width, UNIT_PIXEL, ctypes.byref(pen))
        path = self._make_round_path(x, y, w, h, r)
        try:
            gdiplus.GdipDrawPath(self.g, pen, path)
        finally:
            gdiplus.GdipDeletePath(path)
            gdiplus.GdipDeletePen(pen)

    def fill_rect(self, x: float, y: float, w: float, h: float, color: int) -> None:
        brush = ctypes.c_void_p()
        gdiplus.GdipCreateSolidFill(color, ctypes.byref(brush))
        try:
            gdiplus.GdipFillRectangle(self.g, brush, x, y, w, h)
        finally:
            gdiplus.GdipDeleteBrush(brush)

    def fill_ellipse(self, x: float, y: float, w: float, h: float, color: int) -> None:
        brush = ctypes.c_void_p()
        gdiplus.GdipCreateSolidFill(color, ctypes.byref(brush))
        try:
            gdiplus.GdipFillEllipse(self.g, brush, x, y, w, h)
        finally:
            gdiplus.GdipDeleteBrush(brush)

    def stroke_ellipse(self, x: float, y: float, w: float, h: float, color: int, width: float = 1.5) -> None:
        pen = ctypes.c_void_p()
        gdiplus.GdipCreatePen1(color, width, UNIT_PIXEL, ctypes.byref(pen))
        try:
            gdiplus.GdipDrawEllipse(self.g, pen, x, y, w, h)
        finally:
            gdiplus.GdipDeletePen(pen)

    def draw_line(
        self, x1: float, y1: float, x2: float, y2: float, color: int, width: float = 1.5, rounded: bool = True
    ) -> None:
        pen = ctypes.c_void_p()
        gdiplus.GdipCreatePen1(color, width, UNIT_PIXEL, ctypes.byref(pen))
        if rounded:
            gdiplus.GdipSetPenStartCap(pen, LINE_CAP_ROUND)
            gdiplus.GdipSetPenEndCap(pen, LINE_CAP_ROUND)
        try:
            gdiplus.GdipDrawLine(self.g, pen, x1, y1, x2, y2)
        finally:
            gdiplus.GdipDeletePen(pen)

    def draw_arc(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        start_deg: float,
        sweep_deg: float,
        color: int,
        width: float = 1.8,
    ) -> None:
        pen = ctypes.c_void_p()
        gdiplus.GdipCreatePen1(color, width, UNIT_PIXEL, ctypes.byref(pen))
        gdiplus.GdipSetPenStartCap(pen, LINE_CAP_ROUND)
        gdiplus.GdipSetPenEndCap(pen, LINE_CAP_ROUND)
        try:
            gdiplus.GdipDrawArc(self.g, pen, x, y, w, h, start_deg, sweep_deg)
        finally:
            gdiplus.GdipDeletePen(pen)

    def fill_polygon(self, points: Iterable[Tuple[float, float]], color: int) -> None:
        pts = list(points)
        if len(pts) < 3:
            return
        arr = (PointF * len(pts))(*[PointF(px, py) for px, py in pts])
        brush = ctypes.c_void_p()
        gdiplus.GdipCreateSolidFill(color, ctypes.byref(brush))
        try:
            gdiplus.GdipFillPolygon(self.g, brush, arr, len(pts), 0)
        finally:
            gdiplus.GdipDeleteBrush(brush)

    def draw_polyline(self, points: Iterable[Tuple[float, float]], color: int, width: float = 1.8) -> None:
        pts = list(points)
        if len(pts) < 2:
            return
        arr = (PointF * len(pts))(*[PointF(px, py) for px, py in pts])
        pen = ctypes.c_void_p()
        gdiplus.GdipCreatePen1(color, width, UNIT_PIXEL, ctypes.byref(pen))
        gdiplus.GdipSetPenStartCap(pen, LINE_CAP_ROUND)
        gdiplus.GdipSetPenEndCap(pen, LINE_CAP_ROUND)
        gdiplus.GdipSetPenLineJoin(pen, LINE_JOIN_ROUND)
        try:
            gdiplus.GdipDrawLines(self.g, pen, arr, len(pts))
        finally:
            gdiplus.GdipDeletePen(pen)

    def draw_text(
        self,
        text: str,
        x: float,
        y: float,
        w: float,
        h: float,
        size_px: float,
        color: int,
        bold: bool = False,
        align: str = "left",
        valign: str = "center",
        family: str = "Microsoft YaHei UI",
        ellipsis: bool = True,
    ) -> None:
        fam = ctypes.c_void_p()
        st = gdiplus.GdipCreateFontFamilyFromName(family, None, ctypes.byref(fam))
        if st != 0:
            gdiplus.GdipCreateFontFamilyFromName("Segoe UI", None, ctypes.byref(fam))
        font = ctypes.c_void_p()
        fmt = ctypes.c_void_p()
        brush = ctypes.c_void_p()
        try:
            gdiplus.GdipCreateFont(
                fam, size_px, FONT_STYLE_BOLD if bold else FONT_STYLE_REGULAR, UNIT_PIXEL, ctypes.byref(font)
            )
            gdiplus.GdipCreateStringFormat(STRING_FORMAT_NO_WRAP if ellipsis else 0, 0, ctypes.byref(fmt))
            align_map = {"left": 0, "center": 1, "right": 2}
            valign_map = {"top": 0, "center": 1, "bottom": 2}
            gdiplus.GdipSetStringFormatAlign(fmt, align_map.get(align, 0))
            gdiplus.GdipSetStringFormatLineAlign(fmt, valign_map.get(valign, 1))
            if ellipsis:
                gdiplus.GdipSetStringFormatTrimming(fmt, STRING_TRIM_ELLIPSIS_CHAR)
            gdiplus.GdipCreateSolidFill(color, ctypes.byref(brush))
            rect = RectF(x, y, max(1.0, w), max(1.0, h))
            gdiplus.GdipDrawString(self.g, text, -1, font, ctypes.byref(rect), fmt, brush)
        finally:
            if brush.value:
                gdiplus.GdipDeleteBrush(brush)
            if fmt.value:
                gdiplus.GdipDeleteStringFormat(fmt)
            if font.value:
                gdiplus.GdipDeleteFont(font)
            if fam.value:
                gdiplus.GdipDeleteFontFamily(fam)

    # -----------------------------------------------------------------------
    # Vector Peripheral & UI Icons (crisp at any DPI)
    # -----------------------------------------------------------------------
    def draw_device_icon(self, kind: DeviceKind, cx: float, cy: float, size: float, color: int) -> None:
        s = size
        lw = max(1.4, s * 0.085)

        if kind == DeviceKind.MOUSE:
            mw, mh = s * 0.56, s * 0.84
            mx, my = cx - mw / 2, cy - mh / 2
            self.stroke_round_rect(mx, my, mw, mh, mw * 0.48, color, lw)
            self.draw_line(cx, my + mh * 0.18, cx, my + mh * 0.40, color, lw * 1.15)
        elif kind == DeviceKind.HEADSET:
            aw, ah = s * 0.78, s * 0.72
            ax, ay = cx - aw / 2, cy - ah / 2 - s * 0.04
            self.draw_arc(ax, ay, aw, ah, 180.0, 180.0, color, lw * 1.1)
            ew, eh = s * 0.19, s * 0.34
            self.fill_round_rect(ax - ew * 0.2, cy + s * 0.02, ew, eh, ew * 0.45, color)
            self.fill_round_rect(ax + aw - ew * 0.8, cy + s * 0.02, ew, eh, ew * 0.45, color)
        elif kind == DeviceKind.EARBUDS:
            # Left & right TWS earbuds
            bw, bh = s * 0.28, s * 0.26
            self.fill_ellipse(cx - s * 0.36, cy - s * 0.28, bw, bh, color)
            self.draw_line(cx - s * 0.18, cy - s * 0.06, cx - s * 0.18, cy + s * 0.32, color, lw * 1.25)
            self.fill_ellipse(cx + s * 0.08, cy - s * 0.28, bw, bh, color)
            self.draw_line(cx + s * 0.18, cy - s * 0.06, cx + s * 0.18, cy + s * 0.32, color, lw * 1.25)
        elif kind == DeviceKind.KEYBOARD:
            kw, kh = s * 0.86, s * 0.54
            kx, ky = cx - kw / 2, cy - kh / 2
            self.stroke_round_rect(kx, ky, kw, kh, s * 0.12, color, lw)
            dot = max(1.6, s * 0.09)
            for row in (0.30, 0.56):
                for col in (0.20, 0.38, 0.56, 0.74):
                    self.fill_rect(kx + kw * col - dot / 2, ky + kh * row - dot / 2, dot, dot, color)
            self.draw_line(kx + kw * 0.28, ky + kh * 0.78, kx + kw * 0.72, ky + kh * 0.78, color, lw)
        elif kind == DeviceKind.GAMEPAD:
            gw, gh = s * 0.88, s * 0.56
            gx, gy = cx - gw / 2, cy - gh / 2
            self.stroke_round_rect(gx, gy, gw, gh, gh * 0.45, color, lw)
            # D-pad left
            self.draw_line(gx + gw * 0.20, cy, gx + gw * 0.34, cy, color, lw)
            self.draw_line(gx + gw * 0.27, cy - gh * 0.16, gx + gw * 0.27, cy + gh * 0.16, color, lw)
            # Buttons right
            dot = max(2.0, s * 0.11)
            self.fill_ellipse(gx + gw * 0.65, cy - dot * 1.1, dot, dot, color)
            self.fill_ellipse(gx + gw * 0.75, cy + dot * 0.1, dot, dot, color)
        elif kind == DeviceKind.LAPTOP:
            sw, sh = s * 0.74, s * 0.48
            sx, sy = cx - sw / 2, cy - sh / 2 - s * 0.08
            self.stroke_round_rect(sx, sy, sw, sh, s * 0.08, color, lw)
            self.draw_line(cx - s * 0.46, cy + sh / 2 + s * 0.06, cx + s * 0.46, cy + sh / 2 + s * 0.06, color, lw * 1.2)
        else:
            # Generic battery icon
            bw, bh = s * 0.76, s * 0.46
            bx, by = cx - bw / 2 - s * 0.04, cy - bh / 2
            self.stroke_round_rect(bx, by, bw, bh, s * 0.10, color, lw)
            self.fill_round_rect(bx + bw + lw * 0.6, cy - bh * 0.22, s * 0.10, bh * 0.44, s * 0.04, color)
            self.fill_round_rect(bx + lw * 1.8, by + lw * 1.8, bw * 0.52, bh - lw * 3.6, s * 0.04, color)

    def draw_bolt(self, cx: float, cy: float, size: float, color: int) -> None:
        s = size * 0.5
        pts = [
            (cx + s * 0.18, cy - s * 0.95),
            (cx - s * 0.62, cy + s * 0.08),
            (cx - s * 0.05, cy + s * 0.08),
            (cx - s * 0.22, cy + s * 0.95),
            (cx + s * 0.62, cy - s * 0.10),
            (cx + s * 0.05, cy - s * 0.10),
        ]
        self.fill_polygon(pts, color)

    def draw_refresh_icon(self, cx: float, cy: float, size: float, color: int) -> None:
        r = size * 0.36
        lw = max(1.5, size * 0.10)
        self.draw_arc(cx - r, cy - r, r * 2, r * 2, -45.0, 290.0, color, lw)
        # Arrowhead
        ax = cx + r * 0.76
        ay = cy - r * 0.68
        d = size * 0.18
        self.draw_polyline([(ax - d, ay), (ax, ay), (ax, ay - d)], color, lw)

    def draw_gear_icon(self, cx: float, cy: float, size: float, color: int) -> None:
        import math
        r_out = size * 0.36
        r_in = size * 0.16
        lw = max(1.5, size * 0.095)
        self.stroke_ellipse(cx - r_in, cy - r_in, r_in * 2, r_in * 2, color, lw)
        self.stroke_ellipse(cx - r_out * 0.82, cy - r_out * 0.82, r_out * 1.64, r_out * 1.64, color, lw)
        for i in range(6):
            ang = math.radians(i * 60)
            x1 = cx + math.cos(ang) * (r_out * 0.78)
            y1 = cy + math.sin(ang) * (r_out * 0.78)
            x2 = cx + math.cos(ang) * (r_out * 1.12)
            y2 = cy + math.sin(ang) * (r_out * 1.12)
            self.draw_line(x1, y1, x2, y2, color, lw * 1.15)

    def draw_back_icon(self, cx: float, cy: float, size: float, color: int) -> None:
        lw = max(1.6, size * 0.11)
        d = size * 0.30
        self.draw_line(cx - d, cy, cx + d, cy, color, lw)
        self.draw_polyline([(cx - d * 0.15, cy - d * 0.75), (cx - d, cy), (cx - d * 0.15, cy + d * 0.75)], color, lw)
