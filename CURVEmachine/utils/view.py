from typing import Tuple
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d

def get_view_origin_and_dir(context, coord=None) -> Tuple[Vector, Vector]:
    if not coord:
        coord = Vector((context.region.width / 2, context.region.height / 2))

    view_origin = region_2d_to_origin_3d(context.region, context.region_data, coord)
    view_dir = region_2d_to_vector_3d(context.region, context.region_data, coord)

    return view_origin, view_dir

def get_location_2d(context, co3d, default=(0, 0), debug=False):
    if default == 'OFF_SCREEN':
        default = Vector((-1000, -1000))
    co2d = Vector(round(i) for i in location_3d_to_region_2d(context.region, context.region_data, co3d, default=default))
    if debug:
        print(tuple(co3d), "is", tuple(co2d))

    return co2d
