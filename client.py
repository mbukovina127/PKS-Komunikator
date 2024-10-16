import socket

from packet import Packet, Flags

from peer import Peer

class Client(Peer):
    def __init__(self, ip, port_l, port_t):
        super().__init__(ip, port_l, port_t)
        print("Client created successfully")

    def init_connection(self):
        sync_packet = Packet.build(flags=Flags.SYN.value)
        self.listening_socket.settimeout(5)
        while True:

            self.send_packet(sync_packet)
            print("SYN sent... ", end="")
            # TODO: change buffer size
            try:
                rec_pkt = super().recv_packet(1024)
                if (rec_pkt.flag == Flags.ACK.value):
                    print("ACK received")
                    break
            except socket.timeout:
                print("no reply... trying again")

        self.send_packet(Packet.build(flags=Flags.ACK.value))
        print("Connection established")
        return

    def init_connection_message(self):
        message = input("Send message: ")
        self.transmitting_socket.sendto(bytes(message, 'utf-8'), (self.dest_ip, self.port_transmit))
        print("Message sent successfully")
        data = self.listening_socket.recv(1024)
        print("Message received from server: %s" % data)
        return
        

    def launch(self):
        print("Client up")
        self.init_connection()

        super().init_termination()



