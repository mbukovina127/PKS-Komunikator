import socket

from setuptools.discovery import FlatLayoutModuleFinder

from packet import Packet, Flags
from peer import Peer


class Server:
    def __init__(self, ip, port_l, port_t):
        self.dest_ip = ip
        self.port_listen = port_l
        self.port_transmit = port_t
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.bind((self.dest_ip, self.port_listen))

        print("Server created successfully")

    def send_packet(self, packet: Packet):
        self.transmitting_socket.sendto(packet.to_bytes(), (self.dest_ip, self.port_transmit))

    # TODO: I dont know if it throws exception
    def recv_packet(self, buffer_s) -> Packet:
        data, addr = self.listening_socket.recvfrom(buffer_s)
        pkt = Packet(data)
        return pkt

    def init_connection(self):
        self.listening_socket.settimeout(60)
        print("Waiting to connect... 60s")
        # TODO: remove constant
        try:
            rec_pkt, addr = self.listening_socket.recvfrom(1024)
            rec_pkt = Packet(rec_pkt)
            if (rec_pkt.flag != Flags.SYN.value):
                print("Recived wrong message")
        except socket.timeout:
            print("Connection time out")
            return
        while True:
            self.send_packet(Packet.build(flags=Flags.ACK.value))
            try:
                # TODO: remove constant
                rec_pkt, addr = self.listening_socket.recvfrom(1024)
                rec_pkt = Packet(rec_pkt)
                if (rec_pkt.flag == Flags.ACK.value):
                    print("Connection established")
                    return
            except socket.timeout:
                print("No reply... trying again")
        



    def init_connection_message(self):
        print("Waiting for message")
        data = self.listening_socket.recv(1024)
        print("Message received: %s" % data)
        message = input("Message to reply with: ")
        self.transmitting_socket.sendto(bytes(message, "utf-8"), (self.dest_ip, self.port_transmit))
        print("Message sent")
        return

    def launch(self):
        print("Server up")
        self.init_connection()

        self.quit()

    def quit(self):
        print("Closing server...")

        self.listening_socket.close()
        # print("Listening socket closed...")
        self.transmitting_socket.close()
        # print("Transmitting socket closed...")
        print("Server offline")


