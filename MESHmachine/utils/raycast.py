import bpy
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
import bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree as BVH
from mathutils.geometry import intersect_line_plane
from math import radians
import sys
from . object import flatten
from . registration import get_addon

def cast_bvh_ray_from_mouse(mousepos, candidates=None, flatten_visible=False, exclude_decals=True, debug=False):
    region = bpy.context.region
    region_data = bpy.context.region_data

    origin_3d = region_2d_to_origin_3d(region, region_data, mousepos)
    vector_3d = region_2d_to_vector_3d(region, region_data, mousepos)

    if not candidates:
        candidates = bpy.context.visible_objects

    visible = [(obj, None) for obj in candidates if obj.type == "MESH"]

    if flatten_visible:
        objects = []

        for obj, _ in visible:
            dup = obj.copy()
            dup.data = obj.data.copy()

            bpy.context.collection.objects.link(dup)
            flatten(dup)

            objects.append((dup, obj))

    else:
        objects = visible

    hitobj = None
    hitlocation = None
    hitnormal = None
    hitindex = None
    hitdistance = sys.maxsize

    for obj, src in objects:
        mx = obj.matrix_world
        mxi = mx.inverted_safe()

        bm = bmesh.new()
        bm.from_mesh(obj.data)

        ray_origin = mxi @ origin_3d
        ray_direction = mxi.to_3x3() @ vector_3d

        bvh = BVH.FromBMesh(bm)

        location, normal, index, distance = bvh.ray_cast(ray_origin, ray_direction)

        if distance:
            distance = (mx @ location - origin_3d).length

        bm.free()

        if debug:
            print("candidate:", obj.name, location, normal, index, distance)

        if distance and distance < hitdistance:
            hitobj, hitlocation, hitnormal, hitindex, hitdistance = src if flatten_visible else obj, mx @ location, mx.to_3x3() @ normal, index, distance

    if flatten_visible:
        for obj, src in objects:
            bpy.data.meshes.remove(obj.data, do_unlink=True)

    if debug:
        print("best hit:", hitobj.name if hitobj else None, hitlocation, hitnormal, hitindex, hitdistance if hitobj else None)

    if hitobj:
        return hitobj, hitlocation, hitnormal, hitindex, hitdistance

    return None, None, None, None, None

def cast_obj_ray_from_mouse(mousepos, candidates=None, exclude_decals=True, debug=False):
    region = bpy.context.region
    region_data = bpy.context.region_data

    origin_3d = region_2d_to_origin_3d(region, region_data, mousepos)
    vector_3d = region_2d_to_vector_3d(region, region_data, mousepos)

    if not candidates:
        candidates = bpy.context.visible_objects

    if exclude_decals and get_addon('DECALmachine')[0]:
        objects = [(obj, None) for obj in candidates if obj.type == "MESH" and not obj.DM.isdecal]
    else:
        objects = [(obj, None) for obj in candidates if obj.type == "MESH"]

    hitobj = None
    hitlocation = None
    hitnormal = None
    hitindex = None
    hitdistance = sys.maxsize

    for obj, src in objects:
        mx = obj.matrix_world
        mxi = mx.inverted_safe()

        ray_origin = mxi @ origin_3d
        ray_direction = mxi.to_3x3() @ vector_3d

        success, location, normal, index = obj.ray_cast(origin=ray_origin, direction=ray_direction)
        distance = (mx @ location - origin_3d).length

        if debug:
            print("candidate:", success, obj.name, location, normal, index, distance)

        if success and distance < hitdistance:
            hitobj, hitlocation, hitnormal, hitindex, hitdistance = obj, mx @ location, mx.to_3x3() @ normal, index, distance

    if debug:
        print("best hit:", hitobj.name if hitobj else None, hitlocation, hitnormal, hitindex, hitdistance if hitobj else None)
        print()

    if hitobj:
        return hitobj, hitlocation, hitnormal, hitindex, hitdistance

    return None, None, None, None, None

