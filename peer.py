
from packet import Packet, Flags
import asyncio
import socket

class Peer:
    def __init__(self, ip, port_l, port_t):
        self.dest_ip = ip
        self.port_listen = port_l
        self.port_transmit = port_t
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.settimeout(60)


    def send_message(self, message: str):
        self.transmitting_socket.sendto(message.encode(), (self.dest_ip, self.port_transmit))

    def recv_message(self, buffer_s):
        data, addr = self.listening_socket.recvfrom(buffer_s)
        message = data.decode()
        return message

    def send_packet(self, packet: Packet):
        self.transmitting_socket.sendto(packet.to_bytes(), (self.dest_ip, self.port_transmit))

    def recv_packet(self, buffer_s) -> Packet:
        data, addr = self.listening_socket.recvfrom(buffer_s)
        pkt = Packet(data)
        return pkt

    def message_handler(self):
        while True:
            inp = input("Send message: ")
            if (inp == "quit"):
                return
            self.send_message(inp)

    def parse_packet(self, pkt: Packet):
        print("pkt received")
        match (pkt.flag):
            case Flags.KEEP_ALIVE.value:
                return
            case Flags.SYN.value:
                return
            case Flags.ACK.value:
                return
            case Flags.FIN.value:
                self.FIN_received()
                return
            case _:
                return 

    def listen(self, buffer_s):
        self.listening_socket.settimeout(60)
        while True:
            try:
                rec_pkt = self.recv_packet(buffer_s)
                self.parse_packet(rec_pkt)
            except socket.timeout:
                pass
            except OSError:
                return

    def message_listen(self):
        self.listening_socket.settimeout(None)
        while True:
            try:
                msg = self.recv_message(1500)
                print(msg)
            except OSError:
                return

    def init_termination(self):
        print("Terminating connection")
        self.listening_socket.settimeout(5)
        while True:
            self.send_packet(Packet.build(flags=Flags.FIN.value))
            try:
                rec_pkt = self.recv_packet(1024)
                # TODO: possible delayed packets
                if (rec_pkt.flag == Flags.ACK.value):
                    print("ACK received")
                    self.quit()
                    return
            except socket.timeout:
                pass
            print("failed to terminate connection... trying again")

    def FIN_received(self):
        self.send_packet(Packet.build(flags=Flags.ACK.value))
        self.quit()
        

    def quit(self):
        print("Closing connection...")
        self.listening_socket.close()
        # print("Listening socket closed...")
        self.transmitting_socket.close()
        # print("Transmitting socket closed...")
        print("Offline")