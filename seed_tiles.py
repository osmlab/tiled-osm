#!/usr/bin/env python

import boto
import boto.s3.connection
import math
import itertools
import tempfile
import urllib2
import os

# Left, Bottom, Right, Top
bbox_limit = (-93.78, 44.53, -92.61, 45.44)

zoom = 17
api = 'http://api.openstreetmap.org/api/0.6/map'
s3 = boto.connect_s3(
    host='objects.dreamhost.com',
    calling_format=boto.s3.connection.OrdinaryCallingFormat(),
)
bucket = s3.create_bucket('osm-data')

class GlobalMercator(object):

    def __init__(self, tileSize=256):
        "Initialize the TMS Global Mercator pyramid"
        self.tileSize = tileSize
        self.initialResolution = 2 * math.pi * 6378137 / self.tileSize
        # 156543.03392804062 for tileSize 256 pixels
        self.originShift = 2 * math.pi * 6378137 / 2.0
        # 20037508.342789244

    def LatLonToMeters(self, lat, lon):
        "Converts given lat/lon in WGS84 Datum to XY in Spherical Mercator EPSG:900913"

        mx = lon * self.originShift / 180.0
        my = math.log(math.tan((90 + lat) * math.pi / 360.0)) / (math.pi / 180.0)

        my = my * self.originShift / 180.0
        return mx, my

    def MetersToLatLon(self, mx, my):
        "Converts XY point from Spherical Mercator EPSG:900913 to lat/lon in WGS84 Datum"

        lon = (mx / self.originShift) * 180.0
        lat = (my / self.originShift) * 180.0

        lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
        return lat, lon

    def PixelsToMeters(self, px, py, zoom):
        "Converts pixel coordinates in given zoom level of pyramid to EPSG:900913"

        res = self.Resolution(zoom)
        mx = px * res - self.originShift
        my = py * res - self.originShift
        return mx, my

    def MetersToPixels(self, mx, my, zoom):
        "Converts EPSG:900913 to pyramid pixel coordinates in given zoom level"

        res = self.Resolution(zoom)
        px = (mx + self.originShift) / res
        py = (my + self.originShift) / res
        return px, py

    def PixelsToTile(self, px, py):
        "Returns a tile covering region in given pixel coordinates"

        tx = int(math.ceil(px / float(self.tileSize)) - 1)
        ty = int(math.ceil(py / float(self.tileSize)) - 1)
        return tx, ty

    def PixelsToRaster(self, px, py, zoom):
        "Move the origin of pixel coordinates to top-left corner"

        mapSize = self.tileSize << zoom
        return px, mapSize - py

    def MetersToTile(self, mx, my, zoom):
        "Returns tile for given mercator coordinates"

        px, py = self.MetersToPixels(mx, my, zoom)
        return self.PixelsToTile(px, py)

    def TileBounds(self, tx, ty, zoom):
        "Returns bounds of the given tile in EPSG:900913 coordinates"

        minx, miny = self.PixelsToMeters(tx*self.tileSize, ty*self.tileSize, zoom)
        maxx, maxy = self.PixelsToMeters((tx+1)*self.tileSize, (ty+1)*self.tileSize, zoom)
        return (minx, miny, maxx, maxy)

    def TileLatLonBounds(self, tx, ty, zoom):
        "Returns bounds of the given tile in latutude/longitude using WGS84 datum"

        bounds = self.TileBounds(tx, ty, zoom)
        minLat, minLon = self.MetersToLatLon(bounds[0], bounds[1])
        maxLat, maxLon = self.MetersToLatLon(bounds[2], bounds[3])

        return (minLat, minLon, maxLat, maxLon)

    def Resolution(self, zoom):
        "Resolution (meters/pixel) for given zoom level (measured at Equator)"

        # return (2 * math.pi * 6378137) / (self.tileSize * 2**zoom)
        return self.initialResolution / (2**zoom)

    def ZoomForPixelSize(self, pixelSize):
        "Maximal scaledown zoom of the pyramid closest to the pixelSize."

        for i in range(30):
            if pixelSize > self.Resolution(i):
                return i - 1 if i != 0 else 0  # We don't want to scale up

    def GoogleTile(self, tx, ty, zoom):
        "Converts TMS tile coordinates to Google Tile coordinates"

        # coordinate origin is moved from bottom-left to top-left corner of the extent
        return tx, (2**zoom - 1) - ty

    def QuadTree(self, tx, ty, zoom):
        "Converts TMS tile coordinates to Microsoft QuadTree"

        quadKey = ""
        ty = (2**zoom - 1) - ty
        for i in range(zoom, 0, -1):
            digit = 0
            mask = 1 << (i-1)
            if (tx & mask) != 0:
                digit += 1
            if (ty & mask) != 0:
                digit += 2
            quadKey += str(digit)

        return quadKey

    def LatLonToGoogleTile(self, lat, lon, zoom):
        (mx, my) = self.LatLonToMeters(lat, lon)
        (px, py) = self.MetersToPixels(mx, my, zoom)
        (tx, ty) = self.PixelsToTile(px, py)
        return self.GoogleTile(tx, ty, zoom)


def downloadChunks(url):
    tmpfile = tempfile.NamedTemporaryFile(delete=False)

    req = urllib2.Request(url)
    req.add_header('User-Agent', 'OSMTiler/1.0 +http://github.com/osmlab/tiled-osm/')
    r = urllib2.urlopen(req)
    tmpfile.write(r.read())
    tmpfile.flush()
    tmpfile.close()

    return tmpfile

tiler = GlobalMercator()

min_tile = tiler.LatLonToGoogleTile(bbox_limit[3], bbox_limit[0], zoom)
max_tile = tiler.LatLonToGoogleTile(bbox_limit[1], bbox_limit[2], zoom)
print "%0.7f,%0.7f,%0.7f,%0.7f limits to tiles (%d,%d)-(%d,%d)" % (bbox_limit[0], bbox_limit[1], bbox_limit[2], bbox_limit[3], min_tile[0], min_tile[1], max_tile[0], max_tile[1])

for (x, y) in itertools.product(range(min_tile[0], max_tile[0]+1), range(min_tile[1], max_tile[1]+1)):
    (tmsx, tmsy) = tiler.GoogleTile(x, y, zoom)
    bbox = tiler.TileLatLonBounds(tmsx, tmsy, zoom)

    key_str = "%d/%d/%d.osm" % (zoom, x, y)
    print "%s = %0.7f,%0.7f,%0.7f,%0.7f" % (key_str, bbox[0], bbox[1], bbox[2], bbox[3])

    url = '%s?bbox=%0.7f,%0.7f,%0.7f,%0.7f' % (api, bbox[1], bbox[0], bbox[3], bbox[2])
    print "Requesting %s" % url
    osm_tile_file = downloadChunks(url)

    k = bucket.new_key(key_str)
    k.set_contents_from_filename(osm_tile_file.name, policy='public-read', headers={'Content-Type': 'text/xml; charset=utf-8'})
    os.unlink(osm_tile_file.name)

    print "Url is %s" % k.generate_url(0, query_auth=False, force_http=True)