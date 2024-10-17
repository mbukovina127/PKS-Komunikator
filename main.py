from client import Client
from server import Server
from peer import Peer
if __name__ == '__main__':
    listening_port = input("Listening port def[50601]: ")
    if (listening_port == ''):
        listening_port = 50601
    else:
        listening_port = int(listening_port)

    app = Peer(listening_port)
    transmitting_port = input("Transmitting port def[50602]: ")

    if (transmitting_port == ''):
        transmitting_port = 50602
    else:
        transmitting_port = int(transmitting_port)

    app.port_transmit = transmitting_port


    while True:
        print("Do you want to initialize connection to a peer: [y]es I want to / [n]o I want to wait for incoming connection")
        inp = input()

        if (inp == 'y'):
            ip = input("IP address to connect def[127.0.0.1]: ")

            if (ip == ''):
                ip = "127.0.0.1"

            app.dest_ip = ip


            if (app.conn_initializer()):
                break
            else:
                print("Couldn't establish connection")

        elif (inp == 'n'):

            app.port_transmit = transmitting_port

            if (app.conn_listener()):
                break
            else:
                print("Couldn't establish connection")
        else:
            print("Invalid input")

    app.communicate()

