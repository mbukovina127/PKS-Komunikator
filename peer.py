import asyncio
import math
import os
import queue
import random
import socket
import sys
import threading
import time
from ast import parse

from packet import Packet, Flags
from packetsending import ThreadingSet, Sender, SlidingWindow

HEADER_SIZE = 7
MAX_SEQ_NUMBER = 4_000_000_000

# TODO: terminate file sending a vycistit cache suboru
#       co ak nam nikdy nepride ocakavany seq num ale keep alive funguje
#       potrebujeme dat casovy limit ak nepride packet ktory updatne seq number
#       ak nic nepride potrebujeme prestat posielat subory

class ConnInfo:
    def __init__(self, ip, port_lst, port_trs):
        self.dest_ip = ip
        self.listen_port = port_lst
        self.dest_port = port_trs
    ### keep_alive
        self.pulse = 3
        self.epoch = 0
    ### states
        self.CONNECTION = False
        self.fin_recv = False
    ### sequence numbers
        self.current_seq = 0
        self.current_fallback = 0
        self.dest_seq = 0
        self.dest_fallback = 0

class Peer:
    def __init__(self, conn_info):
    ### connection variables
        self.ConnInfo = conn_info

    ### fragmentation
        self.frag_size = 1465
        self.trans_time = 0
        self.start_time = 0
        self.end_time = 0

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
        self.menu_halt = asyncio.Event()

    ### DATA
        self.RECEIVED = queue.Queue()
        self.SENT = ThreadingSet()
        self.INPUT = queue.Queue()
        self.WINDOW = SlidingWindow()
    ### Keep Alive
        self.KA_time = 5

    ### MSG
        self.message = ''
        # dictionary of seq n of msg packet
        self.message_buffer = {}
    ### files
        self.STR_arrived = False
        self.file_name = ""
        self.file_data: bytes = bytes(0)
        self.file_buffer = {}

        self.ok_time = 0
        self.sending_err = False
    ### THREADS
        self.SENDER = Sender(socket=self.transmitting_socket, conn_info=self.ConnInfo, lock=self.send_lock, window=self.WINDOW)


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

    def update_dest(self, offset: int = 1):
        self.ConnInfo.dest_seq += offset
        self.ConnInfo.dest_seq = self.ConnInfo.dest_seq % MAX_SEQ_NUMBER
        return self.ConnInfo.dest_seq

    def change_dest_seq(self, sequence_number):
        # print(f"DBG: ack offset {sequence_number}")
        self.ConnInfo.dest_seq = sequence_number % MAX_SEQ_NUMBER

    def update_current(self, offset: int = 1):
        self.ConnInfo.current_seq += offset
        self.ConnInfo.current_seq = self.ConnInfo.current_seq % MAX_SEQ_NUMBER
        return self.ConnInfo.current_seq

    def change_frag_size(self, frag_size: int):
        if frag_size < 1 or frag_size > 1465:
            raise ValueError()
        self.frag_size = frag_size

    def time_epoch(self):
        self.ConnInfo.epoch = time.time()

    def time_incoming(self):
        self.ok_time = time.time()

    def file_receiving_thread(self):
        print(f"DBG: started checking")
        while self.STR_arrived:
            # if the last in order packet arrived less than 10 seconds ago
            print(f"DBG: checking time: {time.time() - self.ok_time} with ok time being: {self.ok_time}" )
            if time.time() - self.ok_time > 15:
                if not self.sending_err:
                    print("ERROR: Incorrect data arriving for 15 seconds clearing stored data in 5 seconds... ")
                    threading.Timer(5, self.clear_file_buffers).start()
                    self.sending_err = True
                return
            time.sleep(2)
        # print("DBG: Ended successfully")
        return

