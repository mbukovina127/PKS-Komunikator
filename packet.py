from enum import Enum


class Flags(Enum):
    SYN = 1
    ACK = 2
    KEEP_ALIVE = 3
    FIN = 4


class Packet:
    def __init__(self, data: bytes):
        self.flag = data[0]
        self.data = data[1:]

    @staticmethod
    def build(flags: bytes = 0, data: bytes = 0) -> 'Packet':
        pkt = Packet(0)
        pkt.flags = flags
        pkt.data = data
        return pkt

    def to_bytes(self) -> bytes:
        return bytes(
            [self.flag, *self.data]
        )