#!/usr/bin/env python

import urllib2
import StringIO
import xml.etree.cElementTree as ElementTree
import datetime
import calendar
import gzip
import time
import boto
import boto.s3.connection
from tiled_osm import OSMTiler, GlobalMercator

ZOOM = 16

def parseOsm(source):
    tiles_to_expire = set()

    for event, elem in ElementTree.iterparse(source, events=('start', 'end')):
        if event == 'start':
            if elem.tag in ('nd', 'node'):
                if 'lat' in elem.attrib and 'lon' in elem.attrib:
                    (tx, ty) = mercator.LatLonToGoogleTile(float(elem.attrib['lat']), float(elem.attrib['lon']), ZOOM)
                    tiles_to_expire.add((ZOOM, tx, ty))
        elem.clear()

    return tiles_to_expire


def minutelyUpdateRun(state):
    # Grab the next sequence number and build a URL out of it
    sqnStr = state['sequenceNumber'].zfill(9)
    url = "http://overpass-api.de/augmented_diffs/%s/%s/%s.osc.gz" % (sqnStr[0:3], sqnStr[3:6], sqnStr[6:9])

    print "Downloading change file (%s)." % (url)
    content = urllib2.urlopen(url)
    content = StringIO.StringIO(content.read())
    gzipper = gzip.GzipFile(fileobj=content)

    print "Parsing change file."
    return parseOsm(gzipper)


def readState(state_file):
    state = {}

    for line in state_file:
        if line[0] == '#':
            continue
        (k, v) = line.split('=')
        state[k] = v.strip().replace("\\:", ":")

    return state


def fetchNextState(currentState):
    # Download the next state file
    nextSqn = int(currentState['sequenceNumber']) + 1
    sqnStr = str(nextSqn).zfill(9)
    url = "http://overpass-api.de/augmented_diffs/%s/%s/%s.state.txt" % (sqnStr[0:3], sqnStr[3:6], sqnStr[6:9])
    try:
        u = urllib2.urlopen(url)
        statefile = readState(u)
        statefile['sequenceNumber'] = nextSqn

        sf_out = open('state.txt', 'w')
        for (k, v) in statefile.iteritems():
            sf_out.write("%s=%s\n" % (k, v))
        sf_out.close()
    except Exception, e:
        print e
        return False

    return True

if __name__ == "__main__":
    mercator = GlobalMercator()
    tiler = OSMTiler()
    while True:
        state = readState(open('state.txt', 'r'))

        start = time.time()
        tiles = minutelyUpdateRun(state)
        tiles = sorted(tiles, key=lambda x: x[0]+x[1]+x[2])

        elapsed = time.time() - start
        print "Found %s tiles to expire in %2.1f seconds." % (len(tiles), elapsed)

        result = tiler.delete_tiles(tiles)
        elapsed = time.time() - start
        print "Busted %s/%s tiles in %2.1f seconds." % (len(result.deleted), (len(result.errors)+len(result.deleted)), elapsed)

        stateTs = datetime.datetime.strptime(state['osm_base'], "%Y-%m-%dT%H:%M:%SZ")
        nextTs = stateTs + datetime.timedelta(minutes=1)

        if datetime.datetime.utcnow() < nextTs:
            timeToSleep = (nextTs - datetime.datetime.utcnow()).seconds + 13.0
        else:
            timeToSleep = 0.0
        print "Waiting %2.1f seconds for the next state.txt." % (timeToSleep)
        time.sleep(timeToSleep)

        result = fetchNextState(state)

        if not result:
            print "Couldn't continue. Sleeping %2.1f more seconds." % (15.0)
            time.sleep(15.0)
