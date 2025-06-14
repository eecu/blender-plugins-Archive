import bpy
from bpy.props import BoolProperty, EnumProperty
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_origin_3d, region_2d_to_vector_3d

from mathutils import Vector

from .. utils.draw import draw_vector, draw_circle, draw_point, draw_label, draw_bbox, draw_cross_3d
from .. utils.math import compare_matrix, compare_quat
from .. utils.modifier import get_mod_obj, move_mod, remove_mod
from .. utils.object import get_eval_bbox, is_decal
from .. utils.property import step_list
from .. utils.registration import get_prefs
from .. utils.system import printd
from .. utils.ui import draw_status_item, finish_modal_handlers, force_ui_update, get_mouse_pos, get_zoom_factor, get_flick_direction, ignore_events, init_modal_handlers, init_status, finish_status, scroll, scroll_up
from .. utils.view import get_loc_2d

from .. colors import red, green, blue, white, yellow
from .. items import axis_items, axis_index_mapping

from .. import MACHIN3toolsManager as M3

def draw_mirror(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text='Mirror')

        draw_status_item(row, key='MOVE', text="Pick Axis")
        draw_status_item(row, key='LMB', text="Finish")
        draw_status_item(row, key='RMB', text="Cancel")

        row.separator(factor=10)

        if not op.remove:
            draw_status_item(row, active=op.cursor, key='C', text="Cursor")

            if op.cursor and op.cursor_empty:
                row.separator(factor=1)

                draw_status_item(row, active=op.use_existing_cursor, key='E', text="Use Existing", gap=1)

        if op.sel_mirror_mods:
            draw_status_item(row, key='A', text="Remove All + Finish", gap=1)

        if op.mirror_mods:
            draw_status_item(row, active=op.remove, key='X', text="Remove Mirror", gap=1)

            if op.remove and op.misaligned:
                draw_status_item(row, text=f"⚠ Misaligned Mirror Object{'s' if len(op.misaligned['sorted_objects']) > 1 else ''}", gap=2)

                if not op.misaligned['isallmisaligned']:
                    draw_status_item(row, active=op.use_misalign, key='Q', text="Pick Misaligned", gap=1)

                if len(op.misaligned['sorted_objects']) > 1:
                    draw_status_item(row, active=op.use_misalign, key='MMB_SCROLL', text="Cycle Misaligned", prop=op.mirror_obj.name if op.use_misalign else None, gap=1)

    return draw

