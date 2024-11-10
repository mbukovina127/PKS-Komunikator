import queue
import threading
import time

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
        with self._lock:
            self._dict.pop(seq)
            self._size -= 1
            return True

    def contains(self, sequence_number):
        with self._lock:
            return sequence_number in self._dict

class Sender:
    def __init__(self, socket, conn_info, lock, window: SlidingWindow, win_limit=4):
        self.socket = socket
        self.ConnInfo = conn_info
        self.send_lock = lock
        self.PACKETS = queue.Queue()
        self.WINDOW = window
        self.WIN_limit = win_limit
        #timer
        self.window_timer = 1



    def queue_packet(self, pkt):
        if isinstance(pkt, Packet):
            self.PACKETS.put(pkt)
        # its gonna be a list ok?
        else:
            [self.PACKETS.put(pkt[i]) for i in range(len(pkt))]

### Retransmitting
    def send_from_window(self, ack_sequence_number):
        with self.send_lock:
            self.socket.sendto(self.WINDOW.get(ack_sequence_number).to_bytes(), (self.ConnInfo.dest_ip, self.ConnInfo.dest_port))
            print("DBG: sent pkt from window " + str(ack_sequence_number))

    def retransmit(self, ack_sequence_number):
        while True:
            #if its still in the window Im going to assume it was not acknowledged
            if self.WINDOW.contains(ack_sequence_number) and isinstance(self.WINDOW.get(ack_sequence_number), Packet):
                self.send_from_window(ack_sequence_number)
            else:
                return
            time.sleep(self.window_timer)

### main

    def run(self):
        print("DBG: sender running")
        while True:
            while (not self.ConnInfo.CONNECTION
                   or self.WINDOW.__len__() == self.WIN_limit):
                time.sleep(1)

            while self.WINDOW.__len__() < self.WIN_limit:
                s_pkt = self.PACKETS.get() # blocking should matter much here
                # TODO: I have no idea what I should do when I lose connection
                # line | offset for data size | 1 for expected acknowledge
                ack_seq = s_pkt.sequence_number + s_pkt.seq_offset + 1
                self.WINDOW.add(ack_seq, s_pkt)
                print("DBG: packet in window")
                threading.Thread(target=self.retransmit, args=(ack_seq,)).start()

