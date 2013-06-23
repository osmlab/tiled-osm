#!/usr/bin/env python

import itertools
from tiled_osm import OSMTiler, GlobalMercator

# Left, Bottom, Right, Top
bbox_limit = (-93.5893, 45.1774, -93.5236, 45.218)

tiler = GlobalMercator()
updater = OSMTiler(api_root='http://www.overpass-api.de/api/xapi?map', bucket_name='tiled-osm')

zoom = 17
min_tile = tiler.LatLonToGoogleTile(bbox_limit[3], bbox_limit[0], zoom)
max_tile = tiler.LatLonToGoogleTile(bbox_limit[1], bbox_limit[2], zoom)
total_tiles = (max_tile[0]-min_tile[0]) * (max_tile[1]-min_tile[1])
print "%0.7f,%0.7f,%0.7f,%0.7f limits to %s tiles (%d,%d)-(%d,%d)" % (bbox_limit[0], bbox_limit[1],
                                                                      bbox_limit[2], bbox_limit[3],
                                                                      total_tiles,
                                                                      min_tile[0], min_tile[1],
                                                                      max_tile[0], max_tile[1])
tiles_complete = 0

for (x, y) in itertools.product(range(min_tile[0], max_tile[0]+1), range(min_tile[1], max_tile[1]+1)):

    url = updater.update_tile(zoom, x, y)
    tiles_complete += 1
    print "(%s of %s) %s" % (tiles_complete, total_tiles, url)
