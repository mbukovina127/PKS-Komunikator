import packet


def loadFile(url: str, fragment_size, seq_start: int):
    with open(url, "rb") as file:
        data = file.read()

    fragments = [data[i: (i + fragment_size)] for i in range(0, len(data), fragment_size)]
    //TODO: seq numbers
    packets = [Packet.build(flags=Flags.STR, length=fragment_size)]
    for fgt in fragments:

