from peer import Peer

if __name__ == '__main__':

    program: str = ""

    while True:
    print("Connect to peer...")

    ip = input("IP address D[127.0.0.1]: ")
    listening_port = input("Listening port D[50601]: ")
    transmitting_port = input("Transmiting port D[50602]: ")


    if (ip == ''):
        ip = "127.0.0.1"
    if (listening_port == ''):
        listening_port = 50601
    if (transmitting_port == ''):
        transmitting_port = 50602

    peer = Peer(ip, listening_port, transmitting_port)
    peer.launch()


