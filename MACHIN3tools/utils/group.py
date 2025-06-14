from typing import Union
import bpy

from mathutils import Vector, Quaternion, Matrix

import re
from math import degrees
from uuid import uuid4

from . math import average_locations, get_loc_matrix, get_rot_matrix
from . mesh import get_coords, get_eval_mesh
from . view import is_obj_on_viewlayer

from . import object as o
from . import registration as r

def group(context, sel, location='AVERAGE', rotation='WORLD'):
    col = get_group_collection(context, sel)

    empty = bpy.data.objects.new(name=get_group_default_name(), object_data=None)
    empty.M3.is_group_empty = True
    empty.matrix_world = get_group_matrix(context, sel, location, rotation)
    col.objects.link(empty)

    context.view_layer.objects.active = empty
    empty.select_set(True)
    empty.show_in_front = True
    empty.empty_display_type = 'CUBE'

    empty.show_name = True
    empty.empty_display_size = r.get_prefs().group_tools_size

    empty.M3.group_size = r.get_prefs().group_tools_size

    for obj in sel:
        o.parent(obj, empty)
        obj.M3.is_group_object = True

    set_group_pose(empty, name='Inception')

    return empty

def ungroup(empty, depsgraph=None):
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    locations = []
    batches = []

    for obj in empty.children:

        if is_obj_on_viewlayer(obj):

            if obj.M3.is_group_empty:
                locations.append(obj.matrix_world.to_translation())

            elif obj.M3.is_group_object:

                if obj.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT']:
                    mesh_eval = get_eval_mesh(depsgraph, obj, data_block=False)
                    batches.append(get_coords(mesh_eval, mx=obj.matrix_world, indices=True))

        o.unparent(obj)

        obj.M3.is_group_object = False

    bpy.data.objects.remove(empty, do_unlink=True)

    return locations, batches

def clean_up_groups(context):
    empties = []
    top_empties = []

    for obj in context.scene.objects:

        if obj.library:
            continue

        if obj.M3.is_group_empty:

            empties.append(obj)

            if r.get_prefs().group_tools_remove_empty and not obj.children:
                print("INFO: Removing empty Group", obj.name)
                bpy.data.objects.remove(obj, do_unlink=True)
                continue

            if obj.parent:
                if obj.parent.M3.is_group_empty and not obj.M3.is_group_object:
                    obj.M3.is_group_object = True
                    print(f"INFO: {obj.name} is now a group object, because it was manually parented to {obj.parent.name}")

            else:
                top_empties.append(obj)

        elif obj.M3.is_group_object:
            if obj.parent:

                if not obj.parent.M3.is_group_empty:
                    obj.M3.is_group_object = False
                    print(f"INFO: {obj.name} is no longer a group object, because it's parent {obj.parent.name} is not a group empty")

            else:
                obj.M3.is_group_object = False
                print(f"INFO: {obj.name} is no longer a group object, because it doesn't have any parent")

        elif not obj.M3.is_group_object and obj.parent and obj.parent.M3.is_group_empty:
            obj.M3.is_group_object = True
            print(f"INFO: {obj.name} is now a group object, because it was manually parented to {obj.parent.name}")

            empties.append(obj)

    for empty in top_empties:
        propagate_pose_preview_alpha(empty)

    ensure_internal_index_group_name(empties)

    return top_empties

def get_group_polls(context):
    active_group = active if (active := context.active_object) and active.M3.is_group_empty and active.select_get() else None
    active_child = active if (active := context.active_object) and active.parent and active.M3.is_group_object and active.select_get() else None

    has_group_empties = bool([obj for obj in context.view_layer.objects if obj.M3.is_group_empty])
    has_visible_group_empties = bool([obj for obj in context.visible_objects if obj.M3.is_group_empty])

    is_groupable = bool([obj for obj in context.selected_objects if (obj.parent and obj.parent.M3.is_group_empty) or not obj.parent])
    is_ungroupable = bool([obj for obj in context.selected_objects if obj.M3.is_group_empty]) if has_group_empties else False

    is_addable = bool([obj for obj in context.selected_objects if obj != (active_group if active_group else active_child.parent) \
        and obj not in (active_group.children if active_group else active_child.parent.children) \
        and (not obj.parent or (obj.parent and obj.parent.M3.is_group_empty and not obj.parent.select_get()))]) if active_group or active_child else False

    is_removable = bool([obj for obj in context.selected_objects if obj.M3.is_group_object])
    is_selectable = bool([obj for obj in context.selected_objects if obj.M3.is_group_empty or obj.M3.is_group_object])
    is_duplicatable = bool([obj for obj in context.selected_objects if obj.M3.is_group_empty])
    is_groupifyable = bool([obj for obj in context.selected_objects if obj.type == 'EMPTY' and not obj.M3.is_group_empty and obj.children])

    is_batchposable = bool([obj for obj in active_group.children_recursive if obj.type == 'EMPTY' and obj.M3.is_group_empty]) if active_group else False

    return bool(active_group), bool(active_child), has_group_empties, has_visible_group_empties, is_groupable, is_ungroupable, is_addable, is_removable, is_selectable, is_duplicatable, is_groupifyable, is_batchposable

