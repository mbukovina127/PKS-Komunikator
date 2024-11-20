from enum import Enum

import crcmod


class Flags(Enum):
    SYN = 1
    ACK = 2
    KEEP_ALIVE = 3
    KAACK = 13
    FIN = 4
    STR = 5
    FRAG = 6
    FRAG_F = 7
    MSG = 11
    MSG_F = 12

crc16_fun = crcmod.mkCrcFun(0x11021, rev=False, initCrc=0xFFFF, xorOut=0x0000)

class Packet:
    def __init__(self, data: bytes):
        self.flag: int = data[0]
        self.dseq: bytes = data[1:5]
        self.data: bytes = data[5:-2]
        self.crc: bytes = data[-2:]

        self.sequence_number = int.from_bytes(self.dseq, 'big', signed=False)
        self.seq_offset = len(self.data)

    @staticmethod
    def build(flags: bytes = bytes(0), sequence_number: int = 0, data: bytes = bytes(0)) -> 'Packet':
        seq_n = sequence_number.to_bytes(4, byteorder='big', signed=False)
        raw_data = bytes([flags, *seq_n, *data])
        # print("DBG: Raw Bytes: " + str(raw_data))
        crc = crc16_fun(raw_data).to_bytes(2, byteorder='big', signed=False)
        # print("DBG: created crc: " + str(crc))
        pkt = Packet(raw_data + crc)
        return pkt

    @staticmethod
    def checkChecksum(pkt: 'Packet') -> bool:
        mine = crc16_fun(pkt.to_bytes_wo_crc())
        # print("DBG: Raw Bytes: " + str(pkt.to_bytes_wo_crc()))
        pkts = int.from_bytes(pkt.crc, 'big', signed=False)
        if mine == pkts:
            return True
        # print("DBG: incorrect checksum mine:" + str(mine) + " packets" + str(pkts))
        return False

    def changeFlag(self, newFlag: int):
            self.flag = newFlag.to_bytes(1, byteorder='big', signed=False)
            raw_data = bytes([self.flag[0], *self.dseq, *self.data])
            self.crc = crc16_fun(raw_data).to_bytes(2, byteorder='big', signed=False)

    def _getChecksum(self):
        return crc16_fun([self.flag, *self.dseq, *self.data])

    def to_bytes_wo_crc(self) -> bytes:
        if isinstance(self.flag, bytes):
            return self.flag + self.dseq + self.data
        return self.flag.to_bytes(1, byteorder='big') + self.dseq + self.data

    def to_bytes(self) -> bytes:
        if isinstance(self.flag, bytes):
            return self.flag + self.dseq + self.data + self.crc
        return self.flag.to_bytes(1, byteorder='big') + self.dseq + self.data + self.crc