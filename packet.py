from enum import Enum
from sys import byteorder


class Flags(Enum):
    SYN = 1
    ACK = 2
    KEEP_ALIVE = 3
    FIN = 4
    STR = 5
    FRAG = 6
    FRAG_F = 7
    MSG = 11


class Packet:
    def __init__(self, data: bytes):
        self.flag = data[0]
        self.dseq = data[1:5]
        self.dlen = data[5:7]
        self.data = data[7:-4]
        self.crc = data[-4:]

        self.sequence_number = int.from_bytes(self.dseq, 'big', signed=False)


    @staticmethod
    def build(flags: bytes = bytes(0), sequence_number: int = 0, length: int = 0, data: bytes = bytes(0)) -> 'Packet':
        len = length.to_bytes(2, byteorder='big', signed=False)
        seq_n = sequence_number.to_bytes(4, byteorder='big', signed=False)
        pkt = Packet(bytes([flags, *seq_n, *len, *data]))
        return pkt

    def to_bytes(self) -> bytes:
        return bytes(
            [self.flag, *self.dseq, *self.dlen, *self.data, *self.crc]
        )
