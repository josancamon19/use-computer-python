import pytest

from use_computer.client import _normalize_sandbox_type
from use_computer.sandbox import SandboxType
from use_computer.simulators import (
    SimulatorFamily,
    family_for_device,
    is_usable_device_type,
    normalize_simulator_family,
    runtime_os,
    select_simulator,
)


def test_normalize_simulator_family_aliases():
    assert normalize_simulator_family("tvOS") is SimulatorFamily.TV
    assert normalize_simulator_family("vision pro") is SimulatorFamily.VISION
    assert normalize_simulator_family(SimulatorFamily.WATCH) is SimulatorFamily.WATCH


def test_normalize_sandbox_type_accepts_enum_and_raw_string():
    assert _normalize_sandbox_type(SandboxType.IOS) is SandboxType.IOS
    assert _normalize_sandbox_type("macos") is SandboxType.MACOS


def test_family_for_device_and_runtime_os():
    assert (
        family_for_device("com.apple.CoreSimulator.SimDeviceType.Apple-TV-4K-3rd-generation")
        is SimulatorFamily.TV
    )
    assert (
        family_for_device({"name": "Apple Vision Pro", "identifier": "ignored"})
        is SimulatorFamily.VISION
    )
    assert runtime_os("com.apple.CoreSimulator.SimRuntime.xrOS-26-4") == "visionOS"


def test_select_simulator_uses_matching_runtime():
    platforms = {
        "ios": {
            "device_types": [
                {
                    "identifier": "com.apple.CoreSimulator.SimDeviceType.Apple-TV-4K-1080p",
                    "name": "Apple TV 4K (at 1080p)",
                },
                {
                    "identifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro",
                    "name": "iPhone 17 Pro",
                },
            ],
            "runtimes": [
                {
                    "identifier": "com.apple.CoreSimulator.SimRuntime.iOS-26-4",
                    "name": "iOS 26.4",
                    "version": "26.4",
                    "isAvailable": True,
                },
                {
                    "identifier": "com.apple.CoreSimulator.SimRuntime.tvOS-26-4",
                    "name": "tvOS 26.4",
                    "version": "26.4",
                    "isAvailable": True,
                },
            ],
        }
    }

    choice = select_simulator(platforms, SimulatorFamily.TV)
    assert choice.device_type.endswith("Apple-TV-4K-1080p")
    assert choice.runtime.endswith("tvOS-26-4")


def test_select_simulator_errors_when_runtime_missing():
    platforms = {
        "ios": {
            "device_types": [
                {
                    "identifier": "com.apple.CoreSimulator.SimDeviceType.Apple-Vision-Pro-4K",
                    "name": "Apple Vision Pro",
                }
            ],
            "runtimes": [],
        }
    }

    with pytest.raises(ValueError, match="no visionOS runtime"):
        select_simulator(platforms, SimulatorFamily.VISION)


def test_select_simulator_filters_bad_vision_device_and_prefers_4k():
    platforms = {
        "ios": {
            "device_types": [
                {
                    "identifier": "com.apple.CoreSimulator.SimDeviceType.Apple-Vision-Pro",
                    "name": "Apple Vision Pro (at 2732x2048)",
                },
                {
                    "identifier": "com.apple.CoreSimulator.SimDeviceType.Apple-Vision-Pro-4K",
                    "name": "Apple Vision Pro",
                },
            ],
            "runtimes": [
                {
                    "identifier": "com.apple.CoreSimulator.SimRuntime.xrOS-26-4",
                    "name": "visionOS 26.4",
                    "version": "26.4",
                    "isAvailable": True,
                },
            ],
        }
    }

    assert not is_usable_device_type("com.apple.CoreSimulator.SimDeviceType.Apple-Vision-Pro")
    choice = select_simulator(platforms, SimulatorFamily.VISION)
    assert choice.device_type.endswith("Apple-Vision-Pro-4K")
