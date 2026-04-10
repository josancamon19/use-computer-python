"""
Transparently rewrite `osascript -e 'tell application "System Events" ...'`
patterns to equivalent `python3.12 -c "..."` invocations that talk to the
Accessibility API directly via PyObjC.

Background
----------
macOSWorld verifiers and pre_command setup scripts rely on
`tell application "System Events" to ...` to read or set UI state. That
requires `kTCCServiceAccessibility`, which lives in **system** TCC and is
SIP-sealed on Sequoia (full memo: proposals/accessibility-tcc-for-osascript.md).
We cannot grant osascript that permission from the bake recipe.

But the trycua base image's bundled python at
`/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12`
**already has** Accessibility — Apple shipped it pre-sealed in the system
snapshot. And cua-server's `run_command` invokes children with
`launchd → cua-server → bash → python3.12` as the responsibility chain
(no `sshd-keygen-wrapper` to deny it), so the grant actually applies.
Verified end-to-end on a warm VM.

Strategy
--------
The SDK intercepts every shell-string heading to the VM (via `exec_ssh`) and
every `.sh` file heading to the VM (via `upload`). For each, we scan for
`osascript -e '...'` invocations and try to convert each AppleScript snippet
to an equivalent python3.12 invocation that uses ApplicationServices /
PyObjC. The python is base64-wrapped to dodge bash quoting headaches inside
the surrounding `bash -c '...'` envelopes the macOSWorld scripts use.

Coverage
--------
The transpiler handles four AppleScript shapes that account for ~100% of
the macOSWorld AX-blocked verifier patterns:

1.  `attribute "AX..." of <PATH>` rooted at the frontmost application or a
    named process. <PATH> can be any chain of `(window|group|scroll area|
    toolbar|...) (N|"name")` segments. The path walker walks AXChildren
    levels and matches by role + name/index at each step.
2.  `get name of first process whose frontmost is true`
3.  `name of every UI element of list 1 of application process "Dock"`
4.  `tell process "X" to get value of <ELEMENT> of <PATH>` — the leaf is a
    pop-up button / text field / etc., the path is window/group nesting,
    and the result is `AXValue` of the leaf.

Lines that don't match any recognized AppleScript shape are passed through
unchanged. The verifier or pre_command will hit the original osascript path
and fail the same way it did before — no regression.

What this does NOT handle
-------------------------
* Synthesized keystrokes / key codes (`keystroke "x"`, `key code N`)
* AppleScript with conditionals or repeats
* `set value of` (we only do reads)
None of the macOSWorld AX-blocked verifiers we've classified need these,
so they're left as future work.
"""

from __future__ import annotations

import base64
import re
import textwrap

# The granted python binary on the trycua base image. This exact path is
# what system TCC.db has Accessibility=allowed for. Other python binaries
# on the image (/usr/bin/python3, /opt/homebrew/bin/python3) do NOT have
# the grant.
PY = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"


# AppleScript element kind → AX role. The role names mirror what
# AXUIElementCopyAttributeValue returns for "AXRole".
_ROLE_MAP: dict[str, str | None] = {
    "window":         "AXWindow",
    "group":          "AXGroup",
    "scroll area":    "AXScrollArea",
    "toolbar":        "AXToolbar",
    "menu button":    "AXMenuButton",
    "button":         "AXButton",
    "pop up button":  "AXPopUpButton",
    "text field":     "AXTextField",
    "text area":      "AXTextArea",
    "checkbox":       "AXCheckBox",
    "radio button":   "AXRadioButton",
    "list":           "AXList",
    "row":            "AXRow",
    "tab":            "AXTab",
    "menu item":      "AXMenuItem",
    "static text":    "AXStaticText",
    "splitter group": "AXSplitGroup",
    "ui element":     None,  # don't filter by role
}

# A path segment is a kind followed by either a name in double-quotes
# or a 1-based index. We sort the kind alternatives by length descending
# so "menu button" wins over "button" when both could match.
_KINDS_SORTED = sorted(_ROLE_MAP.keys(), key=len, reverse=True)
_KIND_ALT = "|".join(re.escape(k) for k in _KINDS_SORTED)
_PATH_SEG_RE = re.compile(
    r'(' + _KIND_ALT + r')\s+(?:"([^"]+)"|(\d+))',
    re.IGNORECASE,
)

# Match an entire osascript -e invocation. The argument can be wrapped in
# either bare single quotes (`'...'`) or the bash-escape form (`'\''...'\''`)
# that test.sh files use to embed osascript inside `bash -c '...'`.
_OSASCRIPT_RE = re.compile(
    r"""osascript\s+-e\s+(?:'\\''|')(.*?)(?:'\\''|')""",
    re.DOTALL,
)


