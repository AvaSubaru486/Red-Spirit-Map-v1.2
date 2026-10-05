"""Windows local deployment; no administrator rights or runtime internet needed.

The native EXE invokes this standard-library-only bootstrap. Package downloads
are only needed on first setup or when the existing environment is incomplete.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import logging
import msvcrt
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


DEPLOY = Path(__file__).resolve().parent
ROOT = DEPLOY.parent
LOGS = DEPLOY / "logs"
CACHE = DEPLOY / "cache"
BUNDLED_PYTHON = ROOT / "runtime" / "python.exe"
PYTHON = BUNDLED_PYTHON if BUNDLED_PYTHON.is_file() else ROOT / ".venv" / "Scripts" / "python.exe"
PROJECT_ID = hashlib.sha256(str(ROOT.resolve()).casefold().encode("utf-8")).hexdigest()
OPENER = build_opener(ProxyHandler({}))  # Local requests must never use a proxy.
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def prepare_environment() -> dict[str, str]:
    for path in (LOGS, CACHE / "tmp", CACHE / "pip", CACHE / "browser"):
        path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(TEMP=str(CACHE / "tmp"), TMP=str(CACHE / "tmp"),
               PIP_CACHE_DIR=str(CACHE / "pip"), PYTHONUTF8="1",
               PYTHONIOENCODING="utf-8", PIP_DISABLE_PIP_VERSION_CHECK="1")
    os.environ.update({key: env[key] for key in (
        "TEMP", "TMP", "PIP_CACHE_DIR", "PYTHONUTF8", "PYTHONIOENCODING")})
    return env


def say(message: str) -> None:
    logging.info(message)
    print(message, flush=True)


@contextlib.contextmanager
def deployment_lock():
    """Serialize launches, including installation, without relying on stale PIDs."""
    with (DEPLOY / ".launcher.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + 180
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("另一个启动程序仍在准备环境，请稍后重试。")
                time.sleep(0.2)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def run_checked(arguments: list[str], env: dict[str, str], timeout: int = 600) -> None:
    with (LOGS / "setup.log").open("a", encoding="utf-8") as output:
        result = subprocess.run(arguments, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=output, stderr=subprocess.STDOUT,
                                creationflags=CREATE_NO_WINDOW, timeout=timeout)
    if result.returncode:
        raise RuntimeError("运行环境准备失败。请查看 自动部署\\logs\\setup.log；首次安装依赖需要联网。")


def ensure_python(env: dict[str, str]) -> None:
    if (ROOT / "PACKAGE_INFO.json").is_file() and not BUNDLED_PYTHON.is_file():
        raise RuntimeError("便携包缺少 runtime/python.exe，请完整解压整个项目。不会使用系统 Python 或联网安装依赖。")
    if not PYTHON.is_file():
        say("正在项目目录创建 Python 虚拟环境…")
        base_python = getattr(sys, "_base_executable", sys.executable)
        run_checked([base_python, "-m", "venv", str(ROOT / ".venv")], env)
    check = [str(PYTHON), "-X", "utf8", "-c", "import fastapi, uvicorn; from app.main import app"]
    with (LOGS / "setup.log").open("a", encoding="utf-8") as output:
        try:
            result = subprocess.run(check, cwd=ROOT, env=env, stdout=output,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    creationflags=CREATE_NO_WINDOW, timeout=45)
        except OSError as exc:
            raise RuntimeError("项目虚拟环境不能运行，请检查 .venv 和已安装的 Python。") from exc
    if result.returncode:
        if PYTHON == BUNDLED_PYTHON:
            raise RuntimeError("便携包内的本地运行依赖不完整。请重新完整解压项目压缩包，不需要也不会联网下载运行依赖。")
        say("正在安装缺失的项目依赖，下载和缓存仅写入 D 盘项目目录…")
        run_checked([str(PYTHON), "-m", "pip", "install", "--no-input", "--retries", "2",
                     "--timeout", "20", "-r", str(ROOT / "requirements.txt")], env)
        run_checked(check, env, timeout=45)


def request(url: str, timeout: float = 2):
    return OPENER.open(url, timeout=timeout)


def is_our_server(port: int) -> bool:
    try:
        with request(f"http://127.0.0.1:{port}/api/health", timeout=0.8) as response:
            return (response.status == 200
                    and response.headers.get("X-Red-Map-Project") == PROJECT_ID
                    and json.load(response).get("status") == "ok")
    except (OSError, URLError, ValueError):
        return False


def port_available(port: int) -> bool:
    with socket.socket() as sock:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def verify_site(port: int) -> None:
    """Do not open a blank page just because a TCP port happens to be listening."""
    base = f"http://127.0.0.1:{port}"
    with request(base + "/", timeout=8) as response:
        if b'id="map"' not in response.read():
            raise RuntimeError("网站返回的不是本项目地图页面。")
    for endpoint, key in (("/api/events", "items"), ("/api/persons", "items"),
                          ("/api/geo/province", "features"), ("/api/history/1935", "territories"),
                          ("/api/regions?parent=100000", "items"), ("/api/geo-status", "structural_valid"),
                          ("/api/persons/mao_zedong/timeline", "nodes")):
        with request(base + endpoint, timeout=12) as response:
            if not json.load(response).get(key):
                raise RuntimeError("本地数据接口为空或损坏：" + endpoint)


def choose_and_start(port: int, env: dict[str, str]) -> dict:
    candidates = list(range(port, min(port + 21, 65536)))
    # Prefer reusing a verified copy even when it previously selected another port.
    for candidate in candidates:
        if not port_available(candidate) and is_our_server(candidate):
            say(f"网站已在运行，直接打开（端口 {candidate}）。")
            verify_site(candidate)
            return {"port": candidate, "reused": True}
    for candidate in candidates:
        if not port_available(candidate):
            say(f"端口 {candidate} 已被占用，正在选择其他本地端口…")
            continue
        logfile = LOGS / f"server-{candidate}.log"
        say(f"正在启动本地网站，端口 {candidate}…")
        with logfile.open("a", encoding="utf-8") as output:
            child = subprocess.Popen(
                [str(PYTHON), "-X", "utf8", "-u", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                 "--port", str(candidate), "--loop", "asyncio", "--http", "h11", "--no-use-colors"],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT, close_fds=True,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if is_our_server(candidate):
                try:
                    verify_site(candidate)
                except Exception:
                    if child.poll() is None:
                        child.terminate()  # Only the process this launch created.
                    raise
                return {"port": candidate, "pid": child.pid, "reused": False}
            if child.poll() is not None:
                if not port_available(candidate):
                    break  # Another process took the port between check and bind.
                raise RuntimeError(f"网站进程提前退出，请查看 {logfile}")
            time.sleep(0.2)
        else:
            if child.poll() is None:
                child.terminate()
            raise RuntimeError(f"网站启动超时，请查看 {logfile}")
    raise RuntimeError("可用的本地端口都被占用，请关闭占用程序后重试。")


def open_browser(url: str, env: dict[str, str], debug_port: int | None = None) -> dict:
    browsers = []
    for folder in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                   os.environ.get("LOCALAPPDATA")):
        if folder:
            browsers.extend(Path(folder) / suffix for suffix in (
                "Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"))
    executable = next((path for path in browsers if path.is_file()), None)
    if executable is None:
        raise RuntimeError(f"网站已启动：{url}；未找到 Edge/Chrome，请用浏览器手动打开该地址。")
    # An independent D: profile keeps this project's browser caches off C: and
    # does not change or close any of the user's existing browser sessions.
    profile = CACHE / (f"browser-test-{debug_port}" if debug_port else "browser")
    arguments = [str(executable), f"--user-data-dir={profile}",
                 f"--disk-cache-dir={profile / 'disk-cache'}", "--no-first-run",
                 "--no-default-browser-check", "--disable-background-mode", f"--app={url}"]
    if debug_port:
        arguments.extend([f"--remote-debugging-port={debug_port}", "--remote-debugging-address=127.0.0.1"])
    browser = subprocess.Popen(arguments, env=env, cwd=ROOT, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=CREATE_NEW_PROCESS_GROUP)
    time.sleep(0.4)
    if browser.poll() not in (None, 0):
        raise RuntimeError(f"浏览器未正常启动。网站已就绪：{url}")
    return {"browser_pid": browser.pid, "browser_profile": str(profile), "browser_open_requested": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-dialog", action="store_true", help="Used by automated EXE tests")
    parser.add_argument("--browser-debug-port", type=int, help="Loopback browser automation for tests only")
    args = parser.parse_args()
    env = prepare_environment()
    logging.basicConfig(filename=LOGS / "launcher.log", encoding="utf-8", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        if not 1024 <= args.port <= 65515:
            raise ValueError("端口必须在 1024～65515 之间。")
        if args.browser_debug_port is not None and not 1024 <= args.browser_debug_port <= 65535:
            raise ValueError("浏览器测试端口无效。")
        for relative in ("app/main.py", "app/history.py", "app/admin.py", "app/ai.py", "static/index.html", "static/history-explorer.js", "static/admin-directory.js", "static/ai-panel.js", "static/vendor/leaflet.js", "requirements.txt",
                         "data/events.json", "data/persons.json", "data/routes.json", "data/geo/province.json",
                         "data/geo/city.json", "data/geo/district.json", "data/geo/south_china_sea.json",
                         "data/geo/admin_catalog.json", "data/geo/admin_reference.json", "data/geo/admin_manifest.json", "data/geo/coverage_audit.json",
                         "data/history/annual.json", "data/history/battles.json", "data/history/journeys.json",
                         "data/history/sources.json", "data/history/catalog.json", "data/ai-models.json"):
            if not (ROOT / relative).is_file():
                raise RuntimeError("项目文件缺失：" + relative + "。请把启动程序留在项目的自动部署文件夹。")
        with deployment_lock():
            say("正在检查本地运行环境和项目资源…")
            ensure_python(env)
            result = choose_and_start(args.port, env)
            result.update(status="ready", url=f"http://127.0.0.1:{result['port']}/", project_root=str(ROOT),
                          project_id=PROJECT_ID, browser_open_requested=False)
            if not args.no_browser:
                say("网站已就绪，正在自动打开项目…")
                result.update(open_browser(result["url"], env, args.browser_debug_port))
            (LOGS / "last-launch.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            say("启动成功：" + result["url"])
        return 0
    except Exception as exc:
        logging.exception("Deployment failed")
        print("启动失败：" + str(exc), flush=True)
        (LOGS / "last-error.txt").write_text(str(exc), encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
