import bpy
import bmesh
from bpy.props import BoolProperty, FloatProperty, EnumProperty
from mathutils import Vector
from ... utils.developer import output_traceback
from ... utils.ui import draw_init, draw_title, draw_prop, init_cursor, wrap_cursor, get_zoom_factor, update_HUD_location
from ... utils.ui import init_status, finish_status
from ... utils.property import step_enum
from ... utils.math import average_locations, get_irregular_circle_center
from ... items import looptools_circle_method

class LoopToolsCircle(bpy.types.Operator):
    bl_idname = "machin3.looptools_circle"
    bl_label = "MACHIN3: LoopTools Circle"
    bl_description = "LoopTools' Circle as a modal"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(name="Method", items=looptools_circle_method, default='best')
    influence: FloatProperty(name="Influence", description="Force of the tool", default=100.0, min=0.0, max=100.0, precision=1, subtype='PERCENTAGE')
    flatten: BoolProperty(name="Flatten", description="Flatten the circle, instead of projecting it on the mesh", default=True)
    regular: BoolProperty(name="Regular", description="Distribute vertices at constant distances along the circle", default=False)
    custom_radius: BoolProperty(name="Radius", description="Force a custom radius", default=False)
    radius: FloatProperty(name="Radius", description="Custom radius for circle", default=1.0, min=0.0, soft_max=1000.0)
    lock_x: BoolProperty(name="Lock X", description="Lock editing of the x-coordinate", default=False)
    lock_y: BoolProperty(name="Lock Y", description="Lock editing of the y-coordinate", default=False)
    lock_z: BoolProperty(name="Lock Z", description="Lock editing of the z-coordinate", default=False)
    fix_midpoint: BoolProperty(name="Fix Midpoint", default=False)
    passthrough: BoolProperty(default=False)
    allowmodalradius: BoolProperty(default=False)
    allowmodalinfluence: BoolProperty(default=False)
    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Circle", subtitle="LoopTools")

            draw_prop(self, "Method", self.method, hint="scroll UP/DOWN")
            self.offset += 10

            draw_prop(self, "Flatten", self.flatten, offset=18, hint="toggle F")
            draw_prop(self, "Regular", self.regular, offset=18, hint="toggle R")
            self.offset += 10

            draw_prop(self, "Custom Radius", self.custom_radius, offset=18, hint="toggle C")
            draw_prop(self, "Radius", self.radius, offset=18, active=self.allowmodalradius, hint="move LEFT/RIGHT, toggle W, reset ALT + W")
            draw_prop(self, "Influence", self.influence, offset=18, active=self.allowmodalinfluence, hint="move UP/DOWN, toggle I, reset ALT + I")
            self.offset += 10

            draw_prop(self, "Fix Midpoint", self.fix_midpoint, offset=18, hint="toggle X")

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            wrap_cursor(self, context, event)
            update_HUD_location(self, event)

        events = ['WHEELUPMOUSE', 'ONE', 'WHEELDOWNMOUSE', 'TWO', 'C', 'W', 'I', 'F', 'R', 'X']

        if any([self.allowmodalradius, self.allowmodalinfluence]):
            events.append('MOUSEMOVE')

        if event.type in events:
            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.passthrough = False

                else:
                    if self.allowmodalradius:
                        divisor = 100 if event.shift else 1 if event.ctrl else 10

                        delta_x = event.mouse_x - self.last_mouse_x
                        delta_radius = delta_x / divisor * self.factor

                        self.radius += delta_radius

                    if self.allowmodalinfluence:
                        divisor = 10 if event.shift else 0.1 if event.ctrl else 1

                        delta_y = event.mouse_y - self.last_mouse_y
                        delta_influence = delta_y / divisor

                        self.influence += delta_influence

            elif event.type in {'WHEELUPMOUSE', 'ONE'} and event.value == 'PRESS':
                self.method = step_enum(self.method, looptools_circle_method, 1)

            elif event.type in {'WHEELDOWNMOUSE', 'TWO'} and event.value == 'PRESS':
                self.method = step_enum(self.method, looptools_circle_method, -1)

            elif event.type == 'C' and event.value == "PRESS":
                self.custom_radius = not self.custom_radius

            elif event.type == 'W' and event.value == "PRESS":
                if event.alt:
                    self.allowmodalradius = False
                    self.radius = 1
                else:
                    self.allowmodalradius = not self.allowmodalradius
                    if not self.custom_radius:
                        self.custom_radius = True

            elif event.type == 'I' and event.value == "PRESS":
                if event.alt:
                    self.allowmodalinfluence = False
                    self.influence = 100
                else:
                    self.allowmodalinfluence = not self.allowmodalinfluence

            elif event.type == 'F' and event.value == "PRESS":
                self.flatten = not self.flatten

            elif event.type == 'R' and event.value == "PRESS":
                self.regular = not self.regular

            elif event.type == 'X' and event.value == "PRESS":
                self.fix_midpoint = not self.fix_midpoint

            try:
                ret = self.main(self.active, modal=True)

                if not ret:
                    self.finish()
                    return {'FINISHED'}

            except Exception as e:
                self.finish()

                if bpy.context.mode == 'OBJECT':
                    bpy.ops.object.mode_set(mode='EDIT')

                output_traceback(self, e)
                return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()
            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def cancel_modal(self, removeHUD=True):
        if removeHUD:
            self.finish()

        bpy.ops.object.mode_set(mode='OBJECT')
        self.initbm.to_mesh(self.active.data)
        bpy.ops.object.mode_set(mode='EDIT')

    def invoke(self, context, event):
        self.active = context.active_object

        self.active.update_from_editmode()

        self.fix_midpoint = False

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

        verts = [v for v in self.initbm.verts if v.select]

        avg_center = average_locations([v.co for v in verts])

        circle_center, _ = get_irregular_circle_center(verts, mx=self.active.matrix_world, debug=False)

        self.circle_offset = circle_center - avg_center if circle_center else Vector()

        self.factor = get_zoom_factor(context, self.active.matrix_world @ average_locations([v.co for v in self.initbm.verts if v.select]))

        init_cursor(self, event)

        try:
            ret = self.main(self.active, modal=True)

            if not ret:
                self.cancel_modal(removeHUD=False)
                return {'FINISHED'}
        except Exception as e:
            if bpy.context.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='EDIT')

            output_traceback(self, e)
            return {'FINISHED'}

        init_status(self, context, 'LoopTools Circle')

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def main(self, active, modal=False):
        if modal:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.initbm.to_mesh(active.data)
            bpy.ops.object.mode_set(mode='EDIT')

        bpy.ops.mesh.looptools_circle(custom_radius=self.custom_radius, fit=self.method, flatten=self.flatten, influence=self.influence, lock_x=self.lock_x, lock_y=self.lock_y, lock_z=self.lock_z, radius=self.radius, regular=self.regular)

        if self.fix_midpoint:
            bpy.ops.transform.translate(value=self.circle_offset)

        return True
