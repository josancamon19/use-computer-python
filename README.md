# use-computer Python SDK

Python client for use.computer macOS and iOS sandboxes.

```bash
pip install use-computer
export USE_COMPUTER_API_KEY=mk_live_...
```

```python
from use_computer import Computer

computer = Computer()
sandbox = computer.create()  # macOS

try:
    png = sandbox.screenshot.take_full_screen()
    sandbox.mouse.click(500, 400)
    sandbox.keyboard.type("hello")
    sandbox.exec_ssh("open -a TextEdit")
finally:
    sandbox.close()
    computer.close()
```

## iOS

```python
from use_computer import Computer

computer = Computer()
ios = computer.create(type="ios")
try:
    ios.apps.open_url("https://example.com")
    ios.input.tap(200, 300)
    ios.input.type_text("hello")
    ios.environment.set_appearance("dark")
finally:
    ios.close()
    computer.close()
```

In runner configs, use `platform: ios`; the runner calls the iOS SDK create path under the hood.

## Action DSL

Actions are dotted method calls plus args/kwargs. They are useful when a model emits tool-like steps. Given an open macOS `sandbox`:

```python
from use_computer import Action, parse_pyautogui, parse_xdotool

actions = [
    Action("mouse.move", [500, 400]),
    Action("mouse.click", [500, 400]),
    Action("keyboard.hotkey", ["command+space"]),
    Action("keyboard.type", ["Safari"]),
    Action("screenshot.take_full_screen"),
]

for action in actions:
    action.execute(sandbox)

for action in parse_pyautogui("pyautogui.click(100, 200); pyautogui.write('hi')"):
    action.execute(sandbox)

for action in parse_xdotool("xdotool mousemove 100 200 click 1 type hello"):
    action.execute(sandbox)
```

Common macOS targets: `mouse.*`, `keyboard.*`, `screenshot.*`, `display.*`, `recording.*`.

Common iOS targets: `input.*`, `apps.*`, `environment.*`, `screenshot.*`, `recording.*`.

Docs: https://api.use.computer/docs

OpenAPI: https://api.use.computer/openapi.yaml

Runner: https://github.com/josancamon19/mmini-runner
