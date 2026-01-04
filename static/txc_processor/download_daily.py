"""
Download daily TXC updates from BODS
Files are temporarily stored in GitHub Actions runner, not VM
"""
import os
import requests
import zipfile
from pathlib import Path
from datetime import datetime

# Get date from environment (set by GitHub Actions)
UPDATE_DATE = os.getenv('UPDATE_DATE', datetime.now().strftime('%Y-%m-%d'))
DAILY_URL = f"https://data.bus-data.dft.gov.uk/timetable/download/change_archive/{UPDATE_DATE}/"

# Use /tmp on GitHub Actions runner (7GB available)
BASE_DIR = Path("/tmp/txc_daily")
DOWNLOAD_DIR = BASE_DIR / "downloads"
EXTRACT_DIR = BASE_DIR / "extracted"

# Create directories
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

print(f"Downloading daily update for {UPDATE_DATE}...")
print(f"Download to: {DOWNLOAD_DIR}")
print(f"Extract to: {EXTRACT_DIR}")

# Download the daily archive ZIP
try:
    response = requests.get(DAILY_URL, stream=True, timeout=300)
    response.raise_for_status()
    
    zip_path = DOWNLOAD_DIR / f"daily_{UPDATE_DATE}.zip"
    
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    progress = (downloaded / total_size) * 100
                    print(f"\rProgress: {progress:.1f}% ({downloaded:,} / {total_size:,} bytes)", end='')
    
    print(f"\n✓ Downloaded: {zip_path} ({zip_path.stat().st_size:,} bytes)")
    
except requests.exceptions.RequestException as e:
    print(f"ERROR downloading daily update: {e}")
    exit(1)

# Extract the main ZIP
print(f"\nExtracting daily archive...")
try:
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)
    
    print(f"✓ Extracted to: {EXTRACT_DIR}")
    
except zipfile.BadZipFile as e:
    print(f"ERROR: Invalid ZIP file: {e}")
    exit(1)

# Extract nested operator ZIPs
print(f"\nExtracting nested operator ZIPs...")
xml_count = 0

for operator_zip in EXTRACT_DIR.glob("*.zip"):
    try:
        operator_dir = EXTRACT_DIR / operator_zip.stem
        operator_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(operator_zip, 'r') as zip_ref:
            zip_ref.extractall(operator_dir)
        
        # Count XML files
        xml_files = list(operator_dir.glob("*.xml"))
        xml_count += len(xml_files)
        
        print(f"  ✓ {operator_zip.name}: {len(xml_files)} XML files")
        
        # Remove the ZIP after extraction
        operator_zip.unlink()
        
    except Exception as e:
        print(f"  ✗ Error extracting {operator_zip.name}: {e}")

print(f"\n{'='*60}")
print(f"EXTRACTION COMPLETE")
print(f"{'='*60}")
print(f"Total XML files: {xml_count}")
print(f"Location: {EXTRACT_DIR}")
print(f"{'='*60}")
