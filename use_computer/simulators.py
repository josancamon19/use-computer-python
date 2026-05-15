from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class SimulatorFamily(str, Enum):
    """CoreSimulator device families supported by the API."""

    IPHONE = "iPhone"
    IPAD = "iPad"
    WATCH = "Apple Watch"
    TV = "Apple TV"
    VISION = "Apple Vision"


@dataclass(frozen=True)
class SimulatorChoice:
    """Resolved CoreSimulator device/runtime pair."""

    family: SimulatorFamily
    device_type: str
    runtime: str
    device_name: str = ""
    runtime_name: str = ""


_FAMILY_RUNTIME_OS: dict[SimulatorFamily, str] = {
    SimulatorFamily.IPHONE: "iOS",
    SimulatorFamily.IPAD: "iOS",
    SimulatorFamily.WATCH: "watchOS",
    SimulatorFamily.TV: "tvOS",
    SimulatorFamily.VISION: "visionOS",
}

_RUNTIME_OS_ALIASES = {
    "xrOS": "visionOS",
}


def normalize_simulator_family(family: SimulatorFamily | str) -> SimulatorFamily:
    """Normalize SDK enum values and common user-facing aliases."""

    if isinstance(family, SimulatorFamily):
        return family
    compact = re.sub(r"[^a-z0-9]", "", family.lower())
    aliases = {
        "iphone": SimulatorFamily.IPHONE,
        "ios": SimulatorFamily.IPHONE,
        "ipad": SimulatorFamily.IPAD,
        "watch": SimulatorFamily.WATCH,
        "applewatch": SimulatorFamily.WATCH,
        "watchos": SimulatorFamily.WATCH,
        "tv": SimulatorFamily.TV,
        "appletv": SimulatorFamily.TV,
        "tvos": SimulatorFamily.TV,
        "vision": SimulatorFamily.VISION,
        "applevision": SimulatorFamily.VISION,
        "visionpro": SimulatorFamily.VISION,
        "applevisionpro": SimulatorFamily.VISION,
        "visionos": SimulatorFamily.VISION,
        "xros": SimulatorFamily.VISION,
    }
    try:
        return aliases[compact]
    except KeyError as exc:
        raise ValueError(f"unknown simulator family: {family!r}") from exc


def family_for_device(device: dict[str, Any] | str) -> SimulatorFamily | None:
    """Return the simulator family for a device type dict, identifier, or name."""

    text = (
        device
        if isinstance(device, str)
        else f"{device.get('name', '')} {device.get('identifier', '')}"
    )
    if re.search(r"Apple[- ]Watch", text, re.I):
        return SimulatorFamily.WATCH
    if re.search(r"Apple[- ]TV", text, re.I):
        return SimulatorFamily.TV
    if re.search(r"Apple[- ]Vision", text, re.I):
        return SimulatorFamily.VISION
    if re.search(r"iPad", text, re.I):
        return SimulatorFamily.IPAD
    if re.search(r"iPhone", text, re.I):
        return SimulatorFamily.IPHONE
    return None


def runtime_os(runtime: dict[str, Any] | str) -> str:
    """Return the normalized OS family for a runtime dict or identifier."""

    identifier = runtime if isinstance(runtime, str) else runtime.get("identifier", "")
    match = re.search(r"SimRuntime\.([^-]+)-", identifier)
    if not match:
        return ""
    os_name = match.group(1)
    return _RUNTIME_OS_ALIASES.get(os_name, os_name)


def required_runtime_os(family: SimulatorFamily | str) -> str:
    """Return the runtime OS required by a simulator family."""

    return _FAMILY_RUNTIME_OS[normalize_simulator_family(family)]


def select_simulator(
    platforms: dict[str, Any],
    family: SimulatorFamily | str,
    *,
    device_name: str = "",
) -> SimulatorChoice:
    """Select a compatible device/runtime pair from `/v1/platforms` output."""

    fam = normalize_simulator_family(family)
    ios = platforms.get("ios") or {}
    devices = [
        d
        for d in ios.get("device_types") or []
        if family_for_device(d) == fam and is_usable_device_type(d)
    ]
    if device_name:
        needle = device_name.lower()
        devices = [d for d in devices if needle in (d.get("name") or "").lower()]
    if not devices:
        raise ValueError(f"no {fam.value} simulator devices available")

    want_os = required_runtime_os(fam)
    runtimes = [
        rt
        for rt in ios.get("runtimes") or []
        if rt.get("isAvailable", True) and runtime_os(rt) == want_os
    ]
    if not runtimes:
        raise ValueError(f"no {want_os} runtime available for {fam.value}")

    devices.sort(key=lambda d: d.get("name") or d.get("identifier") or "")
    runtimes.sort(
        key=lambda rt: (rt.get("version") or "", rt.get("identifier") or ""),
        reverse=True,
    )
    device = _default_device(fam, devices)
    runtime = runtimes[0]
    return SimulatorChoice(
        family=fam,
        device_type=device.get("identifier", ""),
        runtime=runtime.get("identifier", ""),
        device_name=device.get("name", ""),
        runtime_name=runtime.get("name", ""),
    )


def _default_device(family: SimulatorFamily, devices: list[dict[str, Any]]) -> dict[str, Any]:
    if family == SimulatorFamily.IPHONE:
        for d in devices:
            name = d.get("name") or ""
            if re.search(r"17 Pro\b", name) and "Max" not in name:
                return d
    if family == SimulatorFamily.VISION:
        for d in devices:
            if "Apple-Vision-Pro-4K" in (d.get("identifier") or ""):
                return d
    return devices[0]


def is_usable_device_type(device: dict[str, Any] | str) -> bool:
    """Return false for simulator device types known to fail with current runtimes."""

    text = (
        device
        if isinstance(device, str)
        else f"{device.get('name', '')} {device.get('identifier', '')}"
    )
    if re.search(r"Apple[- ]Vision[- ]Pro", text, re.I):
        return "Apple-Vision-Pro-4K" in text or re.search(r"\b4K\b", text, re.I) is not None
    return True
