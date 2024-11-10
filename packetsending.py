import queue
import threading
import time
from tkinter.tix import WINDOW

from packet import Packet


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
        self._lock = threading.Lock()

    def add(self, seq: int, pkt: Packet):
        with self._lock:
            self._dict[seq] = pkt

    def get(self, seq: int) -> Packet:
        with self._lock:
            return self._dict.get(seq)

    def remove(self, seq: int):
        with self._lock:
            self._dict.pop(seq)

    def contains(self, sequence_number):
        with self._lock:
            return sequence_number in self._dict


class Sender:
    def __init__(self, socket, conn_info, sent_packets, lock, window: SlidingWindow, win_limit=4):
        self.socket = socket
        self.ConnInfo = conn_info
        self.send_lock = lock
        self.PACKETS = queue.Queue()
        self.WINDOW = window
        self.WIN_size = 0
        self.WIN_limit = win_limit
        #timer
        self.window_timer = 1
    # I have a window of four packets that I sent
    # I when I receive a packet that was sent first I remove it from the base of window
    # if I receive a packet after the first one I sent all the previous packets again



    def queue_packet(self, pkt):
        if isinstance(pkt, Packet):
            self.PACKETS.put(pkt)
        # its gonna be a list ok?
        else:
            [self.PACKETS.put(pkt[i]) for i in range(len(pkt))]

    # I need an observer function that
    # I need a WINDOW fill function that fills the window until it can't anymore the can't is going to be a timeout exception with the get_nowait()
    # when It's done

### Retransmitting
    def send_from_window(self, sequence_number):
        with self.send_lock:
            self.socket.sendto(self.WINDOW.get(sequence_number).to_bytes(), (self.ConnInfo.dest_ip, self.ConnInfo.dest_port))

    def retransmit(self, sequence_number):
        while True:
            time.sleep(self.window_timer)
            #if its still in the window Im going to assume it was not acknowledged
            if self.WINDOW.contains(sequence_number) and isinstance(self.WINDOW.get(sequence_number), Packet):
                self.send_from_window(sequence_number)
            else:
                return


    def run(self):
        while True:
            while (not self.ConnInfo.CONNECTION
                   or self.WIN_size == self.WIN_limit):
                time.sleep(1)

            while self.WIN_size < self.WIN_limit:
                s_pkt = self.PACKETS.get() # blocking should matter much here
                # line | offset for data size | 1 for expected acknowledge
                #TODO: I have no idea what I should do when I lose connection
                ack_seq = s_pkt.sequence_number + s_pkt.seq_offset + 1
                self.WINDOW.add(ack_seq, s_pkt)
                threading.Thread(target=self.retransmit, args=(ack_seq, s_pkt,)).start()

