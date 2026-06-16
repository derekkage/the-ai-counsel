import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import sys
import os
import json
import threading
import queue
import webbrowser
import re


DEPENDENCIES = [
    {
        "name": "Git",
        "check_cmd": ["git", "--version"],
        "version_regex": r"git version (\d+\.\d+\.\d+)",
        "min_version": (2, 0, 0),
        "install_win": "winget install --silent --accept-package-agreements Git.Git",
        "install_mac": "brew install git",
        "install_linux": "sudo apt install -y git",
        "fallback_url": "https://git-scm.com/download/win",
    },
    {
        "name": "Python 3.10+",
        "check_cmd": [sys.executable, "--version"],
        "version_regex": r"Python (\d+\.\d+\.\d+)",
        "min_version": (3, 10, 0),
        "install_win": "winget install --silent --accept-package-agreements Python.Python.3.12",
        "install_mac": "brew install python@3.12",
        "install_linux": "sudo apt install -y python3 python3-pip",
        "fallback_url": "https://www.python.org/downloads/",
    },
    {
        "name": "Node.js 18+",
        "check_cmd": ["node", "--version"],
        "version_regex": r"v(\d+\.\d+\.\d+)",
        "min_version": (18, 0, 0),
        "install_win": "winget install --silent --accept-package-agreements OpenJS.NodeJS.LTS",
        "install_mac": "brew install node",
        "install_linux": "sudo apt install -y nodejs npm",
        "fallback_url": "https://nodejs.org/",
    },
    {
        "name": "uv",
        "check_cmd": ["uv", "--version"],
        "version_regex": r"uv (\d+\.\d+\.\d+)",
        "min_version": (0, 1, 0),
        "install_win": 'powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"',
        "install_mac": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "install_linux": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "fallback_url": "https://docs.astral.sh/uv/#installation",
    },
]


def _run_cmd(cmd, timeout=15):
    try:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=startupinfo,
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False, ""


def _parse_version(text, pattern):
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        parts = tuple(int(x) for x in match.group(1).split("."))
        return parts
    except (ValueError, TypeError):
        return None


def _version_ge(version, min_version):
    if version is None:
        return False
    return version >= min_version


def _get_platform_install_cmd(dep):
    if sys.platform == "win32":
        return dep["install_win"]
    elif sys.platform == "darwin":
        return dep["install_mac"]
    else:
        return dep["install_linux"]


