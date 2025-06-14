import bpy

import bmesh
from mathutils import Vector

from typing import Union
from uuid import uuid4

from . math import average_locations, create_coords_bbox, flatten_matrix, get_loc_matrix, get_sca_matrix
from . mesh import get_eval_mesh
from . modifier import get_mod_obj
from . system import printd
from . view import ensure_visibility, is_obj_in_scene, restore_visibility, visible_get

def is_valid_object(obj):
    return obj and ' invalid>' not in str(obj)

def is_instance_collection(obj):
    if obj and obj.type == 'EMPTY' and obj.instance_type == 'COLLECTION' and obj.instance_collection:
        return obj.instance_collection

def is_linked_object(obj, recursive=False, debug=False):
    def get_linked_collection_contents(linked, collection, recursive=False):
        if collection.library:
            linked.append(collection)

        for ob in collection.objects:
            if ob.library:
                linked.append(ob)

            if data := ob.data:
                if data.library:
                    linked.append(data)

            elif recursive and (iicol := is_instance_collection(ob)):
                get_linked_collection_contents(linked, iicol, recursive=recursive)

        for col in collection.children:
            if col.library:
                if recursive:
                    get_linked_collection_contents(linked, col, recursive=True)

                else:
                    linked.append(col)

    if debug:
        print("\nchecking if", obj.name, "is linked")

    linked = []

    if obj.library:
        linked.append(obj)

    if data := obj.data:
        if data.library:
            linked.append(data)

    elif icol := is_instance_collection(obj):
        get_linked_collection_contents(linked, icol, recursive=recursive)

    if debug:
        for id in linked:
            print(type(id), id.name, id.library)

    return linked

def get_active_object(context) -> Union[bpy.types.Object, None]:

    objects = getattr(context.view_layer, 'objects', None)

    if objects:
        return getattr(objects, 'active', None)

def get_selected_objects(context) -> list[bpy.types.Object]:
    objects = getattr(context.view_layer, 'objects', None)

    if objects:
        return getattr(objects, 'selected', [])

    return []

def get_view_layer_objects(context) -> list[bpy.types.Object]:
    view_layer = context.view_layer
    objects = getattr(view_layer, 'objects', None)

    if objects:
        return [obj for obj in objects if obj]
    return []

def get_visible_objects(context, local_view=False) -> list[bpy.types.Object]:
    view_layer = context.view_layer
    objects = getattr(view_layer, 'objects', None)

    if objects:
        return [obj for obj in objects if obj and obj.visible_get(view_layer=view_layer)]
    return []

def get_eval_object(context, obj, depsgraph=None):
    if not obj:
        return

    if not depsgraph:
        depsgraph = context.evaluated_depsgraph_get()

    obj_eval = obj.evaluated_get(depsgraph)

    if obj.mode == 'EDIT' and not obj_eval.data.polygons:
        get_eval_mesh(depsgraph, obj, data_block=False)

    return obj.evaluated_get(depsgraph)

def has_bbox(obj):
    return obj.bound_box and not all(Vector(co) == Vector() for co in obj.bound_box)

def get_eval_bbox(obj, advanced=False) -> Union[list, tuple]:
    if icol := is_instance_collection(obj):
        bbox, centers, dimensions = get_instance_collection_bbox(obj, icol)

        if not bbox:
            bbox, centers, dimensions = get_instance_collection_bbox(obj, icol, exclude_wire_objects=False)

        if advanced:
            return bbox, centers, dimensions

        else:
            return bbox

    else:
        bbox = [Vector(obj.bound_box[0]),
                Vector(obj.bound_box[4]),
                Vector(obj.bound_box[7]),
                Vector(obj.bound_box[3]),
                Vector(obj.bound_box[1]),
                Vector(obj.bound_box[5]),
                Vector(obj.bound_box[6]),
                Vector(obj.bound_box[2])]

        if advanced:
            centers = [average_locations([bbox[0], bbox[3], bbox[4], bbox[7]]),
                    average_locations([bbox[1], bbox[2], bbox[5], bbox[6]]),
                    average_locations([bbox[0], bbox[1], bbox[4], bbox[5]]),
                    average_locations([bbox[2], bbox[3], bbox[6], bbox[7]]),
                    average_locations([bbox[0], bbox[1], bbox[2], bbox[3]]),
                    average_locations([bbox[4], bbox[5], bbox[6], bbox[7]])]

            return bbox, centers, obj.dimensions

        else:
            return bbox

