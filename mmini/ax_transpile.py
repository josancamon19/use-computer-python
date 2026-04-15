"""
Rewrite `osascript -e 'tell application "System Events" ...'` patterns into
shell calls that invoke `/usr/local/bin/ax_helper.py` via cua-server's
`run_command` endpoint. The helper (baked into base-macos) does the actual
Accessibility walk with `AXUIElementSetMessagingTimeout` on every element,
so a wedged target can't alarm-kill the verifier the way inline PyObjC
could.

Why route through cua-server's /cmd run_command? Because that responsibility
chain (launchd → cua-server → bash → python3.12) is what makes the system
TCC Accessibility grant on python3.12 actually apply. SSH-backed exec puts
`sshd-keygen-wrapper` in the chain and TCC denies AX with -25211.

Why not inline PyObjC? Previously we emitted base64-wrapped python snippets
at 5 call sites with no `SetMessagingTimeout`. 441 trials alarm-killed
because a wedged AX call couldn't be preempted from outside the framework.
Moving the code into a single baked helper means one place to harden.

Coverage
--------
Six AppleScript shapes (~100% of the macOSWorld AX-blocked verifier
patterns):

1.  `attribute "AX..." of <PATH>` — attr read, path walked from frontmost
    or a named process.
2.  `attributes of <PATH>` — dump all attribute name=value pairs.
3.  `tell process "X" to get value of <ELEMENT> of <PATH>` — AXValue of a
    leaf inside a process.
4.  `get name of first process whose frontmost is true`
5.  `name of every UI element of list 1 of application process "Dock"`
6.  `keystroke "X" [using {modifier list}]` — synthesize CGEvent.

Lines that don't match any recognized shape are passed through unchanged.

What this does NOT handle
-------------------------
* AppleScript with conditionals or repeats
* `set value of` (we only do reads)
* Multi-character `keystroke` strings (only single chars)
None of the classified macOSWorld verifiers need these.
"""

from __future__ import annotations

import base64
import json
import re
import shlex

# ---- Pattern parsing ------------------------------------------------------

# AppleScript element kind → AX role. Must stay in sync with
# scripts/images/ax_helper.py::_role_for_kind().
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
    "ui element":     None,
}

# Sort kinds by length descending so "menu button" wins over "button".
_KINDS_SORTED = sorted(_ROLE_MAP.keys(), key=len, reverse=True)
_KIND_ALT = "|".join(re.escape(k) for k in _KINDS_SORTED)
_PATH_SEG_RE = re.compile(
    r'(' + _KIND_ALT + r')\s+(?:"([^"]+)"|(\d+))',
    re.IGNORECASE,
)

# osascript -e '...' wrapped in either `'...'` or the bash-escape form
# `'\''...'\''` that test.sh files use to embed osascript inside bash -c.
_OSASCRIPT_RE = re.compile(
    r"""osascript\s+-e\s+(?:'\\''|')(.*?)(?:'\\''|')""",
    re.DOTALL,
)


def _parse_path(path_str: str) -> tuple[list[dict], dict] | None:
    """Parse `... of (first application process whose frontmost is true)` or
    `... of process "X"` or just `... of window N`.

    Returns (segments_root_first, root_spec) where root_spec is
    {"root": "frontmost"} or {"root": "process", "name": "X"}. Segments are
    ordered root → leaf as dicts with keys {"kind", "name"?, "index"?}.

    Returns None if we can't parse the path.
    """
    s = path_str.strip()

    m = re.search(
        r"\(?\s*first\s+application\s+process\s+whose\s+frontmost\s+is\s+true\s*\)?\s*$",
        s,
        re.IGNORECASE,
    )
    if m:
        root: dict = {"root": "frontmost"}
        s = s[: m.start()].rstrip()
        s = re.sub(r"\s+of\s*$", "", s, flags=re.IGNORECASE)
    else:
        m = re.search(
            r'(?:application\s+)?process\s+"([^"]+)"\s*$',
            s,
            re.IGNORECASE,
        )
        if not m:
            return None
        root = {"root": "process", "name": m.group(1)}
        s = s[: m.start()].rstrip()
        s = re.sub(r"\s+of\s*$", "", s, flags=re.IGNORECASE)

    # AppleScript writes segments leaf-first, separated by " of ". Reverse
    # into root→leaf.
    segs_leaf_first: list[dict] = []
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
            seg: dict = {"kind": kind}
            if mm.group(2) is not None:
                seg["name"] = mm.group(2)
            elif mm.group(3) is not None:
                seg["index"] = int(mm.group(3))
            segs_leaf_first.append(seg)

    return list(reversed(segs_leaf_first)), root


