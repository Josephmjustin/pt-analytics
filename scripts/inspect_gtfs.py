from google.transit import gtfs_realtime_pb2

feed = gtfs_realtime_pb2.FeedMessage()

with open('liverpool_test.pb', 'rb') as f:
    feed.ParseFromString(f.read())

count = 0

for entity in feed.entity[:1]:
    if entity.HasField('vehicle'):
        vehicle = entity.vehicle
        print("Available fields in vehicle:")
        print(vehicle.DESCRIPTOR.fields_by_name.keys())
        print("\n")
        
        # Then print the actual vehicle object
        print("Full vehicle data:")
        print(vehicle)