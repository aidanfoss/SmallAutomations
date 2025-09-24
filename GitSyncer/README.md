# File Sync

A Python script that syncs files for a repo.  
It will either pull updates from Git or use files from a connected USB drive.  

## How it Works
- If a USB drive is mounted under `/media` or `/run/media`, the repo contents are replaced with the USB contents (the `.git` folder is kept).  
- If no USB drive is found, the script runs `git pull`.  

## Config
At the top of the script you can change:  
- `REPO_PATH` → repo location  
- `USB_MOUNT_BASES` → where to look for USB mounts  
- `KEEP_GIT_FOLDER` → whether to preserve `.git`  

## Usage
```bash
python3 file_sync.py

## To call from another script
from file_sync import sync_files

sync_files()

## Requirements
- Python 3+
- git (atm)