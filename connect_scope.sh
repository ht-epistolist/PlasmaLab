#!/bin/bash

# --- 1. Sudo Privilege Check ---
# Modifying sysfs USB parameters and configuring network profiles requires root privileges.
# EUID is a shell-builtin variable representing the Effective User ID (0 for root).
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo)"
  exit 1
fi

echo "=== Configuring USB Ethernet Adapter ==="

# --- 2. Dynamic USB Adapter Identification ---
# Find the sysfs path of the AX88179 adapter (Vendor ID: 0b95, Product ID: 1790).
# - find searches /sys/bus/usb/devices/ up to 2 directories deep for links containing colons (e.g., 2-1:1.0 representing active USB interfaces).
# - We check the corresponding parent device directories for 'idVendor' and 'idProduct' files.
dev_path=$(find /sys/bus/usb/devices/ -maxdepth 2 -name "*:*" | while read -r p; do
  if [ -f "$p/../idVendor" ] && [ -f "$p/../idProduct" ]; then
    vid=$(cat "$p/../idVendor")
    pid=$(cat "$p/../idProduct")
    # If the Vendor and Product ID match the ASIX AX88179 chipset:
    if [ "$vid" = "0b95" ] && [ "$pid" = "1790" ]; then
      # Extract the parent device directory path by removing the interface suffix (colons and trailing text).
      # e.g., "/sys/bus/usb/devices/2-1:1.0" becomes "/sys/bus/usb/devices/2-1"
      echo "${p%%:*}"
      break
    fi
  fi
done)

# --- 3. Safety Verification ---
# Ensure that the device was successfully found and the path exists in the system.
if [ -z "$dev_path" ] || [ ! -d "$dev_path" ]; then
  echo "ERROR: AX88179 USB Ethernet adapter not found in lsusb / sysfs!"
  exit 1
fi

# Get the base folder name of the USB device (e.g., "2-1").
dev_base=$(basename "$dev_path")
echo "Found AX88179 adapter at sysfs path: /sys/bus/usb/devices/$dev_base"

# --- 4. Driver Unbinding (Device Lock Release) ---
# When plugged in, the device defaults to configuration 2 (generic CDC-NCM), locking the configurations.
# We must iterate over all sub-interfaces (like :1.0, :2.0) and unbind whatever driver is currently in use.
for intf in "$dev_path/$dev_base":*; do
  if [ -d "$intf" ]; then
    intf_name=$(basename "$intf")
    # If a driver is currently bound to this interface:
    if [ -d "$intf/driver" ]; then
      # Resolve the absolute path of the bound driver (e.g., cdc_ncm).
      driver_path=$(readlink -f "$intf/driver")
      echo "Unbinding $(basename "$driver_path") from $intf_name..."
      # Write the interface identifier to the driver's unbind node to release control.
      echo "$intf_name" > "$driver_path/unbind" 2>/dev/null
    fi
  fi
done

# --- 5. USB Configuration Switch ---
# Switch the USB device configuration to Vendor Mode (value 1) logically.
# We do this without power-cycling the physical USB port lines to prevent physical Ethernet link drop.
sleep 1 # Allow the unbind operations to settle in the kernel.
echo "Switching USB configuration value to 1..."
# Write 1 to bConfigurationValue to activate vendor configuration (loads the ax88179_178a driver).
echo 1 > "$dev_path/bConfigurationValue"
sleep 2 # Wait for the new interface initialization and kernel renaming.

# --- 6. Interface Detection ---
# Locate the network interface subdirectory created under the vendor configuration interface (:1.0).
iface=$(ls -1 "/sys/bus/usb/devices/$dev_base/$dev_base:1.0/net/" 2>/dev/null | head -n 1)

# Verify the interface name was successfully registered (e.g., "enp0s13f0u1").
if [ -z "$iface" ]; then
  echo "ERROR: Network interface was not created! Checking kernel logs..."
  dmesg | tail -n 10
  exit 1
fi

echo "Created interface name: $iface"

# --- 7. Network Profile Configuration ---
# Bind NetworkManager's profile "Wired connection 1" (preconfigured with static IP 10.10.10.1/24) to this interface.
echo "Configuring static IP (Wired connection 1) on $iface..."
nmcli connection modify "Wired connection 1" connection.interface-name "$iface"
nmcli connection up "Wired connection 1"

# --- 8. Permanent ARP Table Injection ---
# The DPO 2014B's legacy networking card does not respond reliably to dynamic ARP requests.
# We inject a permanent mapping from the scope's IP (10.10.10.2) to its MAC address (08:00:11:23:13:00) into the routing neighbor table.
echo "Injecting permanent ARP mapping for 10.10.10.2 (08:00:11:23:13:00)..."
ip neigh replace 10.10.10.2 lladdr 08:00:11:23:13:00 dev "$iface"

# --- 9. Interactive Scope Stack Activation Confirmation ---
# Tell the user to physically bind the network settings on the oscilloscope screen.
# This MUST happen after host configuration because the host configuration switch resets the endpoints and drops physical link briefly.
echo "--------------------------------------------------------"
echo "ATTENTION: The host network interface has been successfully configured."
echo "Please go to the oscilloscope screen, navigate to Ethernet settings,"
echo "and press the bezel button next to 'OK Accept Settings' now."
echo "--------------------------------------------------------"
# Wait for the user to press Enter.
read -p "Once pressed, press [ENTER] here to verify the connection... " -r

# --- 10. Ping Verification ---
# Send 3 ICMP echo requests to the scope's static IP to verify successful network communication.
echo "Verifying ping to oscilloscope..."
if ping -c 3 10.10.10.2; then
  echo "SUCCESS: Connected to oscilloscope successfully!"
else
  echo "ERROR: Ping failed. Please try pressing 'OK Accept Settings' on the scope screen again."
fi
