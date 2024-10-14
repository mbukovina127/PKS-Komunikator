import socket

from peer import Peer


class Server:
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
        print("Waiting for message")
        data = self.listening_socket.recv(1024)
        print("Message received: %s" % data)
        message = input("Message to reply with: ")
        self.transmitting_socket.sendto(bytes(message, "utf-8"), (self.dest_ip, self.port_transmit))
        print("Message sent")
        return

    def launch(self):
        print("Server up")
        self.init_connection()

        self.quit()

    def quit(self):
        print("Closing server...")

        self.listening_socket.close()
        # print("Listening socket closed...")
        self.transmitting_socket.close()
        # print("Transmitting socket closed...")
        print("Server offline")


