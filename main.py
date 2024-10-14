from peer import Peer
from client import Client
from server import Server

if __name__ == '__main__':

    print("Choose type...")
    print("[S]erver / [C]lient")
    while True:
        program: str = input("")
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
    else:
        listening_port = int(listening_port)
    if (transmitting_port == ''):
        transmitting_port = 50602
    else:
        transmitting_port = int(transmitting_port)

    if (program.upper() == 'C'):
        client = Client(ip, listening_port, transmitting_port)
        client.launch()
    if (program.upper() == 'S'):
        server = Server(ip, listening_port, transmitting_port)
        server.launch()


