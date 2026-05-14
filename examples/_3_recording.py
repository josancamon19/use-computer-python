import time

from use_computer import Computer

with Computer().create() as mac:
    rec = mac.recording.start(name="demo")
    time.sleep(5)
    mac.recording.stop(rec.id)
    mac.recording.download(rec.id, "demo.mp4")
    print("saved demo.mp4")
