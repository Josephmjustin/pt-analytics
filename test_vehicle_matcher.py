"""
Test vehicle matcher locally
"""

from src.processing.vehicle_matcher import match_vehicle_to_stop
from datetime import datetime

# Test vehicle at Queen Square Stand 5
test_vehicle = {
    'vehicle_id': 'TEST_BUS_14',
    'route_id': '132158',  # Route 14 from your data
    'latitude': 53.4077,  # Queen Sq Stand 5 coordinates
    'longitude': -2.9825,
    'timestamp': datetime.now()
}

print("Testing vehicle matcher...")
print(f"Input: {test_vehicle}")
print()

result = match_vehicle_to_stop(test_vehicle)

print("Result:")
for key, value in result.items():
    print(f"  {key}: {value}")

print()
if result['matched']:
    print(f"✓ SUCCESS: Matched to {result['stop_name']} (Route {result['route_name']})")
    print(f"  Distance: {result['distance_m']}m")
else:
    print(f"✗ FAILED: {result.get('reason', 'unknown')}")
