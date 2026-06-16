import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import threading
import webbrowser
import time
import subprocess

from server_runner import ServerRunner
from setup_wizard import SetupWizard


def _ensure_deps():
    need = []
    try:
        import pystray
    except ImportError:
        need.append("pystray")
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        need.append("Pillow")

    if not need:
        return True

    root = tk.Tk()
    root.withdraw()

    msg = (
        "The AI Counsel Launcher needs two helper libraries to show a system tray icon:\n\n"
        "  \u2022 pystray\n"
        "  \u2022 Pillow\n\n"
        "Install them automatically now?\n\n"
        "(One-time step, about 30 seconds. No terminal needed.)"
    )
    if not messagebox.askyesno("Install Required Packages", msg):
        root.destroy()
        return False

    status = tk.Toplevel(root)
    status.title("Installing...")
    status.geometry("360x80")
    status.resizable(False, False)
    status.transient(root)
    status.grab_set()
    lbl = tk.Label(status, text="Installing packages\u2026", font=("Segoe UI", 11), pady=20)
    lbl.pack()
    status.update()

    all_ok = True
    for pkg in need:
        try:
            lbl.config(text=f"Installing {pkg}\u2026")
            status.update()
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "--user"],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                all_ok = False
                break
        except Exception:
            all_ok = False
            break

    status.destroy()

    if all_ok:
        try:
            import pystray
        except ImportError:
            all_ok = False
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            all_ok = False

    if not all_ok:
        messagebox.showerror(
            "Installation Failed",
            "Could not install required libraries.\n\n"
            "Please run this command in a terminal:\n"
            f'  {sys.executable} -m pip install pystray Pillow --user\n\n'
            "Then double-click run.bat again.",
        )
        root.destroy()
        return False

    messagebox.showinfo(
        "Ready",
        "Libraries installed successfully!\n\nThe launcher will now start.",
    )
    root.destroy()
    return True


_DEPS_OK = _ensure_deps()

if _DEPS_OK:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
else:
    HAS_TRAY = False

APP_NAME = "The AI Counsel Launcher"
REPO_URL = "https://github.com/derekkage/the-ai-counsel"
FRONTEND_URL = "http://127.0.0.1:5173"


def _get_config_dir():
    return os.path.join(os.path.expanduser("~"), "Documents", "The-AI-Counsel")


def _get_config_path():
    return os.path.join(_get_config_dir(), ".launcher-config.json")


def _load_config():
    path = _get_config_path()
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_config(config):
    path = _get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


def _create_tray_image():
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([2, 2, size - 2, size - 2], fill=(37, 99, 235, 255))
    try:
        font = ImageFont.truetype("segoeui.ttf", 32)
    except (IOError, OSError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "A", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) / 2
    y = (size - th) / 2 - 1
    draw.text((x, y), "A", fill=(255, 255, 255), font=font)
    return image


