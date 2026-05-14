from use_computer import Computer

with Computer().create() as mac:
    mac.exec_ssh("open -a TextEdit")
    mac.keyboard.type("hello from use.computer")
    png = mac.screenshot.take_full_screen()
    open("hello_macos.png", "wb").write(png)
    print(f"saved hello_macos.png ({len(png)} bytes)")