def get_group_collection(context, sel):
    collections = set(col for obj in sel for col in obj.users_collection)

    if len(collections) == 1:
        return collections.pop()

    else:
        return context.scene.collection

def get_group_matrix(context, objects, location_type='AVERAGE', rotation_type='WORLD'):

    if location_type == 'AVERAGE':
        location = average_locations([obj.matrix_world.to_translation() for obj in objects])

    elif location_type == 'ACTIVE':
        if context.active_object:
            location = context.active_object.matrix_world.to_translation()

        else:
            location = average_locations([obj.matrix_world.to_translation() for obj in objects])

    elif location_type == 'CURSOR':
        location = context.scene.cursor.location

    elif location_type == 'WORLD':
        location = Vector()

    if rotation_type == 'AVERAGE':
        rotation = Quaternion(average_locations([obj.matrix_world.to_quaternion().to_exponential_map() for obj in objects]))

    elif rotation_type == 'ACTIVE':
        if context.active_object:
            rotation = context.active_object.matrix_world.to_quaternion()

        else:
            rotation = Quaternion(average_locations([obj.matrix_world.to_quaternion().to_exponential_map() for obj in objects]))

    elif rotation_type == 'CURSOR':
        rotation = context.scene.cursor.matrix.to_quaternion()

    elif rotation_type == 'WORLD':
        rotation = Quaternion()

    return get_loc_matrix(location) @ get_rot_matrix(rotation)

def select_group_children(view_layer, empty, recursive=False):
    children = [c for c in empty.children if c.M3.is_group_object and c.name in view_layer.objects]

    if empty.hide_get():
        empty.hide_set(False)

        if empty.visible_get(view_layer=view_layer) and not empty.select_get(view_layer=view_layer):
            empty.select_set(True)

    for obj in children:
        if obj.visible_get(view_layer=view_layer) and not obj.select_get(view_layer=view_layer):
            obj.select_set(True)

        if obj.M3.is_group_empty and recursive:
            select_group_children(view_layer, obj, recursive=True)

def get_group_hierarchy(empty, up=False, layered=False):
    def get_group_child_empties_recursively(empty, empties, depth=0):
        child_empties = [e for e in empty.children if e.type == 'EMPTY' and e.M3.is_group_empty]

        if child_empties:
            depth += 1

            if depth + 1 > len(empties):
                empties.append([])

            for e in  child_empties:
                empties[depth].append(e)
                get_group_child_empties_recursively(e, empties, depth=depth)

    top_empty = empty

    if up:
        while top_empty.parent and top_empty.type == 'EMPTY' and top_empty.M3.is_group_empty:
            top_empty = top_empty.parent

    if layered:
        layered_empties = [top_empty]
        get_group_child_empties_recursively(top_empty, layered_empties, depth=0)

        return [layered_empties[0]] + [empty for layer in layered_empties[1:] for empty in layer]

    else:
        return [top_empty] + [obj for obj in top_empty.children_recursive if obj.type == 'EMPTY' and obj.M3.is_group_empty]

def get_child_depth(self, children, depth=0, init=False):
    if init or depth > self.depth:
        self.depth = depth

    for child in children:
        if child.children:
            get_child_depth(self, child.children, depth + 1, init=False)

    return self.depth

