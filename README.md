# use-computer Python SDK

Python SDK for the use.computer macOS and iOS Computer Use API.

## Install

```bash
pip install use-computer
```

## Usage

```python
from use_computer import Computer

client = Computer(api_key="mk_live_...")
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
recording = sandbox.recording.start(name="my-recording")
# ... do stuff ...
sandbox.recording.stop(recording.id)
sandbox.recording.download(recording.id, "output.mp4")

# Cleanup
sandbox.close()
client.close()
```

## Environment

`Computer()` reads these environment variables when explicit values are not passed:

```bash
USE_COMPUTER_API_KEY=mk_live_...
USE_COMPUTER_BASE_URL=https://api.use.computer
```

`USE_COMPUTER_BASE_URL` is optional. The default is `https://api.use.computer`.

## Async

```python
from use_computer import AsyncComputer

client = AsyncComputer(api_key="mk_live_...")
sandbox = await client.create()
img = await sandbox.screenshot.take_full_screen()
await sandbox.close()
await client.close()
```

## Local Gateway

```python
from use_computer import Computer

client = Computer(
    api_key="sk-local",
    base_url="http://localhost:8080",
)
```

## Backward Compatibility

The original import path still works:

```python
from mmini import Mmini
```

New code should prefer:

```python
from use_computer import Computer
```

## Publishing

CI publishes `use-computer` from the `main` branch. The first release is
`0.0.1`; after that the workflow reads the latest `vX.Y.Z` tag and bumps the
patch version.

For CI, prefer PyPI Trusted Publishing. If using an API token instead, set a
repo secret named `PYPI_API_TOKEN`; do not commit tokens to `.env`.

## Development

```bash
uv run --group dev pre-commit install
```

Pre-commit runs `ruff format`, `ruff check --fix`, and `ty check`.
