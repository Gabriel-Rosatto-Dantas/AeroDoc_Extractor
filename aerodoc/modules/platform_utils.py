"""Recursos que variam entre Windows, macOS e Linux."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


PLATFORMS = (
    ("windows", "Windows"),
    ("macos", "macOS"),
    ("linux", "Linux"),
)


def host_platform() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def target_platform() -> str:
    """Retorna a plataforma escolhida na interface ou a do computador."""
    value = os.environ.get("AERODOC_PLATFORM", "").strip().lower()
    aliases = {
        "win": "windows",
        "win32": "windows",
        "windows": "windows",
        "mac": "macos",
        "macos": "macos",
        "darwin": "macos",
        "osx": "macos",
        "linux": "linux",
    }
    return aliases.get(value, host_platform())


def select_all_key(keys):
    """Retorna Command+A no macOS e Ctrl+A nas demais plataformas."""
    return keys.COMMAND if target_platform() == "macos" else keys.CONTROL


def chrome_candidates() -> list[Path]:
    platform = target_platform()
    if platform == "windows":
        return [
            Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files"))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google/Chrome/Application/chrome.exe",
        ]
    if platform == "macos":
        return [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    return [
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/google-chrome-stable"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
    ]


def find_chrome() -> str | None:
    for candidate in chrome_candidates():
        if candidate.exists():
            return str(candidate)

    commands = {
        "windows": ("chrome.exe", "chrome"),
        "macos": ("google-chrome", "chromium", "chrome"),
        "linux": ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"),
    }
    for command in commands[target_platform()]:
        executable = shutil.which(command)
        if executable:
            return executable
    return None
