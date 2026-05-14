# use-computer Python SDK

Python client for [use.computer](https://use.computer) — rent dedicated Mac minis with macOS and iOS sandboxes built for computer-use agents.

```bash
pip install use-computer
export USE_COMPUTER_API_KEY=mk_live_...
```

```python
from use_computer import Computer

with Computer().create() as mac:
    mac.exec_ssh("open -a TextEdit")
    mac.keyboard.type("hello")
    png = mac.screenshot.take_full_screen()
```

Full DSL reference (macOS + iOS): [docs.use.computer/docs/sdk](https://docs.use.computer/docs/sdk)

## Examples

| File                                                           | What it shows                              |
| -------------------------------------------------------------- | ------------------------------------------ |
| [`examples/_1_hello_macos.py`](examples/_1_hello_macos.py)     | create → exec → keyboard → screenshot      |
| [`examples/_2_hello_ios.py`](examples/_2_hello_ios.py)         | create iOS → open URL → screenshot         |
| [`examples/_3_recording.py`](examples/_3_recording.py)         | start / stop / download a screen recording |
| [`examples/_4_file_transfer.py`](examples/_4_file_transfer.py) | upload bytes, download a file back         |
| [`examples/_5_keepalive.py`](examples/_5_keepalive.py)         | heartbeat for sessions idle > 2 min        |

For agent loops and evals: [use-computer-cookbook](https://github.com/josancamon19/use-computer-cookbook).

## Skill for AI coding assistants

Point your assistant at [`use-computer-cookbook/skills/SKILL.md`](https://github.com/josancamon19/use-computer-cookbook/blob/main/skills/SKILL.md) — short body with per-topic references for macOS, iOS, lifecycle, and the Harbor harness.

## HTTP API

Every SDK method wraps `https://api.use.computer/v1/...` with `Authorization: Bearer mk_live_...`. Swagger: [api.use.computer/docs](https://api.use.computer/docs). OpenAPI spec: [api.use.computer/openapi.yaml](https://api.use.computer/openapi.yaml).
