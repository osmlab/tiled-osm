#!/usr/bin/env python

import itertools
from tiled_osm import OSMTiler, GlobalMercator

# Left, Bottom, Right, Top
bbox_limit = (-93.78, 44.53, -92.61, 45.44)

tiler = GlobalMercator()
updater = OSMTiler()

zoom = 17
min_tile = tiler.LatLonToGoogleTile(bbox_limit[3], bbox_limit[0], zoom)
max_tile = tiler.LatLonToGoogleTile(bbox_limit[1], bbox_limit[2], zoom)
print "%0.7f,%0.7f,%0.7f,%0.7f limits to tiles (%d,%d)-(%d,%d)" % (bbox_limit[0], bbox_limit[1], bbox_limit[2], bbox_limit[3], min_tile[0], min_tile[1], max_tile[0], max_tile[1])

for (x, y) in itertools.product(range(min_tile[0], max_tile[0]+1), range(min_tile[1], max_tile[1]+1)):

    url = updater.update_tile(zoom, x, y)
    print "Url is %s" % url
