from use_computer import Computer, SandboxType, SimulatorFamily

# iPhone is the default when family= is omitted. Pass family= to target a
# different simulator family (iPad, Apple Watch, Apple TV, Apple Vision); the
# SDK picks a compatible installed device_type + runtime pair for you. See
# _6_hello_tvos.py for an Apple TV walkthrough.
with Computer().create(type=SandboxType.IOS, family=SimulatorFamily.IPHONE) as ios:
    ios.apps.open_url("https://example.com")
    png = ios.screenshot.take_full_screen()
    open("hello_ios.png", "wb").write(png)
    print(f"saved hello_ios.png ({len(png)} bytes)")
