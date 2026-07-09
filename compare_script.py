import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# CONFIGURATION SECTION (Edit these variables directly)
# ==============================================================================
# List of CSV filenames in the data/ directory to compare
files = [
    "hill.csv",
    "line.csv",
    "ramp.csv",
    "sawtooth.csv"
]

# List of channels to plot
channels = ["CH1", "CH2", "CH3", "CH4"]

# Multipliers corresponding to each channel in the 'channels' list
multipliers = [1.0, 1.0, 1.0, 10.0]  # Scale CH4 ten times, others unchanged

# Y-axis label unit
yunit = "V (cA)"

# Output folder and filename
output_folder = "plots_compare"
output_filename = "comparison_plot.png"
# ==============================================================================

def main():
    data_dir = "data"
    os.makedirs(output_folder, exist_ok=True)
    
    plt.figure(figsize=(12, 6))
    
    # Map each channel to its multiplier
    multiplier_map = dict(zip(channels, multipliers))
    
    plotted_any = False
    
    for filename in files:
        csv_path = os.path.join(data_dir, filename)
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
            trigger_cols = [col for col in df.columns if "CH1_Raw" in col]
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
                scaled_data = df[raw_col].to_numpy() * mult
                
                # Label format: "filename: channel"
                label = f"{filename.replace('.csv', '')}: {ch}"
                if mult != 1.0:
                    label += f" (x{mult})"
                    
                plt.plot(shifted_time_ms, scaled_data, label=label)
                plotted_any = True
                
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

if __name__ == "__main__":
    main()
