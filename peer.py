from enum import Enum
from packet import Packet
import asyncio
import socket

class Peer:
    def __init__(self, ip, port_l, port_t):
        self.dest_ip = ip
        self.port_listen = port_l
        self.port_transmit = port_t
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.bind((self.dest_ip, self.port_listen))

    def send_message(self, message):
        self.transmitting_socket.sendto( bytes(message), self.dest_ip)

    def send_packet(self, packet: Packet):
        self.transmitting_socket.sendto(packet.to_bytes(), (self.dest_ip, self.port_transmit))

    def recieve_packet(self, buffer_s) -> Packet:
        data, addr = self.listening_socket.recvfrom(buffer_s)



    def receive_message(self):
        data = self.listening_socket.recv(1024)
        packet = Packet(data)
        self.parse_packet(packet)




    def launch(self):

        asyncio.run(self.listen())
        return

    async def listen(self):
        return


    def quit(self):
        self.listening_socket.close()
        self.transmitting_socket.close()
        print("INFO: Server offline...")
