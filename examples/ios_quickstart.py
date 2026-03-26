"""
iOS simulator sandbox — end to end example.

Creates an iPhone simulator, opens Safari, takes a screenshot,
taps around, types a URL, and cleans up.

Usage:
    cd sdk && uv run python examples/ios_quickstart.py
"""

import time

from mmini import Mmini

client = Mmini()  # defaults to http://localhost:8080

# Create an iOS sandbox (iPhone 17 Pro by default)
sandbox = client.create(type="ios")
print(f"Created: {sandbox}")

# Check display info
info = sandbox.display.get_info()
print(f"Display: {info.width}x{info.height} @{info.scale}x")

# Take initial screenshot (home screen)
time.sleep(3)  # wait for simulator to settle
img = sandbox.screenshot.take_full_screen()
with open("ios_home.png", "wb") as f:
    f.write(img)
print(f"Home screen saved ({len(img)} bytes)")

# Open Safari via URL scheme
sandbox.apps.open_url("https://example.com")
time.sleep(3)

# Screenshot Safari
img = sandbox.screenshot.take_full_screen()
with open("ios_safari.png", "wb") as f:
    f.write(img)
print("Safari screenshot saved")

# Tap the address bar (top center of screen)
sandbox.input.tap(info.width / 2, 70)
time.sleep(1)

# Type a URL
sandbox.input.type_text("https://apple.com")
time.sleep(0.5)

# Press Go (tap keyboard return area)
sandbox.input.press_button("HOME")  # dismiss keyboard first
time.sleep(1)

# Screenshot final state
img = sandbox.screenshot.take_full_screen()
with open("ios_final.png", "wb") as f:
    f.write(img)
print("Final screenshot saved")

# Set dark mode
sandbox.environment.set_appearance("dark")
time.sleep(1)
img = sandbox.screenshot.take_full_screen()
with open("ios_dark.png", "wb") as f:
    f.write(img)
print("Dark mode screenshot saved")

# Upload a file to the simulator
sandbox.upload_bytes(b"Hello from mmini iOS!", "Documents/test.txt")
print("File uploaded")

# Download it back
sandbox.download_file("Documents/test.txt", "ios_downloaded.txt")
with open("ios_downloaded.txt") as f:
    print(f"Downloaded: {f.read()}")

# Start recording
rec = sandbox.recording.start(name="demo")
print(f"Recording started: {rec.id}")
time.sleep(3)

# Stop recording
rec = sandbox.recording.stop(rec.id)
print(f"Recording stopped: {rec.status}")

# Clean up
sandbox.close()
print("Sandbox destroyed.")
client.close()
