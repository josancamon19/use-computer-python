"""Unit tests for ax_transpile.

Asserts that each of the 6 recognized AppleScript shapes emits a shell
snippet that invokes /usr/local/bin/ax_helper.py via cua-server's
run_command — and that no PyObjC / ApplicationServices string leaks into
the emitted output (that was the fragile pattern we're replacing).
"""

from __future__ import annotations

import base64
import json
import re
import shlex

import pytest

from mmini.ax_transpile import (
    DEFAULT_OSASCRIPT_TIMEOUT_S,
    HELPER,
    PRE_COMMAND_OSASCRIPT_TIMEOUT_S,
    needs_rewrite,
    transpile,
)

# Matches `echo <B64> | base64 -d | bash` anywhere in a string — emission
# can be embedded inside `bash -c '...'` or appear multiple times in one
# text, so we don't anchor the regex.
_EMIT_RE = re.compile(r"echo ([A-Za-z0-9+/=]+) \| base64 -d \| bash")


def _decode_emissions(emitted: str) -> list[str]:
    """Find every `echo <B64> | base64 -d | bash` emission in the text and
    return the decoded payload scripts."""
    return [base64.b64decode(m.group(1)).decode() for m in _EMIT_RE.finditer(emitted)]


def _decode_emission(emitted: str) -> str:
    """First (and usually only) emission's decoded payload."""
    payloads = _decode_emissions(emitted)
    assert payloads, f"no emission found in: {emitted!r}"
    return payloads[0]


def _extract_helper_argv(emitted: str) -> list[str]:
    """Pull the run_command body out of the decoded payload and return the
    argv that'll run on the VM."""
    payload = _decode_emission(emitted)
    # Payload assigns the JSON body to $B via `echo <body_b64> | base64 -d`.
    m = re.search(r"B=\$\(echo ([A-Za-z0-9+/=]+) \| base64 -d\)", payload)
    assert m, f"no $B assignment in payload: {payload!r}"
    body_json = base64.b64decode(m.group(1)).decode()
    body = json.loads(body_json)
    assert body["command"] == "run_command"
    return shlex.split(body["params"]["command"])


def _assert_no_pyobjc(emitted: str) -> None:
    """The emission itself is opaque base64, but no decoded payload may
    contain PyObjC imports — those were the thing we're replacing."""
    for payload in _decode_emissions(emitted):
        assert "ApplicationServices" not in payload
        assert "AXUIElementCreate" not in payload


def _assert_no_raw_quotes(emitted: str) -> None:
    """The emission replacement itself (not the surrounding text) must
    contain no single/double quotes, so it's embeddable inside
    `bash -c '...'` wrappers. Test by checking every matched emission is
    pure base64 alphabet."""
    for m in _EMIT_RE.finditer(emitted):
        assert "'" not in m.group(0)
        assert '"' not in m.group(0)


# ---- Coverage tests -------------------------------------------------------


def test_frontmost_process_name():
    src = (
        'osascript -e \'tell application "System Events" to get name of '
        "first process whose frontmost is true'"
    )
    out, n = transpile(src)
    assert n == 1
    _assert_no_pyobjc(out)
    _assert_no_raw_quotes(out)
    argv = _extract_helper_argv(out)
    assert argv == [HELPER, "frontmost_name"]


def test_attr_of_path_frontmost_root():
    src = (
        'osascript -e \'tell application "System Events" to get value of '
        'attribute "AXTitle" of window 1 of (first application process '
        "whose frontmost is true)'"
    )
    out, n = transpile(src)
    assert n == 1
    _assert_no_pyobjc(out)
    argv = _extract_helper_argv(out)
    assert argv[0:3] == [HELPER, "attr", "AXTitle"]
    path = json.loads(argv[3])
    assert path[0] == {"root": "frontmost"}
    assert path[1] == {"kind": "window", "index": 1}


