import asyncio
import math
import os
import queue
import random
import socket
import threading
import time
from enum import Enum

from packet import Packet, Flags
from packetsending import ThreadingSet, Sender, SlidingWindow

HEADER_SIZE = 7


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
    ### keep_alive
        self.pulse = 3
    ### states
        self.CONNECTION = False
        self.fin_recv = False
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
        self.frag_size = 1465

    ### socket setup
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.bind(('0.0.0.0', self.ConnInfo.listen_port))
        self.listening_socket.settimeout(60)

    ### handshake variables
        self.syn_send_received = False

    ### Threading functionality
        self.send_lock = threading.Lock()
        self.recv_lock = threading.Lock()
        self.ka_lock = threading.Lock()
        self.Halt = asyncio.Event()

    ### DATA
        self.SENT = ThreadingSet()
        self.INPUT = queue.Queue()
        self.WINDOW = SlidingWindow()

    ### MSG
        self.message = ''
        # dictionary of seq n of msg packet
        self.message_buffer = {}
    ### Keep Alive
        self.KA_time = 5

    ### files
        self.file_name = ""
        self.file_data: bytes = bytes(0)
        self.file_buffer = {}

    ### THREADS
        self.SENDER = Sender(socket=self.transmitting_socket, conn_info=self.ConnInfo, lock=self.send_lock, window=self.WINDOW)
        # self.RECEIVER= Receiver(socket=self.listening_socket, conn_info=self.ConnInfo, s_lock=self.send_lock, ka_lock=self.ka_lock, window=self.WINDOW)


### PACKET FUNCTIONS

    def send_packet(self, packet: Packet):
        with self.send_lock:
            self.transmitting_socket.sendto(packet.to_bytes(), (self.ConnInfo.dest_ip, self.ConnInfo.dest_port))

    def recv_packet(self, buffer_s):
        with self.recv_lock:
            data, addr = self.listening_socket.recvfrom(buffer_s)
        return Packet(data)

    def send_ack(self, pkt: Packet):
        ack_seq = pkt.sequence_number + pkt.seq_offset + 1
        # print("DBG: about to send ack")
        self.send_packet(Packet.build(Flags.ACK.value, sequence_number=ack_seq))
        # print("DBG: sent ack" + str(ack_seq))

### Working with parameters

    def update_expected(self, offset: int = 1):
        self.ConnInfo.dest_fallback = self.ConnInfo.dest_seq
        self.ConnInfo.dest_seq += offset
        return self.ConnInfo.dest_seq

    def update_current(self, offset: int = 1):
        self.ConnInfo.current_fallback = self.ConnInfo.current_seq
        self.ConnInfo.current_seq += offset
        return self.ConnInfo.current_seq

    def change_frag_size(self, frag_size: int):
        # TODO: check if its fragmenting further in tcp
        if frag_size < 1 or frag_size > 1465:
            raise ValueError()
        self.frag_size = frag_size


