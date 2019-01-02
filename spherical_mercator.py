from math import pi, sin, log, exp, atan, radians, degrees

def _constrained_sine(rad):
    sine_rad = sin(rad)
    return min(max(sine_rad, -0.9999), 0.9999)


class ZoomLevelSpec:

    def __init__(self, zoom_level, globe_pixels):
        self.zoom_level = zoom_level
        self.globe_pixels = globe_pixels
        self.hemisphere_pixels = globe_pixels / 2
        self.pixels_per_lon_degree = globe_pixels / 360.0
        self.pixels_per_lon_radian = globe_pixels / (2.0 * pi)


class SphericalMercator:

    def __init__(self, levels=18, globe_pixels_zoom_0=256):
        self.zoom_level_specs = []
        globe_pixels = globe_pixels_zoom_0
        for zoom_level in range(0, levels):
            self.zoom_level_specs.append(ZoomLevelSpec(zoom_level, globe_pixels))
            globe_pixels *= 2

    def pixel_for_lonlat(self, ll, zoom):
        zoom_spec = self.zoom_level_specs[zoom]
        px = round(zoom_spec.hemisphere_pixels + ll[0] * zoom_spec.pixels_per_lon_degree)
        sine_lat = _constrained_sine(radians(ll[1]))
        py = round(zoom_spec.hemisphere_pixels + 0.5 * log((1 + sine_lat) / (1 - sine_lat)) * -zoom_spec.pixels_per_lon_radian)
        return (px, py)

    def lonlat_for_pixel(self, pixel, zoom):
        zoom_spec = self.zoom_level_specs[zoom]
        lon = (pixel[0] - zoom_spec.hemisphere_pixels) / zoom_spec.pixels_per_lon_degree
        g = (pixel[1] - zoom_spec.hemisphere_pixels) / -zoom_spec.pixels_per_lon_radian
        lat = degrees(2 * atan(exp(g)) - 0.5 * pi)
        return (lon, lat)
