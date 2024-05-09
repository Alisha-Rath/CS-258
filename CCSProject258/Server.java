//Alisha Rath
//Omkar Yadav

import java.io.*;
import java.net.*;
import java.util.*;

public class Server {
    private static final int PORT = 12345; // Server port number
    private static final int MAX_SEQ_NUM = (int) Math.pow(2, 16);

    public static void main(String[] args) {
        // Create a server socket to listen for incoming client connections
        try (ServerSocket serverSocket = new ServerSocket(PORT)) {
            System.out.println("Server is running...");

            // Continuously accept incoming client connections
            while (true) {
                Socket socket = serverSocket.accept();
                // Start a new thread to handle the client connection
                new ClientHandler(socket).start();
            }
        } catch (IOException e) {
            System.out.println("Error starting server: " + e.getMessage());
        }
    }

    // Inner class representing a thread to handle each client connection
    private static class ClientHandler extends Thread {
        private final Socket socket;
        private int receivedPackets = 0;
        private int missingPackets = 0;
        private int previousSeqNumber = -1;
        private double goodput = 0.0;
        private int totalReceived = 0;
        private double avgGoodput = 0.0;
        private double x = 0.0;
        private int time = 0;
        private String filePath = "Received_Seq_No.csv";

        // Constructor that takes the client socket as an argument
        public ClientHandler(Socket socket) {
            this.socket = socket;
        }

        @Override
        public void run() {
            InetAddress localIP = socket.getLocalAddress();

            System.out.println("Server IP: " + localIP.getHostAddress());
            System.out.println("Connected to client: " + socket.getRemoteSocketAddress());

            // Set up input and output streams for communication with the client
            try (
                DataInputStream inputStream = new DataInputStream(socket.getInputStream());
                DataOutputStream outputStream = new DataOutputStream(socket.getOutputStream())
            ) {
                // Create a file writer to write received sequence numbers to a CSV file
                File file = new File(filePath);
                BufferedWriter writer = new BufferedWriter(new FileWriter(file));

                // Send a "CONN ACK" message to the client to acknowledge the connection
                outputStream.writeUTF("CONN ACK");
                outputStream.flush();

                // Continuously receive sequence numbers and send ACK numbers to the client
                while (true) {
                    int seqNumber = inputStream.readInt();
                    
                    // Write received sequence number and time to the CSV file
                    writer.write(seqNumber + ", " + time + "\n");
                    time++;
                    receivedPackets++;

                    // Check if any sequence numbers were skipped, and update the missingPackets count
                    if (seqNumber != previousSeqNumber + 1 && seqNumber >= previousSeqNumber) {
                        missingPackets += seqNumber - previousSeqNumber - 1;
                    }
                    
                    // Update the previous sequence number
                    if (seqNumber >= previousSeqNumber) {
                        previousSeqNumber = seqNumber;
                    }

                    // Send the ACK number back to the client
                    outputStream.writeInt(seqNumber + 1); // ACK
                    outputStream.flush();

                    // Calculate and display goodput every 1000 received packets
                    if (receivedPackets % 1000 == 0) {
                        totalReceived += receivedPackets;
                        System.out.println("Packets received so far: " + receivedPackets);
                        System.out.println("Packets missed so far: " + missingPackets);
                        System.out.println("Total packets sent by client so far: " + (receivedPackets + missingPackets));
                        goodput = (double) totalReceived / (totalReceived + missingPackets);
                        avgGoodput += goodput;
                        x++;
                        System.out.printf("Current Goodput: %.4f%n", goodput);
                    }
                }
            } catch (IOException e) {
                System.out.println("Connection closed: " + e.getMessage());
            }

            // Calculate and display average goodput when connection ends
            System.out.printf("Average Goodput: %.4f%n", avgGoodput / x);
        }
    }
}
