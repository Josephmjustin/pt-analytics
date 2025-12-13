"""
Export unique routes with both directions
Key: service_code + direction (so same service code can have inbound AND outbound)
"""

import json
import csv

input_file = "C:/Users/justi/Work/Personal/pt-analytics/static/liverpool_transit_data_enriched.json"
output_file = "C:/Users/justi/Work/Personal/pt-analytics/static/route_analysis.csv"

print("Loading JSON...")
with open(input_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Extracting unique routes...")

routes_dict = {}  # Use dict with composite key: (service_code, direction)

for op_name, op_data in data['operators'].items():
    for route in op_data['routes']:
        service_code = route['service_code']
        direction = route.get('direction', 'unknown')
        
        # Create composite key to keep both directions
        route_key = f"{service_code}|{direction}"
        
        # Skip if we've already seen this exact combination
        if route_key in routes_dict:
            continue
        
        origin_name = None
        destination_name = None
        
        # Get origin and destination stop names
        if route.get('origin'):
            origin_name = data['stops'].get(route['origin'], {}).get('name', route['origin'])
        
        if route.get('destination'):
            destination_name = data['stops'].get(route['destination'], {}).get('name', route['destination'])
        
        routes_dict[route_key] = {
            'operator': op_name,
            'route': route['route_name'],
            'direction': direction,
            'service_code': service_code,
            'origin': origin_name,
            'destination': destination_name,
            'stop_count': len(route['stops'])
        }

routes_list = list(routes_dict.values())

# Sort by route name, then direction
routes_list.sort(key=lambda x: (x['route'], x['direction']))

print(f"Writing {len(routes_list)} unique route-direction combinations to CSV...")

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['operator', 'route', 'direction', 'service_code', 'origin', 'destination', 'stop_count'])
    writer.writeheader()
    writer.writerows(routes_list)

print(f"✓ Written to: {output_file}")
print(f"  Each route can have both inbound and outbound")