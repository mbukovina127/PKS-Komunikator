import socket


class Peer:
    def __init__(self, ip, port_l, port_t):
        self.ip = ip
        self.port_l = port_l
        self.port_t = port_t
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.transmitting_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind((self.ip, self.port_l))
        self.transmitting_socket.bind((self.ip, self.port_t))

    def launch(self):
        return

    async def listen(self):
        return


    def quit(self):
        self.sock.close()
        print("Server offline...")
