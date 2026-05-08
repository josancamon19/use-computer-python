# use-computer Python SDK

Python client for the use.computer macOS and iOS Computer Use API.

```bash
pip install use-computer
```

```python
from use_computer import Computer

computer = Computer(api_key="mk_live_...")
sandbox = computer.create()

image = sandbox.screenshot.take_full_screen()
sandbox.mouse.click(500, 400)
sandbox.keyboard.type("hello")

sandbox.close()
computer.close()
```

Docs: https://docs.use.computer

Runner repo: https://github.com/josancamon19/mmini-runner

API reference: https://admin.api.use.computer/docs
