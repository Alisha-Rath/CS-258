//Alisha Rath
//Omkar Yadav

import java.io.*;
import java.net.*;
import java.util.*;

public class Client {
    // Server configuration constants
    private static final String SERVER_IP = "0.0.0.0"; // Server IP address
    private static final int SERVER_PORT = 12345; // Server port number

    // Simulation parameters
    private static final int MAX_SEQ_NUM = (int) Math.pow(2, 16); // Maximum sequence number
    private static final int TOTAL_PACKETS = 10000; // Total number of packets to send
    private static final double DROP_RATE = 0.01; // Probability of packet drop
    private static double windowSize = 1.0; // Initial window size
    private static double time = 0.0; // Simulation time
    private static int ctr = 1; // Counter for retransmission logs

    // File paths for logging
    private static String retransmissionsFilePath = "packet_retransmissions_log.csv";
    private static String congestionWindowFilePath = "congestion_window_sizes.csv";
    private static String droppedPacketsFilePath = "dropped_packets_log.csv";

    public static void main(String[] args) {
        // Continuously attempt to connect to the server
        while (true) {
            try (Socket socket = new Socket(SERVER_IP, SERVER_PORT)) {
                System.out.println("Connection Established: " + socket.getRemoteSocketAddress());

                // Set up input and output streams for communication with the server
                DataInputStream inputStream = new DataInputStream(socket.getInputStream());
                DataOutputStream outputStream = new DataOutputStream(socket.getOutputStream());

                // Receive the "success" message from the server
                String serverMessage = inputStream.readUTF();
                System.out.println("Server message: " + serverMessage);

                int sentPackets = 0;
                int seqNumber = 0;
                List<Integer> droppedPackets = new ArrayList<>();

                // Loggers for congestion window, dropped packets, and retransmissions
                BufferedWriter congestionWindowFileWriter = new BufferedWriter(new FileWriter(new File(congestionWindowFilePath)));
                BufferedWriter droppedPacketsFileWriter = new BufferedWriter(new FileWriter(new File(droppedPacketsFilePath)));
                BufferedWriter retransmissionsFileWriter = new BufferedWriter(new FileWriter(new File(retransmissionsFilePath)));

                // Write initial congestion window size and time to the file
                congestionWindowFileWriter.write(windowSize + ", " + time + "\n");
                time++;

                // Write header for retransmissions log file
                retransmissionsFileWriter.write("retransmission_sequence_number" + ", " + "number_of_packets_dropped" + "\n");

                // Continuously send packets until the total number is reached
                while (sentPackets < TOTAL_PACKETS) {
                    int windowSizeInt = (int) Math.ceil(windowSize);

                    // Send packets in the current window
                    for (int i = 0; i < windowSizeInt && sentPackets < TOTAL_PACKETS; i++) {
                        // Simulate packet dropping with a probability of DROP_RATE
                        if (Math.random() < DROP_RATE) {
                            droppedPackets.add(seqNumber);
                            droppedPacketsFileWriter.write(seqNumber + ", " + time + "\n");
                        } else {
                            // Send the sequence number to the server
                            outputStream.writeInt(seqNumber);
                            outputStream.flush();

                            // Receive the ACK number from the server
                            int ackNumber = inputStream.readInt();
                            System.out.println("Received ACK: " + ackNumber);

                            // Update the congestion window size and log the change
                            updateWindowSize();
                            congestionWindowFileWriter.write(windowSize + ", " + time + "\n");

                            sentPackets++;
                        }
                        time++;

                        // Increment the sequence number, wrapping around to 0 when it reaches MAX_SEQ_NUM
                        seqNumber = (seqNumber + 1) % MAX_SEQ_NUM;
                    }

                    // Retransmit dropped packets
                    int retransmission = 0;
                    for (int i = 0; i < droppedPackets.size(); i++) {
                        int droppedSeqNumber = droppedPackets.get(i);

                        // Simulate packet dropping during retransmission with a probability of DROP_RATE
                        if (Math.random() >= DROP_RATE) {
                            // Send the retransmitted sequence number to the server
                            outputStream.writeInt(droppedSeqNumber);
                            outputStream.flush();
                            retransmission++;

                            // Receive the ACK number for the retransmitted packet from the server
                            int ackNumber = inputStream.readInt();
                            System.out.println("Received ACK (retransmit): " + ackNumber);

                            // Update the congestion window size and count the sent packet
                            updateWindowSize();
                            sentPackets++;

                            // Remove the successfully retransmitted packet from the droppedPackets list
                            droppedPackets.remove(i);
                            i--; // Adjust the index after removal
                        }
                    }

                    // Write retransmission log for the current window
                    retransmissionsFileWriter.write(ctr + ", " + retransmission + "\n");
                    ctr++;
                }

                // Close all loggers after finishing transmission
                congestionWindowFileWriter.flush();
                congestionWindowFileWriter.close();
                droppedPacketsFileWriter.flush();
                droppedPacketsFileWriter.close();
                retransmissionsFileWriter.flush();
                retransmissionsFileWriter.close();

                // If all packets are sent and no packets are dropped, exit the loop
                if (sentPackets >= TOTAL_PACKETS && droppedPackets.isEmpty()) {
                    System.out.println("Finished sending " + TOTAL_PACKETS + " packets.");
                    break; // Exit the loop
                }

            } catch (IOException e) {
                System.out.println("Connection Failed: " + e.getMessage());
            }
        }
    }

    // Method to update the congestion window size based on congestion control algorithm
    private static void updateWindowSize() {
        // Additive increase: increase the window size by a small value
        windowSize += 0.1;

        // Multiplicative decrease: if the window size exceeds a certain threshold, reduce it by a factor
        if (windowSize > 64) {
            windowSize *= 0.5;
        }
    }
}
