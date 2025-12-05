import json

with open("locations.json") as f:
  names = json.load(f)

objects = []
for idx, name in enumerate(names, start=1):
  objects.append({
    "model": "archive.location",
    "pk": idx,
    "fields": {
      "name": name,
      "slug": name.lower().replace(" ", "-"),
      "coord_lat": None,
      "coord_lon": None,
      "parent": None,
      "description": "",
      "date_created": "2024-06-01T00:00:00Z",
      "date_modified": "2024-06-01T00:00:00Z",
      "user": 1
    }
  })

with open("archive/fixtures/locations_fixture.json", "w") as f:
  json.dump(objects, f, indent=2)