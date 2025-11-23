import csv

routes = []

with open("../static/trips.txt", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        routes.append(row)

# Example: print first stop
print(routes[0])
