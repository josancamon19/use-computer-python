from use_computer import Computer, SandboxType

with Computer().create(type=SandboxType.IOS) as ios:
    ios.apps.open_url("https://example.com")
    png = ios.screenshot.take_full_screen()
    open("hello_ios.png", "wb").write(png)
    print(f"saved hello_ios.png ({len(png)} bytes)")
