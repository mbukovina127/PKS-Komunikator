import threading

from peer import Peer

if __name__ == '__main__':
    listening_port = input("Listening port def[50601]: ")
    if (listening_port == ''):
        listening_port = 50601
    else:
        listening_port = int(listening_port)

    transmitting_port = input("Transmitting port def[50602]: ")


    if (transmitting_port == ''):
        transmitting_port = 50602
    else:
        transmitting_port = int(transmitting_port)


    ip = input("IP address to connect def[127.0.0.1]: ")

    if (ip == ''):
        ip = "127.0.0.1"

    app = Peer(listening_port, transmitting_port, ip)

    ### start of thread
    init_listen = threading.Thread(target=app.init_listen)
    init_connection = threading.Thread(target=app.init_transmit)
    init_listen.start()
    init_connection.start()


    init_listen.join()
    print("INFO: Connection established. press enter")
    init_connection.join()

    try:
        app.communicate()
    except KeyboardInterrupt:
        app.init_termination()
