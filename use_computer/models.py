from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionResult:
    """Result from a mouse/keyboard/tap/swipe action."""

    status: str = "ok"

    @classmethod
    def from_dict(cls, d: dict) -> ActionResult:
        return cls(status=d.get("status", "ok"))


@dataclass
class CursorPosition:
    x: int
    y: int

    @classmethod
    def from_dict(cls, d: dict) -> CursorPosition:
        return cls(x=d.get("x", 0), y=d.get("y", 0))


@dataclass
class DisplayInfo:
    width: int
    height: int
    scale: float = 1.0
    platform: str = ""
    device_type: str = ""
    runtime: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> DisplayInfo:
        return cls(
            width=d.get("width", 0),
            height=d.get("height", 0),
            scale=d.get("scale", 1.0),
            platform=d.get("platform", ""),
            device_type=(
                d.get("device_type") or d.get("deviceType") or d.get("deviceTypeIdentifier", "")
            ),
            runtime=d.get("runtime", ""),
        )


@dataclass
class AccessibilityTree:
    """Best-effort simulator accessibility tree result."""

    available: bool
    tree: Any = None
    error: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> AccessibilityTree:
        return cls(
            available=bool(d.get("available", False)),
            tree=d.get("tree"),
            error=d.get("error", ""),
        )


@dataclass
class RecordingInfo:
    id: str
    status: str = ""
    name: str | None = None
    filename: str = ""
    file_size: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> RecordingInfo:
        return cls(
            id=d.get("id") or d.get("recording_id", ""),
            status=d.get("status", ""),
            name=d.get("name"),
            filename=d.get("filename", ""),
            file_size=d.get("file_size", 0),
        )


@dataclass
class ExecResult:
    return_code: int
    stdout: str

    @classmethod
    def from_dict(cls, d: dict) -> ExecResult:
        return cls(
            return_code=d.get("return_code", 0),
            stdout=d.get("stdout", ""),
        )


@dataclass
class ActResult:
    """Result from a compound act() call."""

    screenshot: bytes | None = None
    data: dict = field(default_factory=dict)
