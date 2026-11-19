"""Diagnostic utility to inspect detected Bluetooth/2.4G HID peripherals and resource usage."""

from __future__ import annotations

import os
import time

from app.config import load_config
from app.providers.hid_24g import dump_hid_diagnostics
from app.providers.manager import BatteryManager


def main() -> None:
    t0 = time.perf_counter()
    cfg = load_config()
    cfg.show_offline_devices = True
    cfg.show_system_battery = True

    mgr = BatteryManager()
    devices = mgr.scan_all(cfg)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    print(f"=== 外设电量扫描结果 (耗时 {elapsed_ms:.1f} ms) ===")
    if not devices:
        print("(未检测到外设电量)")
    for d in devices:
        status = d.status_note or ("在线" if d.online else "离线缓存")
        chg = " 充电中" if d.charging else ""
        volt = f" {d.voltage_mv}mV" if d.voltage_mv else ""
        print(
            f"  [{d.connection.value}] {d.name}: {d.display_percentage}{chg}{volt} "
            f"| {status} | kind={d.kind.value} | source={d.source}"
        )

    print()
    print(dump_hid_diagnostics())

    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        print(f"\n当前诊断进程工作集内存: {mem.rss / 1024 / 1024:.1f} MB")
    except Exception:
        pass


if __name__ == "__main__":
    main()
