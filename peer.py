import asyncio
import queue
import random
import socket
import threading
import time
from enum import Enum

from packet import Packet, Flags
from packetsending import ThreadingSet, Sender, SlidingWindow


class State(Enum):
    Exit = 0
    Halt = 1
    InMenu = 2
    SendMessage = 3
    SendFile = 4

class ConnInfo:
    def __init__(self, ip, port_lst, port_trs):
        self.dest_ip = ip
        self.listen_port = port_lst
        self.dest_port = port_trs
        self.CONNECTION = False
    ### sequence numbers
        # I need to send to dest and expect ack of dest + offset + 1 when I receive ack

        # current is all the non ack packets heading my way we send ack only from this number we don't receive ack packets here I reply with ack of current + 1
        self.current_seq = 0
        self.current_fallback = 0
        # dest is all the non ack packets that I send we receive ack packets with this number
        self.dest_seq = 0
        self.dest_fallback = 0

class Peer:
    def __init__(self, conn_info):
        ### connection variables
        self.ConnInfo = conn_info

    ### socket setup
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.bind(('0.0.0.0', self.ConnInfo.listen_port))
        self.listening_socket.settimeout(60)

    ### handshake vars
        self.syn_send_received = False
        self.fin_send = False

    ### Threading functionality
        self.send_lock = threading.Lock()
        self.Halt = asyncio.Event()

    ### DATA
        self.SENT = ThreadingSet()
        self.INPUT = queue.Queue()
        self.WINDOW = SlidingWindow()

    ### Keep Alive
        self.KA_time = 5
        self.pulse = 3

    ### files
        self.frag_size = 7 + 1465
    ### THREADS
        self.SENDER = Sender(self.transmitting_socket, self.ConnInfo, self.SENT, self.send_lock)

### PACKET FUNCTIONS

    def send_packet(self, packet: Packet):
        with self.send_lock:
            self.transmitting_socket.sendto(packet.to_bytes(), (self.ConnInfo.dest_ip, self.ConnInfo.dest_port))

    def recv_packet(self, buffer_s) -> Packet:
        data, addr = self.listening_socket.recvfrom(buffer_s)
        pkt = Packet(data)
        # TODO: kinda shit
        if Packet.checkChecksum(pkt):
            return pkt
        return None

    def update_expected(self, offset: int = 1):
        self.ConnInfo.dest_fallback = self.ConnInfo.dest_seq
        self.ConnInfo.dest_seq += offset
        return self.ConnInfo.dest_seq

    def update_current(self, offset: int = 1):
        self.ConnInfo.current_fallback = self.ConnInfo.current_seq
        self.ConnInfo.current_seq += offset
        return self.ConnInfo.current_seq

    def send_ack(self, pkt: Packet):
        ack_seq = pkt.sequence_number + pkt.seq_offset + 1
        self.send_packet(Packet.build(Flags.ACK.value, sequence_number=ack_seq))

### Message function
    # TODO: ask for fragment size / split message accordingly
    async def send_message(self):
        self.clear_queue()
        #getting fragment size
        print("Fragment size [1-1465] | [K]eep default: ", end='')
        inp = self.INPUT.get()
        if inp != "K":
            self.frag_size = int(inp)
        inp = ""
        print("Write message [--quit]: ", end='')
        inp = self.INPUT.get()
        if inp.lower() == "--quit":
            print("INFO: Not sending any message")
            return True
        if self.ConnInfo.CONNECTION:
            self.split_message()
            print("INFO: Message sent")
            return True
        else:
            print("ERROR: No connection")
            return False

    def recv_message(self, pkt):
        pass

    def split_message(self, message: str):
        seq = self.ConnInfo.dest_seq
        # TODO: wonky as fuk
        # TODO: FAAAAAAAAAAAAAAAAAAAAAAAAAAAAK I have to make a receiver for this because we can miss some packets
        msg_chunks = [
            (Packet.build(flags=Flags.MSG.value
                           ,sequence_number=seq + i*(self.frag_size + 1)
                           ,data=(message[i: i+ self.frag_size]).encode()) )
            for i in range(0, len(message), self.frag_size)]

        msg_chunks[-1].flag = Flags.MSG_F.value
        self.SENDER.queue_packet(msg_chunks)