### Packet parser
    #handeling acks for our sent packet. Removing them from our window should suffice

    def ack_received(self, pkt):
        if self.WINDOW.remove(pkt.sequence_number):
            if pkt.sequence_number > self.ConnInfo.dest_seq:
                # print("DBG: Received ack...")
                self.change_dest_seq(pkt.sequence_number)
            return True
        return False
            # print("DBG: ack removed successfully" + str(pkt.sequence_number))

    def verify_packet(self, pkt: Packet):
        if Packet.checkChecksum(pkt):
            print(f"INFO: Packet-{pkt.sequence_number} received -- success")
            return True
        else:
            print(f"INFO: Packet-{pkt.sequence_number} received -- fail")
            return False

    def PARSER(self):
        while True:
            pkt = self.RECEIVED.get()
            self.parse_packet(pkt)


    def parse_packet(self, pkt: Packet):
        self.time_epoch()
        # print(f"DBG: dsq - {self.ConnInfo.dest_seq} csq - {self.ConnInfo.current_seq}")
        match (pkt.flag):
            case Flags.KEEP_ALIVE.value:
                # print("DBG: KEEP ALIVE rec")
                self.send_packet(Packet.build(Flags.KAACK.value))
                return
            case Flags.KAACK.value:
                # print("DBG: KEEP ALIVE ACK rec")
                with self.ka_lock:
                    self.ConnInfo.pulse = 3
            #ack has seq of dest_seq + 1
            case Flags.ACK.value:
                if self.ConnInfo.fin_recv:
                    # print("DBG: Ack for fin received")
                    self.ack_received(pkt)
                    threading.Timer( 1, self.quit).start()
                self.ack_received(pkt)
                return
            # str seq of current
            case Flags.STR.value:
                self.incoming_file(pkt)
                return
            # Frag seq of current
            case Flags.FRAG.value | Flags.FRAG_F.value:
                if self.sending_err or not self.STR_arrived:
                    return
                if self.verify_packet(pkt):
                    self.process_frag(pkt)
                return
            #Frag seq of current
            case Flags.MSG.value | Flags.MSG_F.value:
                if self.verify_packet(pkt):
                    self.process_MSG(pkt)
                return
            case Flags.FIN.value:
                if self.verify_packet(pkt):
                    self.FIN_received(pkt)
                return
            case _:
                return


### THREAD FUNCTIONS

    def LISTENER(self, buffer_s):
        self.listening_socket.settimeout(60)
        while self.ConnInfo.CONNECTION:
            try:
                rec_pkt = self.recv_packet(buffer_s)
                try:
                    self.RECEIVED.put_nowait(rec_pkt)
                except queue.Full:
                    continue
            except socket.timeout:
                pass
            except SystemExit:
                return
            except OSError:
                return

### Terminating fucntions

    def init_termination(self):
        print("INFO: Terminating connection...")
        self.SENDER.queue_packet(Packet.build(flags=Flags.FIN.value, sequence_number=self.ConnInfo.dest_seq))

    def FIN_received(self, pkt):
        # if we received fin already we just send ack
        if self.ConnInfo.fin_recv:
            # print("DBG: Second fin received sending ack for fin")
            self.send_ack(pkt)
        else:
            # print("DBG: First fin received")
            #we get first fin we sed flag to true
            self.ConnInfo.fin_recv = True
            # we que fin it is going to send fin until it gets an ack from the the if above
            # after we send it we move to packet parser ack
            self.SENDER.queue_packet(Packet.build(flags=Flags.FIN.value, sequence_number=self.ConnInfo.dest_seq))
            # print("DBG: Sending fins")

    def quit(self):
        print("INFO: Closing connection...")
        self.ConnInfo.CONNECTION = False
        self.listening_socket.close()
        self.transmitting_socket.close()
        print("INFO: Offline")
        sys.exit(0)
