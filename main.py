"""CLI entry point for Peripheral Battery Tray Monitor."""

from __future__ import annotations

import argparse
import sys

from app.config import is_autostart_enabled, load_config, save_config, set_autostart
from app.providers.manager import BatteryManager
from app.ui.tray_app import TrayBatteryApp


def main() -> int:
    parser = argparse.ArgumentParser(description="轻量级 Windows 桌面托盘外设电量显示")
    parser.add_argument(
        "--once",
        action="store_true",
        help="仅扫描并打印当前检测到的所有外设电量后退出",
    )
    parser.add_argument(
        "--autostart",
        choices=("on", "off"),
        default=None,
        help="开启或关闭 Windows 开机自启后退出",
    )
    args = parser.parse_args()

    if args.autostart is not None:
        enabled = args.autostart == "on"
        ok = set_autostart(enabled)
        cfg = load_config()
        cfg.autostart = is_autostart_enabled()
        save_config(cfg)
        state_str = "已开启" if cfg.autostart else "已关闭"
        print(f"开机自启{state_str} ({'成功' if ok else '失败'})")
        return 0 if ok else 1

    if args.once:
        cfg = load_config()
        mgr = BatteryManager()
        devices = mgr.scan_all(cfg)
        if not devices:
            print("暂未检测到支持电量读取的外设。")
            return 0
        for d in devices:
            status = d.status_note or ("在线" if d.online else "离线缓存")
            chg = " [充电中]" if d.charging else ""
            volt = f" ({d.voltage_mv / 1000.0:.2f}V)" if d.voltage_mv else ""
            print(f"- {d.name} | {d.display_percentage}{chg}{volt} | {d.connection.value} | {status} | 来源: {d.source}")
        return 0

    app = TrayBatteryApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