def fade_group_sizes(context, size=None, groups=[], init=False):
    if init:
        groups = [obj for obj in context.scene.objects if obj.M3.is_group_empty and not obj.parent]

    for group in groups:
        if size:
            factor = r.get_prefs().group_tools_fade_factor

            group.empty_display_size = factor * size
            group.M3.group_size = group.empty_display_size

        sub_groups = [c for c in group.children if c.M3.is_group_empty]

        if sub_groups:
            fade_group_sizes(context, size=group.M3.group_size, groups=sub_groups, init=False)

def get_group_root_empty(empty):
    top_empty = empty

    while top_empty.parent and top_empty.type == 'EMPTY' and top_empty.M3.is_group_empty:
        top_empty = top_empty.parent

    return top_empty

def get_group_default_name():
    p = r.get_prefs()

    basename = p.group_tools_basename

    if r.get_prefs().group_tools_auto_name:
        name = f"{p.group_tools_prefix}{basename}{p.group_tools_suffix}"

        c = 0

        while bpy.data.objects.get(name):
            c += 1
            name = f"{p.group_tools_prefix}{basename}.{str(c).zfill(3)}{p.group_tools_suffix}"
        return name

    else:
        return basename

def get_group_base_name(name, remove_index=True, debug=False):

    basename = name

    if remove_index:
        indexRegex = re.compile(r"\.[\d]{3}")
        matches = indexRegex.findall(name)

        basename = name

        if matches:
            for match in matches:
                basename = basename.replace(match, '')

    if debug:
        if basename == name:
            print(" passed in name is basename:", basename)
        else:
            print(" re-constructed basename:", basename)

    p = r.get_prefs()

    if r.get_prefs().group_tools_auto_name:
        if (prefix := p.group_tools_prefix) and basename.startswith(prefix):
            basename = basename[len(prefix):]

        else:
            prefix = None

        if (suffix := p.group_tools_suffix) and basename.endswith(suffix):
            basename = basename[:-len(suffix)]
        else:
            suffix = None

        if debug:
            print()
            print("name:", name)
            print("prefix:", prefix)
            print("basename:", basename)
            print("suffix:", suffix)

        return prefix, basename, suffix
    else:
        return None, name, None

def set_unique_group_name(group):
    _, basename, _ = get_group_base_name(group.name, debug=False)

    p = r.get_prefs()

    if p.group_tools_auto_name:
        name = f"{p.group_tools_prefix}{basename}{p.group_tools_suffix}"

        if group.name != name:

            c = 0

            while obj := bpy.data.objects.get(name):
                if obj == group:
                    return

                c += 1
                name = f"{p.group_tools_prefix}{basename}.{str(c).zfill(3)}{p.group_tools_suffix}"

            group.name = name

    elif group.name != basename:
        group.name = basename

def ensure_internal_index_group_name(group:Union[bpy.types.Object, list[bpy.types.Object], set[bpy.types.Object]]):
    p = r.get_prefs()

    if p.group_tools_auto_name and p.group_tools_suffix:
        groups = [group] if type(group) is bpy.types.Object else group

        indexRegex = re.compile(r".*(\.[\d]{3})$")

        for group in groups:
            if o.is_valid_object(group):
                mo = indexRegex.match(group.name)

                if mo:
                    set_unique_group_name(group)

            else:
                print(f"WARNING: Encountered Invalid Object Reference '{str(group)}' when trying to set unique object name")

def init_group_origin_adjustment(context):
    m3 = context.scene.M3

    m3['group_origin_mode_toggle'] = {
        'group_select': m3.group_select,
        'group_recursive_select': m3.group_recursive_select,
        'group_hide': m3.group_hide,

        'draw_group_relations': m3.draw_group_relations,
        'draw_group_relations_objects': m3.draw_group_relations_objects
    }

    context.scene.tool_settings.use_transform_skip_children = True

    m3.group_select = False
    m3.group_recursive_select = False
    m3.group_hide = False

    m3.draw_group_relations = True
    m3.draw_group_relations_objects = True

    if True:
        m3['group_origin_mode_toggle']['show_group_gizmos'] = m3.show_group_gizmos

        if active := context.active_object:
            m3['group_origin_mode_toggle']['active'] = {
                'object': active,
                'lock_rotation': active.lock_rotation,
                'draw_active_group_pose': active.M3.draw_active_group_pose,
            }

            for idx, pose in enumerate(active.M3.group_pose_COL):
                if is_inception_pose(pose):
                    m3['group_origin_mode_toggle']['active']['inception_pose_index'] = idx
                    break

            active.lock_rotation = False, False, False
            active.M3.draw_active_group_pose = False

        m3.show_group_gizmos = False

