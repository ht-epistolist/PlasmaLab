#!/usr/bin/env python3
"""
Simplified Waveform Acquisition Script for Tektronix DPO 2014B
Connects via tm_devices, retrieves active channel waveforms, saves data to CSV, and plots them.
"""

import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt
import scipy.signal
from tm_devices import DeviceManager
from tm_devices.helpers import PYVISA_PY_BACKEND

def main():
    parser = argparse.ArgumentParser(description="Acquire waveforms from Tektronix DPO 2014B using tm_devices.")
    parser.add_argument("--ip", default="10.10.10.2", help="IP address of the oscilloscope (default: 10.10.10.2)")
    parser.add_argument("--channels", help="Comma-separated list of channels to acquire (e.g. CH1,CH4). If not specified, automatically detects active channels.")
    parser.add_argument("--csv", default="waveform_data.csv", help="Filename to save CSV data (default: waveform_data.csv)")
    parser.add_argument("--plot", default="waveform_plot.png", help="Filename to save plot image (default: waveform_plot.png)")
    parser.add_argument("--filter", action="store_true", help="Apply a Butterworth low-pass filter to the acquired data")
    parser.add_argument("--fc", type=float, help="Cutoff frequency for the low-pass filter in Hz (defaults to 10% of Nyquist frequency)")
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

            raw_waveforms = {}
            scaling_params = {}
            waveforms = {}
            time_axis = None
            xunit = "s"
            yunit = "V"

            # 1. Acquisition Loop (Download raw bytes from scope)
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

                    # Get scaling parameters
                    params = {
                        "xincr": float(scope.query("WFMPre:XINcr?").strip()),
                        "xzero": float(scope.query("WFMPre:XZEro?").strip()),
                        "pt_off": float(scope.query("WFMPre:PT_Off?").strip()),
                        "ymult": float(scope.query("WFMPre:YMUlt?").strip()),
                        "yoff": float(scope.query("WFMPre:YOFf?").strip()),
                        "yzero": float(scope.query("WFMPre:YZEro?").strip()),
                        "yunit": scope.query("WFMPre:YUNit?").strip().replace('"', ''),
                        "xunit": scope.query("WFMPre:XUNit?").strip().replace('"', '')
                    }
                    scaling_params[ch] = params

                    # Retrieve and parse raw binary curve data using query_binary
                    raw_ints = np.array(
                        scope.query_binary(
                            "CURVe?",
                            datatype="h",         # 'h' = signed 16-bit short
                            is_big_endian=True    # RIBinary with 2 bytes is big-endian
                        )
                    )
                    raw_waveforms[ch] = raw_ints
                    print("  Raw waveform data retrieved successfully.")
                except Exception as e:
                    print(f"  Error acquiring channel {ch}: {e}", file=sys.stderr)

            # 2. Scaling Step (Scale raw bytes to physical units)
            if raw_waveforms:
                print("\nScaling waveform data to physical units...")
                for ch, raw_ints in raw_waveforms.items():
                    params = scaling_params[ch]
                    yunit = params["yunit"]
                    xunit = params["xunit"]
                    if xunit == "V" or not xunit:
                        xunit = "s"

                    print(f"  Scaling {ch}: XInc={params['xincr']} {xunit}, YMult={params['ymult']} {yunit}")
                    scaled_voltages = (raw_ints - params["yoff"]) * params["ymult"] + params["yzero"]
                    
                    # Apply 10x multiplier on Channel 4
                    if ch == "CH4":
                        scaled_voltages *= 10.0
                    waveforms[ch] = scaled_voltages

                    # Reconstruct time axis if not done already
                    if time_axis is None:
                        time_axis = params["xzero"] + params["xincr"] * (np.arange(len(raw_ints)) - params["pt_off"])

            if not waveforms:
                print("No waveform data could be retrieved. Exiting.", file=sys.stderr)
                sys.exit(1)

    except Exception as e:
        print(f"Error communicating with oscilloscope: {e}", file=sys.stderr)
        sys.exit(1)

    # Apply Low-Pass Filter if requested
    filtered_waveforms = {}
    if args.filter:
        print("\nApplying low-pass filter...")
        try:
            # Get sampling interval from any of the acquired channels
            first_ch = list(waveforms.keys())[0]
            fs = 1.0 / scaling_params[first_ch]["xincr"]
            nyquist = fs / 2.0
            
            # Default cutoff is 10% of Nyquist if not specified
            fc = args.fc if args.fc is not None else 0.1 * nyquist
            print(f"  Sampling Frequency: {fs:.2f} Hz")
            print(f"  Low-pass Cutoff: {fc:.2f} Hz")
            
            # Design Butterworth filter (4th order)
            b, a = scipy.signal.butter(4, fc, fs=fs, btype='low')
            
            for ch, data in waveforms.items():
                filtered_waveforms[ch] = scipy.signal.filtfilt(b, a, data)
            print("  Low-pass filter applied successfully.")
        except Exception as e:
            print(f"  Error applying low-pass filter: {e}", file=sys.stderr)

    # Save to CSV
    print(f"\nSaving data to {args.csv}...")
    try:
        columns = [time_axis]
        header_parts = [f"Time ({xunit})"]
        
        for ch in waveforms.keys():
            columns.append(waveforms[ch])
            if filtered_waveforms:
                header_parts.append(f"{ch}_Raw ({yunit})")
                columns.append(filtered_waveforms[ch])
                header_parts.append(f"{ch}_Filtered ({yunit})")
            else:
                header_parts.append(f"{ch} ({yunit})")
                
        csv_header = ",".join(header_parts)
        csv_data = np.column_stack(columns)
        np.savetxt(args.csv, csv_data, delimiter=",", header=csv_header, comments="")
        print(f"  Successfully saved {len(time_axis)} points.")
    except Exception as e:
        print(f"  Error saving CSV file: {e}", file=sys.stderr)

    # Plot waveforms
    import os
    base_plot, ext = os.path.splitext(args.plot)
    plot_all_path = f"{base_plot}_all{ext}"
    plot_ch3_ch4_path = f"{base_plot}_ch3_ch4{ext}"
    plot_filtered_path = f"{base_plot}_filtered{ext}"

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

    # Plot 1: All active channels (raw)
    if waveforms:
        print(f"Plotting and saving all channels to {plot_all_path}...")
        try:
            plt.figure(figsize=(10, 6))
            for ch in waveforms.keys():
                plt.plot(time_axis * time_multiplier, waveforms[ch], label=ch)
            plt.title(f"All Active Channels - Tektronix DPO 2014B\nIDN: {idn.strip()}")
            plt.xlabel(f"Time ({plot_time_unit})")
            plt.ylabel(f"Amplitude ({yunit})")
            plt.grid(True)
            plt.legend()
            plt.tight_layout()
            plt.savefig(plot_all_path, dpi=150)
            plt.close()
            print("  Successfully generated all-channels plot.")
        except Exception as e:
            print(f"  Error generating all-channels plot: {e}", file=sys.stderr)

    # Plot 2: CH3 and CH4 (last two channels, raw)
    ch3_ch4_active = [ch for ch in ["CH3", "CH4"] if ch in waveforms]
    if ch3_ch4_active:
        print(f"Plotting and saving CH3/CH4 to {plot_ch3_ch4_path}...")
        try:
            plt.figure(figsize=(10, 6))
            for ch in ch3_ch4_active:
                plt.plot(time_axis * time_multiplier, waveforms[ch], label=ch)
            plt.title(f"Channels 3 & 4 - Tektronix DPO 2014B\nIDN: {idn.strip()}")
            plt.xlabel(f"Time ({plot_time_unit})")
            plt.ylabel(f"Amplitude ({yunit})")
            plt.grid(True)
            plt.legend()
            plt.tight_layout()
            plt.savefig(plot_ch3_ch4_path, dpi=150)
            plt.close()
            print("  Successfully generated CH3/CH4 plot.")
        except Exception as e:
            print(f"  Error generating CH3/CH4 plot: {e}", file=sys.stderr)

    # Plot 3: Filtered vs Raw Comparison (only if filtering was run)
    if filtered_waveforms:
        print(f"Plotting and saving raw vs filtered comparison to {plot_filtered_path}...")
        try:
            plt.figure(figsize=(10, 6))
            for ch in waveforms.keys():
                plt.plot(time_axis * time_multiplier, waveforms[ch], ':', label=f"{ch} (Raw)", alpha=0.5)
                plt.plot(time_axis * time_multiplier, filtered_waveforms[ch], '-', label=f"{ch} (Filtered)")
            plt.title(f"Raw vs Filtered Signals - Tektronix DPO 2014B\nCutoff: {fc:.2e} Hz")
            plt.xlabel(f"Time ({plot_time_unit})")
            plt.ylabel(f"Amplitude ({yunit})")
            plt.grid(True)
            plt.legend()
            plt.tight_layout()
            plt.savefig(plot_filtered_path, dpi=150)
            plt.close()
            print("  Successfully generated raw vs filtered comparison plot.")
        except Exception as e:
            print(f"  Error generating filtered comparison plot: {e}", file=sys.stderr)

    print("Done!")

if __name__ == "__main__":
    main()
