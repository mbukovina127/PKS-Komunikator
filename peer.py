import random
import threading
import time
from sys import flags

from packet import Packet, Flags
import asyncio
import socket

class Peer:
    def __init__(self, port_lst, port_trs, ip):
        ### connection variables
        self.pulse = 3
        self.dest_ip = ip
        self.listen_port = port_lst
        self.dest_port = port_trs

    ### socket setup
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.bind(('0.0.0.0', self.listen_port))
        self.listening_socket.settimeout(60)

    ### async variables
        self.CONNECTION = False
        self.syn_send_received = False
        self.fin_send = False
        self.menu_on = True

    ### sequence numbers
        self.current_seq = 0
        self.expect_seq = 0

    ### files
        self.frag_size = 7 + 1465

### PACKET FUNCTIONS

    def send_packet(self, packet: Packet):
        self.transmitting_socket.sendto(packet.to_bytes(), (self.dest_ip, self.dest_port))

    def recv_packet(self, buffer_s) -> Packet:
        data, addr = self.listening_socket.recvfrom(buffer_s)
        pkt = Packet(data)
        return pkt

    def update_expected(self, offset: int = 1):
        self.expect_seq += offset
        return self.expect_seq
    def update_current(self, offset:int = 1):
        self.current_seq += offset
        return self.current_seq

    def parse_packet(self, pkt: Packet):
        # print("pkt received")
        match (pkt.flag):
            case Flags.KEEP_ALIVE.value:
                print("DBG: KEEP ALIVE rec")
                self.pulse = 3
                return
            case Flags.ACK.value:
                if (self.fin_send == True):
                    quit()
                return
            case Flags.STR.value:
                self.incoming_file(pkt)
                return
            case Flags.FRAG.value:
                return
            case Flags.FRAG_F.value:
                return
            case Flags.MSG.value:
                print(pkt.data.decode("utf-8"))
                return
            case Flags.FIN.value:
                self.FIN_received()
                return
            # case Flags.SYN.value:
            #     return
            case _:
                return

### THREAD FUNCTIONS

    def message_handler(self):
        while self.CONNECTION:
            inp = input()
            if (inp == "quit"):
                self.init_termination()
                return
            if self.CONNECTION:
                self.send_packet(Packet.build(Flags.MSG.value, sequence_number=self.current_seq, data=inp.encode('utf-8')))

    def LISTENER(self, buffer_s):
        self.listening_socket.settimeout(60)
        while self.CONNECTION:
            try:
                rec_pkt = self.recv_packet(buffer_s)
                self.parse_packet(rec_pkt)
            except socket.timeout:
                pass
            except OSError:
                return
        self.quit()

    def init_termination(self):
        print("INFO: Terminating connection")
        self.send_packet(Packet.build(flags=Flags.FIN.value, sequence_number=self.current_seq))
        self.fin_send = True

    def FIN_received(self):
        self.send_packet(Packet.build(flags=Flags.FIN.value, sequence_number=self.update_current()))
        time.sleep(0.2)
        self.send_packet(Packet.build(flags=Flags.ACK.value))
        self.quit()


    def quit(self):
        print("INFO: Closing connection...")
        self.CONNECTION = False
        self.listening_socket.close()
        self.transmitting_socket.close()
        print("INFO: Offline")

### KEEP ALIVE FUNCTION

    def keep_alive(self):
        while self.CONNECTION:
            if self.pulse == 0:
                print("ERROR: Connection lost... heart beat not received")
                self.CONNECTION = False
                return
            self.pulse -= 1
            self.heart_beat()
            print("DBG: heart beat sent")
            time.sleep(5)



    def heart_beat(self):
        ka_pkt = Packet.build(flags=Flags.KEEP_ALIVE.value)
        self.transmitting_socket.sendto(ka_pkt.to_bytes(), (self.dest_ip, self.dest_port))