def get_instance_collection_bbox(empty, col, exclude_wire_objects=True):
    def get_instance_collection_bbox_recursively(col_coords, obj, col, mx):
        offsetmx = get_loc_matrix(col.instance_offset)
        instance_mx = mx @ obj.matrix_world @ offsetmx.inverted_safe()

        for ob in col.objects:
            if ((exclude_wire_objects and ob.display_type not in ['WIRE', 'BOUNDS']) or not exclude_wire_objects) and has_bbox(ob):
                bbox = [instance_mx @ ob.matrix_world @ co for co in get_eval_bbox(ob)]
                col_coords.extend(bbox)

            elif icol := is_instance_collection(ob):
                get_instance_collection_bbox_recursively(col_coords, ob, icol, instance_mx)

    coords = []

    get_instance_collection_bbox_recursively(coords, empty, col, empty.matrix_world.inverted_safe())

    if coords:
        bbox, centers, dimensions = create_coords_bbox(coords)
        return bbox, centers, get_sca_matrix(empty.matrix_world.decompose()[2]) @ dimensions

    return [], [], Vector()

def remove_obj(obj):
    if not obj.data:
        bpy.data.objects.remove(obj, do_unlink=True)

    elif obj.data.users > 1:
        bpy.data.objects.remove(obj, do_unlink=True)

    elif obj.type == 'MESH':
        bpy.data.meshes.remove(obj.data, do_unlink=True)

    else:
        bpy.data.objects.remove(obj, do_unlink=True)

def duplicate_objects(context, objects, linked=False, debug=False):
    from . group import ensure_internal_index_group_name

    bpy.ops.object.select_all(action='DESELECT')

    originals = {str(uuid4()): (obj, visible_get(obj), obj.use_fake_user) for obj in objects}

    for dup_hash, (ob, vis, fake_user) in originals.items():
        if debug:
            print(ob.name, dup_hash, ", is visible:", vis['visible'], ", meta:", vis['meta'], ", fake user:", fake_user)

        ob.M3.dup_hash = dup_hash
        ensure_visibility(context, ob, select=True)

    bpy.ops.object.duplicate(linked=linked)

    duplicates = {}

    for dup in context.selected_objects:
        orig, vis, fake_user = originals[dup.M3.dup_hash]

        if debug:
            print(orig.name, "-", dup.name, ", was visible:", vis['visible'], ", was in local view:", vis['meta'], ", was fake user:", fake_user)

        duplicates[dup] = {
            'original': orig,
            'vis': vis,
            'fake_user': fake_user,
        }

        for ob in [orig, dup]:
            restore_visibility(ob, vis)

            ob.use_fake_user = fake_user

            ob.M3.dup_hash = ''

        if dup.M3.is_group_empty:
            ensure_internal_index_group_name(dup)

    if debug:
        printd(duplicates)

    return duplicates

