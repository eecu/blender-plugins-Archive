from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_plane
from math import log10, floor, degrees, pi
import numpy as np

def dynamic_format(value, decimal_offset=0):
    if round(value, 6) == 0:
        return '0'

    l10 = log10(abs(value))
    f = floor(abs(l10))

    if l10 < 0:
        precision = f + 1 + decimal_offset

    else:
        precision = decimal_offset
    return f"{'-' if value < 0 else ''}{abs(value):.{precision}f}"

def remap(value, srcMin, srcMax, resMin, resMax):
    srcRange = srcMax - srcMin

    if srcRange == 0:
        return resMin
    else:
        resRange = resMax - resMin
        return (((value - srcMin) * resRange) / srcRange) + resMin

def tween(a, b, tw):
    return a * (1 - tw) + b * tw

def average_locations(locationslist, size=3):
    avg = Vector.Fill(size)

    for n in locationslist:
        avg += n

    return avg / len(locationslist)

def get_world_space_normal(normal, mx):
    return (mx.inverted_safe().transposed().to_3x3() @ normal).normalized()

def find_outliers(data, lowp=25, highp=75, multiplier=1.5, bounds=False):
    q1 = np.percentile(data, lowp)
    q3 = np.percentile(data, highp)
    
    iqr = q3 - q1
    
    lower_bound = q1 - (multiplier * iqr)
    upper_bound = q3 + (multiplier * iqr)

    if bounds:
        return lower_bound, upper_bound

    else:
        outliers = [x for x in data if x < lower_bound or x > upper_bound]
        return outliers
