# Laptop Network Effects & Troubleshooting Guide

This guide documents the changes made to the host laptop's network subsystem during the oscilloscope configuration and explains the potential side-effects on other network devices along with manual recovery procedures.

---

## ⚠️ Summary of System Changes

### 1. NetworkManager Profile Modification (`Wired connection 1`)
* **Change Details:** Modified the profile named `"Wired connection 1"` to use a static IPv4 configuration (`10.10.10.1/24`, gateway/DNS `10.10.10.1`) and dynamically bound its target interface name to the vendor-mode interface (e.g., `enp0s13f0u1`).
* **Side-Effect on Other Devices:** If you connect a different USB-to-Ethernet adapter or connect the laptop to a standard local network (LAN) that relies on DHCP, NetworkManager may automatically assign the `"Wired connection 1"` profile. The laptop will enforce the static IP `10.10.10.1`, which will **cause a loss of internet or local network connectivity on that port**.
* **Reversion / Fix:**
  To restore the profile to automatic DHCP, run:
  ```bash
  nmcli connection modify "Wired connection 1" ipv4.method auto
  ```
  Or manually create/select a different profile (like `"Wired connection 2"`) in your NetworkManager system tray menu.

---

### 2. Static ARP Neighbor Entry
* **Change Details:** Injected a permanent (static) ARP mapping on the adapter's interface that binds IP `10.10.10.2` to the oscilloscope's MAC address (`08:00:11:23:13:00`).
* **Side-Effect on Other Devices:** If you connect to another network using the `10.10.10.x` subnet, and there is a device at IP `10.10.10.2` with a different MAC address, **your laptop will be unable to communicate with it**. The laptop will force all packets meant for `10.10.10.2` to go to the oscilloscope's MAC.
* **Reversion / Fix:**
  This entry is automatically flushed when the USB adapter is unplugged. However, to manually delete it while connected, run:
  ```bash
  sudo ip neigh delete 10.10.10.2 dev <interface_name>
  ```

---

### 3. Firewall Openings (UFW Rules)
* **Change Details:** Configured the Uncomplicated Firewall (UFW) to allow all incoming traffic on the specific interface names associated with this adapter (e.g., `enp0s13f0u1`, `enp0s13f0u1c2`).
* **Side-Effect on Other Devices:** While your Wi-Fi interface (`wlan0`) remains fully protected, this specific USB-to-Ethernet adapter's interface is completely open. If you connect this adapter to an untrusted public network, **your laptop will be exposed to incoming network probes on that port**.
* **Reversion / Fix:**
  To close the opening and restore normal firewall protection on the adapter port:
  ```bash
  sudo ufw delete allow in on <interface_name>
  ```

---

## 🛠️ Reverting All Changes to Factory Defaults

If you need to completely remove the setup and restore your laptop's original networking state:

1. **Delete the Connection Profile mapping:**
   ```bash
   nmcli connection modify "Wired connection 1" connection.interface-name "" ipv4.method auto
   ```
2. **Remove UFW Firewall rules:**
   Check the rules list:
   ```bash
   sudo ufw status numbered
   ```
   Delete the lines corresponding to the interface names (`enp0s13f0u1` or `enp0s13f0u1c2`):
   ```bash
   sudo ufw delete <rule_number>
   ```
