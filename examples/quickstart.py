"""
Quick test of the use-computer SDK against a local gateway.

Usage:
    cd sdk && uv run python examples/quickstart.py
"""

import time

from use_computer import Computer

client = Computer(base_url="http://localhost:8080")

sandbox = client.create()
print(f"Created: {sandbox}")
print(f"VNC:     {sandbox.vnc_url}")

# Open TextEdit via exec
sandbox.exec_ssh("open -a TextEdit")
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
sandbox.keyboard.type("Hello from use.computer!")
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
