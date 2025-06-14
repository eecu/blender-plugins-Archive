import bpy
from bpy.props import FloatProperty, EnumProperty, BoolProperty
import bmesh
from .. items import wrap_method_items, wrap_method_dict
from .. utils.ui import init_cursor, wrap_cursor, draw_init, draw_title, draw_prop, update_HUD_location
from .. utils.ui import init_status, finish_status
from .. utils.property import step_collection, step_enum
from .. utils.selection import get_selected_ids
from .. utils.mesh import get_coords
from .. utils.draw import draw_mesh_wire
from .. utils.modifier import apply_mod
from .. utils.vgroup import set_vgroup, get_vgroup
from .. colors import red, white

class Conform(bpy.types.Operator):
    bl_idname = "machin3.conform"
    bl_label = "MACHIN3: Conform"
    bl_description = "Conform selection to Stash surface"
    bl_options = {'REGISTER', 'UNDO'}

    wrap_method: EnumProperty(name="Method", items=wrap_method_items, default="TARGET")
    xray: BoolProperty(name="X-Ray", default=False)
    alpha: FloatProperty(name="Alpha", default=0.2, min=0.01, max=0.99)
    apply_shrink_wrap: BoolProperty(name="Apply Shrink Wrap", default=True)
    remove_vgroup: BoolProperty(name="Remove Vertex Group", default=True)
    allowmodaloffset: BoolProperty(default=False)
    passthrough = False
    normal_offset = 0.002
    batch = None
    toggled_wires = False

    def draw_HUD(self, context):
        if context.area == self.area:
            hintoffset = 220 if self.wrap_method == 'SURFACEPOINT' else 200

            draw_init(self)

            draw_title(self, "Conform")

            draw_prop(self, "Stash", "%d/%d" % (self.stash.index + 1, len(self.active.MM.stashes)), hint_offset=hintoffset, hint="scroll UP/DOWN")
            self.offset += 10

            if self.stash.obj:
                draw_prop(self, "Offset", self.shrink_wrap.offset, offset=18, active=self.allowmodaloffset, hint_offset=hintoffset, hint="MOVE LEFT/RIGHT, toggle W, reset ALT + W")
                draw_prop(self, "Method", self.wrap_method, offset=18, hint_offset=hintoffset, hint="CTRL scroll UP/DOWN")
                self.offset += 10

                draw_prop(self, "X-Ray", self.xray, offset=18, hint_offset=hintoffset, hint="toggle X")
                draw_prop(self, "Alpha", self.alpha, decimal=1, offset=18, hint_offset=hintoffset, hint="ALT scroll UP/DOWN")
                self.offset += 10

                draw_prop(self, "Display", self.shrink_wrap.show_viewport, offset=18, hint_offset=hintoffset, hint="toggle D")
                draw_prop(self, "Show Wire", self.active.show_wire, offset=18, hint_offset=hintoffset, hint="toggle S")

                self.offset += 10
                draw_prop(self, "Apply Mod", self.apply_shrink_wrap, offset=18, hint_offset=hintoffset, hint="toggle A")
                if self.apply_shrink_wrap:
                    draw_prop(self, "Remove VGroup", self.remove_vgroup, offset=18, hint_offset=hintoffset, hint="toggle R")
            else:
                draw_prop(self, "INVALID", "Stash Object Not Found", offset=18, hint_offset=hintoffset, HUDcolor=red)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            if self.batch:
                draw_mesh_wire(self.batch, color=white, alpha=self.alpha, xray=self.xray)

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            active = bpy.context.active_object

            if active.MM.stashes:
                bm = bmesh.from_edit_mesh(active.data)
                return len([v for v in bm.verts if v.select]) >= 1

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            wrap_cursor(self, context, event)
            update_HUD_location(self, event)

        if event.type == "MOUSEMOVE":
            if self.passthrough:
                self.passthrough = False

            else:
                if self.allowmodaloffset:
                    divisor = 1000 if event.shift else 10 if event.ctrl else 100

                    delta_x = event.mouse_x - self.last_mouse_x
                    delta_offset = delta_x / divisor

                    self.shrink_wrap.offset += delta_offset

        if event.type in {'WHEELUPMOUSE', 'ONE'} and event.value == 'PRESS':
            if event.alt:
                self.alpha += 0.1

            elif event.ctrl:
                self.wrap_method = step_enum(self.wrap_method, wrap_method_items, 1)
                self.shrink_wrap.wrap_method = wrap_method_dict[self.wrap_method]

            else:
                self.stash = step_collection(self.active.MM, self.stash, "stashes", "active_stash_idx", -1)

                if self.stash.obj:
                    if self.stash.obj.matrix_world != self.active.matrix_world:
                        self.stash.obj.matrix_world = self.active.matrix_world

                    offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
                    self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

                    self.shrink_wrap.target = self.stash.obj

                else:
                    self.batch = None

        elif event.type in {'WHEELDOWNMOUSE', 'TWO'} and event.value == 'PRESS':
            if event.alt:
                self.alpha -= 0.1

            elif event.ctrl:
                self.wrap_method = step_enum(self.wrap_method, wrap_method_items, -1)
                self.shrink_wrap.wrap_method = wrap_method_dict[self.wrap_method]

            else:
                self.stash = step_collection(self.active.MM, self.stash, "stashes", "active_stash_idx", 1)

                if self.stash.obj:
                    if self.stash.obj.matrix_world != self.active.matrix_world:
                        self.stash.obj.matrix_world = self.active.matrix_world

                    offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
                    self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

                    self.shrink_wrap.target = self.stash.obj

        if self.stash.obj:

            if event.type == 'X' and event.value == 'PRESS':
                self.xray = not self.xray

            elif event.type == 'D' and event.value == 'PRESS':
                self.shrink_wrap.show_viewport = not self.shrink_wrap.show_viewport

            elif event.type == 'S' and event.value == 'PRESS':
                self.active.show_wire = not self.active.show_wire

            elif event.type == 'A' and event.value == 'PRESS':
                self.apply_shrink_wrap = not self.apply_shrink_wrap

            elif event.type == 'R' and event.value == 'PRESS':
                self.remove_vgroup = not self.remove_vgroup

            elif event.type == 'W' and event.value == "PRESS":
                if event.alt:
                    self.shrink_wrap.offset = 0
                    self.allowmodaloffset = False
                else:
                    self.allowmodaloffset = not self.allowmodaloffset

        if event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE']:
            if self.stash.obj:
                if self.apply_shrink_wrap:
                    apply_mod(self.shrink_wrap.name)

                    if self.remove_vgroup:
                        vgroup = get_vgroup(self, self.active, 'conform')
                        self.active.vertex_groups.remove(vgroup)

            else:
                self.active.modifiers.remove(self.shrink_wrap)

                vgroup = get_vgroup(self, self.active, 'conform')
                self.active.vertex_groups.remove(vgroup)

            self.finish()

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:

            self.active.modifiers.remove(self.shrink_wrap)

            vgroup = get_vgroup(self, self.active, 'conform')
            self.active.vertex_groups.remove(vgroup)

            self.finish()

            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

        bpy.ops.object.mode_set(mode='EDIT')

    def invoke(self, context, event):
        self.active = context.active_object

        vgroup, self.shrink_wrap = self.main(self.active)
        set_vgroup(self, vgroup, 'conform')

        self.stash = self.active.MM.stashes[self.active.MM.active_stash_idx]

        if self.stash.obj:
            offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
            self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

        else:
            self.batch = None

        self.allowmodaloffset = False

        init_cursor(self, event)

        init_status(self, context, 'Conform')

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def main(self, active):
        vert_ids = get_selected_ids(active, 'VERT')

        bpy.ops.object.mode_set(mode='OBJECT')

        vgroup = self.add_vgroup(active, vert_ids, "Conform")
        stash = active.MM.stashes[active.MM.active_stash_idx]
        stashobj = stash.obj

        if stashobj.matrix_world != active.matrix_world:
            stashobj.matrix_world = active.matrix_world

        shrink_wrap = self.add_shrink_wrap_mod(active, stashobj, vgroup.name, vgroup, 0, wrap_method_dict[self.wrap_method], 'ABOVE_SURFACE')
        return vgroup, shrink_wrap

    def add_shrink_wrap_mod(self, obj, target, name, vgroup, offset, wrap_method, wrap_mode):
        shrink_wrap = obj.modifiers.new(name, "SHRINKWRAP")
        shrink_wrap.target = target
        shrink_wrap.vertex_group = vgroup.name
        shrink_wrap.offset = offset
        shrink_wrap.wrap_method = wrap_method
        shrink_wrap.wrap_mode = wrap_mode

        shrink_wrap.use_negative_direction = True
        shrink_wrap.use_positive_direction = True

        shrink_wrap.show_expanded = False

        return shrink_wrap

    def add_vgroup(self, obj, vert_ids, name):
        vgroup = obj.vertex_groups.new(name=name)

        vgroup.add(vert_ids, 1, "ADD")
        return vgroup