### KEEP ALIVE FUNCTION

    def KEEP_ALIVE(self):
        # print("DBG: Keep alive running")
        while self.ConnInfo.CONNECTION:
            # print(f"DBG: last packet received at: {self.ConnInfo.epoch} current time is: {time.time()} difference: {time.time() - self.ConnInfo.epoch}")
            if time.time() - self.ConnInfo.epoch > self.KA_time:
                if self.ConnInfo.pulse < 0:
                    self.ConnInfo.CONNECTION = False
                    print("INFO: Keep alive - connection lost - no reply")
                    sys.exit(13)
                self.send_packet(Packet.build(flags=Flags.KEEP_ALIVE.value))
                with self.ka_lock:
                    self.ConnInfo.pulse -= 1
            time.sleep(self.KA_time)


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
                self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.update_dest()))
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
                    try:
                        ack_pkt, addr = self.listening_socket.recvfrom(1500)
                        ack_pkt = Packet(ack_pkt)
                    # print("DBG: ack received after syn sent")
                        if ack_pkt.flag == Flags.ACK.value: # we wait for an ack packet for our syn packet
                            if ack_pkt.sequence_number == self.ConnInfo.current_seq +1: # it has to have seq +1 of the one we sent
                                self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.update_dest())) # we send ack for the one we received
                                self.ConnInfo.CONNECTION = True
                                self.update_current()
                                return
                    except socket.timeout:
                        continue
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
        keep_alive = threading.Thread(target=self.KEEP_ALIVE)
        sending = threading.Thread(target=self.SENDER.run)
        parser = threading.Thread(target=self.PARSER)
        listening.start()
        parser.start()
        sending.start()
        keep_alive.start()

        asyncio.run(self.menu())

        listening.join()
        keep_alive.join(0)
        sending.join(0)
        parser.join(0)

### INPUT
    def handle_input(self):
        try:
            while True:
                inp = input()
                if inp.strip():
                    # print("... put into queue")
                    self.INPUT.put(inp)
                else:
                    self.INPUT.put("\n")
        except UnicodeDecodeError:
            print("INFO: Quiting input handler thread")
            return
        except SystemExit:
            return
    def clear_queue(self):
        # i geuss a bit risky but we are getting user input so it should be fine
        while not self.INPUT.empty(): self.INPUT.get_nowait()

### Menu
    async def menu(self):
        while self.ConnInfo.CONNECTION:
            if self.menu_halt.is_set():
                await self.menu_halt.wait()
            else:
                print("Choose option:")
                print("[M]essage | [S]end files | [C]hange fragment size | [Q]uit ")

                choice = None
                while True:
                    try:
                        if self.menu_halt.is_set():
                            continue
                        choice = self.INPUT.get_nowait()
                        break
                    except queue.Empty:
                        time.sleep(0.1)
                        continue
                # print("DBG: outside the input loop")
                if choice == '\n' or self.menu_halt.is_set() or not self.ConnInfo.CONNECTION:
                    continue

                match choice.lower():
                    case 'm':
                        print("INFO: Message sending")
                        await self.send_message()
                        continue
                    case 's':
                        print("INFO: File sending")
                        await self.send_file()
                        continue
                    case 'c':
                        self.prompt_frag_change()
                        continue
                    case 'q':
                        self.init_termination()
                        break

                    case _:
                        print("ERROR: No such option!")
                        continue

    ### Message function

    async def send_message(self):
        self.clear_queue()
        # getting fragment size
        while True:
            print("Write message [--quit]: ", end='')
            inp = self.INPUT.get()
            if inp == '\n':
                continue
            break
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
        msg_chunks = []
        for i in range(0, math.ceil(len(message) / self.frag_size)):
            send_seq = seq + i * (self.frag_size + 1) % MAX_SEQ_NUMBER
            msg_chunks.append(Packet.build(flags=Flags.MSG.value
                                           , sequence_number=(send_seq)
                                           , data=(
                message[i * self.frag_size: i * self.frag_size + self.frag_size]).encode()))
        msg_chunks[-1].changeFlag(Flags.MSG_F.value)

        if len(msg_chunks) > 1:
            print(f"INFO: Sending message: "
                  f" size-{len(message)} |"
                  f" number of fragments-{len(msg_chunks)} |"
                  f" fragment size-{self.frag_size} |"
                  f"{' last fragment-' + str(msg_chunks[-1].seq_offset) + ' |' if msg_chunks[-1].seq_offset < self.frag_size else ''}")

        self.SENDER.queue_packet(msg_chunks)

    def print_MSG(self):
        if self.get_transmission_time():
            # print(f"DBG: {self.trans_time}")
            print(f"INFO: Transmission time-{(self.trans_time // 60):.0f}m:{(self.trans_time % 60):.2f}s")
        print(f"Message received\n---{self.message}")
        self.message = ""

    # but I guess it will do
    def process_MSG(self, pkt: Packet):
        # print("DBG: processing MSG packet... message thus far: " + self.message)
        if pkt.flag == Flags.MSG.value:
            self.get_start_time()
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
                        self.get_end_time()
                        self.print_MSG()

                # set the ok time
                self.time_incoming()

            elif pkt.sequence_number > self.ConnInfo.current_seq:
