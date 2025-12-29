# P2P UDP Communicator

A peer-to-peer command-line application implementing a custom reliable communication protocol over UDP. Built as a university project for network communication coursework.

## Features

- **Custom Protocol over UDP**: Implements reliability mechanisms on top of UDP
- **Three-Way Handshake**: TCP-like connection establishment
- **ARQ Selective Repeat**: Efficient retransmission strategy for lost packets
- **File Transfer**: Send files of any size with automatic fragmentation
- **Text Messaging**: Real-time text communication between peers
- **Keep-Alive Mechanism**: Automatic connection monitoring with heartbeat packets
- **CRC-16 Integrity Checking**: Data corruption detection using cyclic redundancy check
- **Configurable Fragment Size**: Adjustable packet sizes (1-1465 bytes)
- **Wireshark Integration**: Custom Lua dissector for protocol analysis

## Technical Details

### Protocol Structure

The protocol uses a custom header structure:

```
| Flag (1 byte) | Sequence Number (4 bytes) | Data (variable) | CRC-16 (2 bytes) |
```

**Flags:**
- `SYN (1)` - Synchronization (connection establishment)
- `ACK (2)` - Acknowledgment
- `KEEP_ALIVE (3)` - Heartbeat packet
- `FIN (4)` - Connection termination
- `STR (5)` - Start of data transfer (contains fragment size)
- `FRAG (6)` - Data fragment
- `FRAG_F (7)` - Final fragment
- `MSG (11)` - Text message
- `MSG_F (12)` - Final message fragment
- `KAACK (13)` - Keep-alive acknowledgment

### Key Features

- **Sliding Window Protocol**: Implements flow control with configurable window size
- **Automatic Retransmission**: Packets are retransmitted until acknowledged or timeout
- **Out-of-Order Handling**: Buffers out-of-sequence packets for proper reassembly
- **Error Detection**: CRC-16 checksum validation on all packets
- **Connection Monitoring**: Terminates connection after 3 missed heartbeats

## Requirements

- Python 3.7+
- `crcmod` library for CRC calculations

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/p2p-udp-communicator.git
cd p2p-udp-communicator
```

2. Install dependencies:
```bash
pip install crcmod
```

## Usage

### Starting the Application

Run the main program:
```bash
python main.py
```

You will be prompted to enter:
- **Listening port** (default: 50601)
- **Transmitting port** (default: 50602)
- **IP address** to connect to (default: 127.0.0.1)

### Establishing Connection

After starting, you can:
- Wait for incoming connection (passive mode)
- Press `C` and Enter to initiate connection (active mode)

### Main Menu Options

Once connected, you have the following options:

- **[M]essage** - Send a text message
- **[S]end files** - Transfer a file to the peer
- **[C]hange fragment size** - Adjust packet fragmentation (1-1465 bytes)
- **[Q]uit** - Terminate the connection gracefully

### Example Session

```
Listening port def[50601]: 
Transmitting port def[50602]: 
IP address to connect def[127.0.0.1]: 
INFO: Waiting for connection...
[C]onnect?
C
INFO: Establishing connection...
INFO: Connection established

Choose option:
[M]essage | [S]end files | [C]hange fragment size | [Q]uit 
M
INFO: Message sending
Write message [--quit]: Hello, peer!
INFO: Message sent
```

## Wireshark Integration

A custom Lua dissector is provided for analyzing the protocol in Wireshark.

### Installation

1. Copy `my_protocol.lua` to your Wireshark plugins folder:
   - Windows: `%APPDATA%\Wireshark\plugins\`
   - Linux: `~/.local/lib/wireshark/plugins/`
   - macOS: `~/.wireshark/plugins/`

2. Restart Wireshark

The dissector will automatically parse packets on ports 50601 and 50602, displaying:
- Flag type and value
- Sequence number
- Data payload
- CRC-16 checksum

## Architecture

### Threading Model

The application uses multiple threads for concurrent operations:
- **Input Handler**: Non-blocking console input
- **Listener**: Receives incoming packets
- **Parser**: Processes received packets and manages state
- **Sender**: Manages sliding window and retransmissions
- **Keep-Alive**: Monitors connection health

### File Transfer Flow

1. Sender transmits `STR` packet with filename
2. File is split into fragments of specified size
3. Fragments sent using ARQ Selective Repeat
4. Receiver buffers out-of-order fragments
5. Final fragment (`FRAG_F`) triggers file assembly
6. Receiver saves file to specified directory

## Error Handling

- **Corrupted Packets**: Detected via CRC-16, discarded without acknowledgment
- **Lost Packets**: Automatic retransmission after timeout (0.4s default)
- **Connection Loss**: Detected via keep-alive mechanism (3 missed heartbeats)
- **Incomplete Transfers**: Automatic cleanup after 15 seconds of inactivity

## Limitations

- Maximum fragment size: 1465 bytes (to fit within typical MTU)
- Sequence number wraps at 4,000,000,000
- Single peer-to-peer connection at a time
- No encryption or authentication

## Project Structure

```
.
├── main.py              # Application entry point
├── peer.py              # Main peer logic and protocol implementation
├── packet.py            # Packet structure and CRC handling
├── packetsending.py     # ARQ Selective Repeat and sliding window
├── my_protocol.lua      # Wireshark dissector
└── README.md            # This file
```

## License

This project was created as coursework for PKS 2024 at STU FIIT.

## Author

Marko Bukovina

**Supervisor:** Ing. Ladislav Zemko

**Academic Year:** 2024