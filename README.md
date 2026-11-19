# 桌面托盘外设电量显示 (Peripheral Battery Tray)

专为 Windows 打造的**零显卡占用、极低内存占用**系统托盘外设电量监控工具。采用纯 Python + Windows 原生 Win32 / GDI+ API 实现，无 Electron / WebView2 / Qt 等重型图形框架，零第三方依赖，即开即用。

## 核心特点

- **极低资源占用**
  - **0% 显卡占用 / 0 MB 显存**：纯 CPU GDI+ 离屏双缓冲绘制，进程不加载任何 D3D / Direct2D / OpenGL / WebView 显卡驱动 DLL。
  - **超低内存**：空闲时自动整理工作集（Working Set），常规私有内存约 15~18 MB，空闲工作集可低至数 MB。
  - **0% 空闲 CPU**：后台轮询采用事件等待休眠，无忙等待；支持硬件热插拔监听（`WM_DEVICECHANGE`），插入接收器或连接蓝牙后自动刷新。
- **精致托盘与浮窗体验**
  - 托盘图标直接绘制**主外设电量数字 + 彩色进度条**，自动适配 Windows 浅色 / 深色任务栏与高分屏 DPI。
  - **左键点击托盘**：弹出 Windows 11 风格卡片浮窗，展示全部外设电量、连接方式、充电状态与电压（若协议支持）。
  - **点击任意设备卡片**：一键固定为托盘主显外设（再次点击恢复自动选择最低电量在线外设）。
  - **右键菜单 & 内置设置面板**：支持开机自启动、自定义刷新间隔（15秒/30秒/60秒/2分钟）、低电量桌面提醒及阈值、离线蓝牙缓存显示开关、主题切换（跟随系统/深色/浅色）。

## 支持的外设与协议

1. **Windows 蓝牙 / BLE / 经典蓝牙耳机（原生 SetupAPI PnP，~10ms 扫描）**
   - 自动读取 BLE GATT 电量服务（鼠标、键盘、手柄等）与经典蓝牙 HFP 耳机/TWS 电量，并关联 `ContainerId` 判断在线/离线状态。
2. **2.4G 无线接收器 & USB HID（原生 `hid.dll`）**
   - **WU-mouse / BY-tech 2.4G 鼠标**（`372E:10F8` / `372E:10F9`，`UP=0xFF04` Report ID `0x08` 64 字节协议）
   - **迈从 MCHOSE 2.4G 无线耳机**：`V9 PRO`（`291D:385D`，需接收器固件 `>= 0008`）、`V9 Turbo+`（`3837:600A`）、`X9`（`3837:6045`），自动检测接收器固件版本
   - **CompX / ATK / VXE / VGN / Zaopin 等国产 2.4G 鼠标**（`0x08` 17 字节协议，支持百分比、充电状态与电池电压）
   - **BY-Tech / PixArt 372E 2.4G 鼠标**（`0x03` Feature Report，支持 EWEADN S9 Pro / IPI PIX v1）
   - **Logitech 罗技 HID++ 2.0**（Unifying / Bolt / Lightspeed）
   - **Razer 雷蛇 2.4G 无线外设**
   - **标准 USB HID 电量描述符**（Usage Page `0x0006` / `0x0085`）
3. **Xbox 无线手柄**（XInput 1.4）
4. **可选本机笔记本电池**（默认关闭，可在设置中开启）

## 快速启动

- **方式一（推荐）**：双击 [`启动外设电量托盘.bat`](启动外设电量托盘.bat) 或 [`run.pyw`](run.pyw) 无黑窗后台运行。
- **方式二（命令行）**：
  ```powershell
  python main.py                  # 启动托盘程序
  python main.py --once           # 仅打印当前外设电量
  python main.py --autostart on   # 开启开机自启（off 可关闭）
  python diagnose.py              # 查看本机所有蓝牙与 2.4G HID 厂商接口及固件诊断信息
  ```

## 扩展更多 2.4G 设备

运行 `python diagnose.py` 可查看当前电脑已连接的所有 2.4G 接收器 `VID/PID`、`UsagePage` 及 `ReportID`，并在 `app/providers/hid_24g.py` 中添加对应的协议探测函数即可扩展支持。
