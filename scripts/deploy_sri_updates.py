#!/usr/bin/env python3
"""
Deployment script: Update SRI files to use new table structure
"""

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def backup_file(filepath):
    """Backup a file before replacing"""
    if os.path.exists(filepath):
        backup_path = f"{filepath}.backup"
        shutil.copy2(filepath, backup_path)
        print(f"  ✓ Backed up: {backup_path}")
        return True
    return False

def update_files():
    """Update calculate_sri_scores.py and sri.py"""
    
    print("="*80)
    print("DEPLOYMENT: Update SRI Files")
    print("="*80)
    
    # Files to update
    calc_script_old = PROJECT_ROOT / "scripts" / "calculate_sri_scores.py"
    calc_script_new = PROJECT_ROOT / "scripts" / "calculate_sri_scores_v2.py"
    
    api_route_old = PROJECT_ROOT / "src" / "api" / "routes" / "sri.py"
    api_route_new = PROJECT_ROOT / "src" / "api" / "routes" / "sri_v2.py"
    
    print("\nStep 1: Update calculate_sri_scores.py")
    print("-" * 80)
    
    if not calc_script_new.exists():
        print(f"✗ ERROR: {calc_script_new} not found!")
        print("  Make sure calculate_sri_scores_v2.py exists")
        return False
    
    if backup_file(calc_script_old):
        shutil.copy2(calc_script_new, calc_script_old)
        print(f"  ✓ Updated: {calc_script_old}")
    else:
        print(f"  ℹ Original file not found, creating new: {calc_script_old}")
        shutil.copy2(calc_script_new, calc_script_old)
    
    print("\nStep 2: Update src/api/routes/sri.py")
    print("-" * 80)
    
    if not api_route_new.exists():
        print(f"✗ ERROR: {api_route_new} not found!")
        print("  Make sure sri_v2.py exists")
        return False
    
    if backup_file(api_route_old):
        shutil.copy2(api_route_new, api_route_old)
        print(f"  ✓ Updated: {api_route_old}")
    else:
        print(f"  ℹ Original file not found, creating new: {api_route_old}")
        shutil.copy2(api_route_new, api_route_old)
    
    print("\n" + "="*80)
    print("DEPLOYMENT COMPLETE!")
    print("="*80)
    print("\nFiles updated:")
    print(f"  1. {calc_script_old}")
    print(f"  2. {api_route_old}")
    print("\nBackups created:")
    print(f"  1. {calc_script_old}.backup")
    print(f"  2. {api_route_old}.backup")
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Test calculation script:")
    print("   python scripts/calculate_sri_scores.py")
    print()
    print("2. Restart API and test:")
    print("   # Kill old API process")
    print("   # Start: uvicorn src.api.main:app --reload")
    print("   curl http://localhost:8000/sri/network")
    print()
    print("3. Deploy to Oracle VM:")
    print("   scp scripts/calculate_sri_scores.py oracle-vm:/path/to/pt-analytics/scripts/")
    print("   scp src/api/routes/sri.py oracle-vm:/path/to/pt-analytics/src/api/routes/")
    print("="*80)
    
    return True

if __name__ == "__main__":
    success = update_files()
    exit(0 if success else 1)