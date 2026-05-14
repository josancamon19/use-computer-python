from use_computer import Computer

with Computer().create() as mac:
    # Seed data files the task needs before handing the sandbox to an agent.
    mac.upload_bytes(b"hello from use.computer\n", "/Users/lume/Desktop/hello.txt")
    mac.download_file("/Users/lume/Desktop/hello.txt", "hello.txt")
    print("saved hello.txt")
