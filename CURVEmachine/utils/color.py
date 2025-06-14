from . math import tween

def mix(color1, color2, factor=0.5):
    r = tween(color1[0], color2[0], factor)
    g = tween(color1[1], color2[1], factor)
    b = tween(color1[2], color2[2], factor)

    return (r, g, b)
