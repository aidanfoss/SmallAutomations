import os

# Get the current script directory (assuming it's dropped inside `.minecraft`)
base_path = os.path.abspath(os.path.dirname(__file__))

# Define the old and new filenames
old_filename = "Multiplayer_174.53.233.150"
new_filename = "Multiplayer_earth.quantumaidan.co.za"

# Directories where the file needs to be renamed
directories = ["xaero/minimap", "xaero/world-map"]

# Iterate over both directories
for subdir in directories:
    old_file = os.path.join(base_path, subdir, old_filename)
    new_file = os.path.join(base_path, subdir, new_filename)

    if os.path.exists(old_file):
        try:
            os.rename(old_file, new_file)
            print(f"Renamed: {old_file} → {new_file}")
        except Exception as e:
            print(f"Failed to rename {old_file}: {e}")
    else:
        print(f"File not found: {old_file}")

input("Press Enter to exit...")  # Keeps the window open to see messages
