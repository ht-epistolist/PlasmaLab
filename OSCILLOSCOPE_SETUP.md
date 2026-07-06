# Tektronix DPO 2014B Connection & Setup Guide (PlasmaLab)

This guide describes how to connect and configure your laptop to communicate with the Tektronix DPO 2014B oscilloscope over a direct Ethernet cable, utilizing the `plasma` conda environment and the `tm_devices` package.

---

## ⚡ Quick Reconnection (Scope Already Configured)

If the oscilloscope is already configured with static IP `10.10.10.2`, use these quick steps:

1. **Plug in the Ethernet cable** between the laptop and the oscilloscope.
2. **Activate the conda environment**:
   ```bash
   conda activate plasma
   ```
3. **Bring up the laptop interface**:
   ```bash
   nmcli connection up "Wired connection 1"
   ```
4. **Run the acquisition script**:
   ```bash
   python /home/heliot/Projects/PlasmaLab/acquire_waveforms.py
   ```

---

## 1. Physical Connection
1. Ensure the **DPO2CONN** connectivity module is securely attached to the rear of the oscilloscope.
2. Connect a standard RJ-45 Ethernet cable directly from the oscilloscope's Ethernet port to your laptop's Ethernet port (or USB-to-Ethernet dongle).
3. Verify that the **Link LED (green)** on the oscilloscope's Ethernet port lights up. This confirms physical connection.

---

## 2. Configure the Oscilloscope
On the oscilloscope front panel:
1. Press the **Utility** button.
2. Press the **Utility Page** softkey, turn multipurpose knob **a**, and select **I/O**.
3. Press the **Ethernet Network Settings** softkey.
4. Set **DHCP/BOOTP** to **Off**.
5. Set the following IP configuration:
   * **Instrument IP Address:** `10.10.10.2`
   * **Subnet Mask:** `255.255.255.0`
   * **Gateway IP Address:** `10.10.10.1`
   * **DNS IP Address:** `10.10.10.1`
6. Press the **OK Apply Settings** softkey to save.
7. **Important:** If settings do not take effect immediately, power cycle (reboot) the oscilloscope.

---

## 3. Configure the Laptop Network
Your laptop must be in the same subnet (`10.10.10.x`) as the oscilloscope.

1. **Find your interface name:**
   ```bash
   ip link
   ```
   *(Your Ethernet interface is typically named `enp0s13f0u4c2` or similar).*

2. **Configure a static IP using NetworkManager:**
   Modify the Ethernet connection profile (usually named `"Wired connection 1"`) to use static IP `10.10.10.1` with a 24-bit subnet mask:
   ```bash
   nmcli connection modify "Wired connection 1" ipv4.addresses 10.10.10.1/24 ipv4.method manual
   nmcli connection up "Wired connection 1"
   ```

3. **Check configuration:**
   ```bash
   ip addr show dev <interface_name>
   ```
   *(Verify it displays `inet 10.10.10.1/24`).*

---

## 4. Configure the Firewall
If your Linux system has `ufw` enabled, it may block traffic from the oscilloscope. Allow traffic on the Ethernet interface:
```bash
sudo ufw allow in on <interface_name>
```

---

## 5. Verify the Connection
Test the IP connection using ping:
```bash
ping -c 3 10.10.10.2
```
If the ping is successful, check that the ARP table resolved the oscilloscope's MAC address:
```bash
ip neigh show dev <interface_name>
```
*(You should see `10.10.10.2 lladdr 08:00:11:... REACHABLE`, where `08:00:11` is the Tektronix OUI).*

---

## 6. Run the Acquisition Code

Ensure the `plasma` conda environment is active and dependencies are installed:
```bash
conda activate plasma
pip install tm_devices numpy matplotlib
```

### Python Script
Run the script to automatically acquire, plot, and save the active channel data:
```bash
python /home/heliot/Projects/PlasmaLab/acquire_waveforms.py
```
* **Script File:** [acquire_waveforms.py](file:///home/heliot/Projects/PlasmaLab/acquire_waveforms.py)
* **Output Data:** [waveform_data.csv](file:///home/heliot/Projects/PlasmaLab/waveform_data.csv)
* **Output Plot:** `waveform_plot.png`

### Jupyter Notebook
Alternatively, open and run the interactive notebook:
```bash
jupyter notebook /home/heliot/Projects/PlasmaLab/acquire_waveforms.ipynb
```
* **Notebook File:** [acquire_waveforms.ipynb](file:///home/heliot/Projects/PlasmaLab/acquire_waveforms.ipynb)
