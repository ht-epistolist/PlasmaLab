#!/usr/bin/env python3
"""
Simplified Waveform Acquisition Script for Tektronix DPO 2014B
Connects via tm_devices, retrieves active channel waveforms, saves data to CSV, and plots them.
"""

import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt
from tm_devices import DeviceManager
from tm_devices.helpers import PYVISA_PY_BACKEND

def main():
    parser = argparse.ArgumentParser(description="Acquire waveforms from Tektronix DPO 2014B using tm_devices.")
    parser.add_argument("--ip", default="10.10.10.2", help="IP address of the oscilloscope (default: 10.10.10.2)")
    parser.add_argument("--channels", help="Comma-separated list of channels to acquire (e.g. CH1,CH4). If not specified, automatically detects active channels.")
    parser.add_argument("--csv", default="waveform_data.csv", help="Filename to save CSV data (default: waveform_data.csv)")
    parser.add_argument("--plot", default="waveform_plot.png", help="Filename to save plot image (default: waveform_plot.png)")
    args = parser.parse_args()

    # Construct the correct resource expression for pyvisa-py compatibility
    resource_expression = f"TCPIP::{args.ip}::INSTR"
    print(f"Connecting to oscilloscope at {args.ip} using tm_devices...")
    
    try:
        # Use DeviceManager as context manager to handle automatic connection and cleanup
        with DeviceManager() as dm:
            dm.visa_library = PYVISA_PY_BACKEND
            scope = dm.add_unsupported_device(resource_expression)
            
            idn = scope.query("*IDN?")
            print(f"Instrument IDN: {idn.strip()}")

            # Determine which channels to acquire
            if args.channels:
                channels_to_acquire = [ch.strip().upper() for ch in args.channels.split(",")]
            else:
                # Auto-detect active channels
                print("Auto-detecting active channels...")
                channels_to_acquire = []
                for ch in ["CH1", "CH2", "CH3", "CH4"]:
                    try:
                        is_active = scope.query(f"SELect:{ch}?").strip()
                        if is_active == "1":
                            channels_to_acquire.append(ch)
                    except Exception as e:
                        print(f"Warning: Could not query status for {ch}: {e}")
                
                if not channels_to_acquire:
                    print("No active channels detected! Defaulting to CH1.")
                    channels_to_acquire = ["CH1"]

            print(f"Channels to acquire: {', '.join(channels_to_acquire)}")

            # Set up data transfer preferences
            scope.write("DATa:ENCdg RIBinary")  # Signed integer binary format
            scope.write("DATa:WIDth 2")        # 16-bit resolution (2 bytes per point)

            waveforms = {}
            time_axis = None
            xunit = "s"
            yunit = "V"

            for ch in channels_to_acquire:
                print(f"\nAcquiring waveform from {ch}...")
                try:
                    # Set transfer source
                    scope.write(f"DATa:SOUrce {ch}")

                    # Get record length
                    record_length = int(scope.query("HORizontal:RECOrdlength?").strip())
                    scope.write("DATa:STARt 1")
                    scope.write(f"DATa:STOP {record_length}")
                    print(f"  Record length: {record_length} points")

                    # Get horizontal scaling factors
                    xincr = float(scope.query("WFMPre:XINcr?").strip())
                    xzero = float(scope.query("WFMPre:XZEro?").strip())
                    pt_off = float(scope.query("WFMPre:PT_Off?").strip())
                    
                    # Get vertical scaling factors
                    ymult = float(scope.query("WFMPre:YMUlt?").strip())
                    yoff = float(scope.query("WFMPre:YOFf?").strip())
                    yzero = float(scope.query("WFMPre:YZEro?").strip())
                    yunit = scope.query("WFMPre:YUNit?").strip().replace('"', '')
                    xunit = scope.query("WFMPre:XUNit?").strip().replace('"', '')

                    if xunit == "V" or not xunit:
                        xunit = "s"

                    print(f"  Scaling: XInc={xincr} {xunit}, YMult={ymult} {yunit}")

                    # Retrieve and parse raw binary curve data using query_binary_values
                    raw_ints = scope.query_binary_values(
                        "CURVe?",
                        datatype="h",         # 'h' = signed 16-bit short
                        is_big_endian=True,   # RIBinary with 2 bytes is big-endian
                        container=np.ndarray
                    )
                    
                    # Apply scaling
                    scaled_voltages = (raw_ints - yoff) * ymult + yzero
                    waveforms[ch] = scaled_voltages

                    # Reconstruct time axis if not done already
                    if time_axis is None:
                        time_axis = xzero + xincr * (np.arange(len(raw_ints)) - pt_off)

                except Exception as e:
                    print(f"  Error acquiring channel {ch}: {e}", file=sys.stderr)

            if not waveforms:
                print("No waveform data could be retrieved. Exiting.", file=sys.stderr)
                sys.exit(1)

    except Exception as e:
        print(f"Error communicating with oscilloscope: {e}", file=sys.stderr)
        sys.exit(1)

    # Save to CSV
    print(f"\nSaving data to {args.csv}...")
    try:
        csv_header = f"Time ({xunit})," + ",".join([f"{ch} ({yunit})" for ch in waveforms.keys()])
        csv_data = np.column_stack([time_axis] + [waveforms[ch] for ch in waveforms.keys()])
        np.savetxt(args.csv, csv_data, delimiter=",", header=csv_header, comments="")
        print(f"  Successfully saved {len(time_axis)} points.")
    except Exception as e:
        print(f"  Error saving CSV file: {e}", file=sys.stderr)

    # Plot waveforms
    print(f"Plotting and saving figure to {args.plot}...")
    try:
        plt.figure(figsize=(10, 6))
        
        # Determine time scale units for nice plotting labels
        max_time = np.max(np.abs(time_axis))
        time_multiplier = 1.0
        plot_time_unit = xunit
        
        if max_time < 1e-6:
            time_multiplier = 1e9
            plot_time_unit = "ns"
        elif max_time < 1e-3:
            time_multiplier = 1e6
            plot_time_unit = "µs"
        elif max_time < 1.0:
            time_multiplier = 1e3
            plot_time_unit = "ms"

        for ch, scaled_data in waveforms.items():
            plt.plot(time_axis * time_multiplier, scaled_data, label=ch)

        plt.title(f"Waveform from Tektronix DPO 2014B\nIDN: {idn.strip()}")
        plt.xlabel(f"Time ({plot_time_unit})")
        plt.ylabel(f"Amplitude ({yunit})")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(args.plot, dpi=150)
        plt.close()
        print("  Successfully generated plot.")
    except Exception as e:
        print(f"  Error generating plot: {e}", file=sys.stderr)

    print("Done!")

if __name__ == "__main__":
    main()