def finish_group_origin_adjustment(context):
    m3 = context.scene.M3

    context.scene.tool_settings.use_transform_skip_children = False

    if init_state := m3.get('group_origin_mode_toggle'):
        for name, prop in init_state.items():

            if True and name == 'active':

                active = prop['object']
                active.lock_rotation = prop['lock_rotation']
                active.M3.draw_active_group_pose = prop['draw_active_group_pose']

                if (index := prop.get('inception_pose_index', None)) is not None:
                    bpy.ops.machin3.update_group_pose(index=index, update_up=False, update_unlinked=False)

            else:
                setattr(m3, name, prop)

        if 'active' in init_state:
            del init_state['active']

        del m3['group_origin_mode_toggle']

    else:
        m3.group_select = True
        m3.group_recursive_select = True
        m3.group_hide = True

        m3.draw_group_relations = False
        m3.draw_group_relations_objects = False

def set_group_pose(empty, name='', uuid='', batch=False, debug=False) -> str:

    idx = len(empty.M3.group_pose_COL)

    if not name:
        name = f"Pose.{str(idx).zfill(3)}"

    if debug:
        print(f"Setting new pose {name} at index {idx}")

    pose = empty.M3.group_pose_COL.add()
    pose.index = idx

    pose.avoid_update = True
    pose.name = name

    pose.mx = empty.matrix_local
    pose.batch = batch

    if uuid:
        pose.uuid = uuid

    else:
        uuid = set_pose_uuid(pose)

    empty.M3.group_pose_IDX = pose.index

    set_pose_axis_and_angle(empty, pose)

    return uuid

def set_pose_axis_and_angle(empty, pose, inceptions=[]):
    if not inceptions:
        inceptions = [p for p in empty.M3.group_pose_COL if is_inception_pose(p) and p != pose]

    if inceptions:
        inception_rotation = inceptions[0].mx.to_quaternion()
        rotation = pose.mx.to_quaternion()

        delta_rot = inception_rotation.rotation_difference(rotation)

        axis_vector = delta_rot.axis
        axis = 'X' if abs(round(axis_vector.x)) == 1 else 'Y' if abs(round(axis_vector.y)) == 1  else 'Z' if abs(round(axis_vector.z)) == 1 else None

        angle = degrees(delta_rot.angle)

        if axis:
            factor = -1 if getattr(axis_vector, axis.lower()) < 0 else 1

            pose.axis = axis
            pose.angle = factor * angle

def set_pose_uuid(pose):
    if pose.name == 'Inception':
        uuid = '00000000-0000-0000-0000-000000000000'

    elif pose.name == 'LegacyPose':
        uuid = '11111111-1111-1111-1111-111111111111'

    else:
        uuid = str(uuid4())

    pose.uuid = uuid

    return uuid

def retrieve_group_pose(empty, index=None, debug=False):

    idx = index if index is not None else empty.M3.group_pose_IDX

    if debug:
        print(f"Recalling {'active ' if index == empty.M3.group_pose_IDX else''}pose with index {idx}")

    if 0 <= idx < len(empty.M3.group_pose_COL):
        pose = empty.M3.group_pose_COL[idx]

        loc, _, sca = empty.matrix_local.decompose()
        rot = pose.mx.to_quaternion()
        empty.matrix_local = Matrix.LocRotScale(loc, rot, sca)

def get_remove_poses(self, active, uuid):
    remove_poses = []
    remove_indices = []

    if self.remove_batch:
        empties = get_group_hierarchy(active, up=self.remove_up)

    else:
        empties = [active]

    for obj in empties:
        for idx, pose in enumerate(obj.M3.group_pose_COL):
            if pose.uuid == uuid and pose.batch and (self.remove_unlinked or pose.batchlinked):
                remove_poses.append((obj == active, get_group_base_name(obj.name), pose.name, pose.batchlinked))

                remove_indices.append((obj, idx))
                break

    if not remove_poses:
        for idx, pose in enumerate(active.M3.group_pose_COL):
            if pose.uuid == uuid:
                remove_poses.append((True, get_group_base_name(active.name), pose.name, pose.batchlinked))

                remove_indices.append((active, idx))
                break

    bpy.types.MACHIN3_OT_remove_group_pose.remove_poses = remove_poses

    return remove_indices

