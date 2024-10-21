import threading
import time
from sys import flags

from packet import Packet, Flags
import asyncio
import socket

class Peer:
    def __init__(self, port_lst, port_trs, ip):
        ### connection variables
        self.dest_ip = ip
        self.listen_port = port_lst
        self.dest_port = port_trs

        ### socket setup
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.bind(('0.0.0.0', self.listen_port))
        self.listening_socket.settimeout(60)

        ### aync variables
        self.CONNECTION = False
        self.syn_send_received = False
        self.fin_send = False

    ### PACKET FUNCTIONS

    def send_packet(self, packet: Packet):
        self.transmitting_socket.sendto(packet.to_bytes(), (self.dest_ip, self.dest_port))

    def recv_packet(self, buffer_s) -> Packet:
        data, addr = self.listening_socket.recvfrom(buffer_s)
        pkt = Packet(data)
        return pkt

    def parse_packet(self, pkt: Packet):
        print("pkt received")
        match (pkt.flag):
            case Flags.KEEP_ALIVE.value:
                return
            case Flags.SYN.value:
                return
            case Flags.ACK.value:
                if (self.fin_send == True):
                    quit()
                return
            case Flags.FIN.value:
                self.FIN_received()
                return
            case Flags.MSG.value:
                print(self.message_parse(pkt))
                return
            case _:
                return

    ### MESSAGING FUNCTIONS

    def message_parse(self, packet: Packet):
        if packet.flag != Flags.MSG.value:
            return "Incorrect packet received"
        return packet.data.decode("utf-8")

    ### THREAD FUNCTIONS

    def message_handler(self):
        while self.CONNECTION:
            inp = input()
            if (inp == "quit"):
                self.init_termination()
                return
            if self.CONNECTION:
                self.send_packet(Packet.build(Flags.MSG.value, inp.encode('utf-8')))

    def listen(self, buffer_s):
        self.listening_socket.settimeout(60)
        while self.CONNECTION:
            try:
                rec_pkt = self.recv_packet(buffer_s)
                self.parse_packet(rec_pkt)
            except socket.timeout:
                pass
            except OSError:
                return

    def init_termination(self):
        print("Terminating connection")
        self.send_packet(Packet.build(flags=Flags.FIN.value))
        self.fin_send = True

    def FIN_received(self):
        self.send_packet(Packet.build(flags=Flags.FIN.value))
        time.sleep(0.2)
        self.send_packet(Packet.build(flags=Flags.ACK.value))
        self.quit()


    def quit(self):
        print("Closing connection...")
        self.CONNECTION = False
        self.listening_socket.close()
        self.transmitting_socket.close()
        print("Offline")

    ### HANDSHAKE FUNCTIONS

    def init_listen(self):
        print("Waiting for connection...")
        self.listening_socket.settimeout(10)
        while True:
            try:
                rec_pkt_data, addr = self.listening_socket.recvfrom(1500)
                rec_pkt = Packet(rec_pkt_data)
            except socket.timeout:
                if (self.syn_send_received):
                    print("Connection lost")
                    self.syn_send_received = False
                continue
            if (rec_pkt.flag == Flags.ACK.value and self.syn_send_received):
                self.send_packet(Packet.build(flags=Flags.ACK.value))
                self.CONNECTION = True
                return
            if (rec_pkt.flag == Flags.SYN.value and not self.syn_send_received):
                self.send_packet(Packet.build(flags=Flags.ACK.value))
                self.syn_send_received = True
                continue

            print("Connection lost")

    def init_transmit(self):
        while not self.CONNECTION:
            print("Press enter to try to connect")
            input()
            # Don't send packet if connection is established
            # TODO: possible fix with the sleep loop
            if self.CONNECTION:
                return
            if not self.syn_send_received and not self.CONNECTION:
                self.send_packet(Packet.build(flags=Flags.SYN.value))
                self.syn_send_received = True
                print("Establishing connection...")
            while self.syn_send_received and not self.CONNECTION:
                time.sleep(1)



    def communicate(self):
        listening = threading.Thread(target=self.listen, args=(1500,))
        messaging = threading.Thread(target=self.message_handler)
        listening.start()
        messaging.start()
        print("You can now send messages")

        listening.join()
        messaging.join()

