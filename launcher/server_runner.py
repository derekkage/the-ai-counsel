import subprocess
import urllib.request
import json
import time
import socket
import os
import sys


class ServerRunner:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.backend_process = None
        self.frontend_process = None
        self.backend_port = 8001
        self.frontend_port = 5173
        self._stopped = False

    def check_port(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            return result != 0
        finally:
            sock.close()

    def find_free_port(self, start_port):
        port = start_port
        while not self.check_port(port):
            port += 1
            if port > start_port + 100:
                raise RuntimeError(
                    f"Could not find a free port near {start_port}. "
                    f"Too many ports are in use."
                )
        return port

    def start_backend(self):
        if self.check_port(self.backend_port):
            port = self.backend_port
        else:
            port = self.find_free_port(self.backend_port + 1)
            self.backend_port = port

        env = os.environ.copy()
        env["HOST"] = "127.0.0.1"
        env["LLM_COUNCIL_BIND_HOST"] = "127.0.0.1"

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self.backend_process = subprocess.Popen(
            ["uv", "run", "python", "-m", "backend.main"],
            cwd=self.repo_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
        return self.backend_port

    def start_frontend(self):
        if self.check_port(self.frontend_port):
            port = self.frontend_port
        else:
            port = self.find_free_port(self.frontend_port + 1)
            self.frontend_port = port

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self.frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=os.path.join(self.repo_path, "frontend"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
        return self.frontend_port

    def _stop_process(self, process):
        if process is None:
            return
        if process.poll() is not None:
            return
        try:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        except Exception:
            pass

    def stop_all(self):
        self._stopped = True
        self._stop_process(self.frontend_process)
        self._stop_process(self.backend_process)
        self.frontend_process = None
        self.backend_process = None

    def is_running(self, process):
        if process is None:
            return False
        return process.poll() is None

    def backend_is_running(self):
        return self.is_running(self.backend_process)

    def frontend_is_running(self):
        return self.is_running(self.frontend_process)

    def poll_health(self, status_callback):
        backend_ok = False
        frontend_ok = False
        timeout = 60
        start = time.time()
        self._stopped = False

        while not (backend_ok and frontend_ok):
            if self._stopped:
                return False

            elapsed = time.time() - start
            if elapsed > timeout:
                if not self.backend_is_running():
                    status_callback("error", "Backend process crashed. Check your configuration.")
                elif not self.frontend_is_running():
                    status_callback("error", "Frontend process crashed. Check your Node.js installation.")
                else:
                    status_callback("error", "Servers are taking too long to start. Check your network connection.")
                return False

            if not backend_ok:
                if not self.backend_is_running():
                    status_callback("error", "Backend stopped unexpectedly.")
                    return False
                try:
                    resp = urllib.request.urlopen(
                        f"http://127.0.0.1:{self.backend_port}/api/health",
                        timeout=2,
                    )
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "ok":
                        backend_ok = True
                        status_callback("backend", "ready")
                except Exception:
                    status_callback("backend", "starting")

            if not frontend_ok:
                if not self.frontend_is_running():
                    status_callback("error", "Frontend stopped unexpectedly.")
                    return False
                try:
                    resp = urllib.request.urlopen(
                        f"http://127.0.0.1:{self.frontend_port}",
                        timeout=2,
                    )
                    if resp.status == 200:
                        frontend_ok = True
                        status_callback("frontend", "ready")
                except Exception:
                    status_callback("frontend", "starting")

            time.sleep(0.5)

        status_callback("all", "ready")
        return True

    def read_latest_logs(self, max_lines=30):
        lines = []
        for proc, name in [(self.backend_process, "Backend"), (self.frontend_process, "Frontend")]:
            if proc and proc.stdout:
                try:
                    output = proc.stdout.read(max_lines)
                    for line in output.split("\n")[-max_lines:]:
                        lines.append(f"[{name}] {line}")
                except Exception:
                    pass
        return "\n".join(lines) if lines else "No log data available."