def _parse_leaf_path(path_str: str) -> list[dict] | None:
    """Parse a path inside `tell process "X" to get value of <PATH>` — no
    root suffix, just a leaf-first chain of segments. Returns root→leaf."""
    segs_leaf_first: list[dict] = []
    for chunk in re.split(r"\s+of\s+", path_str.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        mm = _PATH_SEG_RE.match(chunk)
        if not mm:
            return None
        kind = mm.group(1).lower()
        if kind not in _ROLE_MAP:
            return None
        seg: dict = {"kind": kind}
        if mm.group(2) is not None:
            seg["name"] = mm.group(2)
        elif mm.group(3) is not None:
            seg["index"] = int(mm.group(3))
        segs_leaf_first.append(seg)
    return list(reversed(segs_leaf_first)) if segs_leaf_first else None


# ---- Emission -------------------------------------------------------------

HELPER = "/usr/local/bin/ax_helper.py"


def _emit_helper_call(op: str, *args: str) -> str:
    """Emit a shell snippet that POSTs to cua-server's /cmd run_command,
    invokes ax_helper.py, and prints stdout.

    The whole emission is base64-wrapped and piped through `base64 -d |
    bash` so the replacement contains ZERO single/double quotes in its
    payload surface. Verifier test.sh files wrap osascript calls inside
    `bash -c '...'` — any raw single quote in our replacement would break
    the outer quoting. Base64 alphabet (A-Z/a-z/0-9/+//=) never collides.
    """
    argv = [HELPER, op, *args]
    cmd = " ".join(shlex.quote(a) for a in argv)
    body = json.dumps({"command": "run_command", "params": {"command": cmd}})
    body_b64 = base64.b64encode(body.encode()).decode()

    # Payload executed by bash after decoding.
    #
    # Critical: do NOT use `python3 <<HEREDOC` to pass the parser source —
    # heredoc input hijacks python's stdin, so the curl pipe goes nowhere
    # and `sys.stdin.read()` returns empty (or the heredoc bytes). Instead
    # we base64-decode the parser at runtime into `python3 -c "$P"`, which
    # leaves python's stdin free for the curl pipe.
    parser_py = (
        "import sys, json\n"
        "raw = sys.stdin.read()\n"
        "for line in raw.splitlines():\n"
        "    line = line.strip()\n"
        "    if line.startswith('data:'):\n"
        "        line = line[5:].strip()\n"
        "    if not line:\n"
        "        continue\n"
        "    try:\n"
        "        d = json.loads(line)\n"
        "    except Exception:\n"
        "        continue\n"
        "    print(d.get('stdout', '').rstrip())\n"
        "    break\n"
    )
    parser_b64 = base64.b64encode(parser_py.encode()).decode()
    payload = (
        f"B=$(echo {body_b64} | base64 -d); "
        f"P=$(echo {parser_b64} | base64 -d); "
        f"curl -s -X POST http://127.0.0.1:8000/cmd "
        f"-H Content-Type:application/json "
        f'--data-raw "$B" 2>/dev/null '
        f'| python3 -c "$P"'
    )
    payload_b64 = base64.b64encode(payload.encode()).decode()
    return f"echo {payload_b64} | base64 -d | bash"


# ---- Per-shape converters -------------------------------------------------

def _try_attr_of_path(script: str) -> str | None:
    """get value of attribute "AX..." of <PATH>"""
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
    segs, root = parsed
    path_json = json.dumps([root, *segs])
    return _emit_helper_call("attr", attr, path_json)


def _try_attributes_of_path(script: str) -> str | None:
    """get value of attributes of <PATH>"""
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
    segs, root = parsed
    path_json = json.dumps([root, *segs])
    return _emit_helper_call("attrs", path_json)


def _try_value_of_named_element(script: str) -> str | None:
    """tell process "X" to get value of <LEAF> of <PATH>"""
    m = re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+tell\s+process\s+"([^"]+)"\s+to\s+get\s+value\s+of\s+(.+)\s*$',
        script,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    process = m.group(1)
    segs = _parse_leaf_path(m.group(2))
    if segs is None:
        return None
    return _emit_helper_call("value", process, json.dumps(segs))


def _try_front_process_name(script: str) -> str | None:
    """get name of first process whose frontmost is true"""
    if not re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+get\s+name\s+of\s+first\s+process\s+whose\s+frontmost\s+is\s+true\s*$',
        script,
        re.IGNORECASE,
    ):
        return None
    return _emit_helper_call("frontmost_name")


def _try_dock_items(script: str) -> str | None:
    """set VAR to name of every UI element of list 1 of application process "Dock" """
    if not re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+set\s+\w+\s+to\s+name\s+of\s+every\s+UI\s+element\s+of\s+list\s+1\s+of\s+application\s+process\s+"Dock"\s*$',
        script,
        re.IGNORECASE,
    ):
        return None
    return _emit_helper_call("dock_items")


