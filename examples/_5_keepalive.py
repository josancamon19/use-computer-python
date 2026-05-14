import time

from use_computer import Computer

with Computer().create() as mac:
    mac.start_keepalive(interval=30)
    time.sleep(180)
    png = mac.screenshot.take_full_screen()
    print(f"still alive: screenshot {len(png)} bytes")
