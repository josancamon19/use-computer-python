from use_computer import Computer, RemoteButton, SandboxType, SimulatorFamily

# tvOS sims have no touch — drive them with the remote (D-pad + select / menu /
# home). `press_remote` accepts the enum or a string.
with Computer().create(type=SandboxType.IOS, family=SimulatorFamily.TV) as tv:
    tv.input.press_remote(RemoteButton.DOWN)
    tv.input.press_remote(RemoteButton.DOWN)
    tv.input.press_remote(RemoteButton.SELECT)
    png = tv.screenshot.take_full_screen()
    open("hello_tvos.png", "wb").write(png)
    print(f"saved hello_tvos.png ({len(png)} bytes)")