def _try_keystroke(script: str) -> str | None:
    """keystroke "X" [using {modifier list}]. Single-character only."""
    m = re.match(
        r'\s*tell\s+application\s+"System Events"\s+to\s+keystroke\s+"([^"]+)"(?:\s+using\s+\{([^}]+)\})?\s*$',
        script,
        re.IGNORECASE,
    )
    if not m:
        return None
    key = m.group(1)
    if len(key) != 1:
        return None
    mods_raw = (m.group(2) or "").lower()
    mods: list[str] = []
    if "command down" in mods_raw or "cmd down" in mods_raw:
        mods.append("cmd")
    if "shift down" in mods_raw:
        mods.append("shift")
    if "option down" in mods_raw or "alt down" in mods_raw:
        mods.append("alt")
    if "control down" in mods_raw or "ctrl down" in mods_raw:
        mods.append("ctrl")
    return _emit_helper_call("keystroke", key, *mods)


# Default timeout applied to every osascript body that isn't otherwise
# specialised. 5s is well below the outer harbor alarm (28s) and well above
# the ~1s a responsive Apple Events target needs.
DEFAULT_OSASCRIPT_TIMEOUT_S = 5

# Timeout used when transpiling pre_command lines (seeding VM state). Notes and
# iWork apps can take 8-20s to respond cold; we need state to actually be
# written, so we allow a generous budget. Cap at 25s — cua-server's run_command
# endpoint has a hard 30s limit; we need 5s margin to avoid 500 errors.
PRE_COMMAND_OSASCRIPT_TIMEOUT_S = 25


def _emit_with_timeout(applescript_body: str, timeout_s: int = DEFAULT_OSASCRIPT_TIMEOUT_S) -> str:
    """Wrap an arbitrary AppleScript body in `with timeout of N seconds`.

    Used as the fallback for `osascript -e '<body>'` calls that none of the
    specialised converters matched — the many `tell application "Notes"` /
    "Keynote" / "Contacts" / "Reminders" patterns that hang on fresh VMs
    because the target app waits on iCloud, an unopened document, or a
    missing UI. Live-verified: a wrapped query returns
    `-1712 (AppleEvent timed out)` at exactly N seconds instead of hanging
    past the outer alarm. Caller's `grep -qi 'true'` then falls through to
    score 0 cleanly rather than alarm-killing the trial.

    Emission is base64-wrapped so it's safe inside any bash-c wrapper; the
    body goes through a single-quoted heredoc ('__AS_EOF__') so embedded
    quotes in the AppleScript pass through verbatim without further escaping.
    """
    script = (
        f"osascript <<'__AS_EOF__'\n"
        f"with timeout of {timeout_s} seconds\n"
        f"{applescript_body}\n"
        f"end timeout\n"
        f"__AS_EOF__\n"
    )
    script_b64 = base64.b64encode(script.encode()).decode()
    return f"echo {script_b64} | base64 -d | bash"


_CONVERTERS = (
    _try_attr_of_path,
    _try_attributes_of_path,
    _try_value_of_named_element,
    _try_front_process_name,
    _try_dock_items,
    _try_keystroke,
)


def _applescript_to_shell(script: str, fallback_timeout_s: int = DEFAULT_OSASCRIPT_TIMEOUT_S) -> str | None:
    """Try each specialised converter; fall back to timeout-wrapped osascript.

    `fallback_timeout_s` controls the `with timeout of N seconds` wrapper used
    when no specialised converter matches. Callers transpiling pre_command lines
    should pass PRE_COMMAND_OSASCRIPT_TIMEOUT_S (30s) so state-seeding calls
    don't get killed before the app responds. Verifier calls use the default 5s
    (fail fast = score 0, no alarm-kill).
    """
    for fn in _CONVERTERS:
        out = fn(script)
        if out is not None:
            return out
    # Terminal fallback: wrap with timeout so the call never hangs forever.
    return _emit_with_timeout(script.strip(), timeout_s=fallback_timeout_s)


# ---- Public API -----------------------------------------------------------

def transpile(text: str, fallback_timeout_s: int = DEFAULT_OSASCRIPT_TIMEOUT_S) -> tuple[str, int]:
    """Rewrite osascript+System Events lines in `text` to ax_helper calls.

    Returns (rewritten_text, num_substitutions). Lines that don't match a
    known pattern are left untouched.

    `fallback_timeout_s` sets the `with timeout of N seconds` applied to
    osascript bodies that hit the fallback converter. Pass
    PRE_COMMAND_OSASCRIPT_TIMEOUT_S when transpiling pre_command lines.
    """
    count = 0

    def _replace(m: re.Match) -> str:
        nonlocal count
        applescript = m.group(1)
        decoded = applescript.replace(r"'\''", "'")
        replacement = _applescript_to_shell(decoded, fallback_timeout_s=fallback_timeout_s)
        if replacement is None:
            return m.group(0)
        count += 1
        return replacement

    return _OSASCRIPT_RE.sub(_replace, text), count


def needs_rewrite(text: str) -> bool:
    """Any `osascript -e` invocation gets rewritten now (the fallback
    converter wraps everything with `with timeout of N seconds`)."""
    return bool(_OSASCRIPT_RE.search(text))