def cast_obj_ray_from_point(origin, direction, candidates, debug=False):
    hitobj = None
    hitlocation = None
    hitnormal = None
    hitindex = None
    hitdistance = sys.maxsize

    for obj in candidates:
        mx = obj.matrix_world
        mxi = mx.inverted_safe()

        origin_local = mxi @ origin
        direction_local = mxi.to_3x3() @ direction

        success, location, normal, index = obj.ray_cast(origin=origin_local, direction=direction_local)
        distance = (mx @ location - origin).length if success else sys.maxsize

        if debug:
            print("candidate:", success, obj.name, location, normal, index, distance)

        rsuccess, rlocation, rnormal, rindex = obj.ray_cast(origin=origin_local, direction=direction_local * -1)
        rdistance = (mx @ rlocation - origin).length if rsuccess else sys.maxsize

        if debug:
            print(" reverse candidate:", rsuccess, obj.name, rlocation, rnormal, rindex, rdistance)

        if rsuccess and rdistance < distance:
            success = rsuccess
            location = rlocation
            normal = rnormal
            index = rindex
            distance = rdistance

            if debug:
                print("  reverse ray cast found a closer and properly aligned face.")

        if success:
            if distance < hitdistance:
                hitobj, hitlocation, hitnormal, hitindex, hitdistance = obj, mx @ location, mx.to_3x3() @ normal, index, distance

    if debug:
        print("best hit:", hitobj.name if hitobj else None, hitlocation, hitnormal, hitindex, hitdistance if hitobj else None)
        print()

    if hitobj:
        return hitobj, hitlocation, hitnormal, hitindex, hitdistance

    return None, None, None, None, None

def cast_scene_ray_from_mouse(mousepos, depsgraph, exclude=[], exclude_wire=False, unhide=[], debug=False):
    region = bpy.context.region
    region_data = bpy.context.region_data

    view_origin = region_2d_to_origin_3d(region, region_data, mousepos)
    view_dir = region_2d_to_vector_3d(region, region_data, mousepos)

    scene = bpy.context.scene

    for ob in unhide:
        ob.hide_set(False)

    hit, location, normal, index, obj, mx = scene.ray_cast(depsgraph=depsgraph, origin=view_origin, direction=view_dir)

    hidden = []

    if hit:
        if obj in exclude or (exclude_wire and obj.display_type == 'WIRE'):
            ignore = True

            while ignore:
                if debug:
                    print(" Ignoring object", obj.name)

                obj.hide_set(True)
                hidden.append(obj)

                hit, location, normal, index, obj, mx = scene.ray_cast(depsgraph=depsgraph, origin=view_origin, direction=view_dir)

                if hit:
                    ignore = obj in exclude or (exclude_wire and obj.display_type == 'WIRE')
                else:
                    break

    for ob in unhide:
        ob.hide_set(True)

    for ob in hidden:
        ob.hide_set(False)

    if hit:
        if debug:
            print(obj.name, index, location, normal)

        return hit, obj, index, location, normal, mx

    else:
        if debug:
            print(None)

        return None, None, None, None, None, None

def get_grid_intersection(mousepos):
    region = bpy.context.region
    region_data = bpy.context.region_data

    origin_3d = region_2d_to_origin_3d(region, region_data, mousepos)
    vector_3d = region_2d_to_vector_3d(region, region_data, mousepos)

    xdot = round(Vector((1, 0, 0)).dot(vector_3d), 2)
    ydot = round(Vector((0, 1, 0)).dot(vector_3d), 2)
    zdot = round(Vector((0, 0, 1)).dot(vector_3d), 2)

    if abs(zdot * 2) >= max([abs(xdot), abs(ydot)]):
        angle = 0 if zdot <= 0 else 180
        return intersect_line_plane(origin_3d, origin_3d + vector_3d, Vector((0, 0, 0)), Vector((0, 0, 1))), Matrix.Rotation(radians(angle), 4, "X")

    elif abs(ydot) > abs(xdot):
        angle = 90 if ydot >= 0 else -90
        return intersect_line_plane(origin_3d, origin_3d + vector_3d, Vector((0, 0, 0)), Vector((0, 1, 0))), Matrix.Rotation(radians(angle), 4, "X")

    else:
        angle = 90 if xdot <= 0 else -90
        return intersect_line_plane(origin_3d, origin_3d + vector_3d, Vector((0, 0, 0)), Vector((1, 0, 0))), Matrix.Rotation(radians(angle), 4, "Y")
