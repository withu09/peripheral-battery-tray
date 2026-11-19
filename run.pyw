"""Windowless launcher for Windows (double-click or run with pythonw.exe)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ui.tray_app import TrayBatteryApp

if __name__ == "__main__":
    sys.exit(TrayBatteryApp().run())
