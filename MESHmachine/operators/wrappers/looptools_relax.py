import bpy
import bmesh
from bpy.props import BoolProperty, FloatProperty, EnumProperty
from ... utils.developer import output_traceback
from ... utils.ui import draw_init, draw_title, draw_prop, init_cursor, wrap_cursor, update_HUD_location
from ... utils.ui import init_status, finish_status
from ... utils.property import step_enum
from ... items import looptools_relax_input_items, looptools_relax_interpolation_items, looptools_relax_iterations_items

class LoopToolsRelax(bpy.types.Operator):
    bl_idname = "machin3.looptools_relax"
    bl_label = "MACHIN3: LoopTools Relax"
    bl_description = "LoopTools's Relax as a modal"
    bl_options = {'REGISTER', 'UNDO'}

    iterations: EnumProperty(name="Iterations", items=looptools_relax_iterations_items, description="Number of times the loop is relaxed", default="1")
    input: EnumProperty(name="Input", items=looptools_relax_input_items, description="Loops that are relaxed", default='selected')
    interpolation: EnumProperty(name="Interpolation", items=looptools_relax_interpolation_items, description="Algorithm used for interpolation", default='cubic')
    regular: BoolProperty(name="Regular", description="Distribute vertices at constant distances along the loop", default=False)
    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Relax", subtitle="LoopTools")

            draw_prop(self, "Iterations", self.iterations, hint="scroll UP/DOWN")
            draw_prop(self, "Regular", self.regular, offset=18, hint="toggle R")
            self.offset += 10

            draw_prop(self, "Input", self.input, offset=18, hint="CTRL scroll UP/DOWN")
            draw_prop(self, "Interpolation", self.interpolation, offset=18, hint="ALT scroll UP/DOWN")

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        if event.type in ['WHEELUPMOUSE', 'ONE', 'WHEELDOWNMOUSE', 'TWO', 'R']:

            if event.type in {'WHEELUPMOUSE', 'ONE'} and event.value == 'PRESS':
                if event.ctrl:
                    self.input = step_enum(self.input, looptools_relax_input_items, 1)

                elif event.alt:
                    self.interpolation = step_enum(self.interpolation, looptools_relax_interpolation_items, 1)

                else:
                    self.iterations = step_enum(self.iterations, looptools_relax_iterations_items, 1, loop=False)

            elif event.type in {'WHEELDOWNMOUSE', 'TWO'} and event.value == 'PRESS':
                if event.ctrl:
                    self.input = step_enum(self.input, looptools_relax_input_items, -1)

                elif event.alt:
                    self.interpolation = step_enum(self.interpolation, looptools_relax_interpolation_items, -1)

                else:
                    self.iterations = step_enum(self.iterations, looptools_relax_iterations_items, -1, loop=False)

            elif event.type == 'R' and event.value == "PRESS":
                self.regular = not self.regular

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
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()
            return {'CANCELLED'}

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

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

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

        init_status(self, context, 'LoopTools Relax')

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def main(self, active, modal=False):
        if modal:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.initbm.to_mesh(active.data)
            bpy.ops.object.mode_set(mode='EDIT')

        bpy.ops.mesh.looptools_relax(input=self.input, interpolation=self.interpolation, iterations=self.iterations, regular=self.regular)

        return True
