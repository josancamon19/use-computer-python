"""
Example: upload a file to a sandbox and verify it.

Uses the file upload endpoint to put a file on the VM's filesystem,
then verifies it exists via exec.

Usage:
    cd sdk && uv run python examples/upload_file.py
"""

import asyncio

from mmini import AsyncMmini


async def main() -> None:
    client = AsyncMmini()
    sandbox = await client.create()
    print(f"Created: {sandbox.sandbox_id}")

    # Create some content
    content = b"Name,Score\nAlice,95\nBob,87\nCharlie,92\n"

    # Upload to the VM
    await sandbox.upload_bytes(content, "/Users/lume/Desktop/scores.csv")
    print("Uploaded scores.csv to Desktop")

    # Verify it's there
    _, output = await sandbox.exec_ssh("cat /Users/lume/Desktop/scores.csv")
    print(f"File contents:\n{output}")

    # Upload a script and run it
    script = b"#!/bin/bash\necho 'Hello from uploaded script!'\nls ~/Desktop/\n"
    await sandbox.upload_bytes(script, "/Users/lume/Desktop/check.sh")
    await sandbox.exec_ssh("chmod +x /Users/lume/Desktop/check.sh")
    _, output = await sandbox.exec_ssh("/Users/lume/Desktop/check.sh")
    print(f"Script output:\n{output}")

    await sandbox.close()
    await client.close()


asyncio.run(main())
