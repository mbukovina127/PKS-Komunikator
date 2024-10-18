import threading
import time

from packet import Packet, Flags
import asyncio
import socket

class Peer:
    def __init__(self, port_lst):
        self.dest_ip = ""
        self.listen_port = port_lst
        self.dest_port = 0
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.bind(('0.0.0.0', self.listen_port))

        self.listening_socket.settimeout(60)
        self.c_running = True
        self.syn_send_received = False
        self.conn_esta = False




    def send_message(self, message: str):
        self.transmitting_socket.sendto(message.encode(), (self.dest_ip, self.dest_port))

    def recv_message(self, buffer_s):
        data, addr = self.listening_socket.recvfrom(buffer_s)
        message = data.decode()
        return message

    def send_packet(self, packet: Packet):
        self.transmitting_socket.sendto(packet.to_bytes(), (self.dest_ip, self.dest_port))

    def recv_packet(self, buffer_s) -> Packet:
        data, addr = self.listening_socket.recvfrom(buffer_s)
        pkt = Packet(data)
        return pkt

    def message_handler(self):
        while self.c_running:
            inp = input()
            if (inp == "quit"):
                self.quit()
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
        while self.c_running:
            try:
                rec_pkt = self.recv_packet(buffer_s)
                self.parse_packet(rec_pkt)
            except socket.timeout:
                pass
            except OSError:
                return

    def message_listen(self):
        self.listening_socket.settimeout(None)
        while self.c_running:
            try:
                msg, addr = self.listening_socket.recvfrom(1500)
                print("Received: %s"  %msg)
            except KeyboardInterrupt:
                quit()
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
        self.c_running = False
        self.listening_socket.close()
        # print("Listening socket closed...")
        self.transmitting_socket.close()
        # print("Transmitting socket closed...")
        print("Offline")

    def init_listen(self):
        print("Waiting for connection")
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
                self.conn_esta = True
                return
            if (rec_pkt.flag == Flags.SYN.value and not self.syn_send_received):
                self.send_packet(Packet.build(flags=Flags.ACK.value))
                self.syn_send_received = True
                continue

            print("Connection lost")

    def init_transmit(self):
        while not self.conn_esta:
            print("Press enter to try to connect")
            input()
            if (self.conn_esta):
                return
            if not self.syn_send_received and not self.conn_esta:
                self.send_packet(Packet.build(flags=Flags.SYN.value))
                self.syn_send_received = True
                print("Establishing connection...")
            while self.syn_send_received and not self.conn_esta:
                time.sleep(1)



    def communicate(self):
        listening = threading.Thread(target=self.message_listen)
        messaging = threading.Thread(target=self.message_handler)
        listening.start()
        messaging.start()


        print("You can now send messages")
        listening.join()
        messaging.join()