class Mirror(bpy.types.Operator):
    bl_idname = "machin3.mirror"
    bl_label = "MACHIN3: Mirror"
    bl_options = {'REGISTER', 'UNDO'}

    flick: BoolProperty(name="Flick", default=False)
    remove: BoolProperty(name="Remove", default=False)
    axis: EnumProperty(name="Axis", items=axis_items, default="X")
    use_x: BoolProperty(name="X", default=True)
    use_y: BoolProperty(name="Y", default=False)
    use_z: BoolProperty(name="Z", default=False)
    bisect_x: BoolProperty(name="Bisect", default=False)
    bisect_y: BoolProperty(name="Bisect", default=False)
    bisect_z: BoolProperty(name="Bisect", default=False)
    flip_x: BoolProperty(name="Flip", default=False)
    flip_y: BoolProperty(name="Flip", default=False)
    flip_z: BoolProperty(name="Flip", default=False)
    DM_mirror_u: BoolProperty(name="U", default=True)
    DM_mirror_v: BoolProperty(name="V", default=False)
    cursor: BoolProperty(name="Mirror across Cursor", default=False)
    use_misalign: BoolProperty(name="Use Mislinged Object Removal", default=False)
    use_existing_cursor: BoolProperty(name="Use existing Cursor Empty", default=False)
    passthrough = None

    across = False
    removeacross = False
    removecursor = False
    removeall = False

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row(align=True)
        row.prop(self, 'cursor', toggle=True)

        row = column.row(align=True)
        row.prop(self, "use_x", toggle=True)
        row.prop(self, "use_y", toggle=True)
        row.prop(self, "use_z", toggle=True)

        if self.meshes_present and len(context.selected_objects) == 1 and self.active in context.selected_objects and not self.cursor:
            row = column.row(align=True)
            r = row.row()
            r.active = self.use_x
            r.prop(self, "bisect_x")
            r = row.row()
            r.active = self.use_y
            r.prop(self, "bisect_y")
            r = row.row()
            r.active = self.use_z
            r.prop(self, "bisect_z")

            row = column.row(align=True)
            r = row.row()
            r.active = self.use_x
            r.prop(self, "flip_x")
            r = row.row()
            r.active = self.use_y
            r.prop(self, "flip_y")
            r = row.row()
            r.active = self.use_z
            r.prop(self, "flip_z")

        if self.decals_present:
            column.separator()

            column.label(text="DECALmachine - UVs")
            row = column.row(align=True)
            row.prop(self, "DM_mirror_u", toggle=True)
            row.prop(self, "DM_mirror_v", toggle=True)

    @classmethod
    def poll(cls, context):
        if context.mode == "OBJECT":
            return context.active_object

    def draw_HUD(self, context):
        if context.area == self.area:
            if not self.passthrough:
                draw_vector(self.flick_vector, origin=self.init_mouse)

                color = red if self.remove else white
                alpha = 0.2 if self.remove else 0.02
                draw_circle(self.init_mouse, radius=self.flick_distance, width=3, color=color, alpha=alpha)

                title = 'Remove' if self.remove else 'Mirror'
                alpha = 1 if self.remove else 0.8
                draw_label(context, title=title, coords=Vector((self.init_mouse.x, self.init_mouse.y + self.flick_distance - (15 * self.scale))), center=True, color=color, alpha=alpha)

                if self.remove and self.misaligned and self.use_misalign:
                    name = 'Cursor Empty' if self.use_misalign and self.mirror_obj.type == 'EMPTY' else self.mirror_obj.name if self.use_misalign else 'None'
                    alpha = 1 if self.use_misalign else 0.3
                    color = blue if self.use_misalign and self.mirror_obj.type == 'EMPTY' else yellow if self.use_misalign else white

                    draw_label(context, title=name, coords=Vector((self.init_mouse.x, self.init_mouse.y - self.flick_distance + (30 * self.scale))), center=True, color=color, alpha=alpha)

                elif not self.remove and self.cursor or len(self.sel) > 1:
                        title, color = ('New Cursor', green) if self.cursor and not self.use_existing_cursor else ('Existing Cursor', blue) if self.cursor else (self.active.name, yellow)
                        draw_label(context, title=title, coords=Vector((self.init_mouse.x, self.init_mouse.y - self.flick_distance + (30 * self.scale))), center=True, color=color)

                title = self.flick_direction.split('_')[1] if self.remove else self.flick_direction.replace('_', ' ').title()
                draw_label(context, title=title, coords=Vector((self.init_mouse.x, self.init_mouse.y - self.flick_distance + (15 * self.scale))), center=True, alpha=0.4)

            if self.remove and self.misaligned and self.use_misalign:

                if self.mirror_obj.type == 'EMPTY':

                    if self.passthrough:
                        self.mirror_obj_2d = get_loc_2d(context, self.mirror_obj.matrix_world.to_translation())

                    draw_circle(self.mirror_obj_2d, radius=10 * self.scale, width=2 * self.scale, color=blue)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            if not self.passthrough:
                for direction, axis, color in zip(self.axes.keys(), self.axes.values(), self.colors):
                    is_positive = 'POSITIVE' in direction

                    width, alpha = (2, 0.99) if is_positive or self.remove else (1, 0.3)
                    draw_vector(axis * self.zoom / 2, origin=self.init_mouse_3d, color=color, width=width, alpha=alpha)

                draw_point(self.init_mouse_3d + self.axes[self.flick_direction] * self.zoom / 2 * 1.2, size=5, alpha=0.8)

                if self.remove and self.misaligned and self.use_misalign:
                    mx = self.misaligned['matrices'][self.mirror_obj]

                    if self.mirror_obj.type  == 'EMPTY' and not self.mirror_obj.instance_collection:
                        loc = mx.inverted_safe() @ mx.to_translation()
                        draw_cross_3d(loc, mx=mx, color=blue, width=2 * self.scale, length=2 * self.cursor_empty_zoom)

                    else:
                        bbox = get_eval_bbox(self.mirror_obj)
                        draw_bbox(bbox, mx=mx, color=yellow, corners=0.1, width=2 * self.scale, alpha=0.5)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event, hud=False)
            self.mouse_pos.resize(3)

        events = ['MOUSEMOVE']

        if not self.remove:
            events.append('C')

            if self.cursor and self.cursor_empty:
                events.append('E')

        if self.mirror_mods:
            events.extend(['X', 'D', 'R'])

            if self.remove and self.misaligned:
                events.append('Q')

        if self.sel_mirror_mods:
            events.append('A')

        if event.type in events or scroll(event):
            if self.passthrough:
                self.passthrough = False
                self.init_mouse = self.mouse_pos
                self.init_mouse_3d = region_2d_to_location_3d(context.region, context.region_data, self.init_mouse, self.origin)
                self.zoom = get_zoom_factor(context, depth_location=self.origin, scale=self.flick_distance, ignore_obj_scale=True)

                if self.mirror_obj and self.mirror_obj.type == 'EMPTY':
                    loc = self.mirror_obj.matrix_world.to_translation()
                    self.mirror_obj_2d = get_loc_2d(context, loc)

                    self.cursor_empty_zoom = get_zoom_factor(context, depth_location=loc, scale=10, ignore_obj_scale=True)

            if event.type == 'MOUSEMOVE':

                self.flick_vector = self.mouse_pos - self.init_mouse

                if self.flick_vector.length:
                    self.flick_direction = get_flick_direction(context, self.init_mouse_3d, self.flick_vector, self.axes)

                    self.set_mirror_props()

                if self.flick_vector.length > self.flick_distance:
                    self.finish()

                    self.execute(context)
                    return {'FINISHED'}

            elif (event.type in {'C', 'E', 'A', 'X', 'D', 'R', 'Q'} and event.value == 'PRESS') or scroll(event):

                if event.type in {'X', 'D', 'R'}:
                    self.remove = not self.remove
                    self.active.select_set(True)

                elif event.type == 'C':
                    self.cursor = not self.cursor
                    self.active.select_set(True)

                elif event.type == 'E':
                    self.use_existing_cursor = not self.use_existing_cursor
                    self.active.select_set(True)

                if self.misaligned:

                    if not self.misaligned['isallmisaligned'] and event.type == 'Q' and event.value == 'PRESS':
                        self.use_misalign = not self.use_misalign
                        self.active.select_set(True)

                    if scroll(event):
                        if self.use_misalign:
                            if scroll_up(event):
                                self.mirror_obj = step_list(self.mirror_obj, self.misaligned['sorted_objects'], step=-1, loop=True)

                            else:
                                self.mirror_obj = step_list(self.mirror_obj, self.misaligned['sorted_objects'], step=1, loop=True)
                        else:
                            self.use_misalign = True
                            self.active.select_set(True)

                        force_ui_update(context)

                if self.remove and self.misaligned and self.use_misalign:
                    mo_mx = self.misaligned['matrices'][self.mirror_obj]
                    self.axes = self.get_axes(mo_mx)

                elif not self.remove and self.cursor:
                    self.axes = self.get_axes(self.cmx)

                else:
                    self.axes = self.get_axes(self.mx)

                if self.misaligned and self.mirror_obj.type == 'EMPTY':
                    loc = self.mirror_obj.matrix_world.to_translation()
                    self.mirror_obj_2d = get_loc_2d(context, loc)
                    self.cursor_empty_zoom = get_zoom_factor(context, depth_location=loc, scale=10, ignore_obj_scale=True)

                if event.type == 'A':
                    self.finish()

                    for mod in self.sel_mirror_mods:
                        remove_mod(mod)

                    self.removeall = True
                    return {'FINISHED'}

        if event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
                self.finish()

                self.execute(context)
                return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish()

            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self):
        finish_modal_handlers(self)

        finish_status(self)

        self.active.select_set(True)

    def invoke(self, context, event):
        scene = context.scene

        self.active = context.active_object
        self.sel = context.selected_objects
        self.meshes_present = any([obj for obj in self.sel if obj.type == 'MESH'])
        self.decals_present = M3.get_addon("DECALmachine") and any([obj for obj in self.sel if is_decal(obj)])

        if self.flick:
            self.mx = self.active.matrix_world
            self.cmx = scene.cursor.matrix

            self.scale = context.preferences.system.ui_scale * get_prefs().modal_hud_scale
            self.flick_distance = get_prefs().mirror_flick_distance * self.scale

            self.mirror_obj = None
            self.mirror_mods = self.get_mirror_mods([self.active])
            self.sel_mirror_mods = self.get_mirror_mods(self.sel)
            self.cursor_empty = self.get_matching_cursor_empty(context)

            self.use_existing_cursor = True if self.cursor_empty else False

            self.removeall = False

            self.aligned, self.misaligned = self.get_misaligned_mods(context, self.active, self.mx, debug=False)

            if self.misaligned:

                self.use_misalign = self.misaligned['isallmisaligned']
                self.mirror_obj = self.misaligned['sorted_objects'][-1]

                if self.mirror_obj.type == 'EMPTY':
                    loc = self.mirror_obj.matrix_world.to_translation()
                    self.mirror_obj_2d = get_loc_2d(context, loc)
                    self.cursor_empty_zoom = get_zoom_factor(context, depth_location=loc, scale=10, ignore_obj_scale=True)

            get_mouse_pos(self, context, event, hud=False)
            self.mouse_pos.resize(3)

            view_origin = region_2d_to_origin_3d(context.region, context.region_data, self.mouse_pos)
            view_dir = region_2d_to_vector_3d(context.region, context.region_data, self.mouse_pos)

            self.origin = view_origin + view_dir * 10
            self.zoom = get_zoom_factor(context, depth_location=self.origin, scale=self.flick_distance, ignore_obj_scale=True)

            self.init_mouse = self.mouse_pos.copy()
            self.init_mouse_3d = region_2d_to_location_3d(context.region, context.region_data, self.init_mouse, self.origin)

            self.flick_vector = self.mouse_pos - self.init_mouse
            self.flick_direction = 'NEGATIVE_X'

            self.axes = self.get_axes(self.cmx if self.cursor else self.mx)

            self.colors = [red, red, green, green, blue, blue]

            init_status(self, context, func=draw_mirror(self))
            self.active.select_set(True)

            init_modal_handlers(self, context, hud=True, view3d=True)
            return {'RUNNING_MODAL'}

        else:
            self.mirror(context, self.active, self.sel)
            return {'FINISHED'}

    def execute(self, context):
        self.active = context.active_object
        self.sel = context.selected_objects

        if self.flick and self.remove:
            self.remove_mirror(self.active)

        else:
            self.across = len(self.sel) > 1

            self.mirror(context, self.active, self.sel)

        return {'FINISHED'}

    def get_axes(self, mx):
        axes = {'POSITIVE_X': mx.to_quaternion() @ Vector((1, 0, 0)),
                'NEGATIVE_X': mx.to_quaternion() @ Vector((-1, 0, 0)),
                'POSITIVE_Y': mx.to_quaternion() @ Vector((0, 1, 0)),
                'NEGATIVE_Y': mx.to_quaternion() @ Vector((0, -1, 0)),
                'POSITIVE_Z': mx.to_quaternion() @ Vector((0, 0, 1)),
                'NEGATIVE_Z': mx.to_quaternion() @ Vector((0, 0, -1))}

        return axes

    def get_matching_cursor_empty(self, context):
        scene = context.scene

        matching_empties = [obj for obj in scene.objects if obj.type == 'EMPTY' and compare_matrix(obj.matrix_world, self.cmx, precision=5)]

        if matching_empties:
            return matching_empties[0]

    def get_mirror_mods(self, objects):
        mods = []

        for obj in objects:
            if obj.type == 'GPENCIL':
                mods.extend([mod for mod in obj.grease_pencil_modifiers if mod.type == 'GP_MIRROR'])

            elif obj.type == 'GREASEPENCIL':
                mods.extend([mod for mod in obj.modifiers if mod.type == 'GREASE_PENCIL_MIRROR'])

            else:
                mods.extend([mod for mod in obj.modifiers if mod.type == 'MIRROR'])

        return mods

    def mirror(self, context, active, sel):
        if self.cursor:
            if self.flick and self.cursor_empty and self.use_existing_cursor:
                empty = self.cursor_empty

            else:
                empty = bpy.data.objects.new(name=f"{active.name} Mirror", object_data=None)
                context.scene.collection.objects.link(empty)
                empty.matrix_world = context.scene.cursor.matrix

                empty.show_in_front = True
                empty.empty_display_type = 'ARROWS'
                empty.empty_display_size = (context.scene.cursor.location - sel[0].matrix_world.to_translation()).length / 10

                empty.hide_set(True)

        if len(sel) == 1 and active in sel:

            if self.cursor:
                self.bisect_x = self.bisect_y = self.bisect_z = False
                self.flip_x = self.flip_y = self.flip_z = False

            if active.type in ["MESH", "CURVE"]:
                self.mirror_mesh_obj(context, active, mirror_object=empty if self.cursor else None)

            elif active.type == "GPENCIL":
                self.mirror_gpencil_obj(context, active, mirror_object=empty if self.cursor else None)

            elif active.type == "EMPTY" and active.instance_collection:
                self.mirror_instance_collection(context, active, mirror_object=empty if self.cursor else None)

        elif len(sel) > 1 and active in sel:

            self.bisect_x = self.bisect_y = self.bisect_z = False
            self.flip_x = self.flip_y = self.flip_z = False

            if not self.cursor:
                sel.remove(active)

            for obj in sel:
                if obj.type in ["MESH", "CURVE"]:
                    self.mirror_mesh_obj(context, obj, mirror_object=empty if self.cursor else active)

                elif obj.type in ["GPENCIL", "GREASEPENCIL"]:
                    self.mirror_gpencil_obj(context, obj, mirror_object=empty if self.cursor else active)

                elif obj.type == "EMPTY" and obj.instance_collection:
                    self.mirror_instance_collection(context, obj, mirror_object=empty if self.cursor else active)

    def mirror_mesh_obj(self, context, obj, mirror_object=None):
        mirror = obj.modifiers.new(name="Mirror", type="MIRROR")
        mirror.use_axis = (self.use_x, self.use_y, self.use_z)
        mirror.use_bisect_axis = (self.bisect_x, self.bisect_y, self.bisect_z)
        mirror.use_bisect_flip_axis = (self.flip_x, self.flip_y, self.flip_z)
        mirror.show_expanded = False

        if mirror_object:
            mirror.mirror_object = mirror_object

        if M3.get_addon("DECALmachine"):
            if obj.DM.isdecal:
                mirror.use_mirror_u = self.DM_mirror_u
                mirror.use_mirror_v = self.DM_mirror_v

                nrmtransfer = obj.modifiers.get("NormalTransfer")

                if nrmtransfer:
                    move_mod(nrmtransfer, len(obj.modifiers) - 1)

    def mirror_gpencil_obj(self, context, obj, mirror_object=None):
        if bpy.app.version < (4, 3, 0):
            mirror = obj.grease_pencil_modifiers.new(name="Mirror", type="GP_MIRROR")

        else:
            mirror = obj.modifiers.new(name="Mirror", type="GREASE_PENCIL_MIRROR")

        mirror.use_axis_x = self.use_x
        mirror.use_axis_y = self.use_y
        mirror.use_axis_z = self.use_z
        mirror.show_expanded = False

        if mirror_object:
            mirror.object = mirror_object

    def mirror_instance_collection(self, context, obj, mirror_object=None):
        mirror_empty = bpy.data.objects.new("mirror_empty", object_data=None)

        col = obj.instance_collection

        if mirror_object:
            mirror_empty.matrix_world = mirror_object.matrix_world

        mirror_empty.matrix_world = obj.matrix_world.inverted_safe() @ mirror_empty.matrix_world

        col.objects.link(mirror_empty)

        meshes = [obj for obj in col.objects if obj.type == "MESH"]

        for obj in meshes:
            self.mirror_mesh_obj(context, obj, mirror_empty)

    def set_mirror_props(self):
        self.use_x = self.use_y = self.use_z = False
        self.bisect_x = self.bisect_y = self.bisect_z = False
        self.flip_x = self.flip_y = self.flip_z = False

        direction, axis = self.flick_direction.split('_')

        setattr(self, f'use_{axis.lower()}', True)

        if len(self.sel) == 1:
            setattr(self, f'bisect_{axis.lower()}', True)

        if direction == 'POSITIVE':
            setattr(self, f'flip_{axis.lower()}', True)

        self.axis = axis

    def remove_mirror(self, obj):
        axis = self.flick_direction.split('_')[1]

        if self.misaligned and self.use_misalign:
            if obj.type in ['GPENCIL', 'GREASEPENCIL']:
                mods = [mod for mod in self.misaligned['object_mods'][self.mirror_obj] if getattr(mod, f'use_axis_{axis.lower()}')]

            else:
                mods = [mod for mod in self.misaligned['object_mods'][self.mirror_obj] if mod.use_axis[axis_index_mapping[axis]]]

        else:
            if obj.type in ['GPENCIL', 'GREASEPENCIL']:
                mods = [mod for mod in self.aligned if getattr(mod, f'use_axis_{axis.lower()}')]

            else:
                mods = [mod for mod in self.aligned if mod.use_axis[axis_index_mapping[axis]]]

        if mods:
            mod = mods[-1]

            mod_object = get_mod_obj(mod)

            if mod_object:
                if mod_object.type == 'EMPTY':
                    self.removeacross = False
                    self.removecursor = True
                else:
                    self.removeacross = True
                    self.removecursor = False
            else:
                self.removeacross = False
                self.removecursor = False

            remove_mod(mod)

            return True

    def get_misaligned_mods(self, context, active, mx, debug=False):
        object_mirror_mods = [mod for mod in self.mirror_mods if get_mod_obj(mod)]
        aligned = [mod for mod in self.mirror_mods if mod not in object_mirror_mods]

        if debug:
            print()
            print("object mirrors:", object_mirror_mods)
            print("non-object mirrors:", aligned)

        misaligned = {'sorted_mods': [],
                      'sorted_objects': [],
                      'object_mods': {},
                      'matrices': {},
                      'isallmisaligned': False}

        for mod in object_mirror_mods:
            mirror_obj = get_mod_obj(mod)
            mo_mx = mirror_obj.matrix_world

            if not compare_quat(mx.to_quaternion(), mo_mx.to_quaternion(), precision=8, debug=False):
                misaligned['sorted_mods'].append(mod)

                if mirror_obj not in misaligned['sorted_objects']:
                    misaligned['sorted_objects'].append(mirror_obj)

                if mirror_obj in misaligned['object_mods']:
                    misaligned['object_mods'][mirror_obj].append(mod)

                else:
                    misaligned['object_mods'][mirror_obj] = [mod]
                    misaligned['matrices'][mirror_obj] = mirror_obj.matrix_world

            else:
                aligned.append(mod)

        if len(self.mirror_mods) == len(misaligned['sorted_mods']):
            misaligned['isallmisaligned'] = True

        if debug:
            printd(misaligned)

        if misaligned['sorted_mods']:
            return aligned, misaligned

        else:
            return aligned, False