def _wrap_python(py_src: str) -> str:
    """Wrap a python snippet in a `echo B64 | base64 -d | python3.12 -` shell call.

    base64 encoding keeps the snippet quote-safe inside any bash envelope —
    the alphabet is A-Z/a-z/0-9/+//= so it never collides with single or
    double quotes.
    """
    src = textwrap.dedent(py_src).strip() + "\n"
    b64 = base64.b64encode(src.encode("utf-8")).decode("ascii")
    return f"echo {b64} | base64 -d | {PY} -"


def _parse_path(path_str: str) -> tuple[list[tuple[str, str | None, int | None]], str, str | None] | None:
    """Parse `... of (first application process whose frontmost is true)` or
    `... of process "X"` or just `... of window N` and return:

        (segments_leaf_first, root_kind, root_arg)

    where root_kind is one of:
        "frontmost"  — root_arg None, start from AXFocusedApplication
        "process"    — root_arg = process name, start from AXUIElementCreateApplication

    Returns None if we can't parse the path.
    """
    s = path_str.strip()

    # Find the root suffix
    root_kind = None
    root_arg: str | None = None

    m = re.search(
        r"\(?\s*first\s+application\s+process\s+whose\s+frontmost\s+is\s+true\s*\)?\s*$",
        s,
        re.IGNORECASE,
    )
    if m:
        root_kind = "frontmost"
        s = s[: m.start()].rstrip()
        # strip a trailing " of "
        s = re.sub(r"\s+of\s*$", "", s, flags=re.IGNORECASE)
    else:
        m = re.search(
            r'(?:application\s+)?process\s+"([^"]+)"\s*$',
            s,
            re.IGNORECASE,
        )
        if m:
            root_kind = "process"
            root_arg = m.group(1)
            s = s[: m.start()].rstrip()
            s = re.sub(r"\s+of\s*$", "", s, flags=re.IGNORECASE)
        else:
            return None

    # Now s is just the segment chain (no root suffix). Split by " of ".
    segs: list[tuple[str, str | None, int | None]] = []
    if s:
        for chunk in re.split(r"\s+of\s+", s):
            chunk = chunk.strip()
            if not chunk:
                continue
            mm = _PATH_SEG_RE.match(chunk)
            if not mm:
                return None
            kind = mm.group(1).lower()
            if kind not in _ROLE_MAP:
                return None
            segs.append(
                (kind, mm.group(2), int(mm.group(3)) if mm.group(3) else None)
            )

    return (segs, root_kind, root_arg)


def _emit_walk(segs_leaf_first: list[tuple[str, str | None, int | None]]) -> str:
    """Emit Python that walks `el` through the segments (root → leaf).

    Assumes `el` is already set to the root AXUIElement.
    """
    parts = []
    for kind, name, idx in reversed(segs_leaf_first):  # walk root → leaf
        target_role = _ROLE_MAP[kind]
        parts.append(textwrap.dedent(f"""
            _, _kids = AS.AXUIElementCopyAttributeValue(el, "AXChildren", None)
            _trole = {target_role!r}
            _tname = {name!r}
            _tidx  = {idx if idx is not None else 'None'}
            _seen = 0
            _match = None
            for _k in (_kids or []):
                if _trole is not None:
                    _, _r = AS.AXUIElementCopyAttributeValue(_k, "AXRole", None)
                    if _r != _trole:
                        continue
                if _tname is not None:
                    _, _t = AS.AXUIElementCopyAttributeValue(_k, "AXTitle", None)
                    if _t != _tname:
                        # also try AXDescription / AXIdentifier
                        _, _d = AS.AXUIElementCopyAttributeValue(_k, "AXDescription", None)
                        if _d != _tname:
                            continue
                    _match = _k
                    break
                else:
                    _seen += 1
                    if _seen == _tidx:
                        _match = _k
                        break
            if _match is None:
                print("")
                raise SystemExit(0)
            el = _match
        """).strip())
    return "\n".join(parts)


def _emit_root(root_kind: str, root_arg: str | None) -> str:
    if root_kind == "frontmost":
        return textwrap.dedent("""
            import ApplicationServices as AS
            _sysw = AS.AXUIElementCreateSystemWide()
            _, el = AS.AXUIElementCopyAttributeValue(_sysw, "AXFocusedApplication", None)
            if el is None:
                print("")
                raise SystemExit(0)
        """).strip()
    elif root_kind == "process":
        return textwrap.dedent(f"""
            import ApplicationServices as AS
            import subprocess
            try:
                _pid = int(subprocess.check_output(["pgrep", "-x", "-i", {root_arg!r}]).split()[0])
            except Exception:
                print("")
                raise SystemExit(0)
            el = AS.AXUIElementCreateApplication(_pid)
        """).strip()
    raise ValueError(f"unknown root_kind={root_kind!r}")


