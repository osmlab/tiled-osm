tiled-osm
=========

Scripts and tools to create and update a tiled, full-fidelity OSM data layer.

seed_tiles.py
-------------

Use seed_tiles.py to seed an S3 bucket with tiles of OSM data. This is intended
to create a complete, planetwide set of data that will subsequently get updated
from minutely diffs with the `update_tiles.py` script.

update_tiles.py
---------------

`update_tiles.py` will use minutely diffs to re-fetch tiles based on changes from
OpenStreetMap.