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

class Sender:
    def __init__(self, socket, conn_info, sent_packets, lock):
        self.socket = socket
        self.ConnInfo = conn_info
        self.send_lock = lock
        self.PACKETS = queue.Queue()
        self.SENT = sent_packets

    def queue_packet(self, pkt):
        if isinstance(pkt, Packet):
            self.PACKETS.put(pkt)
        # its gonna be a list ok?
        else:
            # TODO: I could put the whole list there so I know when to start selective repeat while sending files or messages
            [self.PACKETS.put(pkt[i]) for i in range(len(pkt))]

    def run(self):
        while True:
            while not self.ConnInfo.CONNECTION: time.sleep(1)

        # TODO: rework this to work with AQR selective repeat
            s_pkt = self.PACKETS.get()
            # print("DBG: received packet to send")
            # sequence number = base
            # line | offset for data size | 1 for expected acknowledge
            self.SENT.add(s_pkt.sequence_number + s_pkt.seq_offset + 1)
            with self.send_lock:
                self.socket.sendto(s_pkt.to_bytes(), (self.ConnInfo.dest_ip, self.ConnInfo.dest_port))
