import bpy
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
import bmesh
from mathutils.bvhtree import BVHTree as BVH
import sys

from . asset import get_instance_collection_objects_recursively
from . object import is_instance_collection

def cast_bvh_ray_from_mouse(mousepos, candidates=None, bmeshes={}, bvhs={}, objtypes=['MESH'], region=None, debug=False):
    if region:
        region_data = region.data

    else:
        region = bpy.context.region
        region_data = bpy.context.region_data

    origin_3d = region_2d_to_origin_3d(region, region_data, mousepos)
    vector_3d = region_2d_to_vector_3d(region, region_data, mousepos)

    objects = [(obj, None) for obj in candidates if obj.type in objtypes]

    hitobj = None
    hitlocation = None
    hitnormal = None
    hitindex = None
    hitdistance = sys.maxsize

    cache = {'bmesh': {},
             'bvh': {}}

    for obj, src in objects:
        mx = obj.matrix_world
        mxi = mx.inverted_safe()

        ray_origin = mxi @ origin_3d
        ray_direction = mxi.to_3x3() @ vector_3d

        if obj.name in bmeshes:
            bm = bmeshes[obj.name]
        else:
            bm = bmesh.new()

            bm.from_mesh(obj.to_mesh())
            cache['bmesh'][obj.name] = bm

        if obj.name in bvhs:
            bvh = bvhs[obj.name]
        else:
            bvh = BVH.FromBMesh(bm)
            cache['bvh'][obj.name] = bvh

        location, normal, index, distance = bvh.ray_cast(ray_origin, ray_direction)

        if distance:
            distance = (mx @ location - origin_3d).length

        if debug:
            print("candidate:", obj.name, location, normal, index, distance)

        if distance and distance < hitdistance:
            hitobj, hitlocation, hitnormal, hitindex, hitdistance = obj, mx @ location, mx.to_3x3() @ normal, index, distance

    if debug:
        print("best hit:", hitobj.name if hitobj else None, hitlocation, hitnormal, hitindex, hitdistance if hitobj else None)
        print()

    if hitobj:
        return hitobj, hitlocation, hitnormal, hitindex, hitdistance, cache

    return None, None, None, None, None, cache

def cast_bvh_ray_from_point(origin, direction, cache, candidates=None, debug=False):
    objects = [obj for obj in candidates if obj.type == "MESH"]

    hitobj = None
    hitlocation = None
    hitnormal = None
    hitindex = None
    hitdistance = sys.maxsize

    if not cache:
        cache = {'bmesh': {},
                 'bvh': {}}

    for obj in objects:
        if obj.name in cache['bmesh']:
            bm = cache['bmesh'][obj.name]

            if obj.name not in cache['bmesh']:
                cache['bmesh'][obj.name] = bm

        else:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            cache['bmesh'][obj.name] = bm

        if obj.name in cache['bvh']:
            bvh = cache['bvh'][obj.name]

            if obj.name not in cache['bvh']:
                cache['bvh'][obj.name] = bvh
        else:
            bvh = BVH.FromBMesh(bm)
            cache['bvh'][obj.name] = bvh

        location, normal, index, distance = bvh.ray_cast(origin, direction)

        if distance:
            distance = (location - origin).length

        if debug:
            print("candidate:", obj.name, location, normal, index, distance)

        if distance and distance < hitdistance:
            hitobj, hitlocation, hitnormal, hitindex, hitdistance = obj, location, normal, index, distance

    if debug:
        print("best hit:", hitobj.name if hitobj else None, hitlocation, hitnormal, hitindex, hitdistance if hitobj else None)
        print()

    if hitobj:
        return hitobj, hitlocation, hitnormal, hitindex, hitdistance, cache

    return None, None, None, None, None, cache