class LauncherApp:
    def __init__(self):
        self.config = _load_config()
        self.server_runner = None
        self.root = None
        self.tray_icon = None
        self.servers_running = False
        self.starting_up = False

        self._backend_status = tk.StringVar(value="Not started")
        self._frontend_status = tk.StringVar(value="Not started")
        self._update_status = tk.StringVar(value="Checking...")

    def run(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("480+350")
        self.root.resizable(False, False)

        if sys.platform == "win32":
            try:
                self.root.iconbitmap(default="")
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if not self.config or not self.config.get("first_run_complete"):
            self._run_setup_wizard()
            self.config = _load_config()
            if not self.config or not self.config.get("first_run_complete"):
                return

        self._build_main_ui()
        self._check_updates()
        self.root.mainloop()

    def _run_setup_wizard(self):
        wizard = SetupWizard(self.root, _get_config_path())
        self.root.wait_window(wizard.window)
        if wizard.result != "launch":
            self.root.destroy()
            return

    def _build_main_ui(self):
        header_text = f"\U00002699 The AI Counsel"
        tk.Label(
            self.root,
            text=header_text,
            font=("Segoe UI", 18, "bold"),
            pady=(16, 4),
        ).pack(fill=tk.X)
        tk.Label(
            self.root,
            text="Your local AI council is ready to launch.",
            font=("Segoe UI", 10),
            fg="#555555",
        ).pack()

        main = tk.Frame(self.root, padx=32, pady=12)
        main.pack(fill=tk.BOTH, expand=True)

        status_frame = tk.LabelFrame(main, text="Server Status", font=("Segoe UI", 10, "bold"), padx=12, pady=8)
        status_frame.pack(fill=tk.X, pady=(0, 12))

        row_b = tk.Frame(status_frame)
        row_b.pack(fill=tk.X, pady=2)
        self._backend_dot = tk.Label(row_b, text="\u25CF", font=("Segoe UI", 10), fg="#999999")
        self._backend_dot.pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(row_b, text="Backend:", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        tk.Label(row_b, textvariable=self._backend_status, font=("Segoe UI", 10), fg="#555555").pack(side=tk.LEFT, padx=(6, 0))

        row_f = tk.Frame(status_frame)
        row_f.pack(fill=tk.X, pady=2)
        self._frontend_dot = tk.Label(row_f, text="\u25CF", font=("Segoe UI", 10), fg="#999999")
        self._frontend_dot.pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(row_f, text="Frontend:", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        tk.Label(row_f, textvariable=self._frontend_status, font=("Segoe UI", 10), fg="#555555").pack(side=tk.LEFT, padx=(6, 0))

        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(4, 12))

        self._start_btn = tk.Button(
            btn_frame,
            text="\u25B6 Start Servers",
            font=("Segoe UI", 11, "bold"),
            bg="#2563eb",
            fg="white",
            padx=16,
            pady=6,
            cursor="hand2",
            relief=tk.FLAT,
            command=self._start_servers,
        )
        self._start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._open_btn = tk.Button(
            btn_frame,
            text="\U0001F310 Open in Browser",
            font=("Segoe UI", 10),
            state=tk.DISABLED,
            command=self._open_browser,
        )
        self._open_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._stop_btn = tk.Button(
            btn_frame,
            text="\u23F9 Stop Servers",
            font=("Segoe UI", 10),
            state=tk.DISABLED,
            command=self._stop_servers,
        )
        self._stop_btn.pack(side=tk.LEFT)

        update_frame = tk.LabelFrame(main, text="Updates", font=("Segoe UI", 10, "bold"), padx=12, pady=6)
        update_frame.pack(fill=tk.X)

        row_u = tk.Frame(update_frame)
        row_u.pack(fill=tk.X)

        self._update_dot = tk.Label(row_u, text="\u25CF", font=("Segoe UI", 10), fg="#999999")
        self._update_dot.pack(side=tk.LEFT, padx=(0, 6))
        self._update_label = tk.Label(row_u, textvariable=self._update_status, font=("Segoe UI", 10), fg="#555555")
        self._update_label.pack(side=tk.LEFT)

        self._update_btn = tk.Button(
            row_u,
            text="Update",
            font=("Segoe UI", 9),
            state=tk.DISABLED,
            command=self._do_update,
        )
        self._update_btn.pack(side=tk.RIGHT)

        repo_path = self._get_repo_path()
        if repo_path:
            tk.Label(
                main,
                text=f"Installed at: {repo_path}",
                font=("Segoe UI", 8),
                fg="#999999",
                anchor=tk.W,
            ).pack(fill=tk.X, pady=(4, 0))

        if self.config and self.config.get("auto_start"):
            self.root.after(500, self._start_servers)

    def _get_repo_path(self):
        if self.config and "repo_path" in self.config:
            return self.config["repo_path"]
        return None

    def _set_dot(self, dot_label, fg_color):
        dot_label.config(fg=fg_color)

    def _update_status_ui(self, service, status):
        def update():
            if service == "backend":
                if status == "starting":
                    self._backend_status.set("Starting...")
                    self._set_dot(self._backend_dot, "#f59e0b")
                elif status == "ready":
                    self._backend_status.set(f"Running (port {self.server_runner.backend_port})")
                    self._set_dot(self._backend_dot, "#16a34a")
            elif service == "frontend":
                if status == "starting":
                    self._frontend_status.set("Starting...")
                    self._set_dot(self._frontend_dot, "#f59e0b")
                elif status == "ready":
                    self._frontend_status.set(f"Running (port {self.server_runner.frontend_port})")
                    self._set_dot(self._frontend_dot, "#16a34a")
            elif service == "all":
                self._on_servers_ready()
            elif service == "error":
                self._on_server_error(status)
        self.root.after(0, update)

    def _on_servers_ready(self):
        self.servers_running = True
        self.starting_up = False
        self._start_btn.config(state=tk.DISABLED)
        self._stop_btn.config(state=tk.NORMAL)
        self._open_btn.config(state=tk.NORMAL)
        self._open_browser()
        if HAS_TRAY:
            self.root.after(1500, self._minimize_to_tray)

    def _on_server_error(self, message):
        self.starting_up = False
        self._start_btn.config(state=tk.NORMAL)
        self._stop_servers()
        tk.messagebox.showerror(
            "Server Error",
            message + "\n\nTry restarting the servers.",
            parent=self.root,
        )

    def _start_servers(self):
        if self.starting_up or self.servers_running:
            return
        self.starting_up = True
        self._start_btn.config(state=tk.DISABLED)
        self._backend_status.set("Starting...")
        self._set_dot(self._backend_dot, "#f59e0b")
        self._frontend_status.set("Waiting...")
        self._set_dot(self._frontend_dot, "#999999")

        repo_path = self._get_repo_path()
        if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
            tk.messagebox.showerror(
                "Not Installed",
                "The app is not installed. Please run the setup wizard first.",
                parent=self.root,
            )
            self.starting_up = False
            self._start_btn.config(state=tk.NORMAL)
            return

        self.server_runner = ServerRunner(repo_path)

        def run():
            try:
                backend_port = self.server_runner.start_backend()
                time.sleep(1)
                self.server_runner.start_frontend()
                self.server_runner.poll_health(self._update_status_ui)
            except Exception as e:
                self._update_status_ui("error", f"Failed to start servers: {e}")

        threading.Thread(target=run, daemon=True).start()

    def _stop_servers(self):
        if self.server_runner:
            self.server_runner.stop_all()
        self.servers_running = False
        self.starting_up = False
        self._start_btn.config(state=tk.NORMAL)
        self._stop_btn.config(state=tk.DISABLED)
        self._open_btn.config(state=tk.DISABLED)
        self._backend_status.set("Not started")
        self._set_dot(self._backend_dot, "#999999")
        self._frontend_status.set("Not started")
        self._set_dot(self._frontend_dot, "#999999")
        self._restore_from_tray()

    def _open_browser(self):
        webbrowser.open(FRONTEND_URL)

    def _minimize_to_tray(self):
        if not HAS_TRAY:
            return
        self.root.withdraw()
        if self.tray_icon is None:
            self._show_tray_icon()

    def _restore_from_tray(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        try:
            self.root.deiconify()
            self.root.lift()
        except Exception:
            pass

    def _show_tray_icon(self):
        if not HAS_TRAY:
            return

        menu = pystray.Menu(
            pystray.MenuItem(
                "Open The AI Counsel",
                lambda: (self._restore_from_tray(), self._open_browser()),
                default=True,
            ),
            pystray.MenuItem(
                f"Backend: Running" if self.servers_running else "Backend: Stopped",
                None,
                enabled=False,
            ),
            pystray.MenuItem(
                f"Frontend: Running" if self.servers_running else "Frontend: Stopped",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Show Window",
                lambda: self._restore_from_tray(),
            ),
            pystray.MenuItem(
                "Restart",
                lambda: (
                    self._restore_from_tray(),
                    self._stop_servers(),
                    self.root.after(500, self._start_servers),
                ),
                enabled=self.servers_running,
            ),
            pystray.MenuItem(
                "Stop Servers",
                lambda: (self._restore_from_tray(), self._stop_servers()),
                enabled=self.servers_running,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._exit_app),
        )

        self.tray_icon = pystray.Icon(
            "the-ai-counsel",
            _create_tray_image(),
            APP_NAME,
            menu,
        )

        def run_tray():
            self.tray_icon.run()
            self.tray_icon = None

        threading.Thread(target=run_tray, daemon=True).start()

    def _exit_app(self):
        self._stop_servers()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        try:
            self.root.after(100, self.root.quit)
            self.root.after(200, self.root.destroy)
        except Exception:
            os._exit(0)

    def _on_close(self):
        if self.servers_running and HAS_TRAY:
            self._minimize_to_tray()
        else:
            self._stop_servers()
            self.root.destroy()

    def _check_updates(self):
        repo_path = self._get_repo_path()
        if not repo_path:
            self._update_status.set("Not installed yet")
            return

        def check():
            try:
                startupinfo = None
                if sys.platform == "win32":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=15,
                    startupinfo=startupinfo,
                )

                result = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD..origin/main"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    startupinfo=startupinfo,
                )
                behind = int(result.stdout.strip() or 0)

                if behind > 0:
                    self._update_label.config(fg="#dc2626")
                    self._set_dot(self._update_dot, "#dc2626")
                    self._update_status.set(f"{behind} update(s) available")
                    self._update_btn.config(state=tk.NORMAL)
                else:
                    self._set_dot(self._update_dot, "#16a34a")
                    self._update_status.set("Up to date")
            except Exception:
                self._update_status.set("Could not check")

        threading.Thread(target=check, daemon=True).start()

    def _do_update(self):
        repo_path = self._get_repo_path()
        if not repo_path:
            return

        def pull():
            try:
                startupinfo = None
                if sys.platform == "win32":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                self._update_status.set("Updating...")
                self._update_btn.config(state=tk.DISABLED)

                result = subprocess.run(
                    ["git", "pull", "origin", "main"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    startupinfo=startupinfo,
                )
                if result.returncode == 0:
                    self._set_dot(self._update_dot, "#16a34a")
                    self._update_status.set("Updated! Restart servers to apply.")
                else:
                    self._update_status.set("Update failed. Try manually.")
                    self._update_btn.config(state=tk.NORMAL)
            except Exception:
                self._update_status.set("Update failed. Check your connection.")

        threading.Thread(target=pull, daemon=True).start()


if __name__ == "__main__":
    try:
        app = LauncherApp()
        app.run()
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        tk.messagebox.showerror(
            "Launcher Error",
            f"Something went wrong starting the launcher:\n\n{e}\n\n"
            f"Make sure you have installed the dependencies:\n"
            f"  pip install pystray Pillow\n\n"
            f"Error details have been written to launcher-crash.log",
        )
        try:
            with open(os.path.join(os.path.dirname(__file__), "launcher-crash.log"), "w") as f:
                f.write(error_msg)
        except Exception:
            pass
        sys.exit(1)
