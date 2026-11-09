from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes


WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def parse_hotkey(value: str) -> tuple[int, int]:
    parts = [part.strip().casefold() for part in value.replace("-", "+").split("+") if part.strip()]
    modifiers = 0
    key = None
    names = {
        "ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
        "shift": MOD_SHIFT, "win": MOD_WIN, "windows": MOD_WIN,
    }
    for part in parts:
        if part in names:
            modifiers |= names[part]
            continue
        if key is not None:
            raise ValueError(f"Only one non-modifier key is allowed in {value!r}.")
        if len(part) == 1 and part.isalpha():
            key = ord(part.upper())
        elif len(part) == 1 and part.isdigit():
            key = ord(part)
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            key = 0x70 + int(part[1:]) - 1
        elif part == "space":
            key = 0x20
        elif part == "tab":
            key = 0x09
        else:
            raise ValueError(f"Unsupported hotkey key: {part}")
    if not modifiers or key is None:
        raise ValueError(f"Hotkey must include a modifier and one key: {value!r}")
    return modifiers | MOD_NOREPEAT, key


class GlobalHotkey:
    def __init__(self, preferred: str, fallbacks: tuple[str, ...], callback, notify) -> None:
        self.preferred = preferred
        self.fallbacks = fallbacks
        self.callback = callback
        self.notify = notify
        self.actual: str | None = None
        self.error: str | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._thread_id = 0

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="global-hotkey", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        candidates = [self.preferred, *self.fallbacks]
        tried: set[str] = set()
        for value in candidates:
            if value in tried:
                continue
            tried.add(value)
            try:
                modifiers, key = parse_hotkey(value)
            except ValueError as exc:
                logging.getLogger("voice_thought_capture").warning("Ignoring invalid hotkey %s: %s", value, exc)
                continue
            ctypes.set_last_error(0)
            if user32.RegisterHotKey(None, 1, modifiers, key):
                self.actual = value
                break
            err = ctypes.get_last_error()
            self.error = f"Windows rejected {value} (error {err})."
            logging.getLogger("voice_thought_capture").warning(
                "Could not register hotkey %s (Windows error %s)", value, err
            )
        self._ready.set()
        if self.actual:
            if self.actual.casefold() != self.preferred.casefold():
                self.notify(f"{self.preferred} was unavailable. Using {self.actual}.", "Hotkey changed")
            logging.getLogger("voice_thought_capture").info("Global hotkey registered: %s", self.actual)
        else:
            self.notify("No configured hotkey could be registered. Change it in settings.json.", "Hotkey unavailable")
            logging.getLogger("voice_thought_capture").error("All configured global hotkeys failed to register")

        try:
            if self.actual:
                while True:
                    result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if result <= 0:
                        break
                    if msg.message == WM_HOTKEY and msg.wParam == 1:
                        threading.Thread(target=self.callback, name="hotkey-action", daemon=True).start()
        finally:
            if self.actual:
                user32.UnregisterHotKey(None, 1)
