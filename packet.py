
class Packet:
    def __init__(self, data: bytes):
        self.crc = data[:4]
        self.flags = data[4:5]