### Message function

    async def send_message(self):
        self.clear_queue()
        #getting fragment size
        print("Write message [--quit]: ", end='')
        inp = self.INPUT.get()
        if inp.lower() == "--quit":
            print("INFO: Not sending any message")
            return True
        if self.ConnInfo.CONNECTION:
            self.split_message(inp)
            print("INFO: Message sent")
            return True
        else:
            print("ERROR: No connection")
            return False

    def split_message(self, message: str):
        seq = self.ConnInfo.dest_seq
        # TODO: wonky as fuk
        # TODO: doenst work I need a better for loop
        msg_chunks = [
            (Packet.build(flags=Flags.MSG.value
                           ,sequence_number=(seq + i*(self.frag_size+1))
                           ,data=(message[i*self.frag_size: i*self.frag_size+ self.frag_size]).encode()) )
            for i in range(0, math.ceil(len(message) / self.frag_size))]
        msg_chunks[-1].changeFlag(Flags.MSG_F.value)
        self.SENDER.queue_packet(msg_chunks)

    def print_MSG(self):
        print("Message received: ", end='')
        print(self.message)
        self.message = ""

    # TODO: wonky as two fucks
    # but I guess it will do
    def process_MSG(self, pkt: Packet):
        # print("DBG: processing MSG packet... message thus far: " + self.message)
        if pkt.flag == Flags.MSG.value:
            if pkt.sequence_number == self.ConnInfo.current_seq:
                # print("DBG: packet is in order.. pkts seq: " + str(pkt.sequence_number) + ".. mine is: " + str(self.ConnInfo.current_seq))
                self.message += pkt.data.decode()
                self.update_current(pkt.seq_offset + 1)
                # check out of order packets
                while self.ConnInfo.current_seq in self.message_buffer:
                    pkt = self.message_buffer.pop(self.ConnInfo.current_seq)
                    self.message += pkt.data.decode()
                    self.update_current(pkt.seq_offset + 1)
                    if pkt.flag == Flags.MSG_F.value:
                        self.print_MSG()

            elif pkt.sequence_number > self.ConnInfo.current_seq:
                # print("DBG: packet is out of order.. pkts seq: " + str(pkt.sequence_number) + ".. mine is: " + str(self.ConnInfo.current_seq))
                self.message_buffer[pkt.sequence_number] = pkt

        else: # only other one is MSG_F
            if pkt.sequence_number == self.ConnInfo.current_seq:
                # print("DBG: Fin is in order")
                self.message += pkt.data.decode()
                self.update_current(pkt.seq_offset + 1)
                self.print_MSG()
            else:
                # print("DBG: Fin is out of order... pkts seq: " + str(pkt.sequence_number) + ".. mine is: " + str(self.ConnInfo.current_seq))
                self.message_buffer[pkt.sequence_number] = pkt

        self.send_ack(pkt)

### Packet parser
    #handeling acks for our sent packet. Removing them from our window should suffice

    def ack_received(self, pkt):
        if self.WINDOW.remove(pkt.sequence_number):
            if pkt.sequence_number > self.ConnInfo.dest_seq:
                # print("DBG: Received ack...")
                self.ConnInfo.dest_seq = pkt.sequence_number
            return True
        return False
            # print("DBG: ack removed successfully" + str(pkt.sequence_number))

    def parse_packet(self, pkt: Packet):
        if not self.verify_packet(pkt):
            return False
        match (pkt.flag):
            case Flags.KEEP_ALIVE.value:
                # print("DBG: KEEP ALIVE rec")
                with self.ka_lock:
                    self.ConnInfo.pulse = 3
                return
            #ack has seq of dest_seq + 1
            case Flags.ACK.value:
                # I send fin
                # They receive fin they set their flag on -- fin
                # they send fin -- fin
                # I recieve and I set my flag on -- fin
                # they send ack -- fin
                # I send ack -- fin
                # I get ack and quit
                # they get ack and quit
                if self.ConnInfo.fin_recv:
                    self.ack_received(pkt)
                    self.quit()
                self.ack_received(pkt)
                return
            # str seq of current
            case Flags.STR.value:
                self.incoming_file(pkt)
                return
            # Frag seq of current
            case Flags.FRAG.value:
                self.process_frag(pkt)
                return
            #Frag seq of current
            case Flags.FRAG_F.value:
                # DO SOMETHING
                self.process_frag(pkt)
                return
            #Frag seq of current
            case Flags.MSG.value:
                self.process_MSG(pkt)
                return
            case Flags.MSG_F.value:
                self.process_MSG(pkt)
                return
            case Flags.FIN.value:
                self.FIN_received()
                return
            case _:
                return

    # TODO: test needs a rework
    def verify_packet(self, pkt: Packet):
        return Packet.checkChecksum(pkt)

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
        self.send_packet(Packet.build(flags=Flags.FIN.value, sequence_number=self.ConnInfo.dest_seq))

    def FIN_received(self):
        self.send_packet(Packet.build(flags=Flags.FIN.value, sequence_number=self.ConnInfo.dest_seq))
        self.ConnInfo.fin_recv = True
    def quit(self):
        print("INFO: Closing connection...")
        self.ConnInfo.CONNECTION = False
        self.listening_socket.close()
        self.transmitting_socket.close()
        print("INFO: Offline")

