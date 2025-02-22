import json
import os

# Get the directory where the script is located
script_dir = os.path.dirname(__file__)

def load_whitelist(filename):
    whitelist_path = os.path.join(script_dir, filename)
    try:
        with open(whitelist_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: {filename} contains invalid JSON.")
        return []

def merge_whitelists(whitelist1, whitelist2):
    merged = {entry['uuid']: entry for entry in whitelist1}  # Use UUIDs as keys
    for entry in whitelist2:
        if entry['uuid'] not in merged:
            merged[entry['uuid']] = entry  # Add only new entries
    return list(merged.values())

# Load both whitelists
whitelist1 = load_whitelist('whitelist.json')
whitelist2 = load_whitelist('whitelist2.json')

# Merge the whitelists without duplicates
combined_whitelist = merge_whitelists(whitelist1, whitelist2)

# Save the combined whitelist
output_filename = os.path.join(script_dir, 'merged_whitelist.json')
try:
    with open(output_filename, 'w') as file:
        json.dump(combined_whitelist, file, indent=4)
    print(f"Successfully merged and saved to {output_filename}.")
except Exception as e:
    print(f"Error saving {output_filename}: {e}")

# Prevent the console from closing immediately
input("Press Enter to exit...")
