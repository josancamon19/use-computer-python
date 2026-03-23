# mmini SDK

Python SDK for controlling macOS sandboxes via the mmini gateway.

## Install

```bash
pip install git+https://github.com/josancamon19/mmini-sdk.git
```

## Usage

```python
from mmini import Mmini

client = Mmini()  # gateway at http://localhost:8080
sandbox = client.create()

# Screenshot
img = sandbox.screenshot.take_full_screen()

# Mouse
sandbox.mouse.click(500, 400)
sandbox.mouse.move(100, 200)
sandbox.mouse.scroll(500, 400, "down", 3)
sandbox.mouse.drag(100, 100, 300, 300)

# Keyboard
sandbox.keyboard.type("Hello")
sandbox.keyboard.press("enter")
sandbox.keyboard.hotkey("command+space")

# Display
info = sandbox.display.get_info()
windows = sandbox.display.get_windows()

# Recording
sandbox.recording.start(name="my-recording")
# ... do stuff ...
sandbox.recording.stop(recording_id)
sandbox.recording.download(recording_id, "output.mp4")

# Cleanup
sandbox.close()
client.close()
```

## Async

```python
from mmini import AsyncMmini

client = AsyncMmini()
sandbox = await client.create()
img = await sandbox.screenshot.take_full_screen()
await sandbox.close()
await client.close()
```

## Custom gateway URL

```python
client = Mmini(base_url="https://your-gateway.example.com")
```