class Unmirror(bpy.types.Operator):
    bl_idname = "machin3.unmirror"
    bl_label = "MACHIN3: Unmirror"
    bl_description = "Removes the last modifer in the stack of the selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        mirror_meshes = [obj for obj in context.selected_objects if obj.type == "MESH" and any(mod.type == "MIRROR" for mod in obj.modifiers)]
        if mirror_meshes:
            return True

        if bpy.app.version < (4, 3, 0):
            mirror_gpencils = [obj for obj in context.selected_objects if obj.type == "GPENCIL" and any(mod.type == "GP_MIRROR" for mod in obj.grease_pencil_modifiers)]
        else:
            mirror_gpencils = [obj for obj in context.selected_objects if obj.type == "GREASEPENCIL" and any(mod.type == "GREASE_PENCIL_MIRRORP_MIRROR" for mod in obj.modifiers)]

        if mirror_gpencils:
            return True

    def execute(self, context):
        targets = set()

        for obj in context.selected_objects:
            if obj.type in ["MESH", "CURVE"]:
                target = self.unmirror_mesh_obj(obj)

                if target and target.type == "EMPTY" and not target.children:
                    targets.add(target)

            elif obj.type in ["GPENCIL", 'GREASEPENCIL']:
                self.unmirror_gpencil_obj(obj)

            elif obj.type == "EMPTY" and obj.instance_collection:
                col = obj.instance_collection
                instance_col_targets = set()

                for obj in col.objects:
                    target = self.unmirror_mesh_obj(obj)

                    if target and target.type == "EMPTY":
                        instance_col_targets.add(target)

                if len(instance_col_targets) == 1:
                    bpy.data.objects.remove(list(targets)[0], do_unlink=True)

        if targets:

            targets_in_use = {mod.mirror_object for obj in bpy.data.objects for mod in obj.modifiers if mod.type =='MIRROR' and mod.mirror_object and mod.mirror_object.type == 'EMPTY'}

            for target in targets:
                if target not in targets_in_use:
                    bpy.data.objects.remove(target, do_unlink=True)

        return {'FINISHED'}

    def unmirror_mesh_obj(self, obj):
        mirrors = [mod for mod in obj.modifiers if mod.type == "MIRROR"]

        if mirrors:
            target = mirrors[-1].mirror_object
            obj.modifiers.remove(mirrors[-1])

            return target

    def unmirror_gpencil_obj(self, obj):
        if bpy.app.version < (4, 3, 0):
            mirrors = [mod for mod in obj.grease_pencil_modifiers if mod.type == "GP_MIRROR"]

            if mirrors:
                obj.grease_pencil_modifiers.remove(mirrors[-1])

        else:
            mirrors = [mod for mod in obj.modifiers if mod.type == "GREASE_PENCIL_MIRROR"]

            if mirrors:
                obj.mirrors.remove(mirrors[-1])
