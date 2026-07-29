import os
import math
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def generate_pwm_waveform(pwm_type, maximum=10000, target=150, frequency=0.0001, amplitude=100):
    """
    Generates PWM pulse list matching the mathematical functions in coil_test.ipynb.
    """
    pulseList = []
    pwm_type = pwm_type.lower().strip()
    
    if pwm_type == 'sawtooth':
        nextNum = 100
        flip = False
        for i in range(0,maximum):
            pulseList.append(int(math.floor(nextNum)))
            if flip:
                nextNum += 0.05
            else:
                nextNum -= 0.05
            
            if nextNum >= 175:
                flip = False
            elif nextNum <= 25:
                flip = True
                
    elif pwm_type == 'ramp':
        startNum = 0
        endNum = 200
        inc = (endNum - startNum) / (maximum - 1)
        for i in range(maximum):
            val = startNum + i * inc
            pulseList.append(int(round(val)))
            
    elif pwm_type == 'rampup_flattop':
        ramp_length = int(math.floor(maximum / 2))
        zero = 100
        inc = (target - zero) / ramp_length
        num = zero
        for i in range(ramp_length):
            pulseList.append(int(math.floor(num)))
            num += inc
        for i in range(ramp_length + 1, maximum):
            pulseList.append(target)
        while len(pulseList) < maximum:
            pulseList.append(target)
            
    elif pwm_type == 'rampup_flattop_rampdown':
        ramp_length = int(math.floor(maximum / 4))
        zero = 100
        inc = (target - zero) / ramp_length
        num = zero
        for i in range(ramp_length):
            pulseList.append(int(math.floor(num)))
            num += inc
            
        # middle 2/4
        for i in range(ramp_length + 1, ((ramp_length + 1) + ramp_length * 2)):
            pulseList.append(target)
            
        # ramp down
        num = target
        for i in range(((ramp_length + 1) + ramp_length * 2) + 1, maximum):
            pulseList.append(int(math.floor(num)))
            num -= inc
        while len(pulseList) < maximum:
            pulseList.append(int(math.floor(num)))
            num -= inc
            
    elif pwm_type == 'constant':
        for i in range(maximum):
            pulseList.append(target)
            
    elif pwm_type == 'sine':
        for i in range(maximum):
            pulseList.append(int(math.floor(amplitude * (1 + math.sin(i * 2 * math.pi * frequency)))))
            
    else:
        raise ValueError(f"Unknown PWM type: {pwm_type}")
        
    return pulseList