def test_attr_of_path_process_root():
    src = (
        'osascript -e \'tell application "System Events" to get value of '
        'attribute "AXValue" of pop up button "Default Language:" of '
        'window "General" of process "Script Editor"\''
    )
    out, n = transpile(src)
    assert n == 1
    _assert_no_pyobjc(out)
    argv = _extract_helper_argv(out)
    assert argv[0:3] == [HELPER, "attr", "AXValue"]
    path = json.loads(argv[3])
    assert path[0] == {"root": "process", "name": "Script Editor"}
    # Root → leaf ordering: window → pop up button.
    assert path[1] == {"kind": "window", "name": "General"}
    assert path[2] == {"kind": "pop up button", "name": "Default Language:"}


def test_attributes_of_path():
    src = (
        'osascript -e \'tell application "System Events" to get value of '
        'attributes of window 1 of process "Finder"\''
    )
    out, n = transpile(src)
    assert n == 1
    _assert_no_pyobjc(out)
    argv = _extract_helper_argv(out)
    assert argv[0:2] == [HELPER, "attrs"]
    path = json.loads(argv[2])
    assert path[0] == {"root": "process", "name": "Finder"}
    assert path[1] == {"kind": "window", "index": 1}


def test_value_of_named_element():
    src = (
        'osascript -e \'tell application "System Events" to tell process '
        '"Safari" to get value of text field 1 of window 1\''
    )
    out, n = transpile(src)
    assert n == 1
    _assert_no_pyobjc(out)
    argv = _extract_helper_argv(out)
    assert argv[0:3] == [HELPER, "value", "Safari"]
    path = json.loads(argv[3])
    # Root → leaf: window → text field.
    assert path[0] == {"kind": "window", "index": 1}
    assert path[1] == {"kind": "text field", "index": 1}


def test_dock_items():
    src = (
        'osascript -e \'tell application "System Events" to set docked to '
        'name of every UI element of list 1 of application process "Dock"\''
    )
    out, n = transpile(src)
    assert n == 1
    _assert_no_pyobjc(out)
    argv = _extract_helper_argv(out)
    assert argv == [HELPER, "dock_items"]


def test_keystroke_no_mods():
    src = 'osascript -e \'tell application "System Events" to keystroke "a"\''
    out, n = transpile(src)
    assert n == 1
    _assert_no_pyobjc(out)
    argv = _extract_helper_argv(out)
    assert argv == [HELPER, "keystroke", "a"]


def test_keystroke_with_mods():
    src = (
        'osascript -e \'tell application "System Events" to keystroke "f" '
        "using {command down, control down}'"
    )
    out, n = transpile(src)
    assert n == 1
    _assert_no_pyobjc(out)
    argv = _extract_helper_argv(out)
    assert argv[0:3] == [HELPER, "keystroke", "f"]
    assert "cmd" in argv[3:]
    assert "ctrl" in argv[3:]


# ---- Pass-through + bash-escape form --------------------------------------


def test_fallback_wraps_non_system_events():
    """Non-System-Events `tell application "X"` lines now get wrapped with
    `with timeout of N seconds` by the fallback converter — prevents
    alarm-kill on Notes/Keynote/Contacts/Reminders/etc."""
    src = "osascript -e 'tell application \"Finder\" to get name of startup disk'"
    out, n = transpile(src)
    assert n == 1
    _assert_no_raw_quotes(out)
    payload = _decode_emission(out)
    # Decoded payload must contain the timeout wrapper
    assert "with timeout of" in payload
    assert "end timeout" in payload
    # And the original body
    assert 'tell application "Finder" to get name of startup disk' in payload