def set_obj_origin(obj, mx, bm=None):
    from .. import MACHIN3toolsManager as M3

    omx = obj.matrix_world.copy()

    children = [c for c in obj.children]
    compensate_children(obj, omx, mx)

    deltamx = mx.inverted_safe() @ obj.matrix_world

    obj.matrix_world = mx

    if bm:
        bmesh.ops.transform(bm, verts=bm.verts, matrix=deltamx)
        bmesh.update_edit_mesh(obj.data)
    else:
        obj.data.transform(deltamx)

    if obj.type == 'MESH':
        obj.data.update()

    if M3.get_addon("DECALmachine") and children:

        for c in [c for c in children if is_decal(c) and has_decal_backup(c)]:
            backup = c.DM.decalbackup
            backup.DM.backupmx = flatten_matrix(deltamx @ backup.DM.backupmx)

    if M3.get_addon("MESHmachine") and has_stashes(obj):

        for stash in obj.MM.stashes:

            if getattr(stash, 'version', False) and float('.'.join([v for v in stash.version.split('.')[:2]])) >= 0.7:
                stashdeltamx = stash.obj.MM.stashdeltamx

                if stash.self_stash:
                    if stash.obj.users > 2:
                        print(f"INFO: Duplicating {stash.name}'s stashobj {stash.obj.name} as it's used by multiple stashes")

                        dup = stash.obj.copy()
                        dup.data = stash.obj.data.copy()
                        stash.obj = dup

                stash.obj.MM.stashdeltamx = flatten_matrix(deltamx @ stashdeltamx)
                stash.obj.MM.stashorphanmx = flatten_matrix(mx)

                stash.self_stash = False

            else:
                stashdeltamx = stash.obj.MM.stashtargetmx.inverted_safe() @ stash.obj.MM.stashmx

                stash.obj.MM.stashmx = flatten_matrix(omx @ stashdeltamx)
                stash.obj.MM.stashtargetmx = flatten_matrix(mx)

            stash.obj.data.transform(deltamx)
            stash.obj.matrix_world = mx

def flatten(obj, depsgraph=None):
    if not depsgraph:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    oldmesh = obj.data

    obj.data = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    obj.modifiers.clear()

    bpy.data.meshes.remove(oldmesh, do_unlink=True)

def is_decal(obj):
    return getattr(obj, 'DM', False) and getattr(obj.DM, 'isdecal', False)

def has_decal_backup(obj):
    return getattr(obj, 'DM', False) and getattr(obj.DM, 'decalbackup', None)

def is_decal_backup(obj):
    return getattr(obj, 'DM', False) and getattr(obj.DM, 'isbackup', None)

def has_stashes(obj):
    if getattr(obj, 'MM', False):
       return getattr(obj.MM, 'stashes', None)

def is_stash_object(obj):
    if getattr(obj, 'MM', False):
       return getattr(obj.MM, 'isstashobj', False)

def parent(obj, parentobj):
    if obj.parent:
        unparent(obj)

    obj.parent = parentobj
    obj.matrix_parent_inverse = parentobj.matrix_world.inverted_safe()

def get_parent(obj, recursive=False, debug=False) -> Union[None, bpy.types.Object, list[bpy.types.Object]]:
    if recursive:
        parents = []

        while obj.parent and is_obj_in_scene(obj.parent):
            parents.append(obj.parent)
            obj = obj.parent

        return parents

    else:
        if obj.parent and is_obj_in_scene(obj.parent):
            return obj.parent

def unparent(obj):
    if obj.parent:
        omx = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = omx

def unparent_children(obj):
    children = []

    for c in obj.children:
        unparent(c)
        children.append(c)

    return children

def compensate_children(obj, oldmx, newmx):
    deltamx = newmx.inverted_safe() @ oldmx
    children = [c for c in obj.children]

    for c in children:
        pmx = c.matrix_parent_inverse
        c.matrix_parent_inverse = deltamx @ pmx

def get_object_hierarchy_layers(context, debug=False):
    def add_layer(layers, depth, debug=False):
        if debug:
            print()
            print("layer", depth)

        children = []

        for obj in layers[-1]:
            if debug:
                print("", obj.name)

            if not is_obj_in_scene(obj):
                if debug:
                    print("  > not in scene, ignoring")
                continue

            for obj in obj.children:
                children.append(obj)

        if children:
            depth += 1

            layers.append(children)

            add_layer(layers, depth=depth, debug=debug)

    depth = 0

    top_level_objects = [obj for obj in context.scene.objects if not obj.parent]

    layers = [top_level_objects]

    add_layer(layers, depth, debug=debug)

    return layers