### Packet parser
    #handeling acks for our sent packet. Removing them from our window should suffice
    def ack_received(self, pkt):
        self.WINDOW.remove(pkt.sequence_number)

    def parse_packet(self, pkt: Packet):
        print("pkt received")
        match (pkt.flag):
            case Flags.KEEP_ALIVE.value:
                # print("DBG: KEEP ALIVE rec")
                self.pulse = 3
                return
            #ack has seq of dest_seq + 1
            case Flags.ACK.value:
                self.verify_packet(pkt)
                self.ack_received(pkt)
                if (self.fin_send == True):
                    quit()
                return
            #str seq of current
            case Flags.STR.value:
                self.verify_packet(pkt)
                self.Halt.set()
                self.incoming_file(pkt)
                return
            #Frag seq of current
            case Flags.FRAG.value:
                return
            #Frag seq of current
            case Flags.FRAG_F.value:
                # DO SOMETHING
                self.Halt.clear()
                return
            #Frag seq of current
            case Flags.MSG.value:
                self.recv_message(pkt)
                print(pkt.data.decode("utf-8"))
                self.send_ack(pkt)
                return
            case Flags.FIN.value:
                self.FIN_received()
                return
            case _:
                return

    # TODO: test needs a rework
    def verify_packet(self, pkt: Packet):
        # for incoming packets
        if pkt.sequence_number == self.ConnInfo.current_seq:
            return True
        # for acks of sent packets
        return self.SENT.contains(pkt.sequence_number)

### THREAD FUNCTIONS

    def LISTENER(self, buffer_s):
        self.listening_socket.settimeout(60)
        while self.ConnInfo.CONNECTION:
            try:
                rec_pkt = self.recv_packet(buffer_s)
                self.parse_packet(rec_pkt)
            except socket.timeout:
                pass
            except OSError:
                return
        self.quit()

### Terminating fucntions

    def init_termination(self):
        print("INFO: Terminating connection")
        self.send_packet(Packet.build(flags=Flags.FIN.value, sequence_number=self.ConnInfo.current_seq))
        self.fin_send = True

    def FIN_received(self):
        self.send_packet(Packet.build(flags=Flags.FIN.value, sequence_number=self.update_current()))
        time.sleep(0.2)
        self.send_packet(Packet.build(flags=Flags.ACK.value))
        self.quit()

    def quit(self):
        print("INFO: Closing connection...")
        self.ConnInfo.CONNECTION = False
        self.listening_socket.close()
        self.transmitting_socket.close()
        print("INFO: Offline")

### KEEP ALIVE FUNCTION

    def keep_alive(self):
        while self.ConnInfo.CONNECTION:
            if self.pulse == 0:
                print("ERROR: Connection lost... heart beat not received")
                self.ConnInfo.CONNECTION = False
                return
            self.pulse -= 1
            self.heart_beat()
            # print("DBG: heart beat sent")
            time.sleep(self.KA_time)

    def heart_beat(self):
        ka_pkt = Packet.build(flags=Flags.KEEP_ALIVE.value)
        self.transmitting_socket.sendto(ka_pkt.to_bytes(), (self.ConnInfo.dest_ip, self.ConnInfo.dest_port))

