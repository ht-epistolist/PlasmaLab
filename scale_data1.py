import os
import glob
import pandas as pd

def main():
    data_dir = "/home/heliot/Projects/PlasmaLab/data"
    data1_dir = "/home/heliot/Projects/PlasmaLab/data1"
    
    # Create data1 directory if it doesn't exist
    os.makedirs(data1_dir, exist_ok=True)
    print(f"Created folder: {data1_dir}")
    
    # Find all CSV files in data/
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_files:
        print("No CSV files found in data/")
        return
        
    print(f"Found {len(csv_files)} CSV files to process.")
    
    for csv_path in csv_files:
        filename = os.path.basename(csv_path)
        dest_path = os.path.join(data1_dir, filename)
        
        print(f"Processing {filename}...")
        try:
            df = pd.read_csv(csv_path)
            
            # Find and scale down columns containing CH3 or CH4
            scaled_cols = []
            for col in df.columns:
                if "CH3" in col or "CH4" in col:
                    df[col] = df[col] / 100.0
                    scaled_cols.append(col)
            
            # Save to data1/
            df.to_csv(dest_path, index=False)
            print(f"  Scaled columns: {scaled_cols}")
            print(f"  Saved to: {dest_path}")
            
        except Exception as e:
            print(f"  Error processing {filename}: {e}")

    print("Finished scaling data and creating data1 folder!")

if __name__ == "__main__":
    main()