#                 print("DBG: packet is out of order.. pkts seq: " + str(pkt.sequence_number) + ".. mine is: " + str(self.ConnInfo.current_seq))
                self.message_buffer[pkt.sequence_number] = pkt

        else:  # only other one is MSG_F
            if pkt.sequence_number == self.ConnInfo.current_seq:
#                 print("DBG: Fin is in order")
                self.message += pkt.data.decode()
                self.update_current(pkt.seq_offset + 1)
                self.get_end_time()
                self.print_MSG()
            else:
#                 print("DBG: Fin is out of order... pkts seq: " + str(pkt.sequence_number) + ".. mine is: " + str(self.ConnInfo.current_seq))
                self.message_buffer[pkt.sequence_number] = pkt

        self.send_ack(pkt)
### FILE functions
    async def send_file(self):
        self.clear_queue()
        while True:
            print("File path [--quit]: ")
            url = self.INPUT.get()
            if url == '\n':
                continue
            if os.path.isfile(url):
                break
            if url == "--quit":
                print("INFO: Quiting...")
                return
            print("ERROR: couldn't find the file")

        # split and send the file

        with open(url, "rb") as file:
            data = file.read()

        print("INFO: Sending first packet...")
        str_pkt = Packet.build(Flags.STR.value, sequence_number=self.ConnInfo.dest_seq, data=os.path.basename(url).encode())
        seq_old = self.ConnInfo.dest_seq
        self.SENDER.queue_packet(str_pkt)
        # wait until you get an ack for str
        while seq_old == self.ConnInfo.dest_seq: time.sleep(0.1)
        seq = self.ConnInfo.dest_seq
        print("INFO: Splitting file...")
        fragments = []
        for i in range(0, math.ceil(len(data) / self.frag_size)):
            send_seq = (seq + i*(self.frag_size+1)) % MAX_SEQ_NUMBER # looping over sequence numbers
            fragments.append(Packet.build(
                flags=Flags.FRAG.value,
                sequence_number=send_seq,
                data=data[i*self.frag_size: i*self.frag_size+ self.frag_size]
            ))
        fragments[-1].changeFlag(Flags.FRAG_F.value)

        self.SENDER.queue_packet(fragments)
        print(f"INFO: Sending file:"
              f" file name-{os.path.basename(url)}"
              f" size-{(len(data)//1024)}KB |"
              f" number of fragments-{len(fragments)} |"
              f" fragment size-{self.frag_size} |"
              f"{' last fragment-' + str(fragments[-1].seq_offset) + ' |' if fragments[-1].seq_offset < self.frag_size else ''}")

    def process_frag(self, pkt):
        if pkt.flag == Flags.FRAG.value:
            self.get_start_time()
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
                        self.get_end_time()
                        threading.Thread(target=self.save_file).start()
                self.time_incoming()
            elif pkt.sequence_number > self.ConnInfo.current_seq:
