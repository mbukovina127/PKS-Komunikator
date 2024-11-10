# from packet import Flags, Packet
# from packetsending import SlidingWindow
#
# ######### DONT IMPLEMENT ##############
# class Receiver:
#     def __init__(self, socket, conn_info, s_lock, ka_lock, window: SlidingWindow,):
#         self.socket = socket
#         self.ConnInfo = conn_info
#         self.send_lock = s_lock
#         self.ka_lock = ka_lock
#         self.WINDOW = window
#         # timer
#     def ack_received(self, pkt):
#         self.WINDOW.remove(pkt.sequence_number)
#
#     def parse_packet(self, pkt: Packet):
#         print("pkt received")
#         match (pkt.flag):
#             case Flags.KEEP_ALIVE.value:
#                 # print("DBG: KEEP ALIVE rec")
#                 self.pulse = 3
#                 return
#             #ack has seq of dest_seq + 1
#             case Flags.ACK.value:
#                 self.verify_packet(pkt)
#                 self.ack_received(pkt)
#                 if (self.ConnInfo.fin_send == True):
#                     quit()
#                 return
#             #str seq of current
#             case Flags.STR.value:
#                 self.verify_packet(pkt)
#                 self.Halt.set()
#                 self.incoming_file(pkt)
#                 return
#             #Frag seq of current
#             case Flags.FRAG.value:
#                 return
#             #Frag seq of current
#             case Flags.FRAG_F.value:
#                 # DO SOMETHING
#                 self.Halt.clear()
#                 return
#             #Frag seq of current
#             case Flags.MSG.value:
#                 self.recv_message(pkt)
#                 print(pkt.data.decode("utf-8"))
#                 self.send_ack(pkt)
#                 return
#             case Flags.FIN.value:
#                 self.FIN_received()
#                 return
#             case _:
#                 return
#
#     # TODO: test needs a rework
#     def verify_packet(self, pkt: Packet):
#         # for incoming packets
#         if pkt.sequence_number == self.ConnInfo.current_seq:
#             return True
#         # for acks of sent packets
#         return self.SENT.contains(pkt.sequence_number)
#
# ### THREAD FUNCTIONS
#
#     def LISTENER(self, buffer_s):
#         self.listening_socket.settimeout(60)
#         while self.ConnInfo.CONNECTION:
#             try:
#                 rec_pkt = self.recv_packet(buffer_s)
#                 self.parse_packet(rec_pkt)
#             except socket.timeout:
#                 pass
#             except OSError:
#                 return
#         self.quit()