### HANDSHAKE FUNCTIONS

    def init_listen(self):
        print("INFO: Waiting for connection...")
        self.listening_socket.settimeout(10)
        while True:
            try:
                rec_pkt_data, addr = self.listening_socket.recvfrom(1500)
                rec_pkt = Packet(rec_pkt_data)
            except socket.timeout:
                if (self.syn_send_received):
                    print("ERROR: Connection lost")
                    self.syn_send_received = False
                continue
            #we received syn packet without sending one
            if (rec_pkt.flag == Flags.SYN.value and not self.syn_send_received):
                print("DBG: syn received first seq ==")
                self.expect_seq = rec_pkt.sequence_number
                print(self.expect_seq)
                self.current_seq = random.randint(1,900)
                if self.current_seq == self.expect_seq:
                    self.current_seq += 100
                self.send_packet(Packet.build(flags=Flags.SYN.value, sequence_number=self.current_seq))
                print("DBG: new syn sent")
                print(self.current_seq)
                self.syn_send_received = True
                time.sleep(0.5)
                self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.update_expected()))
                print("DBG: ack sent")
                print(self.expect_seq)
                continue
            #we receive ack after we received syn packet
            if rec_pkt.flag == Flags.ACK.value and self.syn_send_received:
                print("DBG: ack received after syn received first")
                if rec_pkt.sequence_number == (self.current_seq + 1):
                    self.CONNECTION = True
                    return
                print ("DBG: seq doesn't match")
                print(rec_pkt.sequence_number, self.current_seq + 1)
            #we send syn packet first
            if rec_pkt.flag == Flags.SYN.value and self.syn_send_received:
                print("DBG: syn received after syn sent")
                if self.expect_seq == 0: # syn packet arrives after we send ours
                    print("DBG: expected seq is empty")
                    self.expect_seq = rec_pkt.sequence_number # we copy its sq number
                    ack_pkt, addr = self.listening_socket.recvfrom(1500)
                    ack_pkt = Packet(ack_pkt)
                    print("DBG: ack received after syn sent")
                    if ack_pkt.flag == Flags.ACK.value: # we wait for an ack packet for our syn packet
                        if ack_pkt.sequence_number == self.current_seq +1: # it has to have seq +1 of the one we sent
                            self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.update_expected())) # we send ack for the one we received
                            self.CONNECTION = True
                            return
                        print("DBG: seq doesn't match")
                        print(ack_pkt.sequence_number, self.current_seq +1)
            self.current_seq = 0
            self.expect_seq = 0
            print("ERROR: Connection lost")

    def init_transmit(self):
        while not self.CONNECTION:
            print("Press enter to try to connect")
            input()
            # Don't send packet if connection is established
            # TODO: possible fix with the sleep loop
            if self.CONNECTION:
                return
            if not self.syn_send_received and not self.CONNECTION:
                self.current_seq = random.randint(1, 1000)
                self.send_packet(Packet.build(flags=Flags.SYN.value, sequence_number=self.current_seq))
                self.syn_send_received = True
                print("INFO: Establishing connection...")
            while self.syn_send_received and not self.CONNECTION:
                time.sleep(1)


    def communicate(self):
        listening = threading.Thread(target=self.LISTENER, args=(1500,))
        keep_alive = threading.Thread(target=self.keep_alive)
        listening.start()
        keep_alive.start()
        print("You can now send messages")

        menu = threading.Thread(target=self.menu)
        menu.start()

        while self.CONNECTION:
            if not self.menu_on and menu.is_alive():
                menu.join(0)
            time.sleep(1)
        print("DBG: jumped from loop")
        if not self.CONNECTION:
            if menu.is_alive():
                menu.join(timeout=0)






    ### Menu

    def menu(self):
        while self.CONNECTION:
            print("Choose option:")
            print("[M]essage | [S]end files | [Q]uit")
            choice = input()
            match choice.lower():
                case 'm':
                    return
                case 's':
                    return
                case 'q':
                    self.CONNECTION = False
                    self.menu_on = False
                    return


    ### FILE functions


    def incoming_file(self, pkt):
        self.frag_size = int.from_bytes(pkt.data, "big", signed=False)
        self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.current_seq))
        pass