def cast_obj_ray_from_mouse(mousepos, depsgraph=None, candidates=None, objtypes=['MESH'], region=None, debug=False):
    if region:
        region_data = region.data
    else:
        region = bpy.context.region
        region_data = bpy.context.region_data

    origin_3d = region_2d_to_origin_3d(region, region_data, mousepos)
    vector_3d = region_2d_to_vector_3d(region, region_data, mousepos)

    if not candidates:
        candidates = bpy.context.visible_objects

    objects = []

    for obj in candidates:
        if obj.type in objtypes:

            if obj.type == 'CURVE':
                if obj.data.extrude or obj.data.bevel_depth:
                    objects.append(obj)

            else:
                objects.append(obj)

    hitobj = None
    hitobj_eval = None
    hitlocation = None
    hitnormal = None
    hitindex = None
    hitdistance = sys.maxsize

    for obj in objects:
        mx = obj.matrix_world
        mxi = mx.inverted_safe()

        ray_origin = mxi @ origin_3d
        ray_direction = mxi.to_3x3() @ vector_3d

        success, location, normal, index = obj.ray_cast(origin=ray_origin, direction=ray_direction, depsgraph=depsgraph)
        distance = (mx @ location - origin_3d).length

        if debug:
            print("candidate:", success, obj.name, location, normal, index, distance)

        if success and distance < hitdistance:
            hitobj, hitobj_eval, hitlocation, hitnormal, hitindex, hitdistance = obj, obj.evaluated_get(depsgraph) if depsgraph else None, mx @ location, mx.to_3x3() @ normal, index, distance

    if debug:
        print("best hit:", hitobj.name if hitobj else None, hitlocation, hitnormal, hitindex, hitdistance if hitobj else None)
        print()

    if hitobj:
        return hitobj, hitobj_eval, hitlocation, hitnormal, hitindex, hitdistance

    return None, None, None, None, None, None

def get_closest(origin, candidates=[], depsgraph=None, debug=False):
    nearestobj = None
    nearestlocation = None
    nearestnormal = None
    nearestindex = None
    nearestdistance = sys.maxsize

    if not candidates:
        candidates = bpy.context.visible_objects

    objects = [obj for obj in candidates if obj.type == 'MESH']

    for obj in objects:
        mx = obj.matrix_world

        origin_local = mx.inverted_safe() @ origin

        obj_eval = obj.evaluated_get(depsgraph)

        if obj_eval.data.polygons:
            success, location, normal, index = obj.closest_point_on_mesh(origin_local, depsgraph=depsgraph)

            distance = (mx @ location - origin).length if success else sys.maxsize

            if debug:
                print("candidate:", success, obj, location, normal, index, distance)

            if distance is not None and distance < nearestdistance:
                nearestobj, nearestlocation, nearestnormal, nearestindex, nearestdistance = obj, mx @ location, mx.to_3x3() @ normal, index, distance

        elif debug:
                print("candidate:", "%s's evaluated mesh contains no faces" % (obj))

    if debug:
        print("best hit:", nearestobj, nearestlocation, nearestnormal, nearestindex, nearestdistance)

    if nearestobj:
        return nearestobj, nearestobj.evaluated_get(depsgraph), nearestlocation, nearestnormal, nearestindex, nearestdistance

    return None, None, None, None, None, None

def get_hittable_scene_cast_objects(context, exclude=[], exclude_wire=False, force_exclude_wire=False, debug=False):
    debug = False

    scene = context.scene

    hittable_objects = set(obj for obj in context.visible_objects if obj.display_type != 'BOUNDS' and not (obj.type == 'EMPTY' and not obj.instance_collection))

    scene_objects = [obj for obj in scene.objects if obj.name in context.view_layer.objects]
    instance_collection_map = {}

    for obj in scene_objects:
        if icol := is_instance_collection(obj):

            icol_objects = set()
            get_instance_collection_objects_recursively(icol, icol_objects)

            for o in icol_objects:

                if obj.display_type != 'BOUNDS':
                    if o in instance_collection_map:
                        instance_collection_map[o].add(obj)
                    else:
                        instance_collection_map[o] = {obj}

                    if obj in hittable_objects:
                        hittable_objects.add(o)

    exclude_objects = set(obj for obj in exclude if obj in hittable_objects)
    hittable_objects.difference_update(exclude_objects)

    force_excluded_wire_objects = set()

    if exclude_wire:
        wire_objects = set(obj for obj in hittable_objects if obj.display_type in ['WIRE', ''] and not obj.select_get())
        hittable_objects.difference_update(wire_objects)

    if force_exclude_wire:

        if debug:
            print()
            print("force excluding wire objects")

        for obj in set(obj for obj in context.scene.objects if obj.display_type in ['WIRE', 'BOUNDS', ''] and not obj.select_get() and not obj.hide_viewport):
            obj.hide_viewport = True
            force_excluded_wire_objects.add(obj)

            if debug:
                print("", obj.name)

    if debug:
        print()
        print("hittable objects:")

        for obj in hittable_objects:
            print("", obj.name)

    return hittable_objects, instance_collection_map, force_excluded_wire_objects