# ---------- Per-shape converters -------------------------------------------

def _try_attr_of_path(script: str) -> str | None:
    """Pattern: get value of attribute "AX..." of <PATH>."""
    m = re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+get\s+value\s+of\s+attribute\s+"(AX[A-Za-z]+)"\s+of\s+(.+)\s*$',
        script,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    attr = m.group(1)
    parsed = _parse_path(m.group(2))
    if parsed is None:
        return None
    segs, root_kind, root_arg = parsed
    code = _emit_root(root_kind, root_arg) + "\n" + _emit_walk(segs) + "\n" + textwrap.dedent(f"""
        _, _val = AS.AXUIElementCopyAttributeValue(el, "{attr}", None)
        print(_val if _val is not None else "")
    """).strip()
    return _wrap_python(code)


def _try_value_of_named_element(script: str) -> str | None:
    """Pattern: tell process "X" to get value of <ELEMENT> of <PATH>.

    The element is the leaf and `value of <element>` becomes AXValue of it.
    """
    m = re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+tell\s+process\s+"([^"]+)"\s+to\s+get\s+value\s+of\s+(.+)\s*$',
        script,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    process = m.group(1)
    full_path = m.group(2)  # e.g. 'pop up button "Default Language:" of window "General"'

    # The full element path goes from leaf to a window/element root inside the process.
    # We treat the entire chain as a path with NO outer "of process X" — process is
    # explicit. Then walk from AXUIElementCreateApplication(pid).
    segs: list[tuple[str, str | None, int | None]] = []
    for chunk in re.split(r"\s+of\s+", full_path.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        mm = _PATH_SEG_RE.match(chunk)
        if not mm:
            return None
        kind = mm.group(1).lower()
        if kind not in _ROLE_MAP:
            return None
        segs.append((kind, mm.group(2), int(mm.group(3)) if mm.group(3) else None))

    if not segs:
        return None

    code = _emit_root("process", process) + "\n" + _emit_walk(segs) + "\n" + textwrap.dedent("""
        _, _val = AS.AXUIElementCopyAttributeValue(el, "AXValue", None)
        print(_val if _val is not None else "")
    """).strip()
    return _wrap_python(code)


def _try_front_process_name(script: str) -> str | None:
    """Pattern: get name of first process whose frontmost is true."""
    if not re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+get\s+name\s+of\s+first\s+process\s+whose\s+frontmost\s+is\s+true\s*$',
        script,
        re.IGNORECASE,
    ):
        return None
    return _wrap_python("""
        import ApplicationServices as AS
        sysw = AS.AXUIElementCreateSystemWide()
        _, app = AS.AXUIElementCopyAttributeValue(sysw, "AXFocusedApplication", None)
        if app is None:
            print("")
        else:
            _, name = AS.AXUIElementCopyAttributeValue(app, "AXTitle", None)
            print(name if name is not None else "")
    """)


def _try_keystroke(script: str) -> str | None:
    """Pattern: keystroke "X" [using {modifier list}].

    macOSWorld pre_command lines use this almost exclusively for global
    shortcuts like Ctrl+Cmd+F (fullscreen). We synthesize the key event via
    Quartz CGEvent — synthetic key events still need Accessibility (the
    "post events" right), and Python has it.
    """
    m = re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+keystroke\s+"([^"]+)"(?:\s+using\s+\{([^}]+)\})?\s*$',
        script,
        re.IGNORECASE,
    )
    if not m:
        return None
    key_str = m.group(1)
    mods_raw = m.group(2) or ""
    if len(key_str) != 1:
        # multi-character keystroke would need typing each char; punt for now.
        return None

    mod_flags = []
    if "command down" in mods_raw or "cmd down" in mods_raw:
        mod_flags.append("Quartz.kCGEventFlagMaskCommand")
    if "shift down" in mods_raw:
        mod_flags.append("Quartz.kCGEventFlagMaskShift")
    if "option down" in mods_raw or "alt down" in mods_raw:
        mod_flags.append("Quartz.kCGEventFlagMaskAlternate")
    if "control down" in mods_raw or "ctrl down" in mods_raw:
        mod_flags.append("Quartz.kCGEventFlagMaskControl")

    flags_expr = " | ".join(mod_flags) if mod_flags else "0"

    return _wrap_python(f"""
        import Quartz
        # Map a single character to its US-keyboard virtual key code.
        _LETTERS = "abcdefghijklmnopqrstuvwxyz"
        _LETTER_CODES = [0,11,8,2,14,3,5,4,34,38,40,37,46,45,31,35,12,15,1,17,32,9,13,7,16,6]
        _DIGITS = {{"1":18,"2":19,"3":20,"4":21,"5":23,"6":22,"7":26,"8":28,"9":25,"0":29}}
        ch = {key_str!r}.lower()
        if ch in _LETTERS:
            keycode = _LETTER_CODES[_LETTERS.index(ch)]
        elif ch in _DIGITS:
            keycode = _DIGITS[ch]
        else:
            print("")
            raise SystemExit(0)
        flags = {flags_expr}
        for is_down in (True, False):
            ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, is_down)
            if flags:
                Quartz.CGEventSetFlags(ev, flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
    """)


