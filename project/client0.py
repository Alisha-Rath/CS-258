"""
Alisha Rath
Omkar Yadav
"""

import socket
import random
import time
from collections import deque
import threading

class Client:
    def __init__(self, client_name="Maverick", total_packets=10000000, packet_size=4, window_size=1, max_seq_num=65536):
        # Initialize client parameters
        self.client_name = client_name  # client name
        self.total_packets = total_packets  # total number of packets to be sent
        self.packet_size = packet_size  # packet size
        self.window_size = window_size  # window size
        self.max_seq_num = max_seq_num  # maximum sequence number
        self.pkt_success_sent = 0  # counter for successful packets sent
        self.sent_count = 0  # counter for total packets sent (including failed)
        self.seq_num = 1  # initial sequence number
        self.to_send = []  # list of packets to be sent
        self.dropped_pkt = deque()  # deque of dropped packets
        self.track_drop = set()  # set of dropped packets
        self.re_trans = [[], [], [], []]  # 2-D 1x4 list to track retransmission of packets
        self.seq_iter = 0  # sequence iteration
        self.packets_made = 0  # number of packets made
        self.connected = False  # flag to check if the client is connected to the server
        self.conn = None  # socket connection
        self.drp_f = None  # file for logging dropped packets
        self.sender_window_size_f = None  # file for logging window sizes
        self.drp_lock = threading.Lock()  # lock for dropped packets file
        self.win_lock = threading.Lock()  # lock for window sizes file

    def connect(self, host="0.0.0.0", port=4001):
        """
        Establishes a connection with the server.
        """
        if self.connected:
            return 1

        try:
            # Create a socket object and connect to the server
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.connect((host, port))
            self.connected = True

            # Handshake with the server
            if self.pkt_success_sent < 10 or self.pkt_success_sent > self.total_packets * 0.99:
                self.reset()
                self.conn.send(f"SYN {self.client_name[:10]}".encode())
            else:
                self.conn.send(f"RCN {self.client_name[:10]}".encode())

            # Receive response from the server
            res = self.conn.recv(2048).decode()

            if res == "NEW":
                print("Connection Established")
            elif res.startswith("OLD"):
                print("Reconnecting...")
                self.conn.send("SND".encode())
                res = self.conn.recv(4096).decode()
                if res:
                    data = eval(res)
                    self.pkt_success_sent = data['pkt_rec_cnt']
                    self.sent_count = data['pkt_rec_cnt']
                    self.seq_num = data['seq_num']
                else:
                    print("Reconnect Failed!")
            elif res.startswith("SND"):
                data = '{' + f'"pkt_success_sent" : int({self.pkt_success_sent}), "seq_num" : int({self.seq_num})' + '}'
                self.conn.sendall(data.encode())
            else:
                print("Error: Can not reach the server!")
                exit()

            # Start processing packets
            self.process_packets()

        except Exception as e:
            print("Error: ", str(e))
            return -1

    def process_packets(self):
        """
        Processes packets and handles transmission.
        """
        while self.pkt_success_sent < self.total_packets:
            self.to_send = []
            exp_acks = 0

            # Prepare packets to be sent
            for _ in range(self.window_size):
                if self.packets_made < self.total_packets:
                    if self.seq_num % 1000 == 1 and len(self.dropped_pkt) > 0:
                        while len(self.to_send) <= self.window_size and len(self.dropped_pkt) > 0:
                            self.to_send.append(self.dropped_pkt.popleft())
                        break

                    if self.seq_num + self.packet_size > self.max_seq_num:
                        self.seq_num = 1
                        self.seq_iter += 1
                    else:
                        self.seq_num += self.packet_size

                    self.packets_made += 1
                    self.to_send.append(self.seq_num)
                else:
                    while len(self.to_send) <= self.window_size and len(self.dropped_pkt) > 0:
                        self.to_send.append(self.dropped_pkt.popleft())
                    break

            # Send packets and handle acknowledgments
            for pkt in self.to_send:
                self.sent_count += 1

                if self.drop():
                    self.handle_dropped_packet(pkt)
                else:
                    exp_acks += 1
                    self.conn.sendall((str(pkt) + " ").encode())
                    self.pkt_success_sent += 1

            # Receive and process acknowledgments
            self.receive_and_process_acks(exp_acks)

            # Print status
            if self.sent_count % 10 == 0:
                print(f"{self.sent_count} packets sent...")

        # Finalize and close connections
        self.execution_complete()
        self.close_all()

    def drop(self):
        """
        Simulates packet dropping.
        """
        return random.random() < 0.01

    def handle_dropped_packet(self, pkt):
        """
        Handles dropped packets.
        """
        self.dropped_pkt.append(pkt)
        t = threading.Thread(target=self.retrans_handler, args=(pkt, time.time(), self.seq_iter,))
        t.start()
        if self.window_size > 1:
            self.window_size = int(self.window_size / 2)
            t = threading.Thread(target=self.report_window, args=(self.window_size, time.time(),))
            t.start()

    def receive_and_process_acks(self, exp_acks):
        """
        Receives and processes acknowledgments.
        """
        self.conn.settimeout(0.5)
        try:
            while exp_acks > 0:
                ack_str = self.conn.recv(8192).decode()
                if not ack_str:
                    break
                
                acks = list(map(int, ack_str.split()))
                for ack in acks:
                    if ack and self.window_size < 2048:
                        self.window_size += 1
                    exp_acks -= 1

        except socket.timeout:
            # Handle timeout exception (if needed)
            print("Socket receive timeout")
        except Exception as e:
            # Handle other exceptions
            print(f"Error receiving acknowledgments: {e}")

        # Always release the socket timeout
        self.conn.settimeout(None)

        # After receiving acknowledgments, report window size
        t = threading.Thread(target=self.report_window, args=(self.window_size, time.time(),))
        t.start()

    def report_window(self, window_size):
        """
        Reports the current window size.
        """
        print(f"Window size: {window_size}")
        
    def try_connect(self):
        """
        Tries to reconnect to the server.
        """
        self.connected = False
        try:
            while not self.connected:
                self.connect()
                time.sleep(1)
                continue
        except:
            self.execution_complete()
            self.try_connect()

    def reset(self):
        """
        Resets client parameters.
        """
        self.pkt_success_sent = 0
        self.sent_count = 0
        self.seq_num = 70000
        self.window_size = 1
        self.to_send = []
        self.dropped_pkt = deque()
        self.track_drop = set()
        self.re_trans = [[], [], [], []]
        self.seq_iter = 0
        self.packets_made = 0

    def execution_complete(self):
        """
        Handles execution completion.
        """
        if self.pkt_success_sent >= self.total_packets:
            print("Execution Completed")

        print(f"Packets sent: {self.sent_count}")
        print(f"Number of Retransmissions:  1: {len(self.re_trans[0])}  2: {len(self.re_trans[1])}  3: {len(self.re_trans[2])}  4: {len(self.re_trans[3])}")

    def close_all(self):
        """
        Closes connections and files.
        """
        time.sleep(1)
        self.drp_f.close()
        self.sender_window_size_f.close()
        self.conn.close()

if __name__ == '__main__':
    client = Client()
    start_time = time.time()
    client.try_connect()
    end_time = time.time()
    print("Runtime: ", end_time - start_time)
