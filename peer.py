import random
import threading
import time
from enum import Enum
from sys import flags

from packet import Packet, Flags
import asyncio
import socket

class State(Enum):
    Exit = 0
    Halt = 1
    InMenu = 2
    SendMessage = 3
    SendFile = 4


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

    ### async variables
        self.CONNECTION = False
        self.syn_send_received = False
        self.fin_send = False

    ### menu functionality
        self.Halt = asyncio.Event()

    ### sequence numbers
        self.current_seq = 0
        self.current_fallback = 0
        self.expect_seq = 0
        self.expect_fallback = 0

    ### Keep Alive
        self.KA_time = 15
        self.pulse = 3

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
        self.expect_fallback = self.expect_seq
        self.expect_seq += offset
        return self.expect_seq

    def update_current(self, offset: int = 1):
        self.current_fallback = self.current_seq
        self.current_seq += offset
        return self.current_seq

### Message function

    async def send_message(self):
        inp = input("Write message [--quit]: ")
        if not inp.strip() or inp.lower() == "--quit":
            return True
        if self.CONNECTION:
            self.send_packet(Packet.build(Flags.MSG.value, self.expect_seq, inp.encode()))
            print("INFO: Message sent")
            return True
        else:
            print("ERROR: No connection")
            return False

### Packet parser

    def parse_packet(self, pkt: Packet):
        # print("pkt received")
        match (pkt.flag):
            case Flags.KEEP_ALIVE.value:
                # print("DBG: KEEP ALIVE rec")
                self.pulse = 3
                return
            case Flags.ACK.value:
                if (self.fin_send == True):
                    quit()
                return
            case Flags.STR.value:
                self.Halt.set()
                self.incoming_file(pkt)
                return
            case Flags.FRAG.value:
                return
            case Flags.FRAG_F.value:
                # DO SOMETHING
                self.Halt.clear()
                return
            case Flags.MSG.value:
                print(pkt.data.decode("utf-8"))
                return
            case Flags.FIN.value:
                self.FIN_received()
                return
            case _:
                return

### THREAD FUNCTIONS

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

### Terminating fucntions

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
            # print("DBG: heart beat sent")
            time.sleep(self.KA_time)

    def heart_beat(self):
        ka_pkt = Packet.build(flags=Flags.KEEP_ALIVE.value)
        self.transmitting_socket.sendto(ka_pkt.to_bytes(), (self.dest_ip, self.dest_port))

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
                self.expect_seq = rec_pkt.sequence_number
                print("DBG: syn received first seq ==", end="")
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
                    self.update_current()
                    return

                print ("DBG: seq doesn't match ", end="")
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
                            self.update_current()
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


### MAIN ###

    def communicate(self):
        listening = threading.Thread(target=self.LISTENER, args=(1500,))
        keep_alive = threading.Thread(target=self.keep_alive)
        listening.start()
        keep_alive.start()
        print("You can now send messages")

        asyncio.run(self.menu())


        # TODO: how the fuck do I remake this into an observer
        # TODO: I need a thread for menu because I need to cancel the input waiting if something comes up
        # TODO: I need a way for a listner to comunicate with menu in case a file arrives
        # when state is changed what should I update
        # lets have a function update that updates the state machine after that it calls the update switch which checks what to do
        # if halt happens it turns off menu thread
        # if exit happens the same thing as before and terminates connection
        # if menu state is there it should start the menu thread
        # in menu thread it can call the send msg and send file state and exit state
        # but I can't call the update inside the menu because it would need to terminate it's own thread
        # but I can't terminate the menu with halt and exit flag with no worry
        # and I could terminate the menu with send msg and send file by changing the variable and then exiting the function into the updater
        # but how the fuck do I do that if I call the updater only when I switch states I should stay at that state until I switch it
        #

        listening.join()


### Menu
    async def menu(self):
        while self.CONNECTION:
            if self.Halt.is_set():
                await self.Halt.wait()
            else:
                print("Choose option:")
                print("[M]essage | [S]end files | [Q]uit")

                choice = None
                while self.CONNECTION and not self.Halt.is_set():
                    try:
                        choice = await asyncio.wait_for(asyncio.to_thread(input), timeout=3)
                        break
                    except asyncio.TimeoutError:
                        # print("dbg: input timeout")
                        if self.Halt.is_set():
                            break
                        continue
                print("dbg: outside the input loop")
                if self.Halt.is_set():
                    continue
                if not isinstance(choice, str):
                    break
                match choice.lower():
                    case 'm':
                        print("sending message...")
                        await self.send_message()
                        break
                    case 's':
                        print("sending files...")
                        await self.send_file()
                        break
                    case 'q':
                        print("quiting...")
                        self.CONNECTION = False
                        break

    ### FILE functions


    def incoming_file(self, pkt):
        # Halting comm because we are about to receive a file
        # get the frag size
        self.frag_size = int.from_bytes(pkt.data, "big", signed=False)


        self.send_packet(Packet.build(flags=Flags.ACK.value, sequence_number=self.current_seq))
        pass

    async def send_file(self):
        pass

