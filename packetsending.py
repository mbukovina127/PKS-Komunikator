import queue
import random
import threading
import time

from packet import Packet


def simulate_packet_corruption(packet_data: bytes, corruption_rate: float = 0.1) -> bytes:
    corrupted_data = bytearray(packet_data)  # Convert to mutable type for manipulation

    if random.random() < corruption_rate:  # Decide if this byte will be corrupted
        for i in range(len(corrupted_data)):
            if random.random() < corruption_rate:  # Decide if this byte will be corrupted
                # Randomly flip a bit in the byte
                bit_to_flip = 1 << random.randint(0, 7)  # Select a random bit to flip
                corrupted_data[i] ^= bit_to_flip  # Flip the bit using XOR

    return bytes(corrupted_data)

class ThreadingSet:
    def __init__(self):
        self._set = set()
        self._lock = threading.Lock()  # Use threading.Lock instead of asyncio.Lock

    def add(self, item):
        with self._lock:  # Use standard lock without async
            self._set.add(item)

    def remove(self, item):
        with self._lock:
            self._set.remove(item)

    def discard(self, item):
        with self._lock:
            self._set.discard(item)

    def contains(self, item):
        with self._lock:
            return item in self._set

    def items(self):
        with self._lock:
            return list(self._set)

    def clear(self):
        with self._lock:
            self._set.clear()

    def __len__(self):
        with self._lock:
            return len(self._set)

class SlidingWindow:
    def __init__(self):
        self._dict = {}
        self._size = 0
        self._lock = threading.Lock()

    def __len__(self):
        return self._size

    def add(self, seq: int, pkt: Packet):
        with self._lock:
            self._dict[seq] = pkt
            self._size += 1

    def get(self, seq: int) -> Packet:
        with self._lock:
            return self._dict.get(seq)

    def remove(self, seq: int) -> bool:
        try:
            with self._lock:
                self._dict.pop(seq)
                self._size -= 1
                return True
        except KeyError:
            return False

    def clear_dictionary(self):
        with self._lock:
            self._size = 0
            self._dict.clear()

    def contains(self, sequence_number):
        with self._lock:
            return sequence_number in self._dict

class Sender:
    def __init__(self, socket, conn_info, lock, window: SlidingWindow, win_limit=100):
        self.socket = socket
        self.ConnInfo = conn_info
        self.send_lock = lock
        self.PACKETS = queue.Queue()
        self.WINDOW = window
        #window
        self.limit_lock = threading.Lock()
        self.Hard_limit = False
        self.WIN_limit = win_limit
        #timer
        self.retransmit_timer = 0.1
        self.clearing_queue = False



    def queue_packet(self, pkt):
        if isinstance(pkt, Packet):
            self.PACKETS.put(pkt)

        else:
            [self.PACKETS.put(pkt[i]) for i in range(len(pkt))]
        print("DBG: packet added to queue")


### Retransmitting
    def send_from_window(self, ack_sequence_number):
        packet_to_send = self.WINDOW.get(ack_sequence_number).to_bytes()

### KORUPCIA DAT
        packet_to_send = simulate_packet_corruption(packet_to_send, 0.1)

        with self.send_lock:
            self.socket.sendto(packet_to_send, (self.ConnInfo.dest_ip, self.ConnInfo.dest_port))
            # print("DBG: sent pkt from window " + str(ack_sequence_number))

    def retransmit(self, ack_sequence_number):
        st = time.time()
        dt = 0
        while dt < 15 and self.ConnInfo.CONNECTION:
            #if its still in the window Im going to assume it was not acknowledged
            if self.WINDOW.contains(ack_sequence_number):
                self.send_from_window(ack_sequence_number)
            else:
                return
            time.sleep(self.retransmit_timer)
            dt = time.time() - st
        if not self.clearing_queue:
            self.end_packet_sending()
### main

    def run(self):
        # print("DBG: sender running")
        while True:
            while (not self.ConnInfo.CONNECTION
                   or self.WINDOW.__len__() >= self.WIN_limit):
                time.sleep(0.1)
            while self.clearing_queue: time.sleep(0.1)
            while self.WINDOW.__len__() < self.WIN_limit:
                s_pkt = self.PACKETS.get() # blocking shouldnt matter much here
                # line | offset for data size | 1 for expected acknowledge
                ack_seq = s_pkt.sequence_number + s_pkt.seq_offset + 1
                self.WINDOW.add(ack_seq, s_pkt)
                # print("DBG: packet in window")
                threading.Thread(target=self.retransmit, args=(ack_seq,)).start()


    # TODO: I don't know if this is going to work
    def end_packet_sending(self):
        # how the clear window of
        self.clearing_queue = True
        print("ERROR: Failure to send packets... clearing cached packets")
        while True:
            try:
                self.PACKETS.get_nowait()
            except queue.Empty:
                self.WINDOW.clear_dictionary()
                print("INFO: Cached packets cleared")
                self.clearing_queue = False
                return
