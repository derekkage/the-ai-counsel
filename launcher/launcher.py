import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import threading
import webbrowser
import time
import subprocess
import traceback

from server_runner import ServerRunner
from setup_wizard import SetupWizard

HAS_TRAY = False
_pystray = None
_PIL_Image = None
_PIL_ImageDraw = None
_PIL_ImageFont = None

APP_NAME = "The AI Counsel Launcher"
REPO_URL = "https://github.com/derekkage/the-ai-counsel"
FRONTEND_URL = "http://localhost:5173"

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_PATH = os.path.join(_SCRIPT_DIR, "launcher-crash.log")
_BOOT_PATH = os.path.join(_SCRIPT_DIR, "launcher-boot.log")


def _boot_log(msg):
    try:
        with open(_BOOT_PATH, "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


_boot_log("started")
_boot_log(f"python={sys.executable}")
_boot_log(f"cwd={os.getcwd()}")


def _crash_log(msg):
    try:
        with open(_LOG_PATH, "w") as f:
            f.write("The AI Counsel Launcher - Crash Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(msg)
    except Exception:
        pass


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


class LauncherApp:
    def __init__(self):
        self.config = _load_config()
        self.server_runner = None
        self.root = None
        self.tray_icon = None
        self.servers_running = False
        self.starting_up = False
        self.has_tray = False
        self._pystray = None
        self._PIL_Image = None
        self._PIL_ImageDraw = None
        self._PIL_ImageFont = None

        self._backend_status = None
        self._frontend_status = None
        self._update_status = None
        self._error_log_path = None

    def _ensure_deps(self):
        need = []
        try:
            import pystray
            self._pystray = pystray
            need.append(None)
        except ImportError:
            need.append("pystray")
        try:
            from PIL import Image, ImageDraw
            self._PIL_Image = Image
            self._PIL_ImageDraw = ImageDraw
            need.append(None)
        except ImportError:
            need.append("Pillow")
        need = [p for p in need if p is not None]

        if not need:
            self.has_tray = True
            try:
                from PIL import ImageFont
                self._PIL_ImageFont = ImageFont
            except ImportError:
                pass
            return True

        msg = (
            "The AI Counsel Launcher needs two helper libraries to show a system tray icon:\n\n"
            "  \u2022 pystray\n"
            "  \u2022 Pillow\n\n"
            "Install them automatically now?\n\n"
            "(One-time step, about 30 seconds. No terminal needed.)"
        )
        if not messagebox.askyesno("Install Required Packages", msg):
            return False

        status = tk.Toplevel(self.root)
        status.title("Installing...")
        status.geometry("360x80")
        status.resizable(False, False)
        status.transient(self.root)
        status.grab_set()
        lbl = tk.Label(status, text="Installing packages\u2026", font=("Segoe UI", 11), pady=20)
        lbl.pack()
        status.update()

        all_ok = True
        pip_errors = []
        for pkg in need:
            lbl.config(text=f"Installing {pkg}\u2026")
            status.update()
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg, "--user"],
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode != 0:
                    all_ok = False
                    pip_errors.append(f"[{pkg}] exit code {proc.returncode}")
                    pip_errors.append(f"  stdout: {proc.stdout[:200]}")
                    pip_errors.append(f"  stderr: {proc.stderr[:200]}")
                    break
            except subprocess.TimeoutExpired:
                all_ok = False
                pip_errors.append(f"[{pkg}] timed out after 120 seconds")
                pip_errors.append("  Your internet may be slow or blocked.")
                break
            except FileNotFoundError:
                all_ok = False
                pip_errors.append(f"[{pkg}] could not run pip (not found)")
                pip_errors.append(f"  tried: {sys.executable} -m pip install {pkg}")
                break
            except Exception as e:
                all_ok = False
                pip_errors.append(f"[{pkg}] exception: {e}")
                break

        status.destroy()

        if all_ok:
            try:
                import pystray
                self._pystray = pystray
                from PIL import Image, ImageDraw
                self._PIL_Image = Image
                self._PIL_ImageDraw = ImageDraw
                self.has_tray = True
                try:
                    from PIL import ImageFont
                    self._PIL_ImageFont = ImageFont
                except ImportError:
                    pass
                messagebox.showinfo(
                    "Ready",
                    "Libraries installed successfully!\n\nThe launcher will now start.",
                )
                return True
            except ImportError:
                all_ok = False
                pip_errors.append("pip succeeded but import still failed")

        if pip_errors:
            _crash_log("pip install failed:\n" + "\n".join(pip_errors))
            _boot_log("pip install failed, see launcher-crash.log")

        messagebox.showerror(
            "Installation Failed",
            "Could not install the required libraries.\n\n"
            "Details have been saved to:\n"
            f"{_LOG_PATH}\n\n"
            "You can also try installing manually by running this\n"
            "command in a terminal, then double-click run.bat again:\n\n"
            f'  {sys.executable} -m pip install pystray Pillow --user',
        )
        return False

    def run(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("480x350")
        self.root.resizable(False, False)

        self._backend_status = tk.StringVar(value="Not started")
        self._frontend_status = tk.StringVar(value="Not started")
        self._update_status = tk.StringVar(value="Checking...")

        if sys.platform == "win32":
            try:
                self.root.iconbitmap(default="")
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if not self._ensure_deps():
            self.root.destroy()
            return

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
        ).pack(fill=tk.X, pady=(16, 4))
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
        if self.has_tray:
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
        if not self.has_tray:
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
        if not self.has_tray or not self._pystray:
            return

        pystray = self._pystray
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

        img = self._make_tray_image()
        self.tray_icon = pystray.Icon("the-ai-counsel", img, APP_NAME, menu)

        def run_tray():
            self.tray_icon.run()
            self.tray_icon = None

        threading.Thread(target=run_tray, daemon=True).start()

    def _make_tray_image(self):
        if not self._PIL_Image or not self._PIL_ImageDraw:
            return None
        Image = self._PIL_Image
        ImageDraw = self._PIL_ImageDraw
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([2, 2, size - 2, size - 2], fill=(37, 99, 235, 255))
        font = None
        if self._PIL_ImageFont:
            try:
                font = self._PIL_ImageFont.truetype("segoeui.ttf", 32)
            except (IOError, OSError):
                font = self._PIL_ImageFont.load_default()
        if font:
            bbox = draw.textbbox((0, 0), "A", font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            x = (size - tw) / 2
            y = (size - th) / 2 - 1
            draw.text((x, y), "A", fill=(255, 255, 255), font=font)
        return image

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
        if self.servers_running and self.has_tray:
            self._minimize_to_tray()
        else:
            self._stop_servers()
            self.root.destroy()

    def _get_git_branch(self, repo_path):
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True, text=True, timeout=10,
                startupinfo=startupinfo,
            )
            return result.stdout.strip()
        except Exception:
            return "main"

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

                branch = self._get_git_branch(repo_path)
                remote_ref = f"origin/{branch}"

                subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=15,
                    startupinfo=startupinfo,
                )

                result = subprocess.run(
                    ["git", "rev-list", "--count", f"HEAD..{remote_ref}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    startupinfo=startupinfo,
                )
                behind = int(result.stdout.strip() or 0)

                if behind > 0:
                    self.root.after(0, lambda: (
                        self._update_label.config(fg="#dc2626"),
                        self._set_dot(self._update_dot, "#dc2626"),
                        self._update_status.set(f"{behind} update(s) available"),
                        self._update_btn.config(state=tk.NORMAL),
                    ))
                else:
                    self.root.after(0, lambda: (
                        self._set_dot(self._update_dot, "#16a34a"),
                        self._update_status.set("Up to date"),
                    ))
            except Exception:
                self.root.after(0, lambda: self._update_status.set("Could not check"))

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

                branch = self._get_git_branch(repo_path)

                self.root.after(0, lambda: (
                    self._update_status.set("Updating..."),
                    self._update_btn.config(state=tk.DISABLED),
                ))

                result = subprocess.run(
                    ["git", "pull", "origin", branch],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    startupinfo=startupinfo,
                )
                if result.returncode == 0:
                    self.root.after(0, lambda: (
                        self._set_dot(self._update_dot, "#16a34a"),
                        self._update_status.set("Updated! Restart servers to apply."),
                    ))
                else:
                    self.root.after(0, lambda: (
                        self._update_status.set("Update failed. Try manually."),
                        self._update_btn.config(state=tk.NORMAL),
                    ))
            except Exception:
                self.root.after(0, lambda: self._update_status.set("Update failed. Check your connection."))

        threading.Thread(target=pull, daemon=True).start()


if __name__ == "__main__":
    try:
        app = LauncherApp()
        app.run()
    except Exception:
        error_msg = traceback.format_exc()
        _boot_log(f"unhandled exception in __main__:\n{error_msg}")
        _crash_log(error_msg)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Launcher Error",
                "Something went wrong starting the launcher.\n\n"
                f"Details have been saved to:\n{_LOG_PATH}\n\n"
                "Open that file and share its contents if you need help.",
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)
