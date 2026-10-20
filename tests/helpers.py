def write_file(path, data):
    with open(path, "wb" if isinstance(data, bytes) else "w") as f:
        f.write(data)
