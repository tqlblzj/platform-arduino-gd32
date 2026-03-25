import os
import urllib.request
import zipfile
from pathlib import Path
import shutil

# Configuration
FRAMEWORK_URL = "https://github.com/tqlblzj/arduino-gd32/releases/download/v1.0.0/framework-arduino-gd32w.zip"
# Use global PlatformIO packages directory
FRAMEWORK_DIR = Path.home() / ".platformio" / "packages" / "framework-arduino-gd32w"

def download_and_extract():
    if FRAMEWORK_DIR.exists():
        print(f"✓ Framework already exists at {FRAMEWORK_DIR}")
        return

    print(f"→ Downloading framework from {FRAMEWORK_URL}...")

    # Create temporary directory
    temp_dir = Path.home() / ".platformio" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    zip_path = temp_dir / "framework.zip"

    # Download progress callback function
    def download_progress(block_num, block_size, total_size):
        """Display download progress"""
        if total_size > 0:
            downloaded = block_num * block_size
            percent = min(downloaded * 100 / total_size, 100)
            # Use \r to overwrite current line, flush=True ensures immediate display
            print(f"\rDownload progress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end="", flush=True)
        else:
            print(f"\rDownloaded: {block_num * block_size} bytes", end="", flush=True)

    # Download
    urllib.request.urlretrieve(FRAMEWORK_URL, zip_path, reporthook=download_progress)
    print()  # Newline to separate progress bar from subsequent output
    print(f"✓ Download completed: {zip_path}")

    # Extract
    print(f"→ Extracting to {FRAMEWORK_DIR}...")

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(FRAMEWORK_DIR.parent)

    # Cleanup
    shutil.rmtree(temp_dir)
    print(f"✓ Framework installation completed!")

# Execute before build
download_and_extract()
