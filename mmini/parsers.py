"""Parse pyautogui and xdotool commands into mmini Sandbox calls.

Models like Claude and GPT sometimes output raw pyautogui or xdotool commands.
These parsers translate them into Sandbox method calls.

Usage:
    from mmini.parsers import parse_pyautogui, parse_xdotool

    for action in parse_pyautogui("pyautogui.click(100, 200)"):
        action.execute(sandbox)

    for action in parse_xdotool("xdotool mousemove 100 200 click 1"):
        action.execute(sandbox)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mmini.sandbox import Sandbox


@dataclass
class Action:
    """A parsed action that can be executed on a Sandbox."""

    method: str
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)

    def execute(self, sandbox: Sandbox) -> dict | bytes | None:
        parts = self.method.split(".")
        obj: Any = sandbox
        for part in parts:
            obj = getattr(obj, part)
        return obj(*self.args, **self.kwargs)

    def __repr__(self) -> str:
        arg_str = ", ".join(
            [repr(a) for a in self.args] + [f"{k}={v!r}" for k, v in self.kwargs.items()]
        )
        return f"Action({self.method}({arg_str}))"


# ---------------------------------------------------------------------------
# pyautogui parser
# ---------------------------------------------------------------------------

# Map pyautogui function names to (method, arg_parser)
_PYAUTOGUI_MAP = {
    "click": "mouse.click",
    "rightClick": "mouse.click",
    "doubleClick": "mouse.click",
    "moveTo": "mouse.move",
    "moveRel": "mouse.move",
    "drag": "mouse.drag",
    "dragTo": "mouse.drag",
    "scroll": "mouse.scroll",
    "write": "keyboard.type",
    "typewrite": "keyboard.type",
    "press": "keyboard.press",
    "hotkey": "keyboard.hotkey",
    "screenshot": "screenshot.take_full_screen",
}

_PYAUTOGUI_RE = re.compile(r"pyautogui\.(\w+)\(([^)]*)\)")


def _parse_py_args(raw: str) -> tuple[list, dict]:
    """Parse Python-style function arguments."""
    args = []
    kwargs = {}
    if not raw.strip():
        return args, kwargs

    for part in _split_args(raw):
        part = part.strip()
        if "=" in part and not part.startswith(("'", '"')):
            key, val = part.split("=", 1)
            kwargs[key.strip()] = _coerce(val.strip())
        else:
            args.append(_coerce(part))
    return args, kwargs


def _split_args(raw: str) -> list[str]:
    """Split arguments respecting strings and nested parens."""
    parts = []
    depth = 0
    current = ""
    in_str = None
    for c in raw:
        if c in ("'", '"') and in_str is None:
            in_str = c
        elif c == in_str:
            in_str = None
        elif in_str is None:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            elif c == "," and depth == 0:
                parts.append(current)
                current = ""
                continue
        current += c
    if current.strip():
        parts.append(current)
    return parts


def _coerce(val: str):
    """Coerce a string value to int, float, bool, or str."""
    val = val.strip().strip("'\"")
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _pyautogui_to_action(func: str, args: list, kwargs: dict) -> Action | None:
    if func == "click":
        x = args[0] if len(args) > 0 else kwargs.get("x", 0)
        y = args[1] if len(args) > 1 else kwargs.get("y", 0)
        return Action("mouse.click", [x, y])

    if func == "rightClick":
        x = args[0] if len(args) > 0 else kwargs.get("x", 0)
        y = args[1] if len(args) > 1 else kwargs.get("y", 0)
        return Action("mouse.click", [x, y, "right"])

    if func == "doubleClick":
        x = args[0] if len(args) > 0 else kwargs.get("x", 0)
        y = args[1] if len(args) > 1 else kwargs.get("y", 0)
        return Action("mouse.click", [x, y], {"double": True})

    if func in ("moveTo", "moveRel"):
        x = args[0] if len(args) > 0 else kwargs.get("x", 0)
        y = args[1] if len(args) > 1 else kwargs.get("y", 0)
        return Action("mouse.move", [x, y])

    if func in ("drag", "dragTo"):
        # pyautogui.drag(xOffset, yOffset) is relative
        # We need current position for relative, but just map the args
        x = args[0] if len(args) > 0 else kwargs.get("x", 0)
        y = args[1] if len(args) > 1 else kwargs.get("y", 0)
        return Action("mouse.drag", [0, 0, x, y])

    if func == "scroll":
        amount = args[0] if len(args) > 0 else kwargs.get("clicks", 3)
        x = args[1] if len(args) > 1 else kwargs.get("x", 0)
        y = args[2] if len(args) > 2 else kwargs.get("y", 0)
        direction = "up" if amount > 0 else "down"
        return Action("mouse.scroll", [x, y, direction, abs(amount)])

    if func in ("write", "typewrite"):
        text = args[0] if len(args) > 0 else kwargs.get("message", "")
        kw = {}
        interval = kwargs.get("interval")
        if interval:
            kw["delay"] = int(interval * 1000)
        return Action("keyboard.type", [text], kw)

    if func == "press":
        key = args[0] if len(args) > 0 else kwargs.get("key", "")
        return Action("keyboard.press", [key])

    if func == "hotkey":
        keys = "+".join(str(a) for a in args)
        return Action("keyboard.hotkey", [keys])

    if func == "screenshot":
        return Action("screenshot.take_full_screen")

    return None


def parse_pyautogui(text: str) -> list[Action]:
    """Parse pyautogui commands from text into Actions."""
    actions = []
    for match in _PYAUTOGUI_RE.finditer(text):
        func = match.group(1)
        raw_args = match.group(2)
        args, kwargs = _parse_py_args(raw_args)
        action = _pyautogui_to_action(func, args, kwargs)
        if action:
            actions.append(action)
    return actions


# ---------------------------------------------------------------------------
# xdotool parser
# ---------------------------------------------------------------------------

_XDOTOOL_KEY_MAP = {
    "Return": "enter",
    "Escape": "escape",
    "BackSpace": "backspace",
    "Tab": "tab",
    "space": "space",
    "Delete": "delete",
    "Home": "home",
    "End": "end",
    "Page_Up": "pageup",
    "Page_Down": "pagedown",
    "Up": "up",
    "Down": "down",
    "Left": "left",
    "Right": "right",
}

_XDOTOOL_BUTTON_MAP = {
    "1": "left",
    "2": "middle",
    "3": "right",
}


def parse_xdotool(text: str) -> list[Action]:
    """Parse xdotool commands from text into Actions.

    Handles:
        xdotool mousemove X Y
        xdotool click BUTTON
        xdotool key KEY [KEY...]
        xdotool type TEXT
        xdotool mousemove X Y click BUTTON  (chained)
    """
    actions = []

    for line in text.strip().splitlines():
        line = line.strip()
        if not line.startswith("xdotool"):
            continue

        tokens = line.split()[1:]  # drop "xdotool"
        actions.extend(_parse_xdotool_tokens(tokens))

    return actions


def _parse_xdotool_tokens(tokens: list[str]) -> list[Action]:
    """Parse xdotool token stream (supports chained commands)."""
    actions = []
    i = 0

    while i < len(tokens):
        cmd = tokens[i]
        i += 1

        if cmd == "mousemove" and i + 1 < len(tokens):
            x, y = int(tokens[i]), int(tokens[i + 1])
            i += 2
            actions.append(Action("mouse.move", [x, y]))

        elif cmd == "click" and i < len(tokens):
            button = _XDOTOOL_BUTTON_MAP.get(tokens[i], "left")
            i += 1
            actions.append(Action("mouse.click", [0, 0, button]))

        elif cmd == "mousedown" and i < len(tokens):
            i += 1  # skip button, no direct mapping
            pass

        elif cmd == "mouseup" and i < len(tokens):
            i += 1
            pass

        elif cmd == "key" and i < len(tokens):
            key_combo = tokens[i]
            i += 1
            # xdotool uses "super+a", "ctrl+c", etc.
            if "+" in key_combo:
                combo = key_combo.replace("super", "command").replace("ctrl", "control")
                actions.append(Action("keyboard.hotkey", [combo]))
            else:
                mapped = _XDOTOOL_KEY_MAP.get(key_combo, key_combo.lower())
                actions.append(Action("keyboard.press", [mapped]))

        elif cmd == "type" and i < len(tokens):
            # Collect remaining tokens as the text
            text = " ".join(tokens[i:])
            # Strip surrounding quotes if present
            if len(text) >= 2 and text[0] in ("'", '"') and text[-1] == text[0]:
                text = text[1:-1]
            actions.append(Action("keyboard.type", [text]))
            break  # type consumes everything

        elif cmd == "--delay" and i < len(tokens):
            i += 1  # skip delay value, not mapped
        elif cmd == "--clearmodifiers":
            pass  # skip
        elif cmd.startswith("--"):
            i += 1  # skip flag + value

    return actions
