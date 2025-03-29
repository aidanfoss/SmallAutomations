import json
import os

def load_json_file(path):
    """Load JSON data from the given file path."""
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        print(f"Loaded JSON from {path}")
        return data
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return []

def main():
    # List of directories to process
    usercache_dirs = [
        '/docker/ATM10',
        '/docker/EarthMCFabric',
        '/docker/EternalMC',
        '/docker/minecraft/superflat'
    ]
    
    # Dictionary for whitelist entries, using UUID as key to avoid duplicates
    whitelist_dict = {}
    # List to collect excluded usernames (either banned, used by carpet temporarily, or ending with 'afk')
    excluded_names = [
        'Birch',
        'Herobrine',
        'theshogen',
        'Test',
        'quantum10101',
        'ilike2sleeptemp',
        'Dropper',
        'spawn',
        'ghast',
        'WaterHashira',
        'Itachi',
        'Giyu',
        'moninao',
        'burberryheadband',
        'Kosovo',
        'Offline',
        'alyluvr',
        'Duper',
        'end',
        'Sheep'
        ]
    
    # Build a set of banned UUIDs from banned-players.json files
    banned_uuids = set()
    for directory in usercache_dirs:
        banned_path = os.path.join(directory, 'banned-players.json')
        if os.path.exists(banned_path):
            banned_data = load_json_file(banned_path)
            for entry in banned_data:
                banned_uuid = entry.get('uuid')
                if banned_uuid:
                    banned_uuids.add(banned_uuid)
            print(f"Banned players loaded from {banned_path}.")
        else:
            print(f"No banned-players.json found in {directory}.")

    # Process usercache.json from each directory
    for directory in usercache_dirs:
        usercache_path = os.path.join(directory, 'usercache.json')
        if os.path.exists(usercache_path):
            data = load_json_file(usercache_path)
            for entry in data:
                uuid = entry.get('uuid')
                name = entry.get('name')
                if not uuid or not name:
                    print(f"Skipping an entry in {usercache_path} due to missing uuid or name.")
                    continue

                # Exclude if UUID is banned
                if uuid in banned_uuids:
                    print(f"Excluding {name} with UUID {uuid} from {usercache_path} because they are banned.")
                    excluded_names.append(name)
                    continue

                # Exclude if username ends with 'afk'
                if name.lower().endswith("afk"):
                    print(f"Excluding {name} because it ends with 'afk'.")
                    excluded_names.append(name)
                    continue
                    
                # Exclude from exclusion list
                #if name in excluded_names:
                #    print(f"Excluding {name} with UUID {uuid} from {usercache_path} because they are banned.")
                #    excluded_names.append(name)
                #   continue
                #This is redundant, could just add them to the thing at the top

                # Add entry if not already present
                if uuid not in whitelist_dict:
                    whitelist_dict[uuid] = {"uuid": uuid, "name": name}
                    print(f"Added {name} with UUID {uuid} from {usercache_path} to whitelist.")
                else:
                    print(f"Duplicate found for {name} with UUID {uuid} in {usercache_path}.")
        else:
            print(f"usercache.json not found in {directory}.")

    # Optional: merge with an existing whitelist (if present in the script directory)
    script_dir = os.path.dirname(__file__)
    existing_whitelist_path = os.path.join(script_dir, 'whitelist.json')
    if os.path.exists(existing_whitelist_path):
        try:
            with open(existing_whitelist_path, 'r') as f:
                existing_whitelist = json.load(f)
            for entry in existing_whitelist:
                uuid = entry.get('uuid')
                name = entry.get('name')
                if not uuid or not name:
                    continue
                if uuid in banned_uuids:
                    print(f"Excluding {name} from existing whitelist because they are banned.")
                    excluded_names.append(name)
                    continue
                if name.lower().endswith("afk"):
                    print(f"Excluding {name} from existing whitelist because it ends with 'afk'.")
                    excluded_names.append(name)
                    continue
                if uuid not in whitelist_dict:
                    whitelist_dict[uuid] = {"uuid": uuid, "name": name}
                    print(f"Added {name} with UUID {uuid} from existing whitelist.")
            print("Existing whitelist merged.")
        except Exception as e:
            print(f"Error loading existing whitelist: {e}")

    # Convert the whitelist dictionary to a list for saving
    merged_whitelist = list(whitelist_dict.values())
    output_file = os.path.join(script_dir, 'merged_whitelist.json')
    try:
        with open(output_file, 'w') as f:
            json.dump(merged_whitelist, f, indent=4)
        print(f"Successfully saved merged whitelist to {output_file}.")
    except Exception as e:
        print(f"Error saving merged whitelist: {e}")

    # Print out excluded usernames
    if excluded_names:
        unique_exclusions = list(set(excluded_names))
        print("\nExcluded usernames:")
        for name in unique_exclusions:
            print(f" - {name}")
    else:
        print("\nNo usernames were excluded.")

if __name__ == "__main__":
    print(f"Current working directory: {os.getcwd()}")
    main()
    input("Press Enter to exit...")
