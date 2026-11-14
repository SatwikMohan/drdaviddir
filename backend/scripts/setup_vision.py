"""One-command Windows setup for the local Ollama vision service and model."""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from services.vision import ollama_analyse


def ollama_binary():
    """Find Ollama even when its Windows installer did not update this shell's PATH."""
    found = shutil.which("ollama")
    if found:
        return Path(found)
    if sys.platform == "win32":
        candidates = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe",
                      Path(os.environ.get("ProgramFiles", "")) / "Ollama/ollama.exe"]
        return next((path for path in candidates if path.is_file()), None)
    return None


def api(path, payload=None, timeout=10):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(config.VISION_OLLAMA_URL.rstrip("/") + path, body,
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def service_models():
    try:
        return api("/api/tags", timeout=3)["models"]
    except (OSError, urllib.error.URLError, ValueError, KeyError):
        return None


def install_windows_ollama():
    """Use the installer command published at https://ollama.com/download/windows."""
    if sys.platform != "win32":
        raise RuntimeError("Automatic Ollama installation is supported here on Windows only. Install Ollama for this OS, then rerun setup.")
    print("Ollama is missing. Running its official Windows installer...", flush=True)
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                    "irm https://ollama.com/install.ps1 | iex"], check=True)


def ensure_service(install=True, start=True):
    host = urllib.parse.urlparse(config.VISION_OLLAMA_URL).hostname
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Automatic setup requires a local Ollama URL")
    binary = ollama_binary()
    if binary is None:
        if not install:
            raise RuntimeError("Ollama is not installed")
        install_windows_ollama()
        binary = ollama_binary()
        if binary is None:
            raise RuntimeError("Installer finished, but ollama.exe was not found. Reopen the terminal and rerun setup.")
    models = service_models()
    if models is not None:
        print("Ollama service is running.", flush=True)
        return models
    if not start:
        raise RuntimeError("Ollama service is not running")
    print("Starting Ollama service...", flush=True)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen([str(binary), "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags)
    for _ in range(30):
        time.sleep(1)
        models = service_models()
        if models is not None:
            print("Ollama service is ready.", flush=True)
            return models
    raise RuntimeError("Ollama was started, but its API did not become ready within 30 seconds")


def pull_model():
    print(f"Downloading {config.VISION_MODEL} (about 1.9 GB for the default model)...", flush=True)
    body = json.dumps({"model": config.VISION_MODEL, "stream": True}).encode()
    request = urllib.request.Request(config.VISION_OLLAMA_URL.rstrip("/") + "/api/pull", body,
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        last_percent = -1
        for line in response:
            event = json.loads(line)
            if event.get("error"):
                raise RuntimeError(event["error"])
            total, completed = event.get("total"), event.get("completed")
            if isinstance(total, (int, float)) and total > 0 and isinstance(completed, (int, float)):
                percent = max(0, min(100, int(completed / total * 100)))
                if percent // 10 != last_percent // 10:
                    print(f"Model download: {percent}%", flush=True)
                    last_percent = percent
            elif event.get("status") in {"success", "verifying sha256 digest", "writing manifest"}:
                print(event["status"], flush=True)


def verify_image_inference():
    image = Image.new("RGB", (320, 200), "white")
    ImageDraw.Draw(image).text((35, 80), "HELLO CAMERA", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    started = time.monotonic()
    result = ollama_analyse(buffer.getvalue(), detailed=True)
    if not isinstance(result, dict) or not result.get("scene_summary"):
        raise RuntimeError("Model returned no usable image observation")
    print("Image inference seconds:", round(time.monotonic() - started, 2), flush=True)
    print("Image response:", json.dumps(result), flush=True)
    report_processor()


def report_processor():
    """Report Ollama's actual model placement after the test loads it."""
    try:
        running = api("/api/ps", timeout=5).get("models", [])
    except (OSError, ValueError) as exc:
        print(f"GPU placement could not be checked: {type(exc).__name__}", flush=True)
        return
    model = next((item for item in running if item.get("name") == config.VISION_MODEL), None)
    if not model:
        print("GPU placement could not be checked: model is no longer loaded.", flush=True)
        return
    total, vram = int(model.get("size", 0)), int(model.get("size_vram", 0))
    if total <= 0:
        print("GPU placement could not be checked: Ollama did not report model size.", flush=True)
    elif vram <= 0:
        print("Ollama processor: 100% CPU. A supported GPU was not used for this model.", flush=True)
    elif vram >= total:
        print("Ollama processor: 100% GPU.", flush=True)
    else:
        print(f"Ollama processor: about {vram / total:.0%} GPU, {1 - vram / total:.0%} CPU.", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install/start Ollama, pull the vision model, and verify image inference")
    parser.add_argument("--check", action="store_true", help="Check installation and model without changing anything")
    args = parser.parse_args(argv)
    try:
        print("Configured vision model:", config.VISION_MODEL, flush=True)
        models = ensure_service(install=not args.check, start=not args.check)
        names = {model["name"] for model in models}
        if config.VISION_MODEL not in names:
            if args.check:
                raise RuntimeError("Configured vision model is missing")
            pull_model()
            names = {model["name"] for model in service_models() or []}
            if config.VISION_MODEL not in names:
                raise RuntimeError("Download finished, but the model is not listed by Ollama")
        else:
            print("Vision model already installed.", flush=True)
        if not args.check:
            verify_image_inference()
            print("Vision setup complete.", flush=True)
        else:
            print("Vision setup check passed.", flush=True)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Vision setup failed: {exc}") from exc


if __name__ == "__main__":
    main()
