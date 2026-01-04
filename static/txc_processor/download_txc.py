"""
TransXChange Download and Extract Script
Downloads North West bulk archive and extracts Merseyside operators
NO USER PROMPTS - fully automated for cron jobs
"""

import requests
import zipfile
import os
from pathlib import Path
from datetime import datetime
import sys

# Paths - use /tmp on GitHub Actions, local path otherwise
if os.getenv('GITHUB_ACTIONS'):
    BASE_DIR = Path("/tmp/txc_monthly")
else:
    BASE_DIR = Path(__file__).parent

DOWNLOAD_DIR = BASE_DIR / "downloads"
EXTRACT_DIR = BASE_DIR / "extracted"

# BODS URL
BODS_NW_URL = "https://data.bus-data.dft.gov.uk/timetable/download/bulk_archive/NW"

# Target Merseyside operators - Process ALL for production
TARGET_OPERATORS = []  # Empty = process all operators

def download_northwest_bulk():
    """Download North West TransXChange bulk archive"""
    print("=" * 60)
    print("DOWNLOADING NORTH WEST TRANSXCHANGE BULK ARCHIVE")
    print("=" * 60)
    
    zip_path = DOWNLOAD_DIR / f"northwest_bulk_{datetime.now().strftime('%Y%m%d')}.zip"
    
    # Auto-remove old file if exists (for automation)
    if zip_path.exists():
        print(f"Removing existing file: {zip_path}")
        zip_path.unlink()
    
    print(f"Downloading from: {BODS_NW_URL}")
    print("This may take several minutes (332MB)...")
    
    try:
        response = requests.get(BODS_NW_URL, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rProgress: {percent:.1f}% ({downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB)", end='')
        
        print(f"\n✓ Downloaded to: {zip_path}")
        return zip_path
        
    except Exception as e:
        print(f"✗ Download failed: {e}")
        raise

def extract_target_operators(zip_path):
    """Extract all operator folders from bulk archive"""
    print("\n" + "=" * 60)
    print("EXTRACTING ALL OPERATORS")
    print("=" * 60)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        if TARGET_OPERATORS:
            # Extract specific operators only
            all_items = zip_ref.namelist()
            extracted_count = 0
            
            for operator in TARGET_OPERATORS:
                print(f"\nSearching for: {operator}")
                matching_items = [item for item in all_items if operator in item]
                
                if matching_items:
                    print(f"  Found {len(matching_items)} files")
                    for item in matching_items:
                        zip_ref.extract(item, EXTRACT_DIR)
                        extracted_count += 1
                else:
                    print(f"  ⚠ Not found in archive")
            
            print(f"\n✓ Extracted {extracted_count} items")
        else:
            # Extract ALL operators
            print("Extracting all operators from North West...")
            zip_ref.extractall(EXTRACT_DIR)
            print(f"✓ Extracted all files")

def extract_nested_zips():
    """Extract nested operator ZIP files to get XML files"""
    print("\n" + "=" * 60)
    print("EXTRACTING NESTED OPERATOR ZIPS")
    print("=" * 60)
    
    xml_count = 0
    
    for root, dirs, files in os.walk(EXTRACT_DIR):
        for file in files:
            if file.endswith('.zip'):
                nested_zip = Path(root) / file
                # Use shorter extract path to avoid Windows path length limit
                extract_to = nested_zip.parent / "xml"
                
                print(f"\nExtracting: {file}")
                
                try:
                    with zipfile.ZipFile(nested_zip, 'r') as zip_ref:
                        # Extract directly without preserving nested folder structure
                        for member in zip_ref.namelist():
                            if member.endswith('.xml'):
                                # Extract with flattened path
                                filename = Path(member).name
                                source = zip_ref.open(member)
                                target = extract_to / filename
                                
                                # Create directory if needed
                                target.parent.mkdir(parents=True, exist_ok=True)
                                
                                with open(target, 'wb') as f:
                                    f.write(source.read())
                                source.close()  # Close file handle
                                xml_count += 1
                        
                        print(f"  ✓ Extracted XML files")
                    
                    # Remove nested zip after extraction (outside with block)
                    try:
                        nested_zip.unlink()
                    except:
                        pass  # Ignore deletion errors, files extracted successfully
                    
                except Exception as e:
                    print(f"  ✗ Failed: {e}")
    
    print(f"\n✓ Total XML files extracted: {xml_count}")
    return xml_count

def main():
    print("\n" + "=" * 60)
    print("TRANSXCHANGE DOWNLOAD & EXTRACTION")
    print("=" * 60)
    print(f"Base directory: {BASE_DIR}")
    print(f"Download to: {DOWNLOAD_DIR}")
    print(f"Extract to: {EXTRACT_DIR}")
    print()
    
    # Ensure directories exist
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Download bulk archive
    zip_file = download_northwest_bulk()
    
    # Step 2: Extract target operators
    extract_target_operators(zip_file)
    
    # Step 3: Extract nested ZIPs to get XMLs
    xml_count = extract_nested_zips()
    
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"XML files ready for parsing: {xml_count}")
    print(f"Location: {EXTRACT_DIR}")
    print()

if __name__ == "__main__":
    main()
