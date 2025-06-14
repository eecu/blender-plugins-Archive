import bpy
from bpy.props import BoolProperty

from mathutils import Vector

from .. utils.math import flatten_matrix, get_rot_matrix, get_sca_matrix
from .. utils.modifier import get_mod_input, set_mod_input
from .. utils.object import clear_rotation, get_object_hierarchy_layers, has_decal_backup, has_stashes

from .. import MACHIN3toolsManager as M3

class ApplyTransformation(bpy.types.Operator):
    bl_idname = "machin3.apply_transformation"
    bl_label = "MACHIN3: Apply Transformation"
    bl_description = "Apply Transformation while compensating Modifier Properties, Child Objects as well as Decal Backups and Stash Objects."
    bl_options = {'REGISTER', 'UNDO'}

    scale: BoolProperty(name="Scale", default=False)
    rotation: BoolProperty(name="Rotation", default=True)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in context.selected_objects if obj.data]

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row(align=True)
        row.prop(self, "scale", toggle=True)
        row.prop(self, "rotation", toggle=True)

    def execute(self, context):
        context.evaluated_depsgraph_get()

        HC = M3.addons['hypercursor']['module'] if M3.get_addon('HyperCursor') else None

        if any([self.rotation, self.scale]):

            layers = get_object_hierarchy_layers(context)

            apply_objs = [obj for layer in layers for obj in layer if obj.data and obj in context.selected_objects]

            for obj in apply_objs:

                children = [(child, child.matrix_world) for child in obj.children]

                mx_basis = obj.matrix_basis
                _, rot_basis, sca_basis = mx_basis.decompose()

                if self.rotation and self.scale:
                    applymx = get_rot_matrix(rot_basis) @ get_sca_matrix(sca_basis)

                elif self.rotation:
                    applymx = get_rot_matrix(rot_basis)

                elif self.scale:
                    applymx = get_sca_matrix(sca_basis)

                else:
                    return {'CANCELLED'}

                obj.data.transform(applymx)

                obj.matrix_world = obj.matrix_world @ applymx.inverted_safe()

                if self.rotation:
                    clear_rotation(obj)

                if self.scale or self.rotation:

                    factor = (get_sca_matrix(sca_basis) @ Vector((0, 0, 1))).z

                    bevel = set()
                    weld = set()
                    shell = set()
                    displace = set()

                    linear_array = set()
                    linear_hyper_array = set()
                    radial_hyper_array = set()

                    for mod in obj.modifiers:

                        if self.scale:
                            if mod.type == 'BEVEL' and mod.offset_type != 'PERCENT':
                                bevel.add(mod)

                            elif mod.type == 'WELD':
                                weld.add(mod)

                            elif mod.type == 'SOLIDIFY':
                                shell.add(mod)

                            elif mod.type == 'DISPLACE':
                                displace.add(mod)

                            elif mod.type == 'ARRAY':
                                if mod.use_constant_offset:
                                    linear_array.add(mod)

                            elif HC:
                                if (modtype := HC.utils.modifier.is_linear_array(mod)) and modtype == 'LINEAR':
                                    linear_hyper_array.add(mod)

                                elif (modtype := HC.utils.modifier.is_radial_array(mod)) and modtype == 'RADIAL':
                                    radial_hyper_array.add(mod)

                        if self.rotation:
                            if mod.type == 'ARRAY':
                                if mod.use_constant_offset:
                                    linear_array.add(mod)

                            elif HC:
                                if (modtype := HC.utils.modifier.is_linear_array(mod)) and modtype == 'LINEAR':
                                    linear_hyper_array.add(mod)

                    for mod in bevel:
                        mod.width *= factor

                    for mod in weld:
                        mod.merge_threshold *= factor

                    for mod in shell:
                        mod.thickness *= factor

                    for mod in displace:
                        mod.strength *= factor

                    for mod in linear_array:
                        if self.scale:
                            mod.constant_offset_displace *= factor

                            if mod.fit_type == 'FIT_LENGTH':
                                mod.fit_length *= factor

                        if self.rotation:
                            mod.constant_offset_displace.rotate(rot_basis)

                    for mod in linear_hyper_array:
                        if self.scale:
                            offset = get_mod_input(mod, 'Offset')

                            if offset:
                                set_mod_input(mod, 'Offset', Vector(offset) * factor)

                        if self.rotation:
                            offset = get_mod_input(mod, 'Offset')

                            if offset:
                                rotated = Vector(offset)
                                rotated.rotate(rot_basis)

                                set_mod_input(mod, 'Offset', rotated)
                                mod.node_group.interface_update(context)

                    for mod in radial_hyper_array:
                        offset = get_mod_input(mod, 'Helix Offset')

                        if offset:
                            set_mod_input(mod, 'Helix Offset', offset * factor)

                for c, cmx in children:
                    c.matrix_world = cmx

                    if backup := has_decal_backup(c):
                        backup.DM.backupmx = flatten_matrix(applymx @ backup.DM.backupmx)

                if stashes := has_stashes(obj):
                    for stash in stashes:

                        if stash.obj:
                            stash.obj.data.transform(applymx)

        return {'FINISHED'}