def get_object_tree(obj, obj_tree, depth=0, mod_objects=True, mod_dict=None, mod_type_ignore=[], find_disabled_mods=False, include_hidden=(), force_stash_objects=False, force_decal_backups=False, debug=False):
    kwargs = {
        'mod_objects': mod_objects,
        'mod_dict': mod_dict,
        'mod_type_ignore': mod_type_ignore,
        'find_disabled_mods': find_disabled_mods,
        'include_hidden': include_hidden,
        'force_stash_objects': force_stash_objects,
        'force_decal_backups': force_decal_backups,
        'debug': debug
    }

    def find_stash_objects(obj):
        if force_stash_objects and has_stashes(obj):
            for stash in obj.MM.stashes:
                if stash.obj and stash.obj not in obj_tree:
                    obj_tree.append(stash.obj)

    def find_decal_backups(obj):
        if force_decal_backups and has_decal_backup(obj):
            if obj.DM.decalbackup not in obj_tree:
                obj_tree.append(obj.DM.decalbackup)

    depthstr = " " * depth

    if debug:
        print()
        print("depth:", depth, "tree:", [obj.name for obj in obj_tree])
        print(f"{depthstr}{obj.name}")

    for child in obj.children:
        vis = visible_get(child)

        hidden = vis['meta'].replace('HIDDEN_', '') if vis['meta'] in ['SCENE', 'VIEWLAYER', 'HIDDEN_COLLECTION'] else None

        if debug:
            print(f" {depthstr}child: {child.name}", "hidden meta:", hidden)

        if child not in obj_tree:
            if hidden and hidden not in include_hidden:
                if debug:
                    print(f"  {depthstr}! ignoring child '{child.name}' due to severe hidden state {hidden}")
                continue

            obj_tree.append(child)

            get_object_tree(child, obj_tree, depth=depth + 1, **kwargs)

    if mod_objects:
        for mod in obj.modifiers:
            if mod.type not in mod_type_ignore and (mod.show_viewport or find_disabled_mods):
                if mod_obj := get_mod_obj(mod):
                    vis = visible_get(mod_obj)

                    hidden = vis['meta'].replace('HIDDEN_', '') if vis['meta'] in ['SCENE', 'VIEWLAYER', 'HIDDEN_COLLECTION'] else None

                    if debug:
                        print(f" {depthstr}mod: {mod.name} | obj: {mod_obj.name}", "hidden meta:", hidden)

                    if hidden and hidden not in include_hidden:
                        if debug:
                            print(f"  {depthstr}! ignoring child '{mod_obj.name}' due to severe hidden state {hidden}")
                        continue

                    if mod_dict is not None:
                        if mod_obj in mod_dict:
                            mod_dict[mod_obj].append(mod)
                        else:
                            mod_dict[mod_obj] = [mod]

                    if mod_obj not in obj_tree:
                        obj_tree.append(mod_obj)

                        get_object_tree(mod_obj, obj_tree, depth=depth + 1, **kwargs)

                else:
                    if debug:
                        print(f" {depthstr}mod: {mod.name} | obj: None")

    if force_stash_objects:
        find_stash_objects(obj)

    if force_decal_backups:
        find_decal_backups(obj)

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

def clear_rotation(obj:Union[bpy.types.Object, list[bpy.types.Object]]):
    objects = obj if type(obj) is list else [obj]

    for obj in objects:
        if obj.rotation_mode == 'QUATERNION':
            obj.rotation_quaternion.identity()

        elif obj.rotation_mode == 'AXIS_ANGLE':
            for i in range(4):
                obj.rotation_axis_angle[i] = 0
        else:
            obj.rotation_euler.zero()