### KEEP ALIVE FUNCTION

    def keep_alive(self):
        while self.ConnInfo.CONNECTION:
            if self.ConnInfo.pulse == 0:
                print("ERROR: Connection lost... heart beat not received")
                self.ConnInfo.CONNECTION = False
                return
            with self.ka_lock:
                self.ConnInfo.pulse -= 1
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
                # print("DBG: syn received first seq ==", end="")
                self.ConnInfo.current_seq = random.randint(1,900)
                if self.ConnInfo.current_seq == self.ConnInfo.dest_seq:
                    self.ConnInfo.current_seq += 100
                self.send_packet(Packet.build(flags=Flags.SYN.value, sequence_number=self.ConnInfo.current_seq))
                # print("DBG: new syn sent")
                self.syn_send_received = True
                time.sleep(0.5)
                self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.update_expected()))
                # print("DBG: ack sent")
                continue
            #we receive ack after we received syn packet
            if rec_pkt.flag == Flags.ACK.value and self.syn_send_received:
                # print("DBG: ack received after syn received first")
                if rec_pkt.sequence_number == (self.ConnInfo.current_seq + 1):
                    self.ConnInfo.CONNECTION = True
                    self.update_current()
                    return

                # print ("DBG: seq doesn't match ", end="")
            #we send syn packet first
            if rec_pkt.flag == Flags.SYN.value and self.syn_send_received:
                # print("DBG: syn received after syn sent")
                if self.ConnInfo.dest_seq == 0: # syn packet arrives after we send ours
                    # print("DBG: expected seq is empty")
                    self.ConnInfo.dest_seq = rec_pkt.sequence_number # we copy its sq number
                    ack_pkt, addr = self.listening_socket.recvfrom(1500)
                    ack_pkt = Packet(ack_pkt)
                    # print("DBG: ack received after syn sent")
                    if ack_pkt.flag == Flags.ACK.value: # we wait for an ack packet for our syn packet
                        if ack_pkt.sequence_number == self.ConnInfo.current_seq +1: # it has to have seq +1 of the one we sent
                            self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.update_expected())) # we send ack for the one we received
                            self.ConnInfo.CONNECTION = True
                            self.update_current()
                            return
                        # print("DBG: seq doesn't match")
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
            if inp.strip():
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
                print("[M]essage | [S]end files | [C]hange fragment size | [Q]uit ")

                choice = None
                # TODO: if I keep the HALT in input handler i should be able to safely remove this one here and also add a classic get() with no exception throwing
                while self.ConnInfo.CONNECTION:
                    try:
                        if self.Halt.is_set():
                            await self.Halt.wait()
                            self.clear_queue()
                        choice = self.INPUT.get_nowait()
                        break
                    except queue.Empty:
                        time.sleep(0.2)
                        continue
                # print("DBG: outside the input loop")
                if self.Halt.is_set():
                    continue

                match choice.lower():
                    case 'm':
                        print("INFO: sending message...")
                        await self.send_message()
                        continue
                    case 's':
                        print("INFO: sending file...")
                        await self.send_file()
                        continue
                    case 'c':
                        self.prompt_frag_change()
                    case 'q':
                        print("INFO: quiting...")
                        self.ConnInfo.CONNECTION = False
                        break

                    case _:
                        print("no such option...")
                        continue

