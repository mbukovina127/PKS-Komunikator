from peer import Peer
from client import Client
from server import Server

if __name__ == '__main__':

    print("Choose type...")
    while True:
        program: str = input("[S]erver / [C]lient")
        if (program.upper() in ['S', 'C']):
            break
        else:
            print("ERROR: incorect type")

    ip = input("IP address D[127.0.0.1]: ")
    listening_port = input("Listening port D[50601]: ")
    transmitting_port = input("Transmitting port D[50602]: ")


    if (ip == ''):
        ip = "127.0.0.1"
    if (listening_port == ''):
        listening_port = 50601
    if (transmitting_port == ''):
        transmitting_port = 50602

    if (program.upper() == 'C'):
        client = Client(ip, listening_port, transmitting_port)
    if (program.upper() == 'S'):
        client = Server(ip, listening_port, transmitting_port)
    peer = Peer(ip, listening_port, transmitting_port)
    peer.launch()


