import socket

from packet import Packet, Flags

from peer import Peer

class Client:
    def __init__(self, ip, port_l, port_t):
        self.dest_ip = ip
        self.port_listen = port_l
        self.port_transmit = port_t
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listening_socket.bind((self.dest_ip, self.port_listen))

        print("Client created successfully")

    def send_packet(self, packet: Packet):
        self.transmitting_socket.sendto(packet.to_bytes(), (self.dest_ip, self.port_transmit))


    def init_connection(self):
        sync_packet = Packet.build(flags=Flags.SYN.value)
        # send sync packet
        # expect ack packet
        # send ack packet
        self.listening_socket.settimeout(5)
        while True:

            self.send_packet(sync_packet)
            # TODO: change buffer size
            try:
                data, addr = self.listening_socket.recvfrom(1024)
                rec_pkt = Packet(data)
                if (rec_pkt.flag == Flags.ACK.value):
                    break;
            except socket.timeout:
                print("No reply... trying again")

        self.send_packet(Packet.build(flags=Flags.ACK.value))
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

        self.quit()

    def quit(self):
        print("Closing client...")

        self.listening_socket.close()
        # print("Listening socket closed...")
        self.transmitting_socket.close()
        # print("Transmitting socket closed...")
        print("Client offline")


