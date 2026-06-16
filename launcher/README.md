# The AI Counsel - Desktop Launcher

A single-click desktop launcher for [The AI Counsel](https://github.com/derekkage/the-ai-counsel) — a
FastAPI backend + React frontend app. No terminal required.

---

## Quick Start

### What you need

- **Windows** (10 or 11) — recommended
- **Python 3.10 or later** — get it from [python.org](https://www.python.org/downloads/)
  - During installation, check **"Add Python to PATH"**

### Option A: Run from source (no extra tools needed)

1. Open the `launcher` folder
2. Double-click **`run.bat`**
3. A setup wizard will guide you through the installation
4. After setup completes, click **Launch**

### Option B: Build a standalone EXE (one-time setup)

1. Open the `launcher` folder
2. Double-click **`build.bat**`
3. The EXE will be created in the `dist` folder
4. Move `The-AI-Counsel-Launcher.exe` anywhere and double-click it

---

## Features

### First-Run Setup Wizard
- Checks for Git, Python, Node.js, and uv
- Automatically installs anything that's missing
- Lets you choose the install location (default: Documents\The-AI-Counsel)
- Downloads and installs everything with a progress bar

### Launch & Server Management
- Single click starts both backend and frontend servers
- Automatically opens your browser when both servers are ready
- Shows live status (starting / running / stopped)
- Stop or restart servers with one click

### System Tray
- When servers are running, the app minimizes to the system tray
- Right-click the tray icon to:
  - Open the app in your browser
  - See server status at a glance
  - Stop or restart the servers
  - Exit the launcher

### Auto-Update
- Checks for updates to The AI Counsel when you launch
- Shows how many updates are available
- One-click update from the main window

---

## File Guide

| File | What it does |
|------|-------------|
| `run.bat` | Double-click this to launch. Opens `launcher.py` without showing a terminal window. |
| `launcher.py` | The main program. Manages the window, system tray, and overall flow. |
| `setup_wizard.py` | The first-run setup wizard. Checks dependencies, installs missing tools, clones the repo, and runs setup commands. |
| `server_runner.py` | Handles starting, stopping, and checking the health of the backend and frontend servers. |
| `requirements.txt` | Lists the Python libraries the launcher needs (pystray + Pillow). |
| `build.bat` | Double-click this to package the launcher into a standalone `.exe` file. |

---

## Troubleshooting

### "pip is not recognized"
Python is either not installed or not added to your PATH. Install or reinstall Python and check
**"Add Python to PATH"**.

### "No module named pystray"
Run this command in the launcher folder:
```
pip install -r requirements.txt
```

### Port 8001 or 5173 is already in use
- Close any other programs using these ports
- Or change the ports in the config file at Documents\The-AI-Counsel\.launcher-config.json

### The browser doesn't open
- Wait a moment and click **"Open in Browser"** manually
- Check that the servers are showing "Running" in the status window

### Setup wizard gets stuck on "Installing Python packages"
- This step downloads many dependencies and can take several minutes
- If it takes more than 5 minutes, check your internet connection
- Cancel and try again

---

## For Mac or Linux

The launcher is designed for Windows but should work on Mac and Linux with minor changes:

1. Install Python packages: `pip3 install -r requirements.txt`
2. Run: `python3 launcher.py`

The `run.bat` file is Windows-only. On Mac/Linux, create a similar script:
```bash
#!/bin/bash
cd "$(dirname "$0")"
python3 launcher.py 2>launcher-crash.log
```

---

## License

This launcher is provided under the same license as The AI Counsel.