#                 print("DBG: packet is out of order.. pkts seq: " + str(pkt.sequence_number) + ".. mine is: " + str(self.ConnInfo.current_seq))
                self.file_buffer[pkt.sequence_number] = pkt

        else: # only other one is MSG_F
            if pkt.sequence_number == self.ConnInfo.current_seq:
#                 print("DBG: Fin is in order")
                self.file_data += pkt.data
                self.update_current(pkt.seq_offset + 1)
                self.get_end_time()
                threading.Thread(target=self.save_file).start()
            else:
#                 print("DBG: Fin is out of order")
                self.file_buffer[pkt.sequence_number] = pkt

        self.send_ack(pkt)

    def prompt_frag_change(self):
        while True:
            print("Fragment size [1-1465] | [K]eep default: ", end='')
            inp = self.INPUT.get()
            if inp == '\n':
                continue
            if inp == "K" or inp == "k":
                print(f"INFO: Fragmentation size is: {self.frag_size}")
                return
            try:
                self.change_frag_size(int(inp))
                print(f"INFO: Fragmentation size changed to: {self.frag_size}")
                break
            except ValueError:
                print("ERROR: Wrong input")
                continue


    def save_file(self):
        self.STR_arrived = False # to signal sending checker to end
        self.get_end_time()
        self.clear_queue()
        while True:
            print("Path to save directory [--quit]: ")
            url = self.INPUT.get()
            if url == '\n':
                continue
            if os.path.isdir(url):
                break
            if url == "--quit":
                print("INFO: Discarding file...")
                #self.menu_halt.clear()
                self.clear_file_buffers()
                print("INFO: file discarded")
                return
            print("ERROR: Couldn't find the directory")

        with open(url + "\\" + self.file_name, "wb") as file:
            file.write(self.file_data)
        print("INFO: File saved successfully to: " + url + "\\" + self.file_name + "-" + str(self.file_data.__sizeof__()//1024) + "KB")
        if self.get_transmission_time():
            print(f"INFO: File received time-{(self.trans_time//60):.0f}m:{(self.trans_time%60):.2f}s")
        self.SENDER.queue_packet(Packet.build(Flags.MSG_F.value, sequence_number=self.ConnInfo.dest_seq, data=f"System: File-{self.file_name} received in {self.trans_time:.2} sec.".encode()))
        threading.Timer(0.5, self.clear_file_buffers).start()

    def clear_file_buffers(self):
        self.file_name = ""
        self.file_data = bytes(0)
        # god damn ugly
        if self.sending_err:
            for seq, pkt in self.file_buffer.items():
                if seq + pkt.seq_offset + 1 > self.ConnInfo.current_seq:
                    self.ConnInfo.current_seq = seq + pkt.seq_offset + 1
        self.file_buffer = {}
        self.STR_arrived = False
        self.sending_err = False
        print("INFO: stored data cleared")

    def incoming_file(self, pkt):
        if pkt.sequence_number != self.ConnInfo.current_seq:
            return
        self.file_name = pkt.data.decode()
        print("INFO: Incoming file: " + self.file_name)
        print("INFO: Halting menu")
        self.update_current(pkt.seq_offset + 1)
        self.send_ack(pkt)

        self.STR_arrived = True
        self.time_incoming()
        threading.Thread(target=self.file_receiving_thread).start()
    # the thread will start if it didn't receive a file packet in a longer time it's going to clear buffer
    # But I also need to take care of loosing conection as that can trigger buffer clearing
    def get_start_time(self):
        if self.start_time == 0:
            self.trans_time = 0
            self.start_time = time.time()
        pass

    def get_end_time(self):
        self.end_time = time.time()
        pass

    def get_transmission_time(self):
        if self.start_time != 0:
            self.trans_time = self.end_time - self.start_time
            self.end_time = 0
            self.start_time = 0
            return True
        return False