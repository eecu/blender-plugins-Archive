from typing import Union
import bpy
from math import radians, degrees
from . modifier import add_auto_smooth, get_auto_smooth, get_mod_input, get_mod_obj, remove_mod, set_mod_input

def parent(obj, parentobj):
    if obj.parent:
        unparent(obj)

    obj.parent = parentobj
    obj.matrix_parent_inverse = parentobj.matrix_world.inverted_safe()

def unparent(obj):
    if obj.parent:
        omx = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = omx

def get_object_tree(obj, obj_tree, mod_objects=True, depth=0, debug=False):
    depthstr = " " * depth

    if debug:
        print(f"\n{depthstr}{obj.name}")

    for child in obj.children:
        if debug:
            print(f" {depthstr}child: {child.name}")

        if child not in obj_tree:
            obj_tree.append(child)

            get_object_tree(child, obj_tree, mod_objects=mod_objects, depth=depth + 1, debug=debug)

    if mod_objects:
        for mod in obj.modifiers:
            mod_obj = get_mod_obj(mod)

            if debug:
                print(f" {depthstr}mod: {mod.name} | obj: {mod_obj.name if mod_obj else mod_obj}")

            if mod_obj:
                if mod_obj not in obj_tree:
                    obj_tree.append(mod_obj)

                    get_object_tree(mod_obj, obj_tree, mod_objects=mod_objects, depth=depth + 1, debug=debug)

def is_auto_smooth(obj):
    if bpy.app.version >= (4, 1, 0):
        return bool(get_auto_smooth(obj))

    else:
        return obj.type == 'MESH' and obj.data.use_auto_smooth

def enable_auto_smooth(obj, angle=20):
    if bpy.app.version >= (4, 1, 0):
        mod = add_auto_smooth(obj, angle=angle)
        return mod

    else:
        obj.data.use_auto_smooth = True
        obj.data.auto_smooth_angle = radians(20)

def disable_auto_smooth(obj):
    if bpy.app.version >= (4, 1, 0):
        mod = get_auto_smooth(obj)

        if mod:
            remove_mod(mod)

    else:
        obj.data.use_auto_smooth = False

def set_auto_smooth_angle(obj, angle=20):
    if bpy.app.version >= (4, 1, 0):
        mod = get_auto_smooth(obj)

        if mod and mod.node_group:
            set_mod_input(mod, 'Angle', radians(angle))
            mod.id_data.update_tag()

    else:
        if obj.type == 'MESH' and obj.data.use_auto_smooth:
            obj.data.auto_smooth_angle = radians(angle)

def get_auto_smooth_angle(obj):
    if bpy.app.version >= (4, 1, 0):
        mod = get_auto_smooth(obj)

        if mod and mod.node_group:
            return int(degrees(get_mod_input(mod, 'Angle')))

    else:
        if obj.type == 'MESH' and obj.data.use_auto_smooth:
            return int(degrees(obj.data.auto_smooth_angle))

def flatten(obj, depsgraph=None, preserve_data_layers=False):
    if not depsgraph:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    oldmesh = obj.data

    if preserve_data_layers:
        obj.data = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph)
    else:
        obj.data = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    obj.modifiers.clear()

    bpy.data.meshes.remove(oldmesh, do_unlink=True)

def add_facemap(obj, name="", ids=[]):
    fmap = obj.face_maps.new(name=name)

    if ids:
        fmap.add(ids)

    return fmap

def update_local_view(space_data, states):
    if space_data.local_view:
        for obj, local in states:
            obj.local_view_set(space_data, local)

def hide_render(objects, state):
    if isinstance(objects, bpy.types.Object):
        objects = [objects]

    if isinstance(objects, list):
        for obj in objects:
            obj.hide_render = state

            obj.visible_camera = not state
            obj.visible_diffuse = not state
            obj.visible_glossy = not state
            obj.visible_transmission = not state
            obj.visible_volume_scatter = not state
            obj.visible_shadow = not state

def get_active_object(context) -> Union[bpy.types.Object, None]:
    objects = getattr(context.view_layer, 'objects', None)

    if objects:
        return getattr(objects, 'active', None)

def get_selected_objects(context) -> list[bpy.types.Object]:
    objects = getattr(context.view_layer, 'objects', None)

    if objects:
        return getattr(objects, 'selected', [])

    return []

def get_visible_objects(context, local_view=False) -> list[bpy.types.Object]:
    view_layer = context.view_layer
    objects = getattr(view_layer, 'objects', [])

    return [obj for obj in objects if obj.visible_get(view_layer=view_layer)]
