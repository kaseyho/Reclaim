"""Start the downloadable Reclaim test build using Python 3.12 or later."""

import argparse
import hashlib
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import venv
import webbrowser


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".local-build"
PROVIDER_KEYS = (
    "SOCLAAS_API_KEY", "OPENAI_API_KEY", "PAYPAL_CLIENT_ID",
    "PAYPAL_CLIENT_SECRET", "PAYPAL_WEBHOOK_ID", "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
)


def serve(args):
    # Read only this build's optional configuration, never a parent's .env.
    if args.connected:
        from dotenv import dotenv_values
        for key, value in dotenv_values(ROOT / ".env").items():
            if value is not None:
                os.environ.setdefault(key, value)
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["APP_URL"] = f"http://127.0.0.1:{args.port}"
    os.environ["CORS_ORIGINS"] = f"http://127.0.0.1:{args.port},http://localhost:{args.port}"
    if not args.connected:
        for key in PROVIDER_KEYS:
            os.environ.pop(key, None)
        os.environ["PAYMENT_MODE"] = "demo"
        os.environ["AUTH_MODE"] = "workspace"
        os.environ["AUTO_WORKER"] = "true"
        os.environ["DATABASE_URL"] = "sqlite:///" + (RUNTIME / "demo.db").as_posix()
    else:
        os.environ.setdefault("DATABASE_URL", "sqlite:///" + (RUNTIME / "connected.db").as_posix())
    import uvicorn
    uvicorn.run("reclaim.main:app", host="127.0.0.1", port=args.port, access_log=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000, help="Local port (default: 8000)")
    parser.add_argument("--connected", action="store_true", help="Use your own provider settings from this folder's .env/environment")
    parser.add_argument("--no-browser", action="store_true", help="Print the URL without opening a browser")
    parser.add_argument("--setup-only", action="store_true", help="Install dependencies without starting the app")
    parser.add_argument("--_serve", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("Python 3.12 or later is required. See https://www.python.org/downloads/")
    if not 1 <= args.port <= 65535:
        parser.error("The port must be between 1 and 65535.")
    if not (ROOT / "dist/index.html").is_file():
        parser.error("The compiled frontend is missing. Download the local-test-build ZIP, or run npm ci and npm run build first.")
    os.chdir(ROOT)
    RUNTIME.mkdir(exist_ok=True)
    if args._serve:
        serve(args)
        return 0

    if not args.setup_only:
        with socket.socket() as probe:
            if os.name != "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", args.port))
            except OSError:
                parser.error(f"Port {args.port} is already in use. Try --port {args.port + 1}; no existing server was stopped.")

    environment = RUNTIME / "venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        print("Creating a private Python environment in .local-build/venv...", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    requirements = ROOT / "backend/requirements.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = environment / "reclaim-requirements.sha256"
    if not marker.is_file() or marker.read_text().strip() != fingerprint:
        print("Installing the pinned backend packages from PyPI. First setup needs internet access...", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)], check=True)
        marker.write_text(fingerprint + "\n")
    if args.setup_only:
        print("Setup complete. Run this command again without --setup-only to start Reclaim.")
        return 0

    mode = "CONNECTED: your own provider settings" if args.connected else "LOCAL WALKTHROUGH: deterministic text parsing and simulated payments; no money moves"
    url = f"http://127.0.0.1:{args.port}"
    print(f"\nReclaim — {mode}\nOpening {url}\nKeep this terminal open. Press Ctrl+C to stop.\n", flush=True)
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = str(ROOT / "backend")
    child_env["PYTHONUNBUFFERED"] = "1"
    command = [str(python), str(Path(__file__).resolve()), "--_serve", "--port", str(args.port)]
    if args.connected:
        command.append("--connected")
    process = subprocess.Popen(command, env=child_env)
    def stop_requested(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, stop_requested)
    signal.signal(signal.SIGTERM, stop_requested)
    try:
        deadline = time.monotonic() + 30
        ready = False
        while process.poll() is None and time.monotonic() < deadline:
            try:
                with urlopen(url + "/api/health", timeout=1) as response:
                    ready = response.status == 200
            except (URLError, TimeoutError):
                pass
            if ready:
                break
            time.sleep(0.2)
        if not ready:
            print("Reclaim did not become ready. Review the server error above.", file=sys.stderr)
            return 1
        if not args.no_browser:
            webbrowser.open(url)
        return process.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError:
        print("Dependency installation failed. Check internet access and the pip message above, then rerun the same command.", file=sys.stderr)
        sys.exit(1)
