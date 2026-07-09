import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def compare_waveforms(files, channels, CH_ref, yunit, multipliers, first_file_multiplier=1.0, plot_denoised=False, output_folder="plots_compare1", output_filename=None):
    """
    Compares waveform data from multiple CSV files.
    
    Parameters:
        files (list): Array of CSV filenames (located in 'data/' directory).
        channels (list): Array of channels to plot (e.g., ['CH1', 'CH2']).
        yunit (str): Y-axis label unit (e.g., 'V (cA)').
        multipliers (list): Array of Y multipliers corresponding to each channel.
        first_file_multiplier (float): Extra multiplier applied only to channels in the first file.
        output_folder (str): Folder to save the output plot (default: 'plots_compare').
        output_filename (str): Name of the generated plot image. If None, it is generated
                               by concatenating the base names of the input files.
    """
    data_dir = "data1"
    os.makedirs(output_folder, exist_ok=True)
    
    # Generate the output filename by concatenating input file names if not provided
    if output_filename is None:
        base_names = [os.path.splitext(f)[0] for f in files]
        prefix = "d_" if plot_denoised else ""
        output_filename = prefix + "_".join(base_names) + ".png"
        
    plt.figure(figsize=(12, 6))
    
    # Map each channel to its multiplier
    multiplier_map = dict(zip(channels, multipliers))
    
    plotted_any = False
    
    for idx, filename in enumerate(files):
        csv_path = os.path.join(data_dir, filename + ".csv")
        if not os.path.exists(csv_path):
            print(f"Warning: File not found: {csv_path}. Skipping.")
            continue
            
        print(f"Processing {filename}...")
        try:
            df = pd.read_csv(csv_path)
            
            # Find Time column
            time_cols = [col for col in df.columns if "Time" in col]
            if not time_cols:
                print(f"  Error: No Time column in {filename}. Skipping.")
                continue
            time_col = time_cols[0]
            time_axis = df[time_col].to_numpy()  # Time in seconds
            
            # 1. Detect shot trigger using CH1_Raw
            trigger_cols = [col for col in df.columns if f"{CH_ref}_Raw" in col]
            if not trigger_cols:
                print(f"  Error: CH1_Raw column not found in {filename} to detect trigger. Skipping.")
                continue
            trigger_col = trigger_cols[0]
            trigger_data = df[trigger_col].to_numpy()
            
            # Calculate baseline noise on the first 1000 points of CH1_Raw
            baseline_len = min(1000, len(trigger_data))
            baseline = trigger_data[:baseline_len]
            baseline_mean = np.mean(baseline)
            baseline_std = np.std(baseline)
            
            # Find trigger index: first index deviating by > 5 standard deviations
            std_threshold = max(baseline_std, 1e-6)
            deviation = np.abs(trigger_data - baseline_mean)
            trigger_indices = np.where(deviation > 5 * std_threshold)[0]
            
            if len(trigger_indices) > 0:
                trigger_idx = trigger_indices[0]
            else:
                trigger_idx = 0
                print(f"  Warning: No shot trigger detected in {filename}. Defaulting trigger time to start.")
                
            trigger_time = time_axis[trigger_idx]
            print(f"  Detected trigger at index {trigger_idx} (t={trigger_time:.5f} s)")
            
            # Shift time axis so the trigger time corresponds to 10 ms
            # Convert from s to ms: (t - t_trigger) * 1000 + 10
            shifted_time_ms = (time_axis - trigger_time) * 1000.0 + 10.0
            
            # 2. Plot configured channels
            for ch in channels:
                # Find matching raw column for the channel
                raw_cols = [col for col in df.columns if f"{ch}_Raw" in col]
                if not raw_cols:
                    print(f"  Warning: Channel {ch} raw column not found in {filename}. Skipping.")
                    continue
                raw_col = raw_cols[0]
                
                # Apply multiplier
                mult = multiplier_map[ch]
                if idx == 0:
                    mult *= first_file_multiplier
                scaled_data = df[raw_col].to_numpy() * mult
                
                # Label format: "filename: channel"
                label = f"{filename}: {ch}"
                if mult != 1.0:
                    label += f" (x{mult})"
                    
                plt.plot(shifted_time_ms, scaled_data, label=label)
                plotted_any = True
                
                # Plot denoised data if requested
                if plot_denoised:
                    filt_cols = [col for col in df.columns if f"{ch}_Filtered" in col]
                    if filt_cols:
                        filt_col = filt_cols[0]
                        scaled_filt_data = df[filt_col].to_numpy() * mult
                        filt_label = f"{filename}: {ch} (Filtered)"
                        if mult != 1.0:
                            filt_label += f" (x{mult})"
                        plt.plot(shifted_time_ms, scaled_filt_data, '--', label=filt_label)
                
        except Exception as e:
            print(f"  Error reading {filename}: {e}")
            
    if not plotted_any:
        print("Error: No data was plotted. Comparison plot not saved.")
        return
        
    plt.title("Comparison of Shot Waveforms (Time-Aligned to 10 ms)")
    plt.xlabel("Time (ms)")
    plt.ylabel(yunit)
    plt.xlim(0, 500)  # Boundaries set from 0 to 500 ms
    plt.grid(True)
    plt.legend(loc="upper left")
    plt.tight_layout()
    
    plot_save_path = os.path.join(output_folder, output_filename)
    plt.savefig(plot_save_path, dpi=150)
    plt.close()
    
    print(f"\nSuccess! Comparison plot saved to {plot_save_path}")

# Default execution when run as a script
if __name__ == "__main__":
    test_files = ["hill", "line", "ramp", "sawtooth"]
    test_channels = ["CH4"]
    test_reference = "CH4"
    test_multipliers = [1.0]
    test_yunit = "A"
    
    for t in test_files:
        # Standard plot
        compare_waveforms(
            files=[t, f"{t}1"],
            channels=test_channels,
            CH_ref=test_reference,
            yunit=test_yunit,
            multipliers=test_multipliers,
            first_file_multiplier=20,
            plot_denoised=False
        )
        # Denoised plot
        compare_waveforms(
            files=[t, f"{t}1"],
            channels=test_channels,
            CH_ref=test_reference,
            yunit=test_yunit,
            multipliers=test_multipliers,
            first_file_multiplier=20,
            plot_denoised=True
        )
