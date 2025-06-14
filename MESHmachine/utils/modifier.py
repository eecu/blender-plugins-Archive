import bpy
import os
from math import radians
from . append import append_nodetree
from . nodes import get_nodegroup_input_identifier

def add_shrinkwrap(obj, target, vgroup):
    shrinkwrap = obj.modifiers.new(name="Shrinkwrap", type="SHRINKWRAP")

    shrinkwrap.target = target
    shrinkwrap.wrap_method = 'NEAREST_VERTEX'
    shrinkwrap.vertex_group = vgroup
    shrinkwrap.show_expanded = False
    shrinkwrap.show_on_cage = True

def add_boolean(obj, operator, method='DIFFERENCE', solver='FAST'):
    boolean = obj.modifiers.new(name=method.title(), type="BOOLEAN")

    boolean.object = operator
    boolean.operation = 'DIFFERENCE' if method == 'SPLIT' else method
    boolean.show_in_editmode = True
    boolean.show_expanded = False

    if method == 'SPLIT':
        boolean.show_viewport = False

    boolean.solver = solver

    return boolean

def add_displace(obj, name="Displace", mid_level=0, strength=0):
    displace = obj.modifiers.new(name=name, type="DISPLACE")
    displace.mid_level = mid_level
    displace.strength = strength

    displace.show_expanded = False

    return displace

def add_auto_smooth(obj, angle=20):
    smooth_by_angles = [tree for tree in bpy.data.node_groups if tree.name.startswith('Smooth by Angle')]

    if smooth_by_angles:
        ng = smooth_by_angles[0]

    else:
        path = os.path.join(bpy.utils.system_resource('DATAFILES'), 'assets', 'geometry_nodes', 'smooth_by_angle.blend')
        ng = append_nodetree(path, 'Smooth by Angle')

        if not ng:
            print("WARNING: Could not import Smooth by Angle node group from ESSENTIALS! This should never happen")
            return

    mod = obj.modifiers.new(name="Auto Smooth", type="NODES")
    mod.node_group = ng
    mod.show_expanded = False

    set_mod_input(mod, 'Angle', radians(angle))

    mod.id_data.update_tag()
    return mod

def get_auto_smooth(obj):
    if (mod := obj.modifiers.get('Auto Smooth', None)) and mod.type == 'NODES':
        return mod

    elif (mod := obj.modifiers.get('Smooth by Angle', None)) and mod.type == 'NODES':
        return mod
    
    else:
        mods = [mod for mod in obj.modifiers if mod.type == 'NODES' and (ng := mod.node_group) and (ng.name.startswith('Smooth by Angle') or ng.name.startswith('Auto Smooth'))]

        if mods:
            return mods[0]

def apply_mod(modname):
    bpy.ops.object.modifier_apply(modifier=modname)

def remove_mod(mod):
    obj = mod.id_data
    obj.modifiers.remove(mod)

def get_mod_obj(mod):
    if mod.type in ['BOOLEAN', 'HOOK', 'LATTICE', 'DATA_TRANSFER']:
        return mod.object
    elif mod.type == 'MIRROR':
        return mod.mirror_object
    elif mod.type == 'ARRAY':
        return mod.offset_object

def get_mod_objects(obj, mod_objects, mod_types=['BOOLEAN', 'MIRROR', 'ARRAY', 'HOOK', 'LATTICE', 'DATA_TRANSFER'], recursive=True, depth=0, debug=False):
    depthstr = " " * depth

    if debug:
        print(f"\n{depthstr}{obj.name}")

    for mod in obj.modifiers:
        if mod.type in mod_types:
            mod_obj = get_mod_obj(mod)

            print(f" {depthstr}mod: {mod.name} | obj: {mod_obj.name if mod_obj else mod_obj}")

            if mod_obj:
                if mod_obj not in mod_objects:
                    mod_objects.append(mod_obj)

                if recursive:
                    get_mod_objects(mod_obj, mod_objects, mod_types=mod_types, recursive=True, depth=depth + 1, debug=debug)

def move_mod(mod, index=0):
    obj = mod.id_data
    current_index = list(obj.modifiers).index(mod)

    if current_index != index:
        obj.modifiers.move(current_index, index)

def sort_mod(mod):
    def is_boolean(mod):
        return mod.type == 'BOOLEAN'

    def is_mirror(mod):
        return mod.type == 'MIRROR'

    def is_array(mod):
        return mod.type == 'ARRAY'

    def is_auto_smooth(mod):
        return mod.type == 'NODES' and mod.node_group and 'Smooth by Angle' in mod.node_group.name

    def should_preceed(mod, prev_mod):
        if is_boolean(mod):
            return any([is_mirror(prev_mod), is_array(prev_mod), is_auto_smooth(prev_mod)])

        elif is_auto_smooth(mod):
            return any([is_mirror(prev_mod), is_array(prev_mod)])

    if any([is_boolean(mod), is_auto_smooth(mod)]):
        obj = mod.id_data
        mods = list(obj.modifiers)

        if len(mods) > 1:

            move_mod(mod, len(mods) - 1)

            index = len(mods) - 1

            while index:
                index -= 1
                prev_mod = obj.modifiers[index]

                if should_preceed(mod, prev_mod):

                    if index == 0:
                        move_mod(mod, index)
                    continue

                else:
                    move_mod(mod, index + 1)
                    break

def get_mod_input(mod, name):
    if ng := mod.node_group:
        identifier, socket_type = get_nodegroup_input_identifier(ng, name)

        if identifier:
            return mod[identifier]

def set_mod_input(mod, name, value):
    if ng := mod.node_group:
        identifier, socket_type = get_nodegroup_input_identifier(ng, name)

        mod[identifier] = value