def prettify_group_pose_names(poseCOL):
    nameRegex = re.compile(r"Pose\.[\d]{3}")

    for idx, pose in enumerate(poseCOL):
        pose.index = idx

        mo = nameRegex.match(pose.name)

        if not (pose.name.strip() and not mo):
            pose.avoid_update = True
            pose.name = f"Pose.{str(idx).zfill(3)}"

def get_batch_pose_name(objects, basename='BatchPose'):
    pose_names = set()

    for obj in objects:
        for pose in obj.M3.group_pose_COL:
            pose_names.add(pose.name)

    name = basename

    c = 0

    while name in pose_names:
        c += 1
        name = f"{basename}.{str(c).zfill(3)}"

    return name

def process_group_poses(empty, debug=False):

    if debug:
        print()
        print("processing group poses for empty:", empty.name)

    group_empties = get_group_hierarchy(empty, up=True)

    group_poses = {}

    if debug:
        print(" empties (initial):")

    for e in group_empties:
        if debug:
            print(" ", e.name)
            print("   poses:")

        for pose in e.M3.group_pose_COL:
            if debug:
                print("   ", pose.name)

            if pose.name == 'Inception' and not is_inception_pose(pose):
                if debug:
                    print("     setting Inception uuid!")

                pose.uuid = '00000000-0000-0000-0000-000000000000'

            elif pose.name == 'LegacyPose' and pose.uuid != '11111111-1111-1111-1111-111111111111':
                if debug:
                    print("     setting LegacyPose uuid!")

                pose.uuid = '11111111-1111-1111-1111-111111111111'

            if pose.uuid in group_poses:
                group_poses[pose.uuid].append(pose)

            else:
                group_poses[pose.uuid] = [pose]

    ex_inception_uuid = None
    ex_legacy_uuid = None

    if debug:
        print("\n uuids:")

    for uuid, poses in group_poses.items():
        if debug:
            print(" ", uuid)
            print("   poses:")

        for pose in poses:
            if debug:
                print("   ", pose.name, "on", pose.id_data.name)

            if len(poses) > 1 and not pose.batch:
                if debug:
                    print("     enabling batch")

                pose.batch = True

            elif len(poses) == 1 and pose.batch:
                if debug:
                    print("     disabling batch")

                pose.batch = False

                if pose.name.startswith('BatchPose'):
                    if debug:
                        print("     removing BatchPose name too")

                    pose.avoid_update = True
                    pose.name = f"Pose.{str(pose.index).zfill(3)}"

            if uuid == '00000000-0000-0000-0000-000000000000' and pose.name != 'Inception':
                if not ex_inception_uuid:
                    ex_inception_uuid = str(uuid4())

                if debug:
                    print("     turning ex-inception pose into regular pose with new uuid:", ex_inception_uuid)

                pose.uuid = ex_inception_uuid

            if uuid == '11111111-1111-1111-1111-111111111111' and pose.name != 'LegacyPose':
                if not ex_legacy_uuid:
                    ex_legacy_uuid = str(uuid4())

                if debug:
                    print("     turning ex-legacy pose into regular pose with new uuid:", ex_legacy_uuid)

                pose.uuid = ex_legacy_uuid

    if debug:
        print("\n empties (final):")

    for e in group_empties:
        inceptions = [p for p in e.M3.group_pose_COL if is_inception_pose(p)]

        if debug:
            print(" ", e.name)
            print("   has inception:", bool(inceptions))

        if inceptions:

            for p in e.M3.group_pose_COL:
                if p not in inceptions and not p.axis:
                    if debug:
                        print("     calculating new axis/angle for pose", p.name)

                    set_pose_axis_and_angle(e, p, inceptions=inceptions)

        else:
            for p in e.M3.group_pose_COL:
                if p.axis:
                    if debug:
                        print("     clearing axis/angle for pose", p.name)

                    p.axis = ''

