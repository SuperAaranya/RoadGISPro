from __future__ import annotations

from dataclasses import dataclass
import os
import platform


@dataclass(frozen=True)
class PlatformProfile:
    key: str
    label: str
    family: str
    architectures: tuple[str, ...]
    renderer: str
    packaging: tuple[str, ...]
    notes: str


PROFILES: tuple[PlatformProfile, ...] = (
    PlatformProfile(
        key="windows-11",
        label="Windows 11",
        family="windows",
        architectures=("x64",),
        renderer="Tkinter fallback + optional Ursina/Panda3D",
        packaging=("PyInstaller", "Inno Setup"),
        notes="Current primary packaging target.",
    ),
    PlatformProfile(
        key="debian-11",
        label="Debian 11+",
        family="linux",
        architectures=("x64", "arm64"),
        renderer="Tkinter fallback + optional Ursina/OpenGL",
        packaging=("PyInstaller",),
        notes="Designed for Debian and close derivatives.",
    ),
    PlatformProfile(
        key="macos-sonoma",
        label="macOS Sonoma",
        family="macos",
        architectures=("Apple Silicon", "Intel"),
        renderer="Tkinter fallback + optional Ursina/Metal or OpenGL",
        packaging=("PyInstaller",),
        notes="Universal2 app target.",
    ),
    PlatformProfile(
        key="macos-sequoia",
        label="macOS Sequoia",
        family="macos",
        architectures=("Apple Silicon", "Intel"),
        renderer="Tkinter fallback + optional Ursina/Metal or OpenGL",
        packaging=("PyInstaller",),
        notes="Universal2 app target.",
    ),
    PlatformProfile(
        key="macos-tahoe",
        label="macOS Tahoe",
        family="macos",
        architectures=("Apple Silicon", "Intel"),
        renderer="Tkinter fallback + optional Ursina/Metal or OpenGL",
        packaging=("PyInstaller",),
        notes="Universal2 app target.",
    ),
)


def profile_choices() -> list[str]:
    return [profile.label for profile in PROFILES]


def profile_by_label(label: str) -> PlatformProfile:
    label = str(label).strip().lower()
    for profile in PROFILES:
        if profile.label.lower() == label:
            return profile
    return PROFILES[0]


def profile_by_key(key: str) -> PlatformProfile:
    key = str(key).strip().lower()
    for profile in PROFILES:
        if profile.key == key:
            return profile
    return PROFILES[0]


def detect_current_profile() -> PlatformProfile:
    system = platform.system().lower()
    release = platform.release().lower()
    if system == "darwin":
        if "24" in release:
            return profile_by_key("macos-tahoe")
        if "15" in release:
            return profile_by_key("macos-sequoia")
        return profile_by_key("macos-sonoma")
    if system == "linux":
        return profile_by_key("debian-11")
    return profile_by_key("windows-11")


def recommended_language_tokens(profile_key: str) -> list[str]:
    profile = profile_by_key(profile_key)
    base = ["rust_router", "js_metrics", "go_metrics", "rust_validator", "go_validator", "plugins"]
    if profile.family == "windows":
        return base + ["csharp_metrics", "ruby_metrics", "java_metrics"]
    return base + ["ruby_metrics", "java_metrics"]


def installer_paths(base_dir: str) -> list[tuple[str, str]]:
    base_dir = os.path.abspath(base_dir)
    return [
        ("Windows 11", os.path.join(base_dir, "installer", "windows-exe")),
        ("Debian 11+", os.path.join(base_dir, "installer", "linux-pyinstaller")),
        ("macOS Sonoma/Sequoia/Tahoe", os.path.join(base_dir, "installer", "macos-pyinstaller")),
    ]

