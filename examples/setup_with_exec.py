"""
Example: seed a sandbox by running shell commands via exec.

Opens Notes, creates a note, and sets system preferences — all via exec.
This replaces the old seed mechanism with direct shell commands.

Usage:
    cd sdk && uv run python examples/setup_with_exec.py
"""

import asyncio

from mmini import AsyncMmini


async def main() -> None:
    client = AsyncMmini()
    sandbox = await client.create()
    print(f"Created: {sandbox.sandbox_id}")

    # Open an app
    await sandbox.exec_ssh("open -a Notes")
    await asyncio.sleep(2)

    # Create a note via osascript
    await sandbox.exec_ssh(
        'osascript -e \'tell application "Notes" to make new note'
        ' with properties {name:"Test Note", body:"Created by mmini SDK"}\''
    )

    # Set system preferences
    await sandbox.exec_ssh("defaults write com.apple.dock autohide -bool true && killall Dock")

    # Run any shell command
    _, output = await sandbox.exec_ssh("sw_vers -productVersion")
    print(f"macOS version: {output.strip()}")

    # Verify the note was created
    _, notes = await sandbox.exec_ssh(
        "osascript -e 'tell application \"Notes\" to get the name of every note'"
    )
    print(f"Notes: {notes.strip()}")

    # Take a screenshot to see the result
    img = await sandbox.screenshot.take_full_screen()
    with open("setup_result.png", "wb") as f:
        f.write(img)
    print("Screenshot saved to setup_result.png")

    await sandbox.close()
    await client.close()


asyncio.run(main())
