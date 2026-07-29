#!/bin/bash
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo)"
  exit 1
fi

echo "=== Configuring USB Ethernet Adapter ==="
# Find the sysfs path of AX88179 device (VID 0b95, PID 1790)
dev_path=$(find /sys/bus/usb/devices/ -maxdepth 2 -name "*:*" | while read -r p; do
  if [ -f "$p/../idVendor" ] && [ -f "$p/../idProduct" ]; then
    vid=$(cat "$p/../idVendor")
    pid=$(cat "$p/../idProduct")
    if [ "$vid" = "0b95" ] && [ "$pid" = "1790" ]; then
      echo "${p%%:*}"
      break
    fi
  fi
done)

if [ -z "$dev_path" ] || [ ! -d "$dev_path" ]; then
  echo "ERROR: AX88179 USB Ethernet adapter not found in lsusb / sysfs!"
  exit 1
fi

dev_base=$(basename "$dev_path")
echo "Found AX88179 adapter at sysfs path: /sys/bus/usb/devices/$dev_base"

# Unbind any active interface drivers (like cdc_ncm) to unlock the USB configuration
for intf in "$dev_path/$dev_base":*; do
  if [ -d "$intf" ]; then
    intf_name=$(basename "$intf")
    if [ -d "$intf/driver" ]; then
      driver_path=$(readlink -f "$intf/driver")
      echo "Unbinding $(basename "$driver_path") from $intf_name..."
      echo "$intf_name" > "$driver_path/unbind" 2>/dev/null
    fi
  fi
done

# Switch USB configuration to vendor mode (1) logically (without power-cycling the physical link)
sleep 1
echo "Switching USB configuration value to 1..."
echo 1 > "$dev_path/bConfigurationValue"
sleep 2

# Find the network interface name created for this USB device
iface=$(ls -1 "/sys/bus/usb/devices/$dev_base/$dev_base:1.0/net/" 2>/dev/null | head -n 1)

if [ -z "$iface" ]; then
  echo "ERROR: Network interface was not created! Checking kernel logs..."
  dmesg | tail -n 10
  exit 1
fi

echo "Created interface name: $iface"

# Configure NetworkManager to bind "Wired connection 1" (static IP profile) to this interface
echo "Configuring static IP (Wired connection 1) on $iface..."
nmcli connection modify "Wired connection 1" connection.interface-name "$iface"
nmcli connection up "Wired connection 1"

# Inject permanent ARP table mapping
echo "Injecting permanent ARP mapping for 10.10.10.2 (08:00:11:23:13:00)..."
ip neigh replace 10.10.10.2 lladdr 08:00:11:23:13:00 dev "$iface"

# Wait for physical confirmation on the scope
echo "--------------------------------------------------------"
echo "ATTENTION: The host network interface has been successfully configured."
echo "Please go to the oscilloscope screen, navigate to Ethernet settings,"
echo "and press the bezel button next to 'OK Accept Settings' now."
echo "--------------------------------------------------------"
read -p "Once pressed, press [ENTER] here to verify the connection... " -r

# Check ping
echo "Verifying ping to oscilloscope..."
if ping -c 3 10.10.10.2; then
  echo "SUCCESS: Connected to oscilloscope successfully!"
else
  echo "ERROR: Ping failed. Please try pressing 'OK Accept Settings' on the scope screen again."
fi
