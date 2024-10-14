from enum import Enum
from packet import Packet
import asyncio
import socket

class Flags(Enum):
    SYN = 1
    ACK = 2
    KEEP_ALIVE = 3
    FIN = 4


class Peer:
    def __init__(self, ip, port_l, port_t):
        self.dest_ip = ip
        self.port_l = port_l
        self.port_t = port_t
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind((self.ip, self.port_l))
        self.transmitting_socket.bind((self.ip, self.port_t))

        self.keep_alive = 0;

    def send_message(self, message):
        self.transmitting_socket.sendto( bytes(message), self.dest_ip)

    def receive_message(self):
        data = self.listening_socket.recv(1024)
        packet = Packet(data)
        self.parse_packet(packet)

    def parse_packet(self, pkt: Packet):
        match pkt.flag:
            case Flags.SYN.value:
                return
            case Flags.ACK.value:
                return
            case Flags.KEEP_ALIVE.value:
                return
            case Flags.FIN.value:
                return
            case _:
                print("ERROR: Invalid flag")


    def launch(self):

        asyncio.run(self.listen())
        return

    async def listen(self):
        return


    def quit(self):
        self.listening_socket.close()
        self.transmitting_socket.close()
        print("INFO: Server offline...")