def _try_attributes_of_path(script: str) -> str | None:
    """Pattern: get value of attributes (plural) of <PATH>.

    The plural form returns every attribute name + value. macOSWorld
    verifiers grep for a specific value (e.g. "300%"); dumping all
    attributes lets the same grep work against our Python output.
    """
    m = re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+get\s+value\s+of\s+attributes\s+of\s+(.+)\s*$',
        script,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    parsed = _parse_path(m.group(1))
    if parsed is None:
        return None
    segs, root_kind, root_arg = parsed
    code = _emit_root(root_kind, root_arg) + "\n" + _emit_walk(segs) + "\n" + textwrap.dedent("""
        _err, _names = AS.AXUIElementCopyAttributeNames(el, None)
        for _name in (_names or []):
            _, _v = AS.AXUIElementCopyAttributeValue(el, _name, None)
            print(f"{_name}={_v}")
    """).strip()
    return _wrap_python(code)


def _try_dock_items(script: str) -> str | None:
    """Pattern: name of every UI element of list 1 of application process "Dock"."""
    if not re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+set\s+\w+\s+to\s+name\s+of\s+every\s+UI\s+element\s+of\s+list\s+1\s+of\s+application\s+process\s+"Dock"\s*$',
        script,
        re.IGNORECASE,
    ):
        return None
    return _wrap_python("""
        import ApplicationServices as AS
        import subprocess
        try:
            pid = int(subprocess.check_output(["pgrep", "-x", "Dock"]).split()[0])
        except Exception:
            print("")
            raise SystemExit(0)
        app = AS.AXUIElementCreateApplication(pid)
        _, kids = AS.AXUIElementCopyAttributeValue(app, "AXChildren", None)
        names = []
        def walk(el):
            _, role = AS.AXUIElementCopyAttributeValue(el, "AXRole", None)
            if role == "AXList":
                _, items = AS.AXUIElementCopyAttributeValue(el, "AXChildren", None)
                for it in (items or []):
                    _, t = AS.AXUIElementCopyAttributeValue(it, "AXTitle", None)
                    if t:
                        names.append(t)
                return
            _, sub = AS.AXUIElementCopyAttributeValue(el, "AXChildren", None)
            for s in (sub or []):
                walk(s)
        for k in (kids or []):
            walk(k)
        print(", ".join(names))
    """)


_CONVERTERS = (
    _try_attr_of_path,
    _try_attributes_of_path,
    _try_value_of_named_element,
    _try_front_process_name,
    _try_dock_items,
    _try_keystroke,
)


def _applescript_to_shell(script: str) -> str | None:
    """Try every converter; return shell substitute or None if none match."""
    for fn in _CONVERTERS:
        out = fn(script)
        if out is not None:
            return out
    return None


# ---------- Public API -----------------------------------------------------

def transpile(text: str) -> tuple[str, int]:
    """Rewrite osascript+System Events lines in `text` to python3.12 calls.

    Returns (rewritten_text, num_substitutions). Lines that don't match a
    known pattern are left untouched.
    """
    count = 0

    def _replace(m: re.Match) -> str:
        nonlocal count
        applescript = m.group(1)
        # Decode the bash-escape form: in the on-disk shape `'\''` becomes
        # a literal single quote in the AppleScript content. The regex
        # captures everything between the openers, but the captured group
        # may itself contain `'\''` if there were embedded quotes. Decode
        # those before parsing.
        decoded = applescript.replace(r"'\''", "'")
        replacement = _applescript_to_shell(decoded)
        if replacement is None:
            return m.group(0)
        count += 1
        return replacement

    rewritten = _OSASCRIPT_RE.sub(_replace, text)
    return rewritten, count


def needs_rewrite(text: str) -> bool:
    """Quick predicate: does `text` contain at least one osascript+System Events
    pattern we'd transpile? Lets callers skip the work entirely when there's
    nothing to do."""
    return 'tell application "System Events"' in text and "osascript" in text