### HANDSHAKE FUNCTIONS
    # TODO: could move the 10s timeout into another thread
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
                self.ConnInfo.dest_seq = rec_pkt.sequence_number
                print("DBG: syn received first seq ==", end="")
                print(self.ConnInfo.dest_seq)
                self.ConnInfo.current_seq = random.randint(1,900)
                if self.ConnInfo.current_seq == self.ConnInfo.dest_seq:
                    self.ConnInfo.current_seq += 100
                self.send_packet(Packet.build(flags=Flags.SYN.value, sequence_number=self.ConnInfo.current_seq))
                print("DBG: new syn sent")
                print(self.ConnInfo.current_seq)
                self.syn_send_received = True
                time.sleep(0.5)
                self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.update_expected()))
                print("DBG: ack sent")
                print(self.ConnInfo.dest_seq)
                continue
            #we receive ack after we received syn packet
            if rec_pkt.flag == Flags.ACK.value and self.syn_send_received:
                print("DBG: ack received after syn received first")
                if rec_pkt.sequence_number == (self.ConnInfo.current_seq + 1):
                    self.ConnInfo.CONNECTION = True
                    self.update_current()
                    return

                print ("DBG: seq doesn't match ", end="")
                print(rec_pkt.sequence_number, self.ConnInfo.current_seq + 1)
            #we send syn packet first
            if rec_pkt.flag == Flags.SYN.value and self.syn_send_received:
                print("DBG: syn received after syn sent")
                if self.ConnInfo.dest_seq == 0: # syn packet arrives after we send ours
                    print("DBG: expected seq is empty")
                    self.ConnInfo.dest_seq = rec_pkt.sequence_number # we copy its sq number
                    ack_pkt, addr = self.listening_socket.recvfrom(1500)
                    ack_pkt = Packet(ack_pkt)
                    print("DBG: ack received after syn sent")
                    if ack_pkt.flag == Flags.ACK.value: # we wait for an ack packet for our syn packet
                        if ack_pkt.sequence_number == self.ConnInfo.current_seq +1: # it has to have seq +1 of the one we sent
                            self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.update_expected())) # we send ack for the one we received
                            self.ConnInfo.CONNECTION = True
                            self.update_current()
                            return
                        print("DBG: seq doesn't match")
                        print(ack_pkt.sequence_number, self.ConnInfo.current_seq +1)
            self.ConnInfo.current_seq = 0
            self.ConnInfo.dest_seq = 0
            print("ERROR: Connection lost")

    def init_transmit(self):
        while not self.ConnInfo.CONNECTION:
            print("[C]onnect?")
            self.INPUT.get()
            if self.ConnInfo.CONNECTION:
                return
            if not self.syn_send_received and not self.ConnInfo.CONNECTION:
                self.ConnInfo.current_seq = random.randint(1, 1000)
                self.send_packet(Packet.build(flags=Flags.SYN.value, sequence_number=self.ConnInfo.current_seq))
                self.syn_send_received = True
                print("INFO: Establishing connection...")
            while self.syn_send_received and not self.ConnInfo.CONNECTION:
                time.sleep(1)


### MAIN ###

    def communicate(self):
        listening = threading.Thread(target=self.LISTENER, args=(1500,))
        keep_alive = threading.Thread(target=self.keep_alive)
        sending = threading.Thread(target=self.SENDER.run)
        listening.start()
        sending.start()
        # keep_alive.start()

        asyncio.run(self.menu())

        listening.join()
        keep_alive.join(0)
        sending.join(0)

### input
    def handle_input(self):
        while True:
            inp = input()
            # print(inp, end='')
            if self.Halt.is_set():
                print("INFO: Console is Halted because of incoming transmission don't write anything")
            if inp.strip() and not self.Halt.is_set():
                # print("... put into queue")
                self.INPUT.put(inp)

    def clear_queue(self):
        # i geuss a bit risky but we are getting input so it should be fine
        while not self.INPUT.empty(): self.INPUT.get_nowait()

### Menu
    async def menu(self):
        while self.ConnInfo.CONNECTION:
            if self.Halt.is_set():
                await self.Halt.wait()
            else:
                print("Choose option:")
                print("[M]essage | [S]end files | [Q]uit")

                choice = None
                # TODO: if I keep the HALT in input handler i should be able to safely remove this one here and also add a classic get() with no exception throwing
                while self.ConnInfo.CONNECTION and not self.Halt.is_set():
                    try:
                        choice = self.INPUT.get_nowait()
                        break
                    except queue.Empty:
                        time.sleep(1)
                        continue
                print("dbg: outside the input loop")
                if self.Halt.is_set():
                    continue
                match choice.lower():
                    case 'm':
                        print("sending message...")
                        await self.send_message()
                        continue
                    case 's':
                        print("sending files...")
                        await self.send_file()
                        continue
                    case 'q':
                        print("quiting...")
                        self.ConnInfo.CONNECTION = False
                        break
                    case _:
                        print("no such option...")
                        continue

    ### FILE functions


    def incoming_file(self, pkt):
        # Halting comm because we are about to receive a file
        # get the frag size
        self.frag_size = int.from_bytes(pkt.data, "big", signed=False)
        self.SENDER.queue_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.ConnInfo.current_seq))
        pass

    async def send_file(self):
        self.clear_queue()
        print("not now")

        pass
