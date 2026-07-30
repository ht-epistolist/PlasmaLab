import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def main():
    data_dir = "/home/heliot/Projects/PlasmaLab/data/data20"
    plots1_dir = "/home/heliot/Projects/PlasmaLab/plots/plots20"
    
    # Create plots1 directory if it doesn't exist
    os.makedirs(plots1_dir, exist_ok=True)
    print(f"Destination folder created: {plots1_dir}")
    
    # Find all CSV files in data/
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_files:
        print(f"No CSV files found in {data_dir}")
        return
        
    print(f"Found {len(csv_files)} CSV files to process.")
    
    for csv_path in csv_files:
        filename = os.path.basename(csv_path)
        base_name = os.path.splitext(filename)[0]
        plot_path = os.path.join(plots1_dir, f"{base_name}.png")
        
        print(f"Processing {filename}...")
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            
            # Find time column
            time_col = [col for col in df.columns if "Time" in col][0]
            time_axis = df[time_col].to_numpy()
            
            # Determine readable time scale units
            max_time = np.max(np.abs(time_axis))
            time_multiplier = 1.0
            plot_time_unit = "s"
            
            if max_time < 1e-6:
                time_multiplier = 1e9
                plot_time_unit = "ns"
            elif max_time < 1e-3:
                time_multiplier = 1e6
                plot_time_unit = "µs"
            elif max_time < 1.0:
                time_multiplier = 1e3
                plot_time_unit = "ms"
                
            scaled_time = time_axis * time_multiplier
            
            # Map columns to channels
            raw_col_map = {}
            filtered_col_map = {}
            for col in df.columns:
                if "_Raw" in col:
                    ch = col.split("_Raw")[0]
                    raw_col_map[ch] = col
                elif "_Filtered" in col:
                    ch = col.split("_Filtered")[0]
                    filtered_col_map[ch] = col
            
            # Plot
            plt.figure(figsize=(12, 6))
            channels = sorted(raw_col_map.keys())
            total_channels = len(channels)
            cmap = plt.get_cmap('plasma')
            for ch_idx, ch in enumerate(channels):
                raw_col = raw_col_map[ch]
                color_val = 0.9 * ch_idx / max(1, total_channels - 1)
                color = cmap(color_val)
                plt.plot(scaled_time, df[raw_col], ':', label=f"{ch} (Raw)", alpha=0.5, linewidth=1.5, color=color)
                if ch in filtered_col_map:
                    filt_col = filtered_col_map[ch]
                    plt.plot(scaled_time, df[filt_col], '-', label=f"{ch} (Filtered)", alpha=0.9, linewidth=1.8, color=color)
            
            plt.title("Comparison of Raw and Low-Pass Filtered Waveforms", fontsize=14, fontweight='bold', pad=15)
            plt.xlabel(f"Time ({plot_time_unit})", fontsize=12, labelpad=10)
            plt.ylabel("V (cA)", fontsize=12, labelpad=10)
            plt.minorticks_on()
            plt.grid(True, which='major', linestyle='--', color='darkgray', alpha=0.5)
            plt.grid(True, which='minor', linestyle=':', color='lightgray', alpha=0.5)
            plt.legend(loc="upper left", frameon=True, framealpha=0.9, facecolor='white', edgecolor='lightgray')
            plt.tight_layout()
            
            # Save plot
            plt.savefig(plot_path, dpi=300)
            plt.close()
            print(f"  Successfully saved plot to {plot_path}")
            
        except Exception as e:
            print(f"  Error processing {filename}: {e}")

    print("Finished regenerating all plots!")

if __name__ == "__main__":
    main()
