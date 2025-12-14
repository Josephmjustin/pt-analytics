"""
Test BODS SIRI-VM feed to check available fields
Shows structure of 5 vehicles from SIRI-VM XML format
"""

import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

BODS_API_KEY = os.getenv("BODS_API_KEY")
LIVERPOOL_BBOX = "-3.05,53.35,-2.85,53.48"
SIRI_URL = f"https://data.bus-data.dft.gov.uk/api/v1/datafeed/?api_key={BODS_API_KEY}&boundingBox={LIVERPOOL_BBOX}"

print("Fetching SIRI-VM feed from BODS...")
print("="*80)

try:
    response = requests.get(SIRI_URL, timeout=30)
    response.raise_for_status()
    
    print(f"Response size: {len(response.content)} bytes")
    print(f"Content-Type: {response.headers.get('Content-Type')}\n")
    
    # Parse XML
    root = ET.fromstring(response.content)
    
    # SIRI namespace
    ns = {
        'siri': 'http://www.siri.org.uk/siri',
        'sirivm': 'http://www.siri.org.uk/siri'
    }
    
    # Find all vehicle activities
    vehicles = root.findall('.//siri:VehicleActivity', ns)
    print(f"Total vehicles in feed: {len(vehicles)}\n")
    
    # Show first 5 vehicles with ALL fields
    for i, vehicle_activity in enumerate(vehicles[:5], 1):
        print(f"VEHICLE {i}")
        print("-"*80)
        
        # Recorded at time
        recorded_at = vehicle_activity.find('.//siri:RecordedAtTime', ns)
        if recorded_at is not None:
            print(f"Recorded At: {recorded_at.text}")
        
        # Vehicle monitoring reference (typically the entity ID)
        item_id = vehicle_activity.find('.//siri:ItemIdentifier', ns)
        if item_id is not None:
            print(f"Item ID: {item_id.text}")
        
        # Valid until time
        valid_until = vehicle_activity.find('.//siri:ValidUntilTime', ns)
        if valid_until is not None:
            print(f"Valid Until: {valid_until.text}")
        
        # Monitored vehicle journey
        mvj = vehicle_activity.find('.//siri:MonitoredVehicleJourney', ns)
        
        if mvj is not None:
            print("\nMonitored Vehicle Journey:")
            
            # Line ref (route number)
            line_ref = mvj.find('siri:LineRef', ns)
            if line_ref is not None:
                print(f"  Line Ref: {line_ref.text}")
            
            # Direction ref - THIS IS WHAT WE'RE LOOKING FOR
            direction_ref = mvj.find('siri:DirectionRef', ns)
            if direction_ref is not None:
                print(f"  ✓ Direction Ref: {direction_ref.text}")
            else:
                print(f"  ✗ Direction Ref: NOT PROVIDED")
            
            # Published line name
            published_line = mvj.find('siri:PublishedLineName', ns)
            if published_line is not None:
                print(f"  Published Line Name: {published_line.text}")
            
            # Operator ref
            operator_ref = mvj.find('siri:OperatorRef', ns)
            if operator_ref is not None:
                print(f"  Operator Ref: {operator_ref.text}")
            
            # Origin name
            origin_name = mvj.find('siri:OriginName', ns)
            if origin_name is not None:
                print(f"  Origin Name: {origin_name.text}")
            
            # Destination name
            destination_name = mvj.find('siri:DestinationName', ns)
            if destination_name is not None:
                print(f"  Destination Name: {destination_name.text}")
            
            # Origin aimed departure time
            origin_aimed = mvj.find('siri:OriginAimedDepartureTime', ns)
            if origin_aimed is not None:
                print(f"  Origin Aimed Departure: {origin_aimed.text}")
            
            # Vehicle location
            vehicle_location = mvj.find('siri:VehicleLocation', ns)
            if vehicle_location is not None:
                longitude = vehicle_location.find('siri:Longitude', ns)
                latitude = vehicle_location.find('siri:Latitude', ns)
                if longitude is not None and latitude is not None:
                    print(f"  Location: {latitude.text}, {longitude.text}")
            
            # Bearing
            bearing = mvj.find('siri:Bearing', ns)
            if bearing is not None:
                print(f"  Bearing: {bearing.text}°")
            
            # Block ref
            block_ref = mvj.find('siri:BlockRef', ns)
            if block_ref is not None:
                print(f"  Block Ref: {block_ref.text}")
            
            # Vehicle ref
            vehicle_ref = mvj.find('siri:VehicleRef', ns)
            if vehicle_ref is not None:
                print(f"  Vehicle Ref: {vehicle_ref.text}")
            
            # Journey ref (trip ID)
            journey_ref = mvj.find('siri:FramedVehicleJourneyRef/siri:DatedVehicleJourneyRef', ns)
            if journey_ref is not None:
                print(f"  Journey Ref: {journey_ref.text}")
            
            # Monitored (is being tracked)
            monitored = mvj.find('siri:Monitored', ns)
            if monitored is not None:
                print(f"  Monitored: {monitored.text}")
            
            # In congestion
            in_congestion = mvj.find('siri:InCongestion', ns)
            if in_congestion is not None:
                print(f"  In Congestion: {in_congestion.text}")
            
            # Occupancy
            occupancy = mvj.find('siri:Occupancy', ns)
            if occupancy is not None:
                print(f"  Occupancy: {occupancy.text}")
        
        print("\n" + "="*80 + "\n")
    
    # Summary
    print("SUMMARY")
    print("="*80)
    
    # Count how many have DirectionRef
    direction_count = 0
    for vehicle in vehicles:
        direction_ref = vehicle.find('.//siri:DirectionRef', ns)
        if direction_ref is not None:
            direction_count += 1
    
    print(f"Total vehicles: {len(vehicles)}")
    print(f"Vehicles with DirectionRef: {direction_count}")
    print(f"Coverage: {100*direction_count/len(vehicles):.1f}%" if len(vehicles) > 0 else "N/A")
    
    if direction_count > 0:
        print("\n✓ SIRI-VM provides DirectionRef!")
    else:
        print("\n✗ SIRI-VM does NOT provide DirectionRef")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()