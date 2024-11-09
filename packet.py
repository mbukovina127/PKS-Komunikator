from enum import Enum
from sys import byteorder

import crcmod


class Flags(Enum):
    SYN = 1
    ACK = 2
    KEEP_ALIVE = 3
    FIN = 4
    STR = 5
    FRAG = 6
    FRAG_F = 7
    MSG = 11
    MSG_F = 12

crc16_fun = crcmod.mkCrcFun(0x11021, rev=False, initCrc=0xFFFF, xorOut=0x0000)

class Packet:
    def __init__(self, data: bytes):
        self.flag = data[0]
        self.dseq = data[1:5]
        self.data = data[5:-2]
        self.crc = data[-2:]

        self.sequence_number = int.from_bytes(self.dseq, 'big', signed=False)
        self.seq_offset = len(self.data)

    @staticmethod
    def build(flags: bytes = bytes(0), sequence_number: int = 0, data: bytes = bytes(0)) -> 'Packet':
        seq_n = sequence_number.to_bytes(4, byteorder='big', signed=False)
        raw_data = bytes([flags, *seq_n, *data])
        crc = crc16_fun(raw_data).to_bytes(2, byteorder='big', signed=False)
        pkt = Packet(raw_data + crc)
        return pkt

    def getChecksum(self):
        return crc16_fun([self.flag, *self.dseq, *self.data])

    def to_bytes(self) -> bytes:
        return bytes(
            [self.flag, *self.dseq, *self.data, *self.crc]
        )
