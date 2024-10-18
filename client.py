import socket
import threading

from pyexpat.errors import messages

from packet import Packet, Flags

from peer import Peer

class Client(Peer):
    def __init__(self, ip, port_l, port_t):
        super().__init__(ip, port_l, port_t)
        self.listening_socket.bind(('0.0.0.0', self.listen_port))
        print("Client created successfully")

    def init_connection(self):
        self.listening_socket.settimeout(5)
        sync_packet = Packet.build(flags=Flags.SYN.value)
        while True:

            self.send_packet(sync_packet)
            print("SYN sent... ", end="")
            # TODO: change buffer size
            try:
                rec_pkt = self.recv_packet(1024)
                if (rec_pkt.flag == Flags.ACK.value):
                    print("ACK received")
                    break
            except socket.timeout:
                print("no reply... trying again")

        self.send_packet(Packet.build(flags=Flags.ACK.value))
        print("Connection established")
        return

    def launch(self):
        print("Client up")
        self.init_connection()
        listen_thread = threading.Thread(target=self.message_listen())
        listen_thread.start()
        self.message_handler()
        input("wait")
        self.quit()