def cast_scene_ray_from_mouse(mousepos, depsgraph, exclude=[], exclude_wire=False, force_exclude_wire=False, unhide=[], cache={}, region=None, debug=False):
    if region:
        region_data = region.data
    else:
        region = bpy.context.region
        region_data = bpy.context.region_data

    origin = region_2d_to_origin_3d(region, region_data, mousepos)
    direction = region_2d_to_vector_3d(region, region_data, mousepos)

    return cast_scene_ray(origin, direction, depsgraph, exclude=exclude, exclude_wire=exclude_wire, force_exclude_wire=force_exclude_wire, unhide=unhide, cache=cache, debug=debug)

def cast_scene_ray(origin, direction, depsgraph, exclude=[], exclude_wire=False, force_exclude_wire=False, unhide=[], cache={}, debug=False):
    debug = False

    if debug:
        print()
        print("-" * 20)

    context = bpy.context
    scene = context.scene

    for ob in unhide:
        ob.hide_set(False)

        ob.select_set(True)

    if cache:
        if debug:
            print()
            print("fetching hittable from cache")

        hittable_objects = cache['hittable_objects']
        instance_collection_map = cache['instance_collection_map']
        force_excluded_wire_objects = cache['force_excluded_wire_objects']

    else:
        if debug:
            print()
            print("initiating hittable cache")

        hittable_objects, instance_collection_map, force_excluded_wire_objects = get_hittable_scene_cast_objects(context, exclude=exclude, exclude_wire=exclude_wire, force_exclude_wire=force_exclude_wire, debug=debug)

        cache['hittable_objects'] = hittable_objects
        cache['instance_collection_map'] = instance_collection_map
        cache['force_excluded_wire_objects'] = force_excluded_wire_objects

    if debug:
        print()
        print("cache count")
        print("hittable objects: ", len(hittable_objects))
        print("instance collection map: ", len(instance_collection_map))

    hit, location, normal, index, obj, mx = scene.ray_cast(depsgraph=depsgraph, origin=origin, direction=direction)

    undesired = []

    if hit:
        if debug:
            print()
            print("first hit", obj.name)
            print(" is hittable:", obj in hittable_objects)
            print(" is on viewlayer:", obj.name in context.view_layer.objects)

        safety = 0

        if obj not in hittable_objects:
            ignore = True

            while ignore:
                safety += 1

                undesired.append((obj, obj.select_get(), obj.hide_get(), obj.hide_viewport))

                if obj.name in context.view_layer.objects:
                    if not obj.hide_get():
                        obj.hide_set(True)

                        if debug:
                            print(" Ignoring object", obj.name, "(hide_set())")

                if not obj.hide_viewport:
                    obj.hide_viewport = True

                    depsgraph.update()

                    if debug:
                        print(" Ignoring object", obj.name, "(hide_viewport)")

                if False:

                    if obj.name in context.view_layer.objects:
                        if debug:
                            print(" Ignoring object", obj.name)

                        undesired.append((obj, obj.select_get(), obj.hide_get(), obj.hide_viewport))
                        obj.hide_set(True)

                        if obj in instance_collection_map:
                            if not obj.hide_viewport:
                                obj.hide_viewport = True

                                depsgraph.update()

                    elif obj in instance_collection_map:
                        for empty in instance_collection_map[obj]:
                            if debug:
                                print(" Ignoring object", obj.name, f"(in {empty.name}'s instance collection)")

                            undesired.append((empty, empty.select_get(), obj.hide_get(), obj.hide_viewport))
                            empty.hide_set(True)

                    else:
                        print(f"WARNING: undesired hit object {obj.name} is not on the view layer, and does not belong to an instance collection! This should never happen.")
                        break

                hit, location, normal, index, obj, mx = scene.ray_cast(depsgraph=depsgraph, origin=origin, direction=direction)

                if hit:
                    if debug:
                        print()
                        print("re-cast hit", obj.name)
                        print(" is hittable:", obj in hittable_objects)
                        print(" is on viewlayer:", obj.name in context.view_layer.objects)

                    ignore = obj not in hittable_objects
                else:
                    break

                if safety > 20:
                    print("WARNING: HyperCursor is breaking out of potential infinite loop, this should never happen!")
                    break

    for ob in unhide:
        ob.hide_set(True)

    for ob, was_selected, was_hidden, was_hidden_viewport in undesired:
        if not was_hidden:
            ob.hide_set(False)

        if not was_hidden_viewport:
            ob.hide_viewport = False

        if was_selected:
            ob.select_set(True)

    if hit:
        if debug:
            print(obj.name, index, location, normal)

        return hit, obj, index, location, normal, mx

    else:
        if debug:
            print(None)

        return None, None, None, None, None, None
