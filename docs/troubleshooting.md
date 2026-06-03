# ErosSoundX Troubleshooting Guide

Find answers and step-by-step solutions to common errors, conflicts, and performance concerns in ErosSoundX.

---

## 1. Playback and Latency Tuning

### Symptoms
* Audio has high latency (delay between pressing key and playing sound).
* Audio playback clicks, pops, or stutters.

### Resolution
* **Buffer Allocation**: ErosSoundX initializes Pygame audio with a default buffer size of `512` bytes, which delivers sub-50ms latency. If you experience stutters:
  1. If stutters continue, verify that your computer's audio drivers (ASIO, Realtek, or HDMI) match the system output sample rate of `44.1kHz` (16-bit).
  2. Avoid running audio overlays (like Sonic Studio or Nahimic) which block mixer allocations.

---

## 2. Remote Server Connection Failures

### Symptoms
* Mobile browser fails to load remote page or shows "Connection Refused".
* Scan QR code fails to pair.

### Resolution
* **Same Wi-Fi Network Check**: Ensure both your computer and your phone are connected to the same Wi-Fi router/subnet.
* **Windows Private Profile**:
  1. Open Windows Settings -> Network & Internet.
  2. Click on your active connection properties.
  3. Ensure network profile is set to **Private** (Public network profile locks down all ports).
* **Port Conflict**: The remote server defaults to port `8000`. If port 8000 is occupied, it automatically falls back to search up to `8050`. Check your app logs inside **Settings** to see the actual listening port.

---

## 3. Global Hotkeys Blocked

### Symptoms
* Hotkeys don't trigger sounds when gaming or using specific apps in full-screen.

### Resolution
* **Administrator Privileges**: Some games run with elevated Administrator privileges, blocking standard keyboard event loops.
  * Right-click `ErosSoundX.exe` and select **Run as Administrator**.
* **Shortcut Conflicts**: If another program (like Discord, OBS, or Windows Game Bar) registered the same hotkey, only one application will receive the key press. Change the hotkey in sound settings.
