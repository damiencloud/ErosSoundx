# ErosSoundX User Guide

Welcome to ErosSoundX, a premium cyberpunk-themed audio soundboard application designed for streamers, gamers, and content creators.

---

## 1. Quick Start

1. **Launch**: Open ErosSoundX. The neon boot splash screen will display while local caches load.
2. **Add a Soundboard**:
   * Click **+ Add Board** in the top navigation panel.
   * Provide a name and optional category (e.g. "Meme Sounds", "Stream Intros").
3. **Add Sounds**:
   * Select your new tab.
   * Click the **+ Add Sound** card inside the grid.
   * Choose an audio file (`.mp3` or `.wav`), set its display name, default volume, and click Add.

---

## 2. Key Features

### Global Hotkeys
* Double-click any sound card to open its editor dialog.
* Click the hotkey entry and press your desired shortcut keys (e.g., `Ctrl+Alt+F`).
* Save the settings. These keys work globally, even when the application is minimized or running behind other games/software.
* **Panic Stop**: Press `Escape` (default) to stop all audio outputs immediately.

### Mobile Remote Control (QR Pairing)
* Go to the **Settings** view tab.
* In the **Mobile Remote Control** card, click **Start Remote Server**.
* If **Streamer Mode** is active, click **Reveal QR Code** to show the network pairing QR code on screen.
* Scan the QR code using your mobile phone (iPhone/Android) connected to the **same Wi-Fi network**.
* It will open a Web interface in your browser, displaying large touch-friendly buttons to play, stop, and manage active tracks remotely.

### Sound Macros
* Navigate to the **Sound Macros** view in the sidebar.
* Click **+ New Macro** and enter a name.
* In the macro editor panel, click:
  * **+ Play Sound Step** to select an audio file to trigger.
  * **+ Delay Step** to insert a pause duration (in seconds).
* Reorder commands using the `▲` (Up) and `▼` (Down) buttons.
* Click **▶ Play Macro** to execute the sequence.

### Sound Pack Import / Export
* Share your entire soundboards with friends or back up your collections:
  * **Export**: Go to the active soundboard tab and click **Export Pack**. Save the `.sbx` archive.
  * **Import**: Click **📥 Import Board** in the top tab bar. Select any `.sbx` package. It will automatically resolve UUID conflicts and restore all sounds, volume parameters, and macros.
