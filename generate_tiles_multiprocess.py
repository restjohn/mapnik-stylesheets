#!/usr/bin/env python
from math import pi, cos, sin, log, exp, atan
from subprocess import call
import sys
import os
import re
import shutil
import tempfile
import urllib.request
import uuid
import multiprocessing
import spherical_mercator

try:
    import mapnik2 as mapnik
except:
    import mapnik


# Default number of rendering threads to spawn, should be roughly equal to number of CPU cores available
NUM_THREADS = 4


class RenderThread:

    def __init__(self, tile_dir, mapfile, q, printLock, maxZoom):
        self.tile_dir = tile_dir
        self.q = q
        self.mapfile = mapfile
        self.maxZoom = maxZoom
        self.printLock = printLock

    def render_tile(self, tile_uri, x, y, z):
        # Calculate pixel positions of bottom-left & top-right
        p0 = (x * 256, (y + 1) * 256)
        p1 = ((x + 1) * 256, y * 256)

        # Convert to LatLong (EPSG:4326)
        l0 = self.tileproj.lonlat_for_pixel(p0, z)
        l1 = self.tileproj.lonlat_for_pixel(p1, z)

        # Convert to map projection (e.g. mercator co-ords EPSG:900913)
        c0 = self.prj.forward(mapnik.Coord(l0[0], l0[1]))
        c1 = self.prj.forward(mapnik.Coord(l1[0], l1[1]))

        # Bounding box for the tile
        if hasattr(mapnik, 'mapnik_version') and mapnik.mapnik_version() >= 800:
            bbox = mapnik.Box2d(c0.x, c0.y, c1.x, c1.y)
        else:
            bbox = mapnik.Envelope(c0.x, c0.y, c1.x, c1.y)
        render_size = 256
        self.m.resize(render_size, render_size)
        self.m.zoom_to_box(bbox)
        if(self.m.buffer_size < 128):
            self.m.buffer_size = 128

        # Render image with default Agg renderer
        im = mapnik.Image(render_size, render_size)
        mapnik.render(self.m, im)
        im.save(tile_uri, 'png256')

    def loop(self):

        self.m = mapnik.Map(256, 256)
        # Load style XML
        mapnik.load_map(self.m, self.mapfile, True)
        # Obtain <Map> projection
        self.prj = mapnik.Projection(self.m.srs)
        # Projects between tile pixel co-ordinates and LatLong (EPSG:4326)
        self.tileproj = spherical_mercator.SphericalMercator(self.maxZoom + 1)

        while True:
            # Fetch a tile from the queue and render it
            r = self.q.get()
            if (r == None):
                self.q.task_done()
                break
            else:
                (name, tile_uri, x, y, z) = r

            exists = ""
            if os.path.isfile(tile_uri):
                exists = "exists"
            else:
                self.render_tile(tile_uri, x, y, z)
            bytes = os.stat(tile_uri)[6]
            empty = ''
            if bytes == 103:
                empty = " Empty Tile "
            self.printLock.acquire()
            print(name, ":", z, x, y, exists, empty)
            self.printLock.release()
            self.q.task_done()


def render_tiles(bbox, mapfile, tile_dir, minZoom=1, maxZoom=18, name="unknown", num_threads=NUM_THREADS):

    print("render_tiles(", bbox, mapfile, tile_dir, minZoom, maxZoom, name, ")")

    # Launch rendering threads
    queue = multiprocessing.JoinableQueue(32)
    printLock = multiprocessing.Lock()
    renderers = {}
    for i in range(num_threads):
        renderer = RenderThread(tile_dir, mapfile, queue, printLock, maxZoom)
        render_thread = multiprocessing.Process(target=renderer.loop)
        render_thread.start()
        # print("Started render thread %s" % render_thread.getName())
        renderers[i] = render_thread

    if not os.path.isdir(tile_dir):
        os.mkdir(tile_dir)

    gprj = spherical_mercator.SphericalMercator(maxZoom + 1)

    ll0 = (bbox[0], bbox[3])
    ll1 = (bbox[2], bbox[1])

    for z in range(minZoom, maxZoom + 1):
        px0 = gprj.pixel_for_lonlat(ll0, z)
        px1 = gprj.pixel_for_lonlat(ll1, z)

        # check if we have directories in place
        zoom = "%s" % z
        if not os.path.isdir(tile_dir + zoom):
            os.mkdir(tile_dir + zoom)
        for x in range(int(px0[0] / 256.0), int(px1[0] / 256.0) + 1):
            # Validate x co-ordinate
            if (x < 0) or (x >= 2**z):
                continue
            # check if we have directories in place
            str_x = "%s" % x
            if not os.path.isdir(tile_dir + zoom + '/' + str_x):
                os.mkdir(tile_dir + zoom + '/' + str_x)
            for y in range(int(px0[1]/256.0), int(px1[1]/256.0)+1):
                # Validate x co-ordinate
                if (y < 0) or (y >= 2**z):
                    continue
                str_y = "%s" % y
                tile_uri = tile_dir + zoom + '/' + str_x + '/' + str_y + '.png'
                # Submit tile to be rendered into the queue
                t = (name, tile_uri, x, y, z)
                queue.put(t)

    # Signal render threads to exit by sending empty request to queue
    for i in range(num_threads):
        queue.put(None)
    # wait for pending rendering jobs to complete
    queue.join()
    for i in range(num_threads):
        renderers[i].join()


if __name__ == "__main__":

    tiles_name = os.environ["TILES_NAME"]
    tiles_bbox = os.environ["TILES_BBOX"]
    tiles_style_url = os.environ["TILES_MAPNIK_STYLE"]
    tiles_min_zoom = int(os.environ.get("TILES_MIN_ZOOM", "0"))
    tiles_max_zoom = int(os.environ.get("TILES_MAX_ZOOM", "18"))
    tiles_dir = "/tiles/%(tiles_name)s" % locals()

    bbox_parts = re.findall(r"-?\d+(\.\d+", tiles_bbox)
    if bbox_parts.count != 4:
        raise Exception("invalid bbox: %s(bbox)" % tiles_bbox)
    bbox = [(float(bbox_parts[0]), float(bbox_parts[1])), (float(bbox_parts[2]), float(bbox_parts[3]))]
    style_path = "/tmp/tiles-%(name)s-%(suffix)s" % {"name": tiles_name, "suffix": uuid.uuid4()}
    style_file = open(style_path, "w", encoding="utf-8")
    with urllib.request.urlopen(tiles_style_url) as response:
        shutil.copyfileobj(response, style_file)
        style_file.close()

    render_tiles(bbox, style_path, tiles_dir, tiles_min_zoom, tiles_max_zoom)
