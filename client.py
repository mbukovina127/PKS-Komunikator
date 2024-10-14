import socket

from peer import Peer

class Client:
    def __init__(self, ip, port_l, port_t):
        self.dest_ip = ip
        self.port_listen = port_l
        self.port_transmit = port_t
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind((self.dest_ip, self.port_listen))
        self.transmitting_socket.bind((self.dest_ip, self.port_transmit))

        print("Client created successfully")

    def init_connection(self):
        message = input("Send message: ")
        self.transmitting_socket.sendto(bytes(message, 'utf-8'), (self.dest_ip, self.port_transmit))
        print("Message sent successfully")
        data = self.transmitting_socket.recv(1024)
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


