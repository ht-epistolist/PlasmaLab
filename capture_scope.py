import socket
import struct
import sys

def main():
    try:
        # socket.htons(0x0003) captures all ethernet protocols
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
        s.bind(("enp0s13f0u1u1", 0))
        s.settimeout(10.0)
    except Exception as e:
        print(f"Error creating socket: {e}")
        sys.exit(1)

    print("Listening for packets on enp0s13f0u1u1 for 10 seconds...")
    try:
        while True:
            packet, addr = s.recvfrom(2048)
            eth_header = packet[:14]
            eth = struct.unpack('!6s6sH', eth_header)
            dest_mac = ':'.join('%02x' % b for b in eth[0])
            src_mac = ':'.join('%02x' % b for b in eth[1])
            eth_type = eth[2]
            
            # Print basic info
            print(f"Packet: Src={src_mac} -> Dst={dest_mac}, EthType={hex(eth_type)} (len={len(packet)})")
            
            if eth_type == 0x0806: # ARP
                arp_header = packet[14:42]
                arp = struct.unpack('!HHBBH6s4s6s4s', arp_header)
                sha = ':'.join('%02x' % b for b in arp[5])
                spa = socket.inet_ntoa(arp[6])
                tpa = socket.inet_ntoa(arp[8])
                print(f"  ARP: Op={arp[4]}, Sender IP={spa}, Target IP={tpa}")
            elif eth_type == 0x0800: # IPv4
                # Check for DHCP (UDP port 67/68)
                ip_header = packet[14:34]
                iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
                src_ip = socket.inet_ntoa(iph[8])
                dst_ip = socket.inet_ntoa(iph[9])
                protocol = iph[6]
                if protocol == 17: # UDP
                    udp_header = packet[34:42]
                    udph = struct.unpack('!HHHH', udp_header)
                    src_port = udph[0]
                    dst_port = udph[1]
                    print(f"  IP: {src_ip}:{src_port} -> {dst_ip}:{dst_port} (UDP)")
                    if src_port in (67, 68) or dst_port in (67, 68):
                        print("  Detected DHCP packet!")
                else:
                    print(f"  IP: {src_ip} -> {dst_ip} (Proto={protocol})")
    except socket.timeout:
        print("Finished listening.")

if __name__ == "__main__":
    main()
