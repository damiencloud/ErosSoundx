# ErosSoundX Installation Guide

This guide covers the system requirements, installation steps, and packaging processes for the standalone Windows executable deployment.

---

## 1. System Requirements

* **Operating System**: Windows 10 or 11 (64-bit)
* **Processor**: Intel Core i3 or AMD Ryzen 3 (or newer)
* **RAM**: 4GB Minimum (8GB Recommended)
* **Storage**: 100MB of free space for installation + additional space for audio cache
* **Dependencies**: Python 3.8+ (for source installation only; standalone binary runs out-of-the-box)

---

## 2. Installation Methods

### Method A: Standalone Windows Installer (Recommended)
1. Download `ErosSoundX_Setup.exe` from the latest release distribution.
2. Double-click the installer executable.
3. Follow the wizard steps to choose installation path, create desktop shortcuts, and configure program groups.
4. Launch the application from your Desktop or Start Menu.

### Method B: Standalone Portable Binary
1. Extract the `ErosSoundX_Portable.zip` package to any local directory (e.g., `D:\ErosSoundX\`).
2. Double-click `ErosSoundX.exe` to launch. No install setup is required.

---

## 3. Network & Firewall Configuration

For the **Mobile Remote Control** and **QR Pairing** features to work, your firewall must allow incoming local network connections to the application.

1. **Windows Defender Firewall Alert**:
   * On first launch, Windows may present a Security Alert asking to allow network access.
   * Ensure **Private Networks** is checked and click **Allow Access**.
2. **Manual Firewall Exceptions**:
   * If you blocked the network prompt or want to configure it manually:
   * Open **Windows Defender Firewall with Advanced Security**.
   * Select **Inbound Rules** and click **New Rule...**
   * Choose **Port**, click Next. Select **TCP**, and specify ports `8000-8050` (or allow the `ErosSoundX.exe` program itself).
   * Choose **Allow the Connection**, select **Private** network profile, name it "ErosSoundX Remote" and save.
