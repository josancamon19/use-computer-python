"""
Quick test of the mmini SDK against a local gateway.

Usage:
    cd sdk && uv run python examples/quickstart.py
"""

import time

from mmini import Mmini, Seed

client = Mmini()  # defaults to http://localhost:8080

# Create a sandbox with TextEdit already open
sandbox = client.create(seed=[
    Seed.launch("TextEdit"),
])
print(f"Created: {sandbox}")
print(f"VNC:     {sandbox.vnc_url}")

# Wait for TextEdit to fully open
time.sleep(2)

# Click in the document area to focus it
sandbox.mouse.click(512, 400)
time.sleep(0.5)

# Take initial screenshot
img = sandbox.screenshot.take_full_screen()
with open("screen.png", "wb") as f:
    f.write(img)
print(f"Screenshot saved to screen.png ({len(img)} bytes)")

# Type something
sandbox.keyboard.type("Hello from mmini!")
time.sleep(0.5)

# Screenshot after typing
img = sandbox.screenshot.take_full_screen()
with open("screen_after.png", "wb") as f:
    f.write(img)
print("After typing saved to screen_after.png")

# Clean up
sandbox.close()
print("Sandbox destroyed.")
client.close()
