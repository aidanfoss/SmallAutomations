# file_sync.py
import subprocess
import os
import shutil

# ==============================
# Configurable settings
# ==============================
REPO_PATH = "."                # Path to the repo to maintain
USB_MOUNT_BASES = [             # Possible mount locations for USB drives
    "/media",
    "/run/media"
]
KEEP_GIT_FOLDER = True          # Keep .git folder during USB overrides
# ==============================


def sync_files():
    """
    Sync files with two modes:
    - If a USB drive is detected: replace repo contents with USB contents.
    - Otherwise: run 'git pull' in the repo.
    """
    usb_path = detect_usb()

    if usb_path:
        print(f"USB detected at {usb_path}, overriding repo files...")
        override_with_usb(usb_path)
    else:
        print("No USB detected, pulling from git...")
        git_pull()


def detect_usb():
    """
    Detect if a USB drive is mounted under configured mount bases.
    Returns the path if found, else None.
    """
    for base in USB_MOUNT_BASES:
        if not os.path.exists(base):
            continue
        for root, dirs, _ in os.walk(base):
            for d in dirs:
                return os.path.join(root, d)
            break  # only one level down
    return None


def override_with_usb(usb_path):
    """
    Deletes repo contents and replaces them with contents from usb_path.
    """
    try:
        # Wipe old files
        for item in os.listdir(REPO_PATH):
            if KEEP_GIT_FOLDER and item == ".git":
                continue
            item_path = os.path.join(REPO_PATH, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)

        # Copy files from USB
        for item in os.listdir(usb_path):
            src = os.path.join(usb_path, item)
            dst = os.path.join(REPO_PATH, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        print("Repo contents replaced with USB files.")
    except Exception as e:
        print("Error overriding with USB:", e)


def git_pull():
    """Run git pull in the repo path."""
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            check=True
        )
        print("Sync successful:\n", result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error running git pull:\n", e.stderr)


if __name__ == "__main__":
    sync_files()
