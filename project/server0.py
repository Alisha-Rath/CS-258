"""
Alisha Rath
Omkar Yadav
"""

import socket
import threading
import time

class Server:
    def __init__(self):
        self.total_packets = 10000000 # Total number of packets to be received, as per assignment condition
        self.packet_size = 4 # Packet size, a small packet size allows for faster iteration and testing of the networking code. It reduces the time required for transmitting and processing each packet, which can be beneficial when debugging or experimenting with different network configurations
        self.max_seq_num = 65536 # Maximum sequence number,as per assignment condition 2^16
        self.expected_seq_num = 1 # Expected sequence number (next seq number to receive)
        self.missing_packets = [] # List of missing packets
        self.received_packets = [] # List of received packets
        self.good_put_store = [] # List of good put values
        self.sequence_numbers = [] # List of sequence numbers
        self.receive_buffer = '' # Buffer for received packets
        self.buffer_size = 8192 # Buffer size, Choosing this size involves a trade-off between memory usage and performance. A larger buffer size allows the receiver to handle larger bursts of incoming data without overflowing the buffer, reducing the likelihood of packet loss due to buffer overflow. However, it also consumes more memory.
        self.min_buffer_size = 1024 # Minimum buffer size, as its byte transmission for TCP, shouldnt go below 1 byte
        self.max_buffer_size = 32768 # Maximum buffer size. Sequence numbers should be at least twice the buffer size
        self.client_name = '' # Name of the client
        self.start_time = time.time() # Start time
        self.packets_received_count = 0 # Count of packets received
        self.receive_file = None #This file stores the sequence numbers of received packets along with their timestamps. Each line in this file represents one received packet and contains the sequence number of the packet and the timestamp when it was received. This file helps in tracking the sequence of packets received over time
        self.good_put_file = None #This file stores the statistics related to the good put of the server. Each line in this file represents the number of packets received, the total number of packets sent (including both received and missing packets), and the calculated good put value for a particular interval. The good put is calculated as the ratio of received packets to the total number of packets sent
        self.receive_lock = threading.Lock()
        self.window_size_file = None #This file stores the changes in the window size of the server's receive buffer over time. Each line in this file represents a snapshot of the window size at a specific time, along with the corresponding timestamp. This file helps in monitoring the dynamics of the server's receive buffer size during the execution of the program
        self.window_size_lock = threading.Lock()

    def set_connection(self):
        """
        Sets up the initial server connection.
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = "0.0.0.0" # Mac Local #host = socket.gethostname() # Windows Local  and #host = socket.gethostbyname(socket.gethostname()) # 2 PCs
        self.port = 4001

        try:
            self.server_socket.bind((self.host, self.port)) # binding to port
            print("Waiting for connection...")
            self.server_socket.listen(5) # listening for client to connect
            print(f"Listening on {self.host}:{self.port}")
        except socket.error as e:
            print(str(e))

    def connect(self):
        """
        Handles client connections.
        """
        while self.packets_received_count < self.total_packets:
            conn, address = self.server_socket.accept() # accept new connection
            print(f"Connected to: {address}")

            try:
                response = conn.recv(2048).decode() # get first response from new connection
            except:
                continue

            if response[:3] == "SYN": # see if it is a fresh client
                self.handle_new_connection(conn, response)
            elif response[:3] == "RCN":  # Client says that Server left in between
                self.handle_reconnect(conn, response)
            else:
                print("Error: Client failed to connect!")
                exit()

    def handle_new_connection(self, conn, response):
        """
        Handles new client connections.
        """
        if (self.packets_received_count < 10 or self.client_name != response[4:] 
            or self.packets_received_count > self.total_packets * 0.99):
            conn.sendall("NEW".encode()) # Ask client to start sending data
            self.client_name = response[4:] # store client identity
            self.reset()
        else:
            conn.sendall("OLD".encode()) # If client got disconnected in between
            response = conn.recv(2048).decode() # Tell client that you will now send remaining data
            if response[:3] == "SND":
                data = '{' + f'"pkt_rec_cnt": {self.packets_received_count}, "seq_num": {self.expected_seq_num}' + '}'
                conn.sendall(data.encode()) # Send data to sync with the client

        try:
            self.process_packets(conn)
        except Exception as e:
            print(str(e))

    def handle_reconnect(self, conn, response):
        """
        Handles reconnection from clients.
        """
        conn.sendall("SND".encode())# Tell client to send synchronisation data
        self.client_name = response[4:]
        print("Syncing with the sender...")
        response = conn.recv(4096).decode() # Get info to sync
        if response:
            data = eval(response)
            self.packets_received_count = data['pkt_success_sent'] # set the packets already received
            self.expected_seq_num = data['seq_num'] # set the sequence numbers
        else:
            print("Reconnect Failed!")

        try:
            self.process_packets(conn) # Start receiving packets
        except Exception as e:
            print(str(e))

    def process_packets(self, conn):
        """
        Processes received packets.
        """
        while self.packets_received_count < self.total_packets:
            try:
                conn.settimeout(1) # set receive time out to 1 sec
                response = conn.recv(self.buffer_size).decode()
                conn.settimeout(None) # remove connection timeout
            except:
                return self.connect() # try to reconnect if error occured

            if not response:
                 print("No Response")
                 return self.connect() # try to reconnect if no response received

            response_str = response.split() # received string is space separated
            self.sequence_numbers = list(map(int, response_str)) # get integer sequence numbers from response

            if self.receive_buffer: # Check of half received packets stored in receive buffer
                if len(self.sequence_numbers) > 0:
                    self.sequence_numbers[0] = int(self.receive_buffer + response_str[0])
                else:
                    self.sequence_numbers = list(map(int, self.receive_buffer.split()))

                self.receive_buffer = ''

            if response[-1] != " ": # if half received packet found, store it in buffer
                self.sequence_numbers.pop()
                self.receive_buffer += response_str.pop()

            buffer_changed = False # check for changes in receive buffer size
            buffer_changed2 = False

            for seq_num in self.sequence_numbers: # iterate through all received sequence numbers
                old_packet = False # If missing pkt received
                if seq_num != self.expected_seq_num: # check id expected sequence number is not received
                    if seq_num in self.missing_packets: # if missing packet received, remove it from list
                        old_packet = True
                        self.missing_packets.remove(seq_num)
                    else:
                        # change buffer size if lost packet
                        wait_count = 0
                        if not buffer_changed and self.buffer_size * 2 <= self.max_buffer_size:
                            buffer_changed = True
                            self.buffer_size = int(self.buffer_size * 2) # double the buffer size if packets are missing
                            self.report_window_size(self.buffer_size, time.time())

                     # add lost packets to missing packets list and update next expected sequence number
                        while self.expected_seq_num != seq_num:
                            if wait_count > 5:
                                break
                            wait_count += 1
                            self.missing_packets.append(self.expected_seq_num) # add missing packets to list
                            self.expected_seq_num += self.packet_size
                            if self.expected_seq_num > self.max_seq_num:
                                self.expected_seq_num = 1

             # if packets getting send without issue, increase the buffer size
                elif not (buffer_changed or buffer_changed2) and self.buffer_size / 2 >= self.min_buffer_size:
                    buffer_changed2 = True
                    self.buffer_size = int(self.buffer_size / 2)
                    self.report_window_size(self.buffer_size, time.time())

               # for new packets, update next expected sequence number
                if not old_packet:
                    self.expected_seq_num += self.packet_size
                    if self.expected_seq_num > self.max_seq_num:
                        self.expected_seq_num = 1

                self.received_packets.append((seq_num, time.time())) # save the received packets
                self.packets_received_count += 1
                conn.sendall((str(self.expected_seq_num) + " ").encode()) # send the received packets

                if len(self.received_packets) == 1000:
                    self.report_packet_stats(self.received_packets, len(self.missing_packets))
                    self.received_packets = []

            if self.packets_received_count % 100 == 0:
                print(f"Received {self.packets_received_count} packets...")
                if self.packets_received_count % 1000 == 0:
                    print("Time so far:", time.time() - self.start_time)
                     # print(f"Exected Runtime: {(total_packets/packets_received_count*(time.time()-self.start_time)/60)} mins")

    def report_packet_stats(self, received_packets, missing_packets_count):
        """
        Reports packet statistics.
        """
        with self.receive_lock:
            receive_file.write("\n".join([f"{seq},{tm}" for seq, tm in received_packets]) + "\n") # write received sequence number and time stamp to file
            received_count = len(received_packets)  # number of received packets
            sent_count = received_count + missing_packets_count # number of sent packets
            good_put = received_count / sent_count if sent_count != 0 else 0 # good put print(f"Good Put = {received_count}/{sent_count} = {good_put}")
            self.good_put_store.append(good_put) # store good put in an array
            good_put_file.write(f"{received_count},{sent_count},{good_put}\n") # store good put in a file

    def report_window_size(self, window_size, timestamp):
        """
        Reports window size.
        """
        with self.window_size_lock:
            self.window_size_file.write(f"{window_size},{timestamp}\n")

    def reset(self):
        """
        Resets server parameters.
        """
        self.packets_received_count = 0
        self.expected_seq_num = 1
        self.missing_packets = []
        self.received_packets = []
        self.good_put_store = []
        self.sequence_numbers = []
        self.receive_buffer = ''
        self.buffer_size = 8192

    def execution_complete(self):
        """
        Handles execution completion.
        """
        if self.packets_received_count >= self.total_packets:
            print("Execution Completed")

         # print(f"Server IP: {socket.gethostbyname(socket.gethostname())}") # Use only if running on Windows PC
        print(f"Packets received: {self.packets_received_count}") # print packets received

        if self.good_put_store:
            average_good_put = sum(self.good_put_store) / len(self.good_put_store)# calculate and print good put
            print(f"Average Good Put: {average_good_put}")

    def close_all(self):
        """
        Closes all connections and files.
        """
        time.sleep(1)
        self.receive_file.close()
        self.good_put_file.close()
        self.server_socket.close()

if __name__ == '__main__':
    server = Server()
    server.set_connection()
    server.connect()
    server.execution_complete()
    server.close_all()
