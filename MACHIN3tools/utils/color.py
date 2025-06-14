from . math import tween

def mix(color1, color2, factor=0.5):
    r = tween(color1[0], color2[0], factor)
    g = tween(color1[1], color2[1], factor)
    b = tween(color1[2], color2[2], factor)

    return (r, g, b)

def lighten(color, amount=0.05):
    def remap(value, new_low):
        old_range = (1 - 0)
        new_range = (1 - new_low)
        return (((value - 0) * new_range) / old_range) + new_low

    return tuple(remap(c, amount) for c in color)

def linear_to_srgb(color):
    def to_srgb(c):
        if c <= 0.0031308:
            return 12.92 * c
        else:
            return 1.055 * (c ** (1 / 2.4)) - 0.055

    return tuple(to_srgb(c) for c in color)
