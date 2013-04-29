#!/usr/bin/env python

import urllib2
import StringIO
import xml.etree.cElementTree as ElementTree
import datetime
import calendar
import gzip
import time
from tiled_osm import OSMTiler, GlobalMercator


# Parse the diff and write out a simplified version
class OscHandler():
    def __init__(self):
        self.changes = {}
        self.nodes = {}
        self.ways = {}
        self.relations = {}
        self.action = ""
        self.primitive = {}
        self.missingNds = set()

    def startElement(self, name, attributes):
        if name in ('modify', 'delete', 'create'):
            self.action = name
        if name in ('node', 'way', 'relation'):
            self.primitive['id'] = int(attributes['id'])
            self.primitive['version'] = int(attributes['version'])
            self.primitive['changeset'] = int(attributes['changeset'])
            self.primitive['user'] = attributes.get('user')
            self.primitive['timestamp'] = isoToTimestamp(attributes['timestamp'])
            self.primitive['tags'] = {}
            self.primitive['action'] = self.action
        if name == 'node':
            self.primitive['lat'] = float(attributes['lat'])
            self.primitive['lon'] = float(attributes['lon'])
        elif name == 'tag':
            key = attributes['k']
            val = attributes['v']
            self.primitive['tags'][key] = val
        elif name == 'way':
            self.primitive['nodes'] = []
        elif name == 'relation':
            self.primitive['members'] = []
        elif name == 'nd':
            ref = int(attributes['ref'])
            self.primitive['nodes'].append(ref)
            if ref not in self.nodes:
                self.missingNds.add(ref)
        elif name == 'member':
            self.primitive['members'].append({
                'type': attributes['type'],
                'role': attributes['role'],
                'ref': attributes['ref']
            })

    def endElement(self, name):
        if name == 'node':
            self.nodes[self.primitive['id']] = self.primitive
        elif name == 'way':
            self.ways[self.primitive['id']] = self.primitive
        elif name == 'relation':
            self.relations[self.primitive['id']] = self.primitive
        if name in ('node', 'way', 'relation'):
            self.primitive = {}


def isoToTimestamp(isotime):
    t = datetime.datetime.strptime(isotime, "%Y-%m-%dT%H:%M:%SZ")
    return calendar.timegm(t.utctimetuple())


def parseOsm(source, handler):
    for event, elem in ElementTree.iterparse(source, events=('start', 'end')):
        if event == 'start':
            handler.startElement(elem.tag, elem.attrib)
        elif event == 'end':
            handler.endElement(elem.tag)
        elem.clear()


def minutelyUpdateRun(state):
    # Grab the next sequence number and build a URL out of it
    sqnStr = state['sequenceNumber'].zfill(9)
    url = "http://planet.openstreetmap.org/replication/minute/%s/%s/%s.osc.gz" % (sqnStr[0:3], sqnStr[3:6], sqnStr[6:9])

    print "Downloading change file (%s)." % (url)
    content = urllib2.urlopen(url)
    content = StringIO.StringIO(content.read())
    gzipper = gzip.GzipFile(fileobj=content)

    print "Parsing change file."
    handler = OscHandler()
    parseOsm(gzipper, handler)

    return (handler.nodes, handler.ways, handler.relations)


def readState():
    # Read the state.txt
    sf = open('state.txt', 'r')

    state = {}
    for line in sf:
        if line[0] == '#':
            continue
        (k, v) = line.split('=')
        state[k] = v.strip().replace("\\:", ":")

    sf.close()

    return state


def fetchNextState(currentState):
    # Download the next state file
    nextSqn = int(currentState['sequenceNumber']) + 1
    sqnStr = str(nextSqn).zfill(9)
    url = "http://planet.openstreetmap.org/replication/minute/%s/%s/%s.state.txt" % (sqnStr[0:3], sqnStr[3:6], sqnStr[6:9])
    try:
        u = urllib2.urlopen(url)
        statefile = open('state.txt', 'w')
        statefile.write(u.read())
        statefile.close()
    except Exception, e:
        print e
        return False

    return True

if __name__ == "__main__":
    zoom = 17
    mercator = GlobalMercator()
    tiler = OSMTiler()
    while True:
        state = readState()

        start = time.time()
        (nodes, ways, relations) = minutelyUpdateRun(state)

        z17_tiles_to_expire = set()
        for (id, node) in nodes.iteritems():
            (tx, ty) = mercator.LatLonToGoogleTile(node['lat'], node['lon'], 17)
            z17_tiles_to_expire.add((17, tx, ty))

        for (zoom, x, y) in z17_tiles_to_expire:
            url = tiler.update_tile(zoom, x, y)
            print "Url is %s" % url

        elapsed = time.time() - start

        stateTs = datetime.datetime.strptime(state['timestamp'], "%Y-%m-%dT%H:%M:%SZ")
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
