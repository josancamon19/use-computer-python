from use_computer import Computer

with Computer().create() as mac:
    mac.upload_bytes(b"hello from use.computer\n", "/Users/lume/Desktop/hello.txt")
    mac.download_file("/Users/lume/Desktop/hello.txt", "hello.txt")
    print("saved hello.txt")
