"""
Tests every SDK function against a running gateway.
Saves screenshots and recording to results/.

Usage:
    cd sdk && uv run python examples/test.py
"""

import os
import time

from mmini import Mmini, Seed

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(RESULTS, exist_ok=True)

OK = "\033[32mOK\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def test(name, fn):
    try:
        result = fn()
        print(f"  {OK}  {name}")
        return result
    except Exception as e:
        print(f"  {FAIL} {name}: {e}")
        return None


def save(name, data):
    path = os.path.join(RESULTS, name)
    with open(path, "wb") as f:
        f.write(data)
    print(f"       saved results/{name} ({len(data)} bytes)")


client = Mmini()
sandbox = None

try:
    # ============================================================
    # Sandbox lifecycle + seed commands
    # ============================================================
    sandbox = test(
        "create sandbox with seed",
        lambda: client.create(seed=[
            Seed.launch("Finder"),
        ]),
    )
    if not sandbox:
        raise SystemExit("Cannot continue without a sandbox")

    print(f"       id:  {sandbox.sandbox_id}")
    print(f"       vnc: {sandbox.vnc_url}")

    test("get sandbox", lambda: client.get(sandbox.sandbox_id))

    # ============================================================
    # Display
    # ============================================================
    info = test("display.get_info", lambda: sandbox.display.get_info())
    if info:
        print(f"       {info}")
    test("display.get_windows", lambda: sandbox.display.get_windows())

    # ============================================================
    # Screenshots
    # ============================================================
    img = test("screenshot.take_full_screen", lambda: sandbox.screenshot.take_full_screen())
    if img:
        assert len(img) > 1000
        save("01_initial.png", img)

    jpeg = test("screenshot.take_compressed(jpeg, q=50)", lambda: sandbox.screenshot.take_compressed(format="jpeg", quality=50))
    if jpeg:
        save("02_compressed.jpg", jpeg)

    region = test("screenshot.take_region(0,0,200,200)", lambda: sandbox.screenshot.take_region(0, 0, 200, 200))
    if region:
        save("03_region.png", region)

    # ============================================================
    # Mouse
    # ============================================================
    pos = test("mouse.get_position", lambda: sandbox.mouse.get_position())
    if pos:
        print(f"       {pos}")

    test("mouse.move(500, 400)", lambda: sandbox.mouse.move(500, 400))
    test("mouse.click(512, 400)", lambda: sandbox.mouse.click(512, 400))
    test("mouse.click right", lambda: sandbox.mouse.click(512, 400, button="right"))
    time.sleep(0.5)
    # Dismiss context menu
    test("keyboard.press(escape) - dismiss menu", lambda: sandbox.keyboard.press("escape"))

    test("mouse.click double", lambda: sandbox.mouse.click(512, 400, double=True))
    test("mouse.scroll(512, 400, down, 3)", lambda: sandbox.mouse.scroll(512, 400, "down", 3))
    test("mouse.drag(100,100 -> 300,300)", lambda: sandbox.mouse.drag(100, 100, 300, 300))

    # ============================================================
    # Keyboard + Spotlight
    # ============================================================
    test("keyboard.hotkey(command+space)", lambda: sandbox.keyboard.hotkey("command+space"))
    time.sleep(1)

    img = test("screenshot - spotlight", lambda: sandbox.screenshot.take_full_screen())
    if img:
        save("04_spotlight.png", img)

    test("keyboard.type(TextEdit)", lambda: sandbox.keyboard.type("TextEdit"))
    time.sleep(0.5)
    test("keyboard.press(enter)", lambda: sandbox.keyboard.press("enter"))
    time.sleep(2)

    test("mouse.click(512, 400) - TextEdit body", lambda: sandbox.mouse.click(512, 400))
    time.sleep(0.5)
    test("keyboard.type(Hello from mmini!)", lambda: sandbox.keyboard.type("Hello from mmini!"))
    time.sleep(0.5)

    img = test("screenshot - after typing", lambda: sandbox.screenshot.take_full_screen())
    if img:
        save("05_textedit.png", img)

    # ============================================================
    # Act endpoint (action + screenshot in one round trip)
    # ============================================================
    result = test(
        "act(click + screenshot)",
        lambda: sandbox.act({"type": "click", "x": 300, "y": 300}, screenshot_after=True),
    )
    if result and result.get("screenshot"):
        save("06_act_screenshot.png", result["screenshot"])

    # ============================================================
    # File upload
    # ============================================================
    test(
        "upload_bytes(hello.txt)",
        lambda: sandbox.upload_bytes(b"Hello from file upload!", "~/Desktop/hello.txt"),
    )
    # Verify file exists
    verify = test(
        "verify uploaded file",
        lambda: sandbox._http.post(
            f"{sandbox._prefix}/shell",
            json={"command": "cat ~/Desktop/hello.txt"},
        ).json() if hasattr(sandbox._http, 'post') else None,
    )

    # ============================================================
    # Recording - longer with 10 actions
    # ============================================================
    rec = test("recording.start", lambda: sandbox.recording.start(name="full-test"))
    rec_id = None
    if rec:
        rec_id = rec.get("recording_id")
        print(f"       recording_id: {rec_id}")

        # 10 actions while recording
        actions = [
            ("1. hotkey cmd+space", lambda: sandbox.keyboard.hotkey("command+space")),
            ("2. type Calculator", lambda: sandbox.keyboard.type("Calculator")),
            ("3. press enter", lambda: sandbox.keyboard.press("enter")),
            ("4. click (200, 300)", lambda: sandbox.mouse.click(200, 300)),
            ("5. type 123+456", lambda: sandbox.keyboard.type("123+456")),
            ("6. press enter (=)", lambda: sandbox.keyboard.press("enter")),
            ("7. hotkey cmd+a (select all)", lambda: sandbox.keyboard.hotkey("command+a")),
            ("8. hotkey cmd+c (copy)", lambda: sandbox.keyboard.hotkey("command+c")),
            ("9. move mouse (600, 400)", lambda: sandbox.mouse.move(600, 400)),
            ("10. scroll down", lambda: sandbox.mouse.scroll(600, 400, "down", 5)),
        ]

        for name, action in actions:
            test(f"  recording: {name}", action)
            time.sleep(1)

        stopped = test("recording.stop", lambda: sandbox.recording.stop(rec_id))
        if stopped:
            print(f"       file_size: {stopped.get('file_size')} bytes")

        recs = test("recording.list_all", lambda: sandbox.recording.list_all())
        if recs:
            print(f"       count: {len(recs)}")

        test("recording.get", lambda: sandbox.recording.get(rec_id))

        test("recording.download", lambda: sandbox.recording.download(rec_id, os.path.join(RESULTS, "recording.mp4")))
        mp4_path = os.path.join(RESULTS, "recording.mp4")
        if os.path.exists(mp4_path):
            size = os.path.getsize(mp4_path)
            print(f"       saved results/recording.mp4 ({size} bytes)")
            assert size > 1000, f"recording too small: {size} bytes"

        test("recording.delete", lambda: sandbox.recording.delete(rec_id))

    # ============================================================
    # Final screenshot
    # ============================================================
    img = test("screenshot - final", lambda: sandbox.screenshot.take_full_screen())
    if img:
        save("07_final.png", img)

    # ============================================================
    # Cleanup
    # ============================================================
    test("sandbox.close (destroy)", lambda: sandbox.close())
    sandbox = None

    print(f"\nDone. Results saved to {RESULTS}/")

except KeyboardInterrupt:
    print("\nInterrupted.")
finally:
    if sandbox:
        try:
            sandbox.close()
        except Exception:
            pass
    client.close()