def test_fallback_wraps_data_heavy_app_queries():
    """The `tell application "Notes"/"Contacts"/"Keynote"` queries that
    caused the 2026-04-14 alarm-kills get wrapped by the fallback."""
    cases = [
        ('tell application "Notes" to count of notes', 'tell application "Notes"'),
        ('tell application "Contacts" to count of people', 'tell application "Contacts"'),
        ('tell application "Keynote" to get width of document 1', "of document 1"),
        (
            'tell application "Reminders" to return (exists (list "Shopping")) as string',
            "Reminders",
        ),
    ]
    for body, marker in cases:
        src = f"osascript -e '{body}'"
        out, n = transpile(src)
        assert n == 1, f"expected fallback wrap for: {src!r}"
        payload = _decode_emission(out)
        assert "with timeout of" in payload
        assert marker in payload


def test_fallback_wraps_unrecognized_system_events_pattern():
    # `set value` wasn't in our specialised whitelist — still gets wrapped.
    src = (
        'osascript -e \'tell application "System Events" to set value of '
        'text field 1 of window 1 of process "X" to "hello"\''
    )
    out, n = transpile(src)
    assert n == 1
    payload = _decode_emission(out)
    assert "with timeout of" in payload


def test_bash_escape_quote_form():
    """test.sh files embed osascript inside bash -c '...', using the
    '\\'' escape sequence. The transpiler decodes that so the inner
    regex matches."""
    inner = r'tell application "System Events" to get name of first process whose frontmost is true'
    # Outer `bash -c '...'` with the escape.
    src = f"bash -c 'osascript -e '\\''{inner}'\\'' | head -1'"
    out, n = transpile(src)
    assert n == 1, f"expected transpile, got: {out!r}"
    argv = _extract_helper_argv(out)
    assert argv == [HELPER, "frontmost_name"]


def test_multiple_osascript_in_one_text():
    src = (
        "echo one; "
        'osascript -e \'tell application "System Events" to get name of first process '
        "whose frontmost is true'; "
        "echo two; "
        'osascript -e \'tell application "System Events" to keystroke "a"\''
    )
    out, n = transpile(src)
    assert n == 2
    _assert_no_pyobjc(out)


def test_needs_rewrite_predicate():
    # Any osascript -e '...' call triggers a rewrite now (fallback wraps it
    # in `with timeout of N seconds`).
    assert needs_rewrite("osascript -e 'tell application \"System Events\" to beep'")
    assert needs_rewrite("osascript -e 'tell application \"Finder\" to beep'")
    assert not needs_rewrite("echo hello")


def test_multi_e_osascript():
    """osascript -e '...' -e '...' with multiple scripts: all bodies get
    combined and wrapped with timeout. The emission must NOT contain raw
    'tell application ...' as a bare bash command."""
    src = (
        "osascript "
        "-e 'tell application \"Keynote\" to make new document' "
        '-e \'tell application "Keynote" to set the object text of slide 1 to "Hello"\''
    )
    out, n = transpile(src)
    assert n == 1
    _assert_no_raw_quotes(out)
    payload = _decode_emission(out)
    # Both bodies must appear in the decoded payload
    assert 'tell application "Keynote" to make new document' in payload
    assert 'tell application "Keynote" to set the object text' in payload
    # Must be wrapped with timeout
    assert "with timeout of" in payload
    # The payload must NOT start with 'tell' (which would mean bare bash execution)
    assert not payload.startswith("tell")


def test_fallback_timeout_param():
    """transpile(text, fallback_timeout_s=N) controls the `with timeout of N`
    value in the emitted payload. Pre_commands use 45s; verifiers use 5s."""
    src = "osascript -e 'tell application \"Notes\" to count of notes'"

    out_verifier, _ = transpile(src)
    payload_verifier = _decode_emission(out_verifier)
    assert f"with timeout of {DEFAULT_OSASCRIPT_TIMEOUT_S} seconds" in payload_verifier

    out_pre, _ = transpile(src, fallback_timeout_s=PRE_COMMAND_OSASCRIPT_TIMEOUT_S)
    payload_pre = _decode_emission(out_pre)
    assert f"with timeout of {PRE_COMMAND_OSASCRIPT_TIMEOUT_S} seconds" in payload_pre


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
