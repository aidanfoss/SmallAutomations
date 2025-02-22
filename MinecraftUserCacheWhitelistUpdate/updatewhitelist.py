import json
import os


print(f"Current working directory: {os.getcwd()}")

# Load data from usercache.json
try:
    usercache_path = os.path.join(os.path.dirname(__file__), 'usercache.json')
    with open(usercache_path, 'r') as usercache_file:
        usercache_data = json.load(usercache_file)
        print("Loaded usercache.json successfully.")
except FileNotFoundError:
    print("Error: usercache.json not found.")
    input("Press Enter to exit...")
    exit(1)

# Prepare whitelist data
whitelist_data = []
for entry in usercache_data:
    whitelist_entry = {
        "uuid": entry['uuid'],
        "name": entry['name']
    }
    whitelist_data.append(whitelist_entry)
    print(f"Added {entry['name']} with UUID {entry['uuid']} to the whitelist.")

# Save data to whitelist.json
try:
    whitelist_path = os.path.join(os.path.dirname(__file__), 'whitelist2.json')
    with open(whitelist_path, 'w') as whitelist_file:
        json.dump(whitelist_data, whitelist_file, indent=4)
        print("Conversion complete. 'whitelist2.json' has been updated successfully.")
except Exception as e:
    print(f"Error saving whitelist.json: {e}")

# Prevent console from closing immediately
input("Press Enter to exit...")
