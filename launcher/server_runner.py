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

    def _kill_process_on_port(self, port):
        if sys.platform != "win32":
            return
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit():
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True, timeout=5,
                            )
        except Exception:
            pass

    def start_backend(self):
        self._kill_process_on_port(self.backend_port)

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

        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        self.frontend_process = subprocess.Popen(
            [npm_cmd, "run", "dev"],
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

    def _read_stderr(self, process):
        if process is None or process.stdout is None:
            return ""
        try:
            remaining = process.stdout.read()
            if remaining:
                lines = remaining.split("\n")
                error_lines = [l for l in lines if "error" in l.lower() or "traceback" in l.lower() or "errno" in l.lower()]
                if error_lines:
                    detail = "\n".join(error_lines[-5:])
                else:
                    detail = "\n".join(lines[-5:])
                return self._translate_errors(detail)
        except Exception:
            pass
        return ""

    def _translate_errors(self, text):
        lower = text.lower()
        if "errno 10048" in lower or "address already in use" in lower or "only one usage" in lower:
            return (
                "Port 8001 is already in use.\n\n"
                "This usually means The AI Counsel is already running.\n"
                "Close any other launcher windows and try again.\n"
                "If the problem persists, restart your computer."
            )
        if "errno 10061" in lower or "connection refused" in lower:
            return "The backend could not start. Check your firewall settings."
        if "traceback" in lower and "importerror" in lower:
            return "A Python package is missing. Run the setup wizard again."
        if "no module" in lower:
            return f"A Python module is missing.\n{text}"
        return text

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
                    detail = self._read_stderr(self.backend_process)
                    msg = f"Backend process crashed.\n{detail}" if detail else "Backend process crashed. Check your configuration."
                    status_callback("error", msg)
                elif not self.frontend_is_running():
                    status_callback("error", "Frontend process crashed. Check your Node.js installation.")
                else:
                    status_callback("error", "Servers are taking too long to start. Check your network connection.")
                return False

            if not backend_ok:
                if not self.backend_is_running():
                    detail = self._read_stderr(self.backend_process)
                    msg = f"Backend stopped unexpectedly.\n{detail}" if detail else "Backend stopped unexpectedly."
                    status_callback("error", msg)
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
