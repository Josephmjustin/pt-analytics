"""
Complete BODS SIRI-VM data explorer
Dynamically discovers ALL fields in the XML response
"""

import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv
import json
from collections import defaultdict

load_dotenv()

# BODS API Configuration
BODS_API_KEY = os.getenv("BODS_API_KEY")
LIVERPOOL_BBOX = "-3.05,53.35,-2.85,53.48"
SIRI_URL = f"https://data.bus-data.dft.gov.uk/api/v1/datafeed/?api_key={BODS_API_KEY}&boundingBox={LIVERPOOL_BBOX}"

# SIRI namespace
NS = {
    'siri': 'http://www.siri.org.uk/siri'
}


def element_to_dict(element, path=""):
    """Recursively convert XML element to nested dictionary with full paths"""
    result = {}
    
    # Get tag name without namespace
    tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
    current_path = f"{path}/{tag}" if path else tag
    
    # If element has text content (and no children), store it
    if element.text and element.text.strip() and len(element) == 0:
        return {current_path: element.text.strip()}
    
    # Process all child elements
    for child in element:
        child_dict = element_to_dict(child, current_path)
        result.update(child_dict)
    
    return result


def explore_vehicle_activity_complete(activity):
    """Extract ALL fields from VehicleActivity element dynamically"""
    # Convert entire activity to flat dictionary with paths
    all_fields = element_to_dict(activity)
    return all_fields


def print_nested_dict(data, indent=0):
    """Pretty print nested dictionary"""
    for key, value in sorted(data.items()):
        if isinstance(value, dict):
            print("  " * indent + f"{key}:")
            print_nested_dict(value, indent + 1)
        else:
            print("  " * indent + f"{key}: {value}")


def fetch_and_display_sample():
    """Fetch sample data and display ALL available fields"""
    try:
        print(f"Fetching data from BODS API...")
        print(f"Bounding Box: {LIVERPOOL_BBOX}\n")
        
        response = requests.get(SIRI_URL, timeout=30)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        vehicle_activities = root.findall('.//siri:VehicleActivity', NS)
        
        print(f"Found {len(vehicle_activities)} vehicle activities\n")
        print("="*100)
        
        # Collect all unique field paths across all vehicles
        all_field_paths = set()
        vehicle_samples = []
        
        for activity in vehicle_activities:
            fields = explore_vehicle_activity_complete(activity)
            all_field_paths.update(fields.keys())
            vehicle_samples.append(fields)
        
        # Display first 3 vehicles with ALL fields
        print("\nDETAILED VIEW - FIRST 3 VEHICLES:")
        print("="*100)
        
        for i, fields in enumerate(vehicle_samples[:3], 1):
            print(f"\nVEHICLE {i}:")
            print("-"*100)
            for path in sorted(fields.keys()):
                # Show full path and value
                print(f"  {path:70s}: {fields[path]}")
            print("-"*100)
        
        # Show ALL unique field paths found
        print("\n" + "="*100)
        print(f"ALL UNIQUE FIELD PATHS DISCOVERED ({len(all_field_paths)} total):")
        print("="*100)
        
        for path in sorted(all_field_paths):
            print(f"  {path}")
        
        # Show field availability statistics
        print("\n" + "="*100)
        print("FIELD AVAILABILITY STATISTICS:")
        print("="*100)
        
        field_counts = defaultdict(int)
        for vehicle_data in vehicle_samples:
            for field_path in vehicle_data.keys():
                field_counts[field_path] += 1
        
        total_vehicles = len(vehicle_samples)
        for field_path in sorted(field_counts.keys(), key=lambda x: field_counts[x], reverse=True):
            count = field_counts[field_path]
            percentage = (count / total_vehicles * 100) if total_vehicles > 0 else 0
            print(f"  {field_path:70s}: {count:4d}/{total_vehicles:4d} ({percentage:5.1f}%)")
        
        # Save raw XML of first vehicle for inspection
        print("\n" + "="*100)
        if vehicle_activities:
            raw_xml = ET.tostring(vehicle_activities[0], encoding='unicode')
            with open('bods_sample_raw.xml', 'w') as f:
                f.write(raw_xml)
            print(f"Raw XML (first vehicle) saved to: bods_sample_raw.xml")
        
        # Save sample data to JSON
        with open('bods_sample_data.json', 'w') as f:
            json.dump(vehicle_samples[:10], f, indent=2)
        print(f"Sample data (first 10 vehicles) saved to: bods_sample_data.json")
        
        # Save field summary
        field_summary = {
            'total_vehicles': total_vehicles,
            'unique_fields': len(all_field_paths),
            'all_field_paths': sorted(list(all_field_paths)),
            'field_availability': {
                path: {
                    'count': field_counts[path],
                    'percentage': round((field_counts[path] / total_vehicles * 100), 1)
                }
                for path in all_field_paths
            }
        }
        
        with open('bods_field_summary.json', 'w') as f:
            json.dump(field_summary, f, indent=2)
        print(f"Field summary saved to: bods_field_summary.json")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    fetch_and_display_sample()