class SetupWizard:
    def __init__(self, parent, config_path):
        self.parent = parent
        self.config_path = config_path
        self.result = None
        self.stop_flag = False
        self.status_queue = queue.Queue()

        self.window = tk.Toplevel(parent)
        self.window.title("Setup Wizard - The AI Counsel")
        self.window.geometry("580x520")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()
        self._start_setup()

    def _build_ui(self):
        header = tk.Label(
            self.window,
            text="The AI Counsel - Setup Wizard",
            font=("Segoe UI", 16, "bold"),
            pady=12,
        )
        header.pack(fill=tk.X)

        main_frame = tk.Frame(self.window, padx=24, pady=8)
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            main_frame,
            text="We'll check your system, download the app, and install everything needed.",
            wraplength=520,
            justify=tk.LEFT,
            font=("Segoe UI", 10),
        ).pack(anchor=tk.W, pady=(0, 12))

        steps_frame = tk.Frame(main_frame)
        steps_frame.pack(fill=tk.BOTH, expand=True)

        self.step_labels = []
        step_names = [
            "System Requirements",
            "Install Location",
            "Download App",
            "Install Python Packages",
            "Install Frontend Packages",
        ]
        for i, name in enumerate(step_names):
            row = tk.Frame(steps_frame)
            row.pack(fill=tk.X, pady=2)
            icon = tk.Label(row, text="○", font=("Segoe UI", 12), width=3)
            icon.pack(side=tk.LEFT)
            text = tk.Label(
                row,
                text=name,
                font=("Segoe UI", 10),
                anchor=tk.W,
                justify=tk.LEFT,
            )
            text.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.step_labels.append((icon, text))

        self.status_label = tk.Label(
            main_frame,
            text="Checking your system...",
            font=("Segoe UI", 9),
            fg="#555555",
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=520,
        )
        self.status_label.pack(fill=tk.X, pady=(8, 4))

        self.progress = ttk.Progressbar(
            main_frame, mode="determinate", length=520
        )
        self.progress.pack(fill=tk.X, pady=(0, 8))

        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(4, 0))
        self.cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            font=("Segoe UI", 9),
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

    def _set_step_status(self, step_index, status):
        if step_index < len(self.step_labels):
            icon, text = self.step_labels[step_index]
            if status == "active":
                icon.config(text="⟳", fg="#2563eb")
                text.config(fg="#333333")
            elif status == "done":
                icon.config(text="✓", fg="#16a34a")
                text.config(fg="#666666")
            elif status == "error":
                icon.config(text="✗", fg="#dc2626")
                text.config(fg="#dc2626")

    def _set_progress(self, value, status_text):
        self.status_queue.put(("progress", value, status_text))

    def _update_from_queue(self):
        try:
            while True:
                msg = self.status_queue.get_nowait()
                if msg[0] == "progress":
                    self.progress["value"] = msg[1]
                    self.status_label.config(text=msg[2])
                elif msg[0] == "setp":
                    self._set_step_status(msg[1], msg[2])
                elif msg[0] == "done":
                    self._setup_complete()
                    return
                elif msg[0] == "error":
                    self._show_error(msg[1], msg[2] if len(msg) > 2 else None)
                    return
                elif msg[0] == "ask_manual_install":
                    self._ask_manual_install(msg[1], msg[2])
                    return
                elif msg[0] == "filedialog":
                    default = msg[1]
                    event = msg[2]
                    result_container = msg[3]
                    chosen = filedialog.askdirectory(
                        parent=self.window,
                        title="Choose Install Location",
                        initialdir=os.path.dirname(default),
                    )
                    result_container[0] = chosen
                    event.set()
        except queue.Empty:
            pass
        if not self.stop_flag:
            self.window.after(100, self._update_from_queue)

    def _cancel(self):
        self.stop_flag = True
        self.status_queue.put(("done",))
        self.window.destroy()

    def _show_error(self, message, detail=None):
        self.cancel_btn.config(state=tk.NORMAL)
        msg = message
        if detail:
            msg += f"\n\n{detail}"
        tk.messagebox.showerror("Setup Error", msg, parent=self.window)
        self.window.destroy()

    def _setup_complete(self):
        self.cancel_btn.config(text="Launch", command=self._launch)
        self._set_progress(100, "Setup complete! Click Launch to start.")
        tk.messagebox.showinfo(
            "Setup Complete",
            "The AI Counsel has been installed successfully.\n\nClick Launch to start the app!",
            parent=self.window,
        )
        self.result = "launch"
        self.window.destroy()

    def _launch(self):
        self.result = "launch"
        self.window.destroy()

    def _start_setup(self):
        self.window.after(100, self._update_from_queue)
        threading.Thread(target=self._run_setup, daemon=True).start()

    def _run_setup(self):
        try:
            ok, details = self._step_requirements()
            if not ok:
                return

            ok = self._step_location()
            if not ok:
                return

            ok = self._step_clone()
            if not ok:
                return

            ok = self._step_uv_sync()
            if not ok:
                return

            ok = self._step_npm_install()
            if not ok:
                return

            ok = self._step_save_config()
            if not ok:
                return

            self.status_queue.put(("done",))
        except Exception as e:
            self.status_queue.put(("error", f"Unexpected error: {e}"))

    def _step_requirements(self):
        self.status_queue.put(("setp", 0, "active"))
        self._set_progress(0, "Checking installed tools...")
        missing = []

        for dep in DEPENDENCIES:
            if self.stop_flag:
                return False, None
            self._set_progress(0, f"Checking {dep['name']}...")
            ok, output = _run_cmd(dep["check_cmd"])
            if ok:
                version = _parse_version(output, dep["version_regex"])
                if version and _version_ge(version, dep["min_version"]):
                    continue
            missing.append(dep)

        if missing:
            self._set_progress(0, "Installing missing tools...")
            for dep in missing:
                if self.stop_flag:
                    return False, None
                self._set_progress(
                    0, f"Installing {dep['name']} (this may take a minute)..."
                )
                cmd = _get_platform_install_cmd(dep)
                success, _ = _run_cmd(cmd, timeout=120)
                if success:
                    ok2, out2 = _run_cmd(dep["check_cmd"])
                    if ok2:
                        continue
                self.status_queue.put(
                    ("ask_manual_install", dep["name"], dep["fallback_url"])
                )
                return False, None

        self.status_queue.put(("setp", 0, "done"))
        return True, None

    def _ask_manual_install(self, dep_name, url):
        result = tk.messagebox.askyesno(
            "Install Required",
            f"Could not automatically install {dep_name}.\n\n"
            f"Would you like to open the download page?\n\n"
            f"After installing, restart the launcher and try again.",
            parent=self.window,
        )
        if result:
            webbrowser.open(url)
        self._cancel()

    def _step_location(self):
        self.status_queue.put(("setp", 1, "active"))
        self._set_progress(5, "Choosing install location...")

        default_dir = os.path.join(
            os.path.expanduser("~"), "Documents", "The-AI-Counsel"
        )

        event = threading.Event()
        result_container = [None]

        self.status_queue.put(("filedialog", default_dir, event, result_container))
        event.wait()

        path = result_container[0]
        if not path:
            return False

        self.repo_path = path
        self.status_queue.put(("setp", 1, "done"))
        return True

    def _step_clone(self):
        self.status_queue.put(("setp", 2, "active"))

        if os.path.isdir(os.path.join(self.repo_path, ".git")):
            self._set_progress(15, "Repository already exists.")
            self.status_queue.put(("setp", 2, "done"))
            return True

        self._set_progress(10, "Downloading The AI Counsel...")

        clone_done = threading.Event()
        clone_ok = [False]

        def clone():
            try:
                os.makedirs(self.repo_path, exist_ok=True)
                proc = subprocess.Popen(
                    ["git", "clone", "https://github.com/derekkage/the-ai-counsel.git", self.repo_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    encoding="utf-8",
                    errors="replace",
                )
                for line in iter(proc.stdout.readline, ""):
                    if self.stop_flag:
                        proc.terminate()
                        clone_done.set()
                        return
                    if "Receiving objects" in line:
                        self._set_progress(12, "Downloading: receiving files...")
                    elif "Resolving deltas" in line:
                        self._set_progress(14, "Downloading: resolving...")
                proc.wait()
                if proc.returncode == 0:
                    clone_ok[0] = True
                    self._set_progress(15, "App downloaded successfully!")
                    self.status_queue.put(("setp", 2, "done"))
                else:
                    self.status_queue.put(
                        ("error", "Failed to download the app. Check your internet connection and try again.")
                    )
            except Exception as e:
                self.status_queue.put(
                    ("error", f"Failed to download the app: {e}")
                )
            finally:
                clone_done.set()

        threading.Thread(target=clone, daemon=True).start()
        clone_done.wait()
        return clone_ok[0]

    def _step_uv_sync(self):
        self.status_queue.put(("setp", 3, "active"))
        self._set_progress(18, "Installing Python packages (this takes a while)...")

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.Popen(
            ["uv", "sync"],
            cwd=self.repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )

        progress_map = {
            "Resolved": 25,
            "Downloaded": 35,
            "Installed": 45,
        }
        for line in iter(proc.stdout.readline, ""):
            if self.stop_flag:
                proc.terminate()
                return False
            for kw, pct in progress_map.items():
                if kw in line:
                    self._set_progress(pct, f"Python packages: {kw.lower()}...")
                    break
            else:
                if "error" in line.lower():
                    pass

        proc.wait()
        if proc.returncode != 0:
            self.status_queue.put(
                ("error", "Failed to install Python packages. Check your internet connection.")
            )
            return False

        self._set_progress(50, "Python packages installed!")
        self.status_queue.put(("setp", 3, "done"))
        return True

    def _step_npm_install(self):
        self.status_queue.put(("setp", 4, "active"))
        self._set_progress(55, "Installing frontend packages (this takes a while)...")

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.Popen(
            ["npm", "install", "--prefix", "frontend"],
            cwd=self.repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )

        for line in iter(proc.stdout.readline, ""):
            if self.stop_flag:
                proc.terminate()
                return False
            line_lower = line.lower()
            if "added" in line_lower and "package" in line_lower:
                self._set_progress(80, f"Frontend: {line.strip()}")
            elif "audit" in line_lower:
                self._set_progress(90, "Frontend: verifying packages...")
            elif "error" in line_lower:
                pass

        proc.wait()
        if proc.returncode != 0:
            self.status_queue.put(
                ("error", "Failed to install frontend packages. Check your Node.js installation.")
            )
            return False

        self._set_progress(95, "Frontend packages installed!")
        self.status_queue.put(("setp", 4, "done"))
        return True

    def _step_save_config(self):
        config = {
            "repo_path": self.repo_path,
            "backend_port": 8001,
            "frontend_port": 5173,
            "auto_start": True,
            "first_run_complete": True,
        }
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.status_queue.put(
                ("error", f"Could not save settings: {e}")
            )
            return False
        self._set_progress(98, "Saving settings...")
        return True
