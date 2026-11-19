"""Type-safe 64-bit Win32 & GDI+ ctypes bindings (pure CPU rendering, zero GPU context)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import winreg

# Pointer-sized signed integer for WPARAM/LPARAM/LRESULT
LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
HCURSOR = wt.HANDLE
HICON = wt.HANDLE
HBRUSH = wt.HANDLE
HMENU = wt.HANDLE
HBITMAP = wt.HANDLE
HDC = wt.HANDLE
HINSTANCE = wt.HANDLE

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdiplus = ctypes.WinDLL("gdiplus", use_last_error=True)

try:
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
except OSError:
    dwmapi = None

# ---------------------------------------------------------------------------
# Window / Tray / Menu Constants
# ---------------------------------------------------------------------------
WS_POPUP = 0x80000000
WS_CLIPCHILDREN = 0x02000000
WS_CLIPSIBLINGS = 0x04000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000

CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
CS_DROPSHADOW = 0x00020000

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOW = 5

WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_ACTIVATE = 0x0006
WM_PAINT = 0x000F
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_ERASEBKGND = 0x0014
WM_SETTINGCHANGE = 0x001A
WM_SETCURSOR = 0x0020
WM_KEYDOWN = 0x0100
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_MOUSEWHEEL = 0x020A
WM_MOUSELEAVE = 0x02A3
WM_DEVICECHANGE = 0x0219
WM_DPICHANGED = 0x02E0
WM_APP = 0x8000

WM_TRAYICON = WM_APP + 1
WM_DATA_UPDATED = WM_APP + 2
WM_SHOW_POPUP_REQ = WM_APP + 3

WA_INACTIVE = 0
VK_ESCAPE = 0x1B

DBT_DEVNODES_CHANGED = 0x0007
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIM_SETVERSION = 0x00000004

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIF_SHOWTIP = 0x00000080

NIIF_NONE = 0x00000000
NIIF_INFO = 0x00000001
NIIF_WARNING = 0x00000002

NOTIFYICON_VERSION_4 = 4
NIN_SELECT = 0x0400
NIN_KEYSELECT = 0x0401

MF_STRING = 0x00000000
MF_GRAYED = 0x00000001
MF_CHECKED = 0x00000008
MF_POPUP = 0x00000010
MF_SEPARATOR = 0x00000800

TPM_LEFTALIGN = 0x0000
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
TPM_BOTTOMALIGN = 0x0020

IDC_ARROW = 32512
IDC_HAND = 32649

SPI_GETWORKAREA = 0x0030
MONITOR_DEFAULTTONEAREST = 0x00000002

TME_LEAVE = 0x00000002
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2

# ---------------------------------------------------------------------------
# Structs
# ---------------------------------------------------------------------------
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, WPARAM, LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", HICON),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uVersion", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", ctypes.c_ubyte * 16),
        ("hBalloonIcon", HICON),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", HDC),
        ("fErase", wt.BOOL),
        ("rcPaint", wt.RECT),
        ("fRestore", wt.BOOL),
        ("fIncUpdate", wt.BOOL),
        ("rgbReserved", ctypes.c_ubyte * 32),
    ]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("hwndTrack", wt.HWND),
        ("dwHoverTime", wt.DWORD),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", wt.LONG),
        ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wt.DWORD * 3),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wt.BOOL),
        ("xHotspot", wt.DWORD),
        ("yHotspot", wt.DWORD),
        ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", wt.RECT),
        ("rcWork", wt.RECT),
        ("dwFlags", wt.DWORD),
    ]


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", wt.UINT),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", wt.BOOL),
        ("SuppressExternalCodecs", wt.BOOL),
    ]


class RectF(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.c_float),
        ("Y", ctypes.c_float),
        ("Width", ctypes.c_float),
        ("Height", ctypes.c_float),
    ]


class PointF(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.c_float),
        ("Y", ctypes.c_float),
    ]


# ---------------------------------------------------------------------------
# Function Prototypes (x64 safe)
# ---------------------------------------------------------------------------
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = HINSTANCE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL
kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wt.HANDLE
kernel32.SetProcessWorkingSetSize.argtypes = [wt.HANDLE, ctypes.c_size_t, ctypes.c_size_t]
kernel32.SetProcessWorkingSetSize.restype = wt.BOOL

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wt.ATOM
user32.UnregisterClassW.argtypes = [wt.LPCWSTR, HINSTANCE]
user32.UnregisterClassW.restype = wt.BOOL
user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, HMENU, HINSTANCE, ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wt.HWND
user32.DestroyWindow.argtypes = [wt.HWND]
user32.DestroyWindow.restype = wt.BOOL
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL
user32.UpdateWindow.argtypes = [wt.HWND]
user32.UpdateWindow.restype = wt.BOOL
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.SetWindowPos.argtypes = [
    wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT
]
user32.SetWindowPos.restype = wt.BOOL
user32.InvalidateRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT), wt.BOOL]
user32.InvalidateRect.restype = wt.BOOL
user32.BeginPaint.argtypes = [wt.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = HDC
user32.EndPaint.argtypes = [wt.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.EndPaint.restype = wt.BOOL
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetClientRect.restype = wt.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.GetCursorPos.restype = wt.BOOL
user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
user32.MonitorFromPoint.restype = wt.HMONITOR
user32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wt.BOOL
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = wt.BOOL
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = wt.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
user32.RegisterWindowMessageW.restype = wt.UINT
user32.LoadCursorW.argtypes = [HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = HCURSOR
user32.SetCursor.argtypes = [HCURSOR]
user32.SetCursor.restype = HCURSOR
user32.TrackMouseEvent.argtypes = [ctypes.POINTER(TRACKMOUSEEVENT)]
user32.TrackMouseEvent.restype = wt.BOOL
user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = HMENU
user32.DestroyMenu.argtypes = [HMENU]
user32.DestroyMenu.restype = wt.BOOL
user32.AppendMenuW.argtypes = [HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
user32.AppendMenuW.restype = wt.BOOL
user32.TrackPopupMenu.argtypes = [
    HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, ctypes.c_void_p
]
user32.TrackPopupMenu.restype = wt.BOOL
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.CreateIconIndirect.restype = HICON
user32.DestroyIcon.argtypes = [HICON]
user32.DestroyIcon.restype = wt.BOOL
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [wt.HWND, ctypes.c_size_t]
user32.KillTimer.restype = wt.BOOL
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND

shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wt.BOOL

gdi32.CreateCompatibleDC.argtypes = [HDC]
gdi32.CreateCompatibleDC.restype = HDC
gdi32.DeleteDC.argtypes = [HDC]
gdi32.DeleteDC.restype = wt.BOOL
gdi32.SelectObject.argtypes = [HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteObject.restype = wt.BOOL
gdi32.CreateDIBSection.argtypes = [
    HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
    ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD,
]
gdi32.CreateDIBSection.restype = HBITMAP
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wt.UINT, wt.UINT, ctypes.c_void_p]
gdi32.CreateBitmap.restype = HBITMAP
gdi32.BitBlt.argtypes = [
    HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    HDC, ctypes.c_int, ctypes.c_int, wt.DWORD,
]
gdi32.BitBlt.restype = wt.BOOL

if dwmapi is not None:
    dwmapi.DwmSetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
    dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

# GDI+ flat API
gdiplus.GdiplusStartup.argtypes = [
    ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(GdiplusStartupInput), ctypes.c_void_p
]
gdiplus.GdiplusStartup.restype = ctypes.c_int
gdiplus.GdiplusShutdown.argtypes = [ctypes.c_size_t]
gdiplus.GdiplusShutdown.restype = None

gdiplus.GdipCreateFromHDC.argtypes = [HDC, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateFromHDC.restype = ctypes.c_int
gdiplus.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeleteGraphics.restype = ctypes.c_int
gdiplus.GdipSetSmoothingMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetSmoothingMode.restype = ctypes.c_int
gdiplus.GdipSetTextRenderingHint.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetTextRenderingHint.restype = ctypes.c_int
gdiplus.GdipSetPixelOffsetMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetPixelOffsetMode.restype = ctypes.c_int
gdiplus.GdipGraphicsClear.argtypes = [ctypes.c_void_p, wt.DWORD]
gdiplus.GdipGraphicsClear.restype = ctypes.c_int

gdiplus.GdipCreateSolidFill.argtypes = [wt.DWORD, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateSolidFill.restype = ctypes.c_int
gdiplus.GdipDeleteBrush.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeleteBrush.restype = ctypes.c_int

gdiplus.GdipCreatePen1.argtypes = [wt.DWORD, ctypes.c_float, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreatePen1.restype = ctypes.c_int
gdiplus.GdipSetPenStartCap.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetPenEndCap.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetPenLineJoin.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipDeletePen.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeletePen.restype = ctypes.c_int

gdiplus.GdipCreatePath.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreatePath.restype = ctypes.c_int
gdiplus.GdipDeletePath.argtypes = [ctypes.c_void_p]
gdiplus.GdipDeletePath.restype = ctypes.c_int
gdiplus.GdipAddPathArc.argtypes = [
    ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_float,
]
gdiplus.GdipClosePathFigure.argtypes = [ctypes.c_void_p]
gdiplus.GdipFillPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
gdiplus.GdipDrawPath.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
gdiplus.GdipFillRectangle.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
]
gdiplus.GdipDrawRectangle.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
]
gdiplus.GdipFillEllipse.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
]
gdiplus.GdipDrawEllipse.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
]
gdiplus.GdipDrawLine.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
]
gdiplus.GdipDrawArc.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float, ctypes.c_float,
    ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
]
gdiplus.GdipFillPolygon.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(PointF), ctypes.c_int, ctypes.c_int
]
gdiplus.GdipDrawLines.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(PointF), ctypes.c_int
]

gdiplus.GdipCreateFontFamilyFromName.argtypes = [wt.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateFontFamilyFromName.restype = ctypes.c_int
gdiplus.GdipDeleteFontFamily.argtypes = [ctypes.c_void_p]
gdiplus.GdipCreateFont.argtypes = [
    ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)
]
gdiplus.GdipCreateFont.restype = ctypes.c_int
gdiplus.GdipDeleteFont.argtypes = [ctypes.c_void_p]
gdiplus.GdipCreateStringFormat.argtypes = [ctypes.c_int, wt.WORD, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDeleteStringFormat.argtypes = [ctypes.c_void_p]
gdiplus.GdipSetStringFormatAlign.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetStringFormatLineAlign.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetStringFormatTrimming.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipSetStringFormatFlags.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipDrawString.argtypes = [
    ctypes.c_void_p, wt.LPCWSTR, ctypes.c_int, ctypes.c_void_p,
    ctypes.POINTER(RectF), ctypes.c_void_p, ctypes.c_void_p,
]
gdiplus.GdipMeasureString.argtypes = [
    ctypes.c_void_p, wt.LPCWSTR, ctypes.c_int, ctypes.c_void_p,
    ctypes.POINTER(RectF), ctypes.c_void_p, ctypes.POINTER(RectF),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
]


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------
_gdiplus_token = ctypes.c_size_t(0)


def init_dpi_awareness() -> None:
    """Enable Per-Monitor DPI Awareness v2 so tray icons and popups stay razor sharp."""
    try:
        fn = user32.SetProcessDpiAwarenessContext
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = wt.BOOL
        if fn(ctypes.c_void_p(-4)):  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def get_system_dpi() -> int:
    try:
        fn = user32.GetDpiForSystem
        fn.restype = wt.UINT
        dpi = int(fn())
        return dpi if dpi >= 96 else 96
    except Exception:
        return 96


def get_window_dpi(hwnd: int) -> int:
    try:
        fn = user32.GetDpiForWindow
        fn.argtypes = [wt.HWND]
        fn.restype = wt.UINT
        dpi = int(fn(hwnd))
        return dpi if dpi >= 96 else get_system_dpi()
    except Exception:
        return get_system_dpi()


def init_gdiplus() -> None:
    if _gdiplus_token.value:
        return
    inp = GdiplusStartupInput(1, None, False, False)
    gdiplus.GdiplusStartup(ctypes.byref(_gdiplus_token), ctypes.byref(inp), None)


def shutdown_gdiplus() -> None:
    if _gdiplus_token.value:
        gdiplus.GdiplusShutdown(_gdiplus_token)
        _gdiplus_token.value = 0


def trim_working_set() -> None:
    """Ask Windows to trim idle pages from working set to keep RAM usage minimal."""
    try:
        kernel32.SetProcessWorkingSetSize(
            kernel32.GetCurrentProcess(),
            ctypes.c_size_t(-1),
            ctypes.c_size_t(-1),
        )
    except Exception:
        pass


def is_light_taskbar() -> bool:
    """True if Windows taskbar uses light theme (dark icons needed)."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as k:
            val, _ = winreg.QueryValueEx(k, "SystemUsesLightTheme")
            return bool(val)
    except OSError:
        return False


def is_light_apps() -> bool:
    """True if Windows apps use light theme."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as k:
            val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return bool(val)
    except OSError:
        return False


def apply_window_dwm_style(hwnd: int, dark: bool) -> None:
    """Apply Windows 11 native rounded corners and dark/light DWM frame without GPU overhead."""
    if dwmapi is None:
        return
    try:
        val = ctypes.c_int(DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(val), ctypes.sizeof(val)
        )
    except Exception:
        pass
    try:
        dark_val = ctypes.c_int(1 if dark else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark_val), ctypes.sizeof(dark_val)
        )
    except Exception:
        pass