def modal_compare(data_dir, filename, pwm_type, channels=['CH4'], CH_ref='CH4', yunit='A', 
                  multipliers=[1.0], first_file_multiplier=1.0, plot_denoised=False, 
                  output_folder='plotes_color', output_filename=None, colormap='plasma', 
                  alpha=0.75, dpi=300, pwm_sample_period_us=20.0, trigger_time_ms=10.0, 
                  xlim=(0, 250), pwm_target=150, pwm_frequency=0.0001, pwm_amplitude=100, 
                  pwm_maximum=10000):
    """
    Overlays acquired scope waveforms and generated controller PWM signals on a single plot using a dual-y-axis (ax.twinx()).
    """
    os.makedirs(output_folder, exist_ok=True)
    
    # Locate data file
    if not filename.endswith('.csv'):
        csv_path = os.path.join(data_dir, filename + ".csv")
    else:
        csv_path = os.path.join(data_dir, filename)
        filename = os.path.splitext(filename)[0]
        
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Scope data file not found: {csv_path}")
        
    print(f"Reading scope data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Find Time column
    time_cols = [col for col in df.columns if "Time" in col]
    if not time_cols:
        raise ValueError(f"No Time column found in {csv_path}")
    time_col = time_cols[0]
    time_axis = df[time_col].to_numpy()
    
    # Detect trigger using CH_ref_Raw
    trigger_cols = [col for col in df.columns if f"{CH_ref}_Raw" in col]
    if not trigger_cols:
        raise ValueError(f"Trigger reference column '{CH_ref}_Raw' not found in {csv_path}")
    trigger_col = trigger_cols[0]
    trigger_data = df[trigger_col].to_numpy()
    
    # Calculate baseline noise
    baseline_len = min(1000, len(trigger_data))
    baseline = trigger_data[:baseline_len]
    baseline_mean = np.mean(baseline)
    baseline_std = np.std(baseline)
    
    std_threshold = max(baseline_std, 1e-6)
    deviation = np.abs(trigger_data - baseline_mean)
    trigger_indices = np.where(deviation > 5 * std_threshold)[0]
    
    if len(trigger_indices) > 0:
        trigger_idx = trigger_indices[0]
    else:
        trigger_idx = 0
        print(f"Warning: No shot trigger detected. Defaulting to start of file.")
        
    actual_trigger_time = time_axis[trigger_idx]
    print(f"Detected trigger at index {trigger_idx} (t={actual_trigger_time:.5f} s)")
    
    # Shift time axis so trigger corresponds to trigger_time_ms
    shifted_time_ms = (time_axis - actual_trigger_time) * 1000.0 + trigger_time_ms
    
    # Set up matplotlib figure
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    # Map multipliers
    multiplier_map = dict(zip(channels, multipliers))
    
    # Plot scope channels
    cmap = plt.get_cmap(colormap) if colormap else None
    total_curves = len(channels)
    max_val = 0.0
    
    for ch_idx, ch in enumerate(channels):
        raw_cols = [col for col in df.columns if f"{ch}_Raw" in col]
        if not raw_cols:
            print(f"Warning: Channel {ch} raw column not found. Skipping.")
            continue
        raw_col = raw_cols[0]
        
        mult = multiplier_map[ch]
        scaled_data = df[raw_col].to_numpy() * mult
        max_val = max(max_val, np.max(np.abs(scaled_data)))
        
        label = f"{filename}: {ch}"
        if mult != 1.0:
            label += f" (x{mult})"
            
        color = cmap(0.9 * ch_idx / max(1, total_curves - 1)) if cmap else None
        
        ax1.plot(shifted_time_ms, scaled_data, label=label, color=color, alpha=alpha, linewidth=1.8)
        
        if plot_denoised:
            filt_cols = [col for col in df.columns if f"{ch}_Filtered" in col]
            if filt_cols:
                filt_col = filt_cols[0]
                scaled_filt = df[filt_col].to_numpy() * mult
                max_val = max(max_val, np.max(np.abs(scaled_filt)))
                filt_label = f"{filename}: {ch} (Filtered)"
                if mult != 1.0:
                    filt_label += f" (x{mult})"
                ax1.plot(shifted_time_ms, scaled_filt, '--', label=filt_label, color=color, alpha=alpha, linewidth=1.5)

    ax1.set_xlabel("Time (ms)", fontsize=12, labelpad=10)
    ax1.set_ylabel(yunit, fontsize=12, labelpad=10)
    ax1.set_xlim(xlim)
    
    # Align 0 on left Y-axis with 100 on right Y-axis (PWM 0 to 200)
    if max_val == 0.0:
        max_val = 1.0
    y1_limit = max_val * 1.15
    ax1.set_ylim(-y1_limit, y1_limit)
    
    ax1.minorticks_on()
    ax1.grid(True, which='major', linestyle='--', color='darkgray', alpha=0.5)
    ax1.grid(True, which='minor', linestyle=':', color='lightgray', alpha=0.5)
    
    # Generate and plot PWM waveform on secondary y-axis
    print(f"Generating {pwm_type} PWM waveform...")
    pulseList = generate_pwm_waveform(
        pwm_type=pwm_type, 
        maximum=pwm_maximum, 
        target=pwm_target, 
        frequency=pwm_frequency, 
        amplitude=pwm_amplitude
    )
    
    # Calculate PWM timeline: aligned to trigger_time_ms at index 0
    pwm_time_ms = trigger_time_ms + np.arange(len(pulseList)) * (pwm_sample_period_us / 1000.0)
    
    ax2 = ax1.twinx()
    ax2.set_ylim(0, 200)
    # Draw PWM waveform step/line in contrasting crimson color
    ax2.plot(pwm_time_ms, pulseList, '-.', label=f"PWM: {pwm_type}", color='crimson', alpha=0.85, linewidth=1.8)
    ax2.set_ylabel("PWM Duty Cycle Value (0-200)", fontsize=12, labelpad=10, color='crimson')
    ax2.tick_params(axis='y', labelcolor='crimson')
    
    # Combine legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", frameon=True, framealpha=0.9, facecolor='white', edgecolor='lightgray')
    
    plt.title(f"Overlay of Acquired Waveforms and Controller PWM ({pwm_type})", fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    
    if output_filename is None:
        output_filename = f"modal_{filename}_{pwm_type}.png"
    
    plot_save_path = os.path.join(output_folder, output_filename)
    plt.savefig(plot_save_path, dpi=dpi)
    plt.close()
    
    print(f"Success! Modal comparison overlay plot saved to {plot_save_path}\n")

def interactive_modal_compare():
    """
    Interactive CLI helper to let user choose the data folder, select a CSV file, choose a PWM type, and generate the overlay plot.
    """
    print("==================================================")
    print("Welcome to the Modal Comparison Plot Generator!")
    print("==================================================")
    
    # 1. Select data folder
    data_folders = ["data", "data1a", "data20", "dataca", "compare_data"]
    existing_folders = [d for d in data_folders if os.path.isdir(d)]
    
    if not existing_folders:
        print("Error: No data folders found in the workspace.")
        return
        
    print("\nAvailable Data Folders:")
    for idx, folder in enumerate(existing_folders):
        print(f"  {idx + 1}: {folder}")
        
    try:
        folder_choice = int(input("\nSelect a folder number: ")) - 1
        if folder_choice < 0 or folder_choice >= len(existing_folders):
            print("Invalid choice. Exiting.")
            return
        selected_folder = existing_folders[folder_choice]
    except ValueError:
        print("Invalid input. Exiting.")
        return
        
    # 2. Select CSV file
    csv_files = sorted(glob.glob(os.path.join(selected_folder, "*.csv")))
    if not csv_files:
        print(f"No CSV files found in folder {selected_folder}.")
        return
        
    print(f"\nAvailable CSV files in {selected_folder}:")
    for idx, fpath in enumerate(csv_files):
        print(f"  {idx + 1}: {os.path.basename(fpath)}")
        
    try:
        file_choice = int(input("\nSelect a file number: ")) - 1
        if file_choice < 0 or file_choice >= len(csv_files):
            print("Invalid choice. Exiting.")
            return
        selected_file = os.path.basename(csv_files[file_choice])
    except ValueError:
        print("Invalid input. Exiting.")
        return
        
    # 3. Select PWM Waveform Type
    pwm_types = ["sawtooth", "ramp", "rampup_flattop", "rampup_flattop_rampdown", "constant", "sine"]
    print("\nAvailable PWM Waveform Types:")
    for idx, ptype in enumerate(pwm_types):
        print(f"  {idx + 1}: {ptype}")
        
    try:
        pwm_choice = int(input("\nSelect a PWM type number: ")) - 1
        if pwm_choice < 0 or pwm_choice >= len(pwm_types):
            print("Invalid choice. Exiting.")
            return
        selected_pwm = pwm_types[pwm_choice]
    except ValueError:
        print("Invalid input. Exiting.")
        return
        
    # 4. Generate Plot
    try:
        modal_compare(
            data_dir=selected_folder,
            filename=selected_file,
            pwm_type=selected_pwm,
            channels=['CH4'],
            CH_ref='CH4',
            yunit='A',
            colormap='plasma',
            plot_denoised=False
        )
    except Exception as e:
        print(f"An error occurred during plot generation: {e}")

if __name__ == "__main__":
    # If run directly as a script, start interactive helper
    interactive_modal_compare()
