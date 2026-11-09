from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import sys
import threading
from ctypes import wintypes

import pystray
from PIL import Image
from pystray import MenuItem

from .config import APPDATA, CONFIG_FILE, LOG_FILE, ROOT, STATUS_FILE, load_settings
from .controller import CaptureController


APP_NAME = "Voice Thought Capture"
MUTEX_NAME = "Local\\VoiceThoughtCapture-Mutex"
STOP_EVENT_NAME = "Local\\VoiceThoughtCapture-Stop"
RESTART_EVENT_NAME = "Local\\VoiceThoughtCapture-Restart"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateEventW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.OpenEventW.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.SetEvent.argtypes = (wintypes.HANDLE,)
kernel32.SetEvent.restype = wintypes.BOOL
kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
kernel32.ReleaseMutex.restype = wintypes.BOOL
kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.WaitForMultipleObjects.argtypes = (wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL, wintypes.DWORD)
kernel32.WaitForMultipleObjects.restype = wintypes.DWORD
user32.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
user32.MessageBoxW.restype = ctypes.c_int


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
        force=True,
    )
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")


def show_message(message: str, title: str = APP_NAME) -> None:
    user32.MessageBoxW(None, message, title, 0x00000040)


def signal_named_event(name: str) -> bool:
    handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, name)
    if not handle:
        return False
    try:
        return bool(kernel32.SetEvent(handle))
    finally:
        kernel32.CloseHandle(handle)


def _process_is_running(pid: int) -> bool:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def show_status() -> None:
    try:
        status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        pid = int(status.get("pid", 0))
        if not pid or not _process_is_running(pid):
            show_message("Voice Thought Capture is not running. Double-click its Desktop shortcut to start it.", "Status")
            return
        message = (
            f"Status: {status.get('state', 'unknown')}\n"
            f"Hotkey: {status.get('hotkey', 'unknown')}\n"
            f"Notes: {status.get('notes_file', 'unknown')}"
        )
        show_message(message, "Voice Thought Capture status")
    except Exception:
        show_message("Voice Thought Capture is not running, or its status file is unavailable.", "Status")


def run_app() -> int:
    configure_logging()
    log = logging.getLogger("voice_thought_capture")
    try:
        settings = load_settings()
    except Exception as exc:
        show_message(f"Settings problem: {exc}", "Startup problem")
        return 1
    APPDATA.mkdir(parents=True, exist_ok=True)

    ctypes.set_last_error(0)
    mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if not mutex:
        show_message("Windows could not create the single-instance lock. Check the log file.", "Startup problem")
        return 1
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(mutex)
        show_message("Voice Thought Capture is already running in the system tray.", "Already running")
        return 0

    stop_event = kernel32.CreateEventW(None, True, False, STOP_EVENT_NAME)
    restart_event = kernel32.CreateEventW(None, True, False, RESTART_EVENT_NAME)
    if not stop_event or not restart_event:
        log.error("Could not create application control events (Windows error %s)", ctypes.get_last_error())
        if stop_event:
            kernel32.CloseHandle(stop_event)
        if restart_event:
            kernel32.CloseHandle(restart_event)
        kernel32.ReleaseMutex(mutex)
        kernel32.CloseHandle(mutex)
        show_message("Windows could not initialize app controls. Check the log file.", "Startup problem")
        return 1

    controller = CaptureController(settings)
    restart_requested = threading.Event()

    def open_note(icon=None, item=None) -> None:
        settings.notes_file.parent.mkdir(parents=True, exist_ok=True)
        if not settings.notes_file.exists():
            settings.notes_file.write_text("# Voice Thought Capture\n\n", encoding="utf-8")
        os.startfile(str(settings.notes_file))

    def open_settings(icon=None, item=None) -> None:
        os.startfile(str(CONFIG_FILE))

    def show_tray_status(icon=None, item=None) -> None:
        controller.notify(
            f"Status: {controller.state}. Notes: {settings.notes_file}",
            "Voice Thought Capture status",
        )

    menu = pystray.Menu(
        MenuItem("Start or finish a capture", lambda icon, item: controller.toggle_capture()),
        MenuItem("Check status", show_tray_status),
        pystray.Menu.SEPARATOR,
        MenuItem("Open THOUGHTS.md", open_note),
        MenuItem("Open settings", open_settings),
        pystray.Menu.SEPARATOR,
        MenuItem("Restart", lambda icon, item: signal_named_event(RESTART_EVENT_NAME)),
        MenuItem("Stop application", lambda icon, item: signal_named_event(STOP_EVENT_NAME)),
    )

    icon_file = ROOT / "assets" / "voice_thought_capture.ico"
    try:
        image = Image.open(icon_file)
    except Exception:
        image = Image.new("RGB", (64, 64), (25, 54, 92))
    icon = pystray.Icon("VoiceThoughtCapture", image, APP_NAME, menu=menu)

    def monitor_control() -> None:
        handles = (wintypes.HANDLE * 2)(stop_event, restart_event)
        result = kernel32.WaitForMultipleObjects(2, handles, False, 0xFFFFFFFF)
        if result == 1:
            restart_requested.set()
        icon.stop()

    def setup_icon(tray_icon) -> None:
        tray_icon.visible = True
        controller.attach_icon(tray_icon)
        controller.start()
        threading.Thread(target=monitor_control, name="control-events", daemon=True).start()

    try:
        icon.run(setup=setup_icon)
    except Exception:
        log.exception("The background app could not run")
        show_message(f"Voice Thought Capture could not start. See:\n{LOG_FILE}", "Startup problem")
        controller.shutdown()
        for handle in (stop_event, restart_event):
            kernel32.CloseHandle(handle)
        kernel32.ReleaseMutex(mutex)
        kernel32.CloseHandle(mutex)
        return 1

    controller.shutdown()
    for handle in (stop_event, restart_event):
        kernel32.CloseHandle(handle)
    kernel32.ReleaseMutex(mutex)
    kernel32.CloseHandle(mutex)

    if restart_requested.is_set():
        try:
            subprocess.Popen([sys.executable], cwd=str(ROOT), close_fds=True)
        except Exception:
            log.exception("Could not restart the application")
            show_message(f"Restart failed. Launch the Desktop shortcut again.\nSee: {LOG_FILE}", "Restart problem")
            return 1
    return 0


def main() -> int:
    args = {argument.casefold() for argument in sys.argv[1:]}
    if "--status" in args:
        show_status()
        return 0
    if "--stop" in args:
        if not signal_named_event(STOP_EVENT_NAME):
            show_message("Voice Thought Capture is not running.", "Stop")
        return 0
    if "--restart" in args:
        if not signal_named_event(RESTART_EVENT_NAME):
            show_message("Voice Thought Capture is not running.", "Restart")
        return 0
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
