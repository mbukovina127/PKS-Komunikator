
class Packet:
    def __init__(self, data: bytes):
        self.flag = data[0]

