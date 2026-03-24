"""
Example: seed a sandbox by running shell commands via exec.

Opens Notes, creates a note, and sets system preferences — all via exec_ssh.
This replaces the old seed mechanism with direct shell commands.

Usage:
    cd sdk && uv run python examples/setup_with_exec.py
"""

import time

from mmini import Mmini

client = Mmini()
sandbox = client.create()
print(f"Created: {sandbox.sandbox_id}")

# Open an app
sandbox.exec_ssh("open -a Notes")
time.sleep(2)

# Create a note via osascript
sandbox.exec_ssh(
    """osascript -e 'tell application "Notes" to make new note with properties {name:"Test Note", body:"Created by mmini SDK"}'"""
)

# Set system preferences
sandbox.exec_ssh("defaults write com.apple.dock autohide -bool true && killall Dock")

# Run any shell command
return_code, output = sandbox.exec_ssh("sw_vers -productVersion")
print(f"macOS version: {output.strip()}")

# Verify the note was created
_, notes = sandbox.exec_ssh(
    """osascript -e 'tell application "Notes" to get the name of every note'"""
)
print(f"Notes: {notes.strip()}")

# Take a screenshot to see the result
img = sandbox.screenshot.take_full_screen()
with open("setup_result.png", "wb") as f:
    f.write(img)
print("Screenshot saved to setup_result.png")

sandbox.close()
client.close()