### FILE functions
    #TODO: setting up a timeout function that stops clears file buffers if no "file" packet has been sent in a while
    #TODO: it should start after receiving a STR packet


    async def send_file(self):
        self.clear_queue()
        while True:
            print("File path [--quit]: ")
            url = self.INPUT.get()
            if os.path.isfile(url):
                break
            print("ERROR: couldn't find the file")

        # split and send the file

        with open(url, "rb") as file:
            data = file.read()


        # TODO: I will do this without STR flag at first Ill see how it's going to go
        # print("DBG: splitting message first seq is " + str(seq))
        str_pkt = Packet.build(Flags.STR.value, sequence_number=self.ConnInfo.dest_seq, data=os.path.basename(url).encode())
        seq_old = self.ConnInfo.dest_seq
        self.SENDER.queue_packet(str_pkt)
        # wait until you get an ack for str
        while seq_old == self.ConnInfo.dest_seq: time.sleep(0.1)
        seq = self.ConnInfo.dest_seq
        fragments = [( Packet.build(
            flags=Flags.FRAG.value,
            sequence_number=(seq + i*(self.frag_size+1))
                           ,data=(data[i*self.frag_size: i*self.frag_size+ self.frag_size])))
            for i in range(0, math.ceil(len(data) / self.frag_size))]
        fragments[-1].changeFlag(Flags.FRAG_F.value)
        # fragments.insert(0, Packet.build(Flags.STR.value, sequence_number=self.ConnInfo.current_seq, data=))
        self.SENDER.queue_packet(fragments)
        print("INFO: file is being sent...")

    def process_frag(self, pkt):
        if pkt.flag == Flags.FRAG.value:
            if pkt.sequence_number == self.ConnInfo.current_seq:
                # print("DBG: packet is in order.. pkts seq: " + str(pkt.sequence_number) + ".. mine is: " + str(self.ConnInfo.current_seq))
                self.file_data += pkt.data
                self.update_current(pkt.seq_offset + 1)
                # check out of order packets
                while self.ConnInfo.current_seq in self.file_buffer:
                    pkt = self.file_buffer.pop(self.ConnInfo.current_seq)
                    self.file_data += pkt.data
                    self.update_current(pkt.seq_offset + 1)
                    if pkt.flag == Flags.FRAG_F.value:
                        threading.Thread(target=self.save_file).start()

            elif pkt.sequence_number > self.ConnInfo.current_seq:
                # print("DBG: packet is out of order.. pkts seq: " + str(pkt.sequence_number) + ".. mine is: " + str(self.ConnInfo.current_seq))
                self.file_buffer[pkt.sequence_number] = pkt

        else: # only other one is MSG_F
            if pkt.sequence_number == self.ConnInfo.current_seq:
                # print("DBG: Fin is in order")
                self.file_data += pkt.data
                self.update_current(pkt.seq_offset + 1)
                threading.Thread(target=self.save_file).start()
            else:
                # print("DBG: Fin is out of order")
                self.file_buffer[pkt.sequence_number] = pkt

        self.send_ack(pkt)

    def prompt_frag_change(self):
        while True:
            print("Fragment size [1-1465] | [K]eep default: ", end='')
            inp = self.INPUT.get()
            if inp != "K" or "k":
                try:
                    self.change_frag_size(int(inp))
                    break
                except ValueError:
                    print("ERROR: Wrong input")
                    continue
            else:
                return

    def save_file(self):
        print("Incoming file choose save location...")
        self.Halt.set() # yaay
        print("DBG: halting menu")
        self.clear_queue()
        while True:
            print("Directory path [--quit]: ")
            # TODO: possible to replace with classic input()
            url = self.INPUT.get()
            if os.path.isdir(url):
                break
            if url == "--quit":
                print("Discarding file...")
                self.Halt.clear()
                self.clear_file_buffers()
                return
            print("ERROR: Couldn't find the directory")

        self.Halt.clear()
        print("DBG: Resuming menu")
        with open(url + "\\" + self.file_name, "wb") as file:
            file.write(self.file_data)
        print("INFO: File saved successfully")
        self.clear_file_buffers()

    def clear_file_buffers(self):
        self.file_name = ""
        self.file_data = bytes(0)
        self.file_buffer = {}

    def incoming_file(self, pkt):
        if pkt.sequence_number != self.ConnInfo.current_seq:
            return
        self.file_name = pkt.data.decode()
        self.update_current(pkt.seq_offset + 1)
        self.send_ack(pkt)
    # the thread will start if it didn't receive a file packet in a longer time it's going to clear buffer
    # But I also need to take care of loosing conection as that can trigger buffer clearing