def propagate_pose_preview_alpha(empty, up=False):
    group_empties = get_group_hierarchy(empty, up=up)

    for e in group_empties:
        if e != empty:
            if e.M3.group_pose_alpha != empty.M3.group_pose_alpha:
                e.M3.avoid_update = True
                e.M3.group_pose_alpha = empty.M3.group_pose_alpha

def is_inception_pose(pose):
    return pose.uuid == '00000000-0000-0000-0000-000000000000'

def get_pose_batches(context, empty, pose, batches, children=None, dg=None, preview_batch_poses=False):
    if dg is None:
        dg = context.evaluated_depsgraph_get()

    if children is None:
        children = [obj for obj in empty.children_recursive if obj.name in context.view_layer.objects and obj.visible_get()]

    is_batch_pose = pose.batch and pose.batchlinked

    for obj in children:

        locals = [obj.matrix_local]

        ob = obj

        while ob.parent != empty:
            ob = ob.parent

            appended_batch_pose_mx_already = False

            if preview_batch_poses and is_batch_pose and ob.type == 'EMPTY' and ob.M3.is_group_empty:

                for p in ob.M3.group_pose_COL:

                    if p.batch and p.uuid == pose.uuid:

                        if p.batchlinked:

                            loc, _, sca = ob.matrix_local.decompose()
                            locals.append(Matrix.LocRotScale(loc, p.mx.to_quaternion(), sca))

                            appended_batch_pose_mx_already = True

                        break

            if not appended_batch_pose_mx_already:
                locals.append(ob.matrix_local)

        cumulative_local_mx = Matrix()

        for local in reversed(locals):
            cumulative_local_mx @= local

        loc, _, sca = empty.matrix_local.decompose()

        empty_local_posed_mx = Matrix.LocRotScale(loc, pose.mx.to_quaternion(), sca)

        mx = empty.parent.matrix_world @ empty_local_posed_mx @ cumulative_local_mx if empty.parent else empty_local_posed_mx @ cumulative_local_mx

        if obj.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT']:

            obj = dg.objects.get(obj.name)
            mesh_eval = obj.to_mesh()

            batches.append(get_coords(mesh_eval, mx=mx, indices=True))

            del obj
            del mesh_eval

        elif obj.type == 'EMPTY':
            length = obj.M3.group_size if obj.M3.is_group_empty else obj.empty_display_size
            batches.append((mx, length))

def get_group_relation_coords(context, active, others):
    is_draw_objects = context.scene.M3.draw_group_relations_objects

    active_coords = {
        'co': None,
        'vectors': [],
        'origins': []
    }

    other_coords = {
        'coords_visible': [],
        'coords_hidden': [],

        'group_lines': []
    }

    object_coords = {

        'vectors': [],
        'origins': [],

        'coords': []
    }

    group_objects = []

    if active:
        co = active.matrix_world.to_translation()
        active_coords['co'] = co

        children = {obj for obj in active.children if is_obj_on_viewlayer(obj)}
        groups = {obj for obj in children if obj.M3.is_group_empty}

        active_coords['vectors'] = [obj.matrix_world.to_translation() - co for obj in groups]
        active_coords['origins'] = [co for obj in groups]

        if is_draw_objects:
            group_objects.append((co, children - groups))

    if others:
        other_coords['coords'] = [obj.matrix_world.to_translation() for obj in others]

        for obj in others:
            co = obj.matrix_world.to_translation()

            if obj.visible_get():
                other_coords['coords_visible'].append(co)
            else:
                other_coords['coords_hidden'].append(co)

            children = {ob for ob in obj.children if is_obj_on_viewlayer(ob)}
            groups = {ob for ob in children if ob.M3.is_group_empty}

            other_coords['group_lines'].extend([coord for ob in groups for coord in [co, ob.matrix_world.to_translation()]])

            if is_draw_objects:
                group_objects.append((co, children - groups))

        if active:
            for vector in active_coords['vectors']:
                other_coords['group_lines'].extend([active_coords['co'], active_coords['co'] + vector])

    if context.scene.M3.draw_group_relations_objects:
        for co, objects in group_objects:
            for obj in objects:
                if obj.visible_get():

                    obj_co = obj.matrix_world.to_translation()

                    object_coords['vectors'].append(obj_co - co)
                    object_coords['origins'].append(co)

                    object_coords['coords'].append(obj_co)

    return active_coords, other_coords, object_coords
