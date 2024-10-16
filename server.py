import asyncio
import socket

from setuptools.discovery import FlatLayoutModuleFinder

from packet import Packet, Flags
from peer import Peer


class Server(Peer):
    def __init__(self, ip, port_l, port_t):
        super().__init__(ip, port_l, port_t)
        print("Server created successfully")

    def init_connection(self):
        self.listening_socket.settimeout(60)
        print("Waiting to connect... 60s")
        try:
            # TODO: remove constant
            rec_pkt = super().recv_packet(1024)
            if (rec_pkt.flag != Flags.SYN.value):
                print("Received wrong message")
                return
        except socket.timeout:
            print("Connection time out")
            return
        print("SYN received... ", end="")
        self.listening_socket.settimeout(5)
        while True:
            self.send_packet(Packet.build(flags=Flags.ACK.value))
            print("ACK sent... ", end="")
            try:
                # TODO: remove constant
                rec_pkt = super().recv_packet(1024)
                if (rec_pkt.flag == Flags.ACK.value):
                    print("Connection established")
                    return
            except socket.timeout:
                print("no reply... trying again")

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
        # TODO: remove const
        asyncio.run(self.listen(1024))

        super().quit